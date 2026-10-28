package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.shumuzengxiao.smartcattle.domain.ModelRelease;
import com.shumuzengxiao.smartcattle.dto.AudioTrainingLineageDto;
import com.shumuzengxiao.smartcattle.dto.ModelReleaseLineageSourceRequest;
import com.shumuzengxiao.smartcattle.dto.ModelReleaseRequest;
import com.shumuzengxiao.smartcattle.dto.ModelReleaseRevocationRequest;
import com.shumuzengxiao.smartcattle.dto.MotionCaptureTrainingLineageDto;
import com.shumuzengxiao.smartcattle.dto.VisionTrainingLineageDto;
import com.shumuzengxiao.smartcattle.repository.ModelReleaseRepository;
import jakarta.transaction.Transactional;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Lazy;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeMap;

/**
 * Stores an immutable approval record for a screening model. Registration is
 * deliberately stricter than a metadata upload: each referenced clinical
 * archive is rechecked while the request is being handled.
 */
@Service
public class ModelReleaseService {
    private static final Set<String> AUDIO_RISK_LABELS = Set.of(
            "cough_suspect", "wheeze_suspect", "abnormal_vocalization_suspect");
    private static final Set<String> VISION_RISK_LABELS = Set.of(
            "gait_abnormal_suspect", "hoof_lesion_suspect",
            "oral_lesion_suspect", "nasal_discharge_suspect");
    private static final int LAMENESS_SAMPLE_RATE_HZ = 20;
    private static final int MAX_LINEAGE_SOURCES = 5_000;

    private final ModelReleaseRepository releases;
    private final AuditTrailService audit;
    private final AudioEventService audioEvents;
    private final MotionCaptureService motionCaptures;
    private final VisionEventService visionEvents;
    private final ObjectMapper objectMapper;

    public ModelReleaseService(
            ModelReleaseRepository releases,
            AuditTrailService audit,
            AudioEventService audioEvents,
            MotionCaptureService motionCaptures,
            ObjectMapper objectMapper
    ) {
        this(releases, audit, audioEvents, motionCaptures, null, objectMapper);
    }

    @Autowired
    public ModelReleaseService(
            ModelReleaseRepository releases,
            AuditTrailService audit,
            AudioEventService audioEvents,
            MotionCaptureService motionCaptures,
            @Lazy VisionEventService visionEvents,
            ObjectMapper objectMapper
    ) {
        this.releases = releases;
        this.audit = audit;
        this.audioEvents = audioEvents;
        this.motionCaptures = motionCaptures;
        this.visionEvents = visionEvents;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public ModelRelease approve(ModelReleaseRequest request) {
        String family = required(request.modelFamily(), "modelFamily");
        String version = required(request.modelVersion(), "modelVersion");
        LineageSnapshot lineage = verifyLineage(family, request);

        ModelRelease existing = releases.findByModelFamilyAndModelVersion(family, version).orElse(null);
        if (existing != null) {
            if ("revoked".equals(existing.getApprovalState())) {
                throw conflict("model version was revoked and cannot be re-approved; publish a new version");
            }
            if (sameApproval(existing, request, lineage)) {
                return existing;
            }
            throw conflict("model version already exists with different release evidence; publish a new version");
        }

        ModelRelease release = new ModelRelease();
        release.setModelFamily(family);
        release.setModelVersion(version);
        release.setApprovalState("approved");
        release.setDatasetManifestSha256(hash(request.datasetManifestSha256(), "datasetManifestSha256"));
        release.setModelCardSha256(hash(request.modelCardSha256(), "modelCardSha256"));
        release.setFirmwareSha256(hash(request.firmwareSha256(), "firmwareSha256"));
        release.setSourceLineageSha256(lineage.sha256());
        release.setSourceLineageJson(lineage.json());
        release.setEvidenceReference(required(request.evidenceReference(), "evidenceReference"));
        release.setApprovedBy(required(request.approvedBy(), "approvedBy"));
        release.setApprovedAt(Instant.now());
        release.setValidationSummary(required(request.validationSummary(), "validationSummary"));
        release.setNotes(blank(request.notes()));
        release = releases.save(release);
        audit("model_release_approved", release.getApprovedBy(), release);
        return release;
    }

    @Transactional
    public ModelRelease revoke(Long releaseId, ModelReleaseRevocationRequest request) {
        ModelRelease release = releases.findById(releaseId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "model release not found"));
        String revokedBy = required(request.revokedBy(), "revokedBy");
        String evidence = required(request.evidenceReference(), "evidenceReference");
        String notes = blank(request.notes());

        if ("revoked".equals(release.getApprovalState())) {
            if (Objects.equals(release.getRevokedBy(), revokedBy)
                    && Objects.equals(release.getRevocationEvidenceReference(), evidence)
                    && Objects.equals(release.getRevocationNotes(), notes)) {
                return release;
            }
            throw conflict("model release is already revoked; its revocation evidence is immutable");
        }
        if (!"approved".equals(release.getApprovalState())) {
            throw conflict("model release is not in an approvable state for revocation");
        }

        // Preserve approval evidence. A revocation is a second immutable event,
        // not an edit to the record that authorized the original release.
        release.setApprovalState("revoked");
        release.setRevokedBy(revokedBy);
        release.setRevokedAt(Instant.now());
        release.setRevocationEvidenceReference(evidence);
        release.setRevocationNotes(notes);
        release = releases.save(release);
        audit("model_release_revoked", release.getRevokedBy(), release);
        return release;
    }

