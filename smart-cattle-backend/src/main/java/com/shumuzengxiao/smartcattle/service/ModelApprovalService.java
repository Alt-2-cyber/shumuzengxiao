package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.util.Locale;
import java.util.Set;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/**
 * An edge payload cannot approve its own disease-screening model. The firmware
 * may report an installed version, but disease candidates are accepted only
 * when that exact version appears in the server-side approval configuration.
 */
@Service
public class ModelApprovalService {
    private static final Set<String> VISION_SCREENING_EVENTS = Set.of(
            "gait_abnormal_suspect",
            "hoof_lesion_suspect",
            "oral_lesion_suspect",
            "nasal_discharge_suspect");
    private static final Set<String> AUDIO_SCREENING_LABELS = Set.of(
            "cough_suspect",
            "wheeze_suspect",
            "abnormal_vocalization_suspect");

    @Value("${health.models.audio.approved-versions:}")
    private String approvedAudioVersions = "";

    @Value("${health.models.lameness.approved-versions:}")
    private String approvedLamenessVersions = "";

    @Value("${health.models.vision.approved-versions:}")
    private String approvedVisionVersions = "";

    private final AuditTrailService audit;
    private final ModelReleaseService releases;
    private final Set<String> auditedApprovedVersions = ConcurrentHashMap.newKeySet();

    @Autowired
    public ModelApprovalService(AuditTrailService audit, ModelReleaseService releases) {
        this.audit = audit;
        this.releases = releases;
    }

    // Kept for small unit tests that construct the service without Spring.
    public ModelApprovalService() {
        this.audit = null;
        this.releases = null;
    }

    public void enforce(ObjectNode telemetry) {
        ObjectNode microphone = telemetry.withObject("microphone");
        boolean audioApproved = isApproved(
                microphone.path("modelStatus").asText(),
                microphone.path("modelVersion").asText(),
                approvedAudioVersions, "audio");
        microphone.put("approvedByServer", audioApproved);
        if (!audioApproved) {
            microphone.put("modelStatus", "feature_only");
            microphone.put("respiratoryCandidate", false);
            microphone.put("abnormalVocalizationCandidate", false);
        }
        if (audioApproved) {
            audit("audio_model_seen_approved", microphone.path("modelVersion").asText());
        }

        ObjectNode lameness = telemetry.withObject("lamenessScreen");
        boolean lamenessApproved = isApproved(
                lameness.path("modelStatus").asText(),
                lameness.path("modelVersion").asText(),
                approvedLamenessVersions, "lameness");
        lameness.put("approvedByServer", lamenessApproved);
        if (!lamenessApproved) {
            lameness.put("modelStatus", "feature_only");
            lameness.put("candidate", false);
            lameness.put("rejected", false);
            lameness.putNull("score");
        }
        if (lamenessApproved) {
            audit("lameness_model_seen_approved", lameness.path("modelVersion").asText());
        }
    }

    /**
     * Applies the same server-side release gate to an independent audio event
     * before it is archived or considered by health screening.
     */
    public AudioDecision enforceAudioEvent(ObjectNode event) {
        ObjectNode model = event.withObject("model");
        String label = normalizedLabel(event.path("label").asText());
        boolean approved = isApproved(
                model.path("status").asText(),
                model.path("version").asText(),
                approvedAudioVersions,
                "audio");
        boolean hasCattleId = !event.path("cattleId").asText("").trim().isEmpty();
        boolean screeningLabel = AUDIO_SCREENING_LABELS.contains(label);
        boolean screeningEligible = approved && hasCattleId && screeningLabel;
        model.put("approvedByServer", approved);
        model.put("screeningEligible", screeningEligible);
        model.put("approvalReason", approvalReason(approved, hasCattleId, screeningLabel));
        if (!approved) {
            model.put("status", "feature_only");
        }
        if (approved) {
            audit("audio_model_seen_approved", model.path("version").asText());
        }
        return new AudioDecision(approved, screeningEligible, label);
    }

    /**
     * Returns whether a vision event may become health evidence. Ordinary
     * operational events are archivable without a disease model; disease-like
     * events require an explicitly approved vision release and an identified
     * animal.
     */
    public VisionDecision enforceVisionEvent(
            String eventType,
            String modelStatus,
            String modelVersion,
            String targetId
    ) {
        String type = eventType == null ? "" : eventType.trim().toLowerCase(Locale.ROOT);
        boolean screeningEvent = VISION_SCREENING_EVENTS.contains(type);
        boolean approved = isApproved(modelStatus, modelVersion, approvedVisionVersions, "vision");
        boolean hasCattleId = targetId != null && !targetId.isBlank();
        boolean modelApprovalRequired = screeningEvent;
        boolean screeningEligible = modelApprovalRequired && approved && hasCattleId;
        if (approved && modelVersion != null && !modelVersion.isBlank()) {
            audit("vision_model_seen_approved", modelVersion.trim());
        }
        return new VisionDecision(
                approved,
                screeningEligible,
                screeningEvent,
                modelApprovalRequired,
                approvalReason(approved, hasCattleId, modelApprovalRequired));
    }

    public record AudioDecision(boolean approvedByServer, boolean screeningEligible, String normalizedLabel) {
    }

    public record VisionDecision(
            boolean approvedByServer,
            boolean screeningEligible,
            boolean screeningEvent,
            boolean modelApprovalRequired,
            String approvalReason
    ) {
    }

    private boolean isApproved(String reportedStatus, String reportedVersion, String configuredVersions, String family) {
        if (!"deployed".equals(reportedStatus) || reportedVersion == null || reportedVersion.isBlank()) {
            return false;
        }
        Set<String> approved = Arrays.stream(configuredVersions == null ? new String[0] : configuredVersions.split(","))
                .map(String::trim)
                .filter(value -> !value.isEmpty())
                .collect(Collectors.toSet());
        String version = reportedVersion.trim();
        return approved.contains(version) && (releases == null || releases.isApproved(family, version));
    }

    private static String normalizedLabel(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private static String approvalReason(boolean approved, boolean hasCattleId, boolean modelApprovalRequired) {
        if (!modelApprovalRequired) {
            return "non_screening_event";
        }
        if (!hasCattleId) {
            return "missing_verified_cattle_id";
        }
        if (!approved) {
            return "model_not_server_approved";
        }
        return "approved_for_screening";
    }

    private void audit(String eventType, String version) {
        if (audit != null && auditedApprovedVersions.add(eventType + ":" + version)) {
            audit.record(eventType, "system", "model_version", version, Map.of("version", version));
        }
    }
}