    public boolean isApproved(String family, String version) {
        return releases.findByModelFamilyAndModelVersion(family, version)
                .map(item -> "approved".equals(item.getApprovalState()))
                .orElse(false);
    }

    public List<ModelRelease> recent() {
        return releases.findTop100ByOrderByApprovedAtDesc();
    }

    private LineageSnapshot verifyLineage(String family, ModelReleaseRequest request) {
        List<ModelReleaseLineageSourceRequest> sources = request.sourceLineage();
        if (sources == null || sources.isEmpty() || sources.size() > MAX_LINEAGE_SOURCES) {
            throw conflict("release lineage must contain between 1 and " + MAX_LINEAGE_SOURCES + " sources");
        }
        LineageSnapshot snapshot = switch (family) {
            case "audio" -> verifyAudioLineage(sources);
            case "lameness" -> verifyLamenessLineage(sources);
            case "vision" -> verifyVisionLineage(sources);
            default -> throw conflict("unsupported model family");
        };
        String supplied = hash(request.sourceLineageSha256(), "sourceLineageSha256");
        if (!MessageDigest.isEqual(supplied.getBytes(StandardCharsets.US_ASCII),
                snapshot.sha256().getBytes(StandardCharsets.US_ASCII))) {
            throw conflict("source lineage changed since the release trainer ran");
        }
        return snapshot;
    }

    private LineageSnapshot verifyAudioLineage(List<ModelReleaseLineageSourceRequest> sources) {
        List<Map<String, Object>> records = new ArrayList<>();
        Set<String> seen = new LinkedHashSet<>();
        boolean hasRiskLabel = false;
        for (ModelReleaseLineageSourceRequest source : sources) {
            String sourceId = requiredSourceId(source);
            if (!seen.add(sourceId)) {
                throw conflict("release lineage reuses audio sourceEventId " + sourceId);
            }
            if (blank(source.recordingId()) != null) {
                throw conflict("audio release lineage must not set recordingId");
            }
            long eventId;
            try {
                eventId = Long.parseLong(sourceId);
            } catch (NumberFormatException exception) {
                throw conflict("audio sourceEventId must be a positive integer");
            }
            if (eventId < 1) {
                throw conflict("audio sourceEventId must be a positive integer");
            }
            AudioTrainingLineageDto row = audioEvents.trainingLineage(eventId);
            String label = required(row.reviewLabel(), "audio reviewLabel for event " + sourceId);
            if (!"confirmed".equals(row.reviewStatus()) && !"normal".equals(row.reviewStatus())) {
                throw conflict("audio event " + sourceId + " no longer has a confirmed clinical review");
            }
            if (!row.clipIntegrityVerified() || row.clinicallyVerifiedAt() == null) {
                throw conflict("audio event " + sourceId + " lacks an intact clinically verified archive");
            }
            String clipHash = hash(row.clipSha256(), "clipSha256 for audio event " + sourceId);
            String animalId = required(row.clinicalAnimalId(), "clinicalAnimalId for audio event " + sourceId);
            String sessionId = required(row.recordingSessionId(), "recordingSessionId for audio event " + sourceId);
            String veterinarian = required(row.veterinarian(), "veterinarian for audio event " + sourceId);
            String evidence = required(row.clinicalEvidenceReference(),
                    "clinicalEvidenceReference for audio event " + sourceId);
            if (AUDIO_RISK_LABELS.contains(label)) {
                hasRiskLabel = true;
            }

            Map<String, Object> record = new TreeMap<>();
            record.put("sourceEventId", sourceId);
            record.put("clipSha256", clipHash);
            record.put("label", label);
            record.put("reviewStatus", row.reviewStatus());
            record.put("clinicalAnimalId", animalId);
            record.put("recordingSessionId", sessionId);
            record.put("veterinarian", veterinarian);
            record.put("clinicalEvidenceReference", evidence);
            record.put("clinicallyVerifiedAt", row.clinicallyVerifiedAt().toString());
            records.add(record);
        }
        if (!hasRiskLabel) {
            throw conflict("audio release lineage has no clinically verified respiratory or abnormal-vocalization sample");
        }
        return snapshot(records);
    }

    private LineageSnapshot verifyLamenessLineage(List<ModelReleaseLineageSourceRequest> sources) {
        List<Map<String, Object>> records = new ArrayList<>();
        Set<String> seenSessions = new LinkedHashSet<>();
        Set<String> seenRecordings = new LinkedHashSet<>();
        for (ModelReleaseLineageSourceRequest source : sources) {
            String sessionId = requiredSourceId(source);
            String recordingId = required(source.recordingId(), "recordingId for IMU session " + sessionId);
            if (!seenSessions.add(sessionId)) {
                throw conflict("release lineage reuses motion recordingSessionId " + sessionId);
            }
            if (!seenRecordings.add(recordingId)) {
                throw conflict("release lineage reuses motion recordingId " + recordingId);
            }
            MotionCaptureTrainingLineageDto row = motionCaptures.trainingLineage(sessionId);
            verifyMotionQuality(row, sessionId);

            Map<String, Object> record = new TreeMap<>();
            record.put("recordingId", recordingId);
            record.put("recordingSessionId", sessionId);
            record.put("animalId", required(row.cattleId(), "cattleId for IMU session " + sessionId));
            record.put("rawDataSha256", hash(row.rawDataSha256(), "rawDataSha256 for IMU session " + sessionId));
            record.put("videoReference", required(row.videoReference(), "videoReference for IMU session " + sessionId));
            record.put("sampleRateHz", LAMENESS_SAMPLE_RATE_HZ);
            record.put("receivedSamples", row.receivedSamples());
            record.put("expectedSamples", row.expectedSamples());
            record.put("attemptedSamples", row.attemptedSamples());
            record.put("completenessRatio", row.completenessRatio());
            record.put("gaitReviewer", required(row.gaitReviewer(), "gaitReviewer for IMU session " + sessionId));
            record.put("hoofExaminer", required(row.hoofExaminer(), "hoofExaminer for IMU session " + sessionId));
            record.put("veterinarian", required(row.veterinarian(), "veterinarian for IMU session " + sessionId));
            record.put("hoofFinding", required(row.hoofFinding(), "hoofFinding for IMU session " + sessionId));
            record.put("clinicalEvidenceReference", required(row.clinicalEvidenceReference(),
                    "clinicalEvidenceReference for IMU session " + sessionId));
            record.put("verifiedAt", row.clinicallyVerifiedAt().toString());
            record.put("lamenessScore", row.lamenessScore());
            records.add(record);
        }
        return snapshot(records);
    }

    private LineageSnapshot verifyVisionLineage(List<ModelReleaseLineageSourceRequest> sources) {
        if (visionEvents == null) {
            throw conflict("vision lineage service is not configured");
        }
        List<Map<String, Object>> records = new ArrayList<>();
        Set<String> seenEvents = new LinkedHashSet<>();
        Set<String> seenRecordings = new LinkedHashSet<>();
        boolean hasRiskLabel = false;
        for (ModelReleaseLineageSourceRequest source : sources) {
            String sourceId = requiredSourceId(source);
            String recordingId = required(source.recordingId(), "recordingId for vision event " + sourceId);
            if (!seenEvents.add(sourceId)) {
                throw conflict("release lineage reuses vision sourceEventId " + sourceId);
            }
            if (!seenRecordings.add(recordingId)) {
                throw conflict("release lineage reuses vision recordingId " + recordingId);
            }
            long eventId;
            try {
                eventId = Long.parseLong(sourceId);
            } catch (NumberFormatException exception) {
                throw conflict("vision sourceEventId must be a positive integer");
            }
            if (eventId < 1) {
                throw conflict("vision sourceEventId must be a positive integer");
            }

            VisionTrainingLineageDto row = visionEvents.trainingLineage(eventId);
            if (!row.snapshotIntegrityVerified() || row.clinicallyVerifiedAt() == null) {
                throw conflict("vision event " + sourceId + " lacks an intact clinically verified snapshot");
            }
            String reviewStatus = required(row.reviewStatus(), "vision reviewStatus for event " + sourceId);
            if (!"confirmed".equals(reviewStatus) && !"normal".equals(reviewStatus)) {
                throw conflict("vision event " + sourceId + " no longer has a confirmed clinical review");
            }
            String label = required(row.reviewLabel(), "vision reviewLabel for event " + sourceId);
            if (!"normal".equals(label) && !VISION_RISK_LABELS.contains(label)) {
                throw conflict("vision event " + sourceId + " has an unsupported clinical label");
            }
            if (VISION_RISK_LABELS.contains(label)) {
                hasRiskLabel = true;
            }

            Map<String, Object> record = new TreeMap<>();
            record.put("sourceEventId", sourceId);
            record.put("recordingId", recordingId);
            record.put("cameraId", required(row.cameraId(), "cameraId for vision event " + sourceId));
            record.put("barnId", required(row.barnId(), "barnId for vision event " + sourceId));
            record.put("snapshotSha256", hash(row.snapshotSha256(), "snapshotSha256 for vision event " + sourceId));
            record.put("reviewLabel", label);
            record.put("reviewStatus", reviewStatus);
            record.put("clinicalAnimalId", required(row.clinicalAnimalId(),
                    "clinicalAnimalId for vision event " + sourceId));
            record.put("veterinarian", required(row.veterinarian(),
                    "veterinarian for vision event " + sourceId));
            record.put("clinicalEvidenceReference", required(row.clinicalEvidenceReference(),
                    "clinicalEvidenceReference for vision event " + sourceId));
            record.put("clinicallyVerifiedAt", row.clinicallyVerifiedAt().toString());
            record.put("recordedAt", row.recordedAt() == null ? null : row.recordedAt().toString());
            records.add(record);
        }
        if (!hasRiskLabel) {
            throw conflict("vision release lineage has no clinically verified lesion or gait-risk sample");
        }
        return snapshot(records);
    }

    private static void verifyMotionQuality(MotionCaptureTrainingLineageDto row, String sessionId) {
        if (!"completed".equals(row.status()) || !"accepted".equals(row.qualityStatus())
                || !row.archiveIntegrityVerified() || !"verified".equals(row.clinicalReviewStatus())) {
            throw conflict("IMU session " + sessionId + " is not an accepted clinically verified archive");
        }
        if (!Integer.valueOf(LAMENESS_SAMPLE_RATE_HZ).equals(row.sampleRateHz())
                || row.clinicallyVerifiedAt() == null || row.lamenessScore() == null
                || row.lamenessScore() < 0 || row.lamenessScore() > 3) {
            throw conflict("IMU session " + sessionId + " has invalid sampling or clinical review fields");
        }
        Long received = row.receivedSamples();
        Long expected = row.expectedSamples();
        Long attempted = row.attemptedSamples();
        if (received == null || expected == null || attempted == null || expected <= 0
                || ((double) received / expected) < 0.95 || !attempted.equals(expected)
                || nonZero(row.droppedBackpressureSamples()) || nonZero(row.droppedSensorSamples())) {
            throw conflict("IMU session " + sessionId + " no longer meets the 20 Hz capture quality gate");
        }
    }

    private LineageSnapshot snapshot(List<Map<String, Object>> records) {
        try {
            String canonical = objectMapper.writer()
                    .with(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS)
                    .writeValueAsString(records);
            return new LineageSnapshot(sha256(canonical), canonical);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Cannot canonicalize model release lineage", exception);
        }
    }

    private boolean sameApproval(ModelRelease existing, ModelReleaseRequest request, LineageSnapshot lineage) {
        return "approved".equals(existing.getApprovalState())
                && Objects.equals(existing.getModelFamily(), required(request.modelFamily(), "modelFamily"))
                && Objects.equals(existing.getModelVersion(), required(request.modelVersion(), "modelVersion"))
                && Objects.equals(existing.getDatasetManifestSha256(), hash(request.datasetManifestSha256(), "datasetManifestSha256"))
                && Objects.equals(existing.getModelCardSha256(), hash(request.modelCardSha256(), "modelCardSha256"))
                && Objects.equals(existing.getFirmwareSha256(), hash(request.firmwareSha256(), "firmwareSha256"))
                && Objects.equals(existing.getSourceLineageSha256(), lineage.sha256())
                && Objects.equals(existing.getEvidenceReference(), required(request.evidenceReference(), "evidenceReference"))
                && Objects.equals(existing.getApprovedBy(), required(request.approvedBy(), "approvedBy"))
                && Objects.equals(existing.getValidationSummary(), required(request.validationSummary(), "validationSummary"))
                && Objects.equals(existing.getNotes(), blank(request.notes()));
    }

    private void audit(String eventType, String actor, ModelRelease release) {
        if (audit != null) {
            audit.record(eventType, actor, "model_release", String.valueOf(release.getId()), details(release));
        }
    }

    private static Map<String, Object> details(ModelRelease release) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("modelFamily", release.getModelFamily());
        details.put("modelVersion", release.getModelVersion());
        details.put("approvalState", release.getApprovalState());
        details.put("datasetManifestSha256", release.getDatasetManifestSha256());
        details.put("modelCardSha256", release.getModelCardSha256());
        details.put("firmwareSha256", release.getFirmwareSha256());
        details.put("sourceLineageSha256", release.getSourceLineageSha256());
        details.put("evidenceReference", release.getEvidenceReference());
        details.put("revocationEvidenceReference", release.getRevocationEvidenceReference());
        return details;
    }

    private static boolean nonZero(Long value) {
        return value != null && value != 0L;
    }

    private static String requiredSourceId(ModelReleaseLineageSourceRequest source) {
        if (source == null) {
            throw conflict("release lineage contains an invalid source");
        }
        return required(source.sourceId(), "sourceId");
    }

    private static String required(String value, String field) {
        String normalized = blank(value);
        if (normalized == null) {
            throw conflict(field + " is required");
        }
        return normalized;
    }

    private static String hash(String value, String field) {
        String normalized = required(value, field).toLowerCase(Locale.ROOT);
        if (!normalized.matches("[a-f0-9]{64}")) {
            throw conflict(field + " must be a SHA-256 value");
        }
        return normalized;
    }

    private static String sha256(String value) {
        try {
            return java.util.HexFormat.of().formatHex(
                    MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }

    private static ResponseStatusException conflict(String message) {
        return new ResponseStatusException(HttpStatus.CONFLICT, message);
    }

    private static String blank(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private record LineageSnapshot(String sha256, String json) {
    }
}
