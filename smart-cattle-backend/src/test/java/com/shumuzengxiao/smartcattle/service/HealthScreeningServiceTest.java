package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class HealthScreeningServiceTest {
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void staysInLearningModeUntilTheIndividualBaselineIsReady() {
        HealthScreeningService service = new HealthScreeningService();

        Map<String, Object> screen = service.evaluate(
                telemetry("grazing", 0.85, 0.8, 33.0, false),
                Instant.parse("2026-07-19T00:00:00Z"));

        assertThat(screen.get("mode")).isEqualTo("BASELINE_LEARNING");
        assertThat(screen.get("riskLevel")).isEqualTo("NORMAL");
        assertThat((List<?>) screen.get("risks")).isEmpty();
    }

    @Test
    @SuppressWarnings("unchecked")
    void surfacesSustainedMultiSignalAbnormalityAfterLearning() {
        HealthScreeningService service = new HealthScreeningService();
        Instant start = Instant.parse("2026-07-19T00:00:00Z");

        for (int index = 0; index < 18 * 30; index++) {
            String behavior = index % 3 == 0 ? "standing_ruminating" : "grazing";
            service.evaluate(
                    telemetry(behavior, 0.90, 0.82, 33.0, false),
                    start.plus(index * 10L, ChronoUnit.SECONDS));
        }

        Map<String, Object> screen = null;
        for (int index = 18 * 30; index <= 24 * 30; index++) {
            screen = service.evaluate(
                    telemetry("lying_resting", 0.91, 0.08, 34.6, false),
                    start.plus(index * 10L, ChronoUnit.SECONDS));
        }

        assertThat(screen).isNotNull();
        assertThat(screen.get("mode")).isEqualTo("SCREENING");
        assertThat(screen.get("riskLevel")).isEqualTo("WARNING");
        List<Map<String, Object>> risks = (List<Map<String, Object>>) screen.get("risks");
        assertThat(risks).extracting(risk -> risk.get("type"))
                .contains("feeding_rumination_attention", "mobility_activity_attention", "temperature_inflammation_attention");
    }

    @Test
    @SuppressWarnings("unchecked")
    void onlyUsesRespiratoryCandidatesAfterADeployedModelBuildsABaseline() {
        HealthScreeningService service = new HealthScreeningService();
        Instant start = Instant.parse("2026-07-19T00:00:00Z");

        for (int index = 0; index < 18 * 30; index++) {
            service.evaluate(
                    telemetry("grazing", 0.90, 0.70, 33.0, false, true, false),
                    start.plus(index * 10L, ChronoUnit.SECONDS));
        }

        Map<String, Object> screen = null;
        for (int index = 18 * 30; index <= 24 * 30; index++) {
            screen = service.evaluate(
                    telemetry("grazing", 0.90, 0.70, 33.0, false, true, true),
                    start.plus(index * 10L, ChronoUnit.SECONDS));
        }

        List<Map<String, Object>> risks = (List<Map<String, Object>>) screen.get("risks");
        assertThat(risks).extracting(risk -> risk.get("type"))
                .contains("respiratory_sound_attention");
    }

    @Test
    @SuppressWarnings("unchecked")
    void surfacesApprovedAbnormalVocalizationCandidatesAfterADeployedModelBuildsABaseline() {
        HealthScreeningService service = new HealthScreeningService();
        Instant start = Instant.parse("2026-07-19T00:00:00Z");

        establishBaseline(service, start, true);

        Map<String, Object> screen = null;
        for (int index = 18 * 30; index <= 24 * 30; index++) {
            screen = service.evaluate(
                    telemetry("grazing", 0.90, 0.70, 33.0, false, true, false, true),
                    start.plus(index * 10L, ChronoUnit.SECONDS));
        }

        List<Map<String, Object>> risks = (List<Map<String, Object>>) screen.get("risks");
        assertThat(risks).extracting(risk -> risk.get("type"))
                .contains("abnormal_vocalization_attention");
        Map<String, Object> current = (Map<String, Object>) screen.get("current");
        assertThat(((Number) current.get("abnormalVocalizationCandidateSamples")).intValue())
                .isGreaterThan(1);
    }

    @Test
    @SuppressWarnings("unchecked")
    void independentAbnormalVocalizationEventEntersFusionOnlyWhenMarkedEligible() {
        HealthScreeningService service = new HealthScreeningService();
        Instant start = Instant.parse("2026-07-19T00:00:00Z");
        establishBaseline(service, start, true);

        Map<String, Object> screen = null;
        for (int index = 18 * 30; index <= 24 * 30; index++) {
            Instant at = start.plus(index * 10L, ChronoUnit.SECONDS);
            service.recordAudioEvidence(
                    "cattle_01", "abnormal_vocalization_suspect", 0.88, true, at,
                    "abnormal-vocalization-" + index);
            screen = service.evaluate(
                    telemetry("grazing", 0.90, 0.70, 33.0, false, true, false), at);
        }

        List<Map<String, Object>> risks = (List<Map<String, Object>>) screen.get("risks");
        assertThat(risks).extracting(risk -> risk.get("type"))
                .contains("abnormal_vocalization_attention");
        Map<String, Object> audio = (Map<String, Object>) screen.get("audio");
        assertThat(audio.get("vocalizationCandidate")).isEqualTo(true);
        assertThat(((Number) audio.get("vocalizationEventCount")).intValue()).isGreaterThan(1);
    }

    @Test
    @SuppressWarnings("unchecked")
    void fusesApprovedRespiratoryAudioSurfaceTemperatureAndNasalVisionIntoBrdScreening() {
        HealthScreeningService service = new HealthScreeningService();
        Instant start = Instant.parse("2026-07-19T00:00:00Z");
        establishBaseline(service, start, true);

        Instant evidenceAt = start.plus(3, ChronoUnit.HOURS);
        service.recordVisionEvidence("cattle_01", "nasal_discharge_suspect", 0.91, evidenceAt);
        service.recordAudioEvidence(
                "cattle_01", "cough_suspect", 0.93, true, evidenceAt, "brd-audio-001");

        Map<String, Object> screen = null;
        for (int index = 0; index <= 6 * 30; index++) {
            Instant at = evidenceAt.plus(index * 10L, ChronoUnit.SECONDS);
            screen = service.evaluate(
                    telemetry("grazing", 0.90, 0.70, 34.2, false), at);
        }

        List<Map<String, Object>> risks = (List<Map<String, Object>>) screen.get("risks");
        assertThat(risks).as("screen=%s", screen).extracting(risk -> risk.get("type"))
                .contains("brd_suspect");
        Map<String, Object> brd = risks.stream()
                .filter(risk -> "brd_suspect".equals(risk.get("type")))
                .findFirst()
                .orElseThrow();
        List<String> evidence = (List<String>) brd.get("evidence");
        assertThat(evidence).anyMatch(item -> item.contains("批准的声音模型"));
        assertThat(evidence).anyMatch(item -> item.contains("体表温度较个体基线升高"));
        assertThat(evidence).anyMatch(item -> item.contains("视觉端存在鼻部分泌物疑似证据"));
        assertThat(screen.get("decisionScope")).isEqualTo("screening_only");
    }

    @Test
    @SuppressWarnings("unchecked")
    void doesNotUpgradeMobilityToLamenessWithoutAnApprovedThreePositionModel() {
        HealthScreeningService service = new HealthScreeningService();
        Instant start = Instant.parse("2026-07-19T00:00:00Z");

        establishBaseline(service, start, false);
        Map<String, Object> withoutVision = sustainedMobilityChange(service, start.plus(3, ChronoUnit.HOURS));
        List<Map<String, Object>> withoutVisionRisks = (List<Map<String, Object>>) withoutVision.get("risks");
        assertThat(withoutVisionRisks).extracting(risk -> risk.get("type"))
                .contains("mobility_activity_attention")
                .doesNotContain("lameness_suspect");

        HealthScreeningService withVision = new HealthScreeningService();
        establishBaseline(withVision, start, false);
        Instant evidenceAt = start.plus(3, ChronoUnit.HOURS);
        withVision.recordVisionEvidence("cattle_01", "gait_abnormal_suspect", 0.89, evidenceAt);
        Map<String, Object> withVisionScreen = sustainedMobilityChange(withVision, evidenceAt);
        List<Map<String, Object>> withVisionRisks = (List<Map<String, Object>>) withVisionScreen.get("risks");
        assertThat(withVisionRisks).extracting(risk -> risk.get("type"))
                .contains("mobility_activity_attention")
                .doesNotContain("lameness_suspect");
    }

    @Test
    @SuppressWarnings("unchecked")
    void fmdTriageRequiresVisionLesionApprovedLamenessAndPersistedVerifiedCoreTemperature() {
        HealthScreeningService service = new HealthScreeningService();
        Instant start = Instant.parse("2026-07-19T00:00:00Z");
        establishBaseline(service, start, false);
        Instant evidenceAt = start.plus(3, ChronoUnit.HOURS);
        service.recordVisionEvidence("cattle_01", "hoof_lesion_suspect", 0.91, evidenceAt);
        service.recordVisionEvidence("cattle_01", "oral_lesion_suspect", 0.86, evidenceAt);

        service.recordClinicalCheck("cattle_01", "core_temperature", true, true, 40.1, null, evidenceAt);

        Map<String, Object> screen = null;
        for (int index = 0; index <= 6 * 30; index++) {
            ObjectNode telemetry = telemetry("lying_resting", 0.91, 0.08, 34.6, false);
            ObjectNode lameness = telemetry.putObject("lamenessScreen");
            lameness.put("modelStatus", "deployed");
            lameness.put("candidate", true);
            lameness.put("rejected", false);
            lameness.put("score", 0.81);
            screen = service.evaluate(telemetry,
                    evidenceAt.plus(index * 10L, ChronoUnit.SECONDS));
        }

        List<Map<String, Object>> risks = (List<Map<String, Object>>) screen.get("risks");
        assertThat(risks).extracting(risk -> risk.get("type"))
                .contains("lameness_suspect", "fmd_suspect_triage");
    }

    @Test
    @SuppressWarnings("unchecked")
    void fmdTriageDoesNotUseB1SurfaceTemperatureAsCoreTemperatureEvidence() {
        HealthScreeningService service = new HealthScreeningService();
        Instant start = Instant.parse("2026-07-19T00:00:00Z");
        establishBaseline(service, start, false);
        Instant evidenceAt = start.plus(3, ChronoUnit.HOURS);
        service.recordVisionEvidence("cattle_01", "hoof_lesion_suspect", 0.91, evidenceAt);
        service.recordVisionEvidence("cattle_01", "oral_lesion_suspect", 0.86, evidenceAt);

        Map<String, Object> screen = sustainedApprovedLamenessChange(service, evidenceAt);
        List<Map<String, Object>> risks = (List<Map<String, Object>>) screen.get("risks");
        assertThat(risks).extracting(risk -> risk.get("type"))
                .contains("lameness_suspect")
                .doesNotContain("fmd_suspect_triage");
    }

    @Test
    @SuppressWarnings("unchecked")
    void fmdTriageDoesNotUseInjectedTelemetryClinicalField() {
        HealthScreeningService service = new HealthScreeningService();
        Instant start = Instant.parse("2026-07-19T00:00:00Z");
        establishBaseline(service, start, false);
        Instant evidenceAt = start.plus(3, ChronoUnit.HOURS);
        service.recordVisionEvidence("cattle_01", "hoof_lesion_suspect", 0.91, evidenceAt);

        Map<String, Object> screen = null;
        for (int index = 0; index <= 6 * 30; index++) {
            ObjectNode telemetry = telemetry("lying_resting", 0.91, 0.08, 34.6, false);
            telemetry.putObject("clinical").put("coreTemperatureVerified", true).put("coreTemperatureAlert", true);
            ObjectNode lameness = telemetry.putObject("lamenessScreen");
            lameness.put("modelStatus", "deployed");
            lameness.put("candidate", true);
            lameness.put("rejected", false);
            lameness.put("score", 0.81);
            screen = service.evaluate(telemetry, evidenceAt.plus(index * 10L, ChronoUnit.SECONDS));
        }

        List<Map<String, Object>> risks = (List<Map<String, Object>>) screen.get("risks");
        assertThat(risks).extracting(risk -> risk.get("type"))
                .contains("lameness_suspect")
                .doesNotContain("fmd_suspect_triage");
    }

    @Test
    @SuppressWarnings("unchecked")
    void approvedLamenessModelStillNeedsFreshVisionEvidence() {
        HealthScreeningService service = new HealthScreeningService();
        Instant start = Instant.parse("2026-07-19T00:00:00Z");
        establishBaseline(service, start, false);
        Instant evidenceAt = start.plus(3, ChronoUnit.HOURS);

        Map<String, Object> withoutVision = null;
        for (int index = 0; index <= 6 * 30; index++) {
            ObjectNode telemetry = telemetry("standing_resting", 0.90, 0.82, 33.0, false);
            ObjectNode lameness = telemetry.putObject("lamenessScreen");
            lameness.put("modelStatus", "deployed");
            lameness.put("candidate", true);
            lameness.put("rejected", false);
            lameness.put("score", 0.81);
            withoutVision = service.evaluate(telemetry, evidenceAt.plus(index * 10L, ChronoUnit.SECONDS));
        }
        List<Map<String, Object>> withoutVisionRisks = (List<Map<String, Object>>) withoutVision.get("risks");
        assertThat(withoutVisionRisks).extracting(risk -> risk.get("type"))
                .contains("mobility_activity_attention")
                .doesNotContain("lameness_suspect");

        HealthScreeningService withVision = new HealthScreeningService();
        establishBaseline(withVision, start, false);
        withVision.recordVisionEvidence("cattle_01", "gait_abnormal_suspect", 0.92, evidenceAt);
        Map<String, Object> screen = null;
        for (int index = 0; index <= 6 * 30; index++) {
            ObjectNode telemetry = telemetry("standing_resting", 0.90, 0.82, 33.0, false);
            ObjectNode lameness = telemetry.putObject("lamenessScreen");
            lameness.put("modelStatus", "deployed");
            lameness.put("candidate", true);
            lameness.put("rejected", false);
            lameness.put("score", 0.81);
            screen = withVision.evaluate(telemetry, evidenceAt.plus(index * 10L, ChronoUnit.SECONDS));
        }
        List<Map<String, Object>> risks = (List<Map<String, Object>>) screen.get("risks");
        assertThat(risks).extracting(risk -> risk.get("type")).contains("lameness_suspect");
    }

    @Test
    @SuppressWarnings("unchecked")
    void verifiedClinicalGaitEvidenceStillNeedsAnApprovedLamenessModel() {
        HealthScreeningService service = new HealthScreeningService();
        Instant start = Instant.parse("2026-07-19T00:00:00Z");
        establishBaseline(service, start, false);
        Instant evidenceAt = start.plus(3, ChronoUnit.HOURS);
        service.recordClinicalCheck(
                "cattle_01", "gait_exam", true, true, null,
                "gait_abnormal_suspect", evidenceAt);

        Map<String, Object> screen = sustainedMobilityChange(service, evidenceAt);
        List<Map<String, Object>> risks = (List<Map<String, Object>>) screen.get("risks");
        assertThat(risks).extracting(risk -> risk.get("type"))
                .contains("mobility_activity_attention")
                .doesNotContain("lameness_suspect");
    }

    @Test
    @SuppressWarnings("unchecked")
    void duplicateAudioEvidenceIsCountedOnce() {
        HealthScreeningService service = new HealthScreeningService();
        Instant recordedAt = Instant.parse("2026-07-19T12:00:00Z");

        service.recordAudioEvidence("cattle_01", "cough_suspect", 0.82, true,
                recordedAt, "audio-event-001");
        service.recordAudioEvidence("cattle_01", "cough_suspect", 0.95, true,
                recordedAt.plusSeconds(1), "audio-event-001");

        Map<String, Object> screen = service.evaluate(
                telemetry("grazing", 0.90, 0.70, 33.0, false), recordedAt.plusSeconds(2));
        Map<String, Object> audio = (Map<String, Object>) screen.get("audio");

        assertThat(audio.get("activeEventCount")).isEqualTo(1);
        assertThat(audio.get("screeningEligibleCount")).isEqualTo(1);
        assertThat(audio.get("respiratoryEventCount")).isEqualTo(1);
    }

    @Test
    @SuppressWarnings("unchecked")
    void featureOnlyAudioIsObservedButExcludedFromDiseaseFusion() {
        HealthScreeningService service = new HealthScreeningService();

        Map<String, Object> screen = service.evaluate(
                telemetry("grazing", 0.90, 0.70, 33.0, true),
                Instant.parse("2026-07-19T12:00:00Z"));

        Map<String, Object> sources = (Map<String, Object>) screen.get("sources");
        Map<String, Object> audio = (Map<String, Object>) sources.get("audio");
        assertThat(audio.get("online")).isEqualTo(true);
        assertThat(audio.get("observed")).isEqualTo(true);
        assertThat(audio.get("modelApproved")).isEqualTo(false);
        assertThat(audio.get("participating")).isEqualTo(false);

        Map<String, Object> fusion = (Map<String, Object>) screen.get("fusion");
        assertThat((List<String>) fusion.get("observedSources")).contains("motion", "audio");
        assertThat((List<String>) fusion.get("participatingSources"))
                .containsExactly("motion", "surfaceTemperature")
                .doesNotContain("audio");
        assertThat(fusion.get("evidenceCount")).isEqualTo(2);
    }

    private void establishBaseline(HealthScreeningService service, Instant start, boolean modelDeployed) {
        for (int index = 0; index < 18 * 30; index++) {
            String behavior = index % 3 == 0 ? "standing_ruminating" : "grazing";
            service.evaluate(
                    telemetry(behavior, 0.90, 0.82, 33.0, false, modelDeployed, false),
                    start.plus(index * 10L, ChronoUnit.SECONDS));
        }
    }

    private Map<String, Object> sustainedMobilityChange(HealthScreeningService service, Instant start) {
        Map<String, Object> screen = null;
        for (int index = 0; index <= 6 * 30; index++) {
            screen = service.evaluate(
                    telemetry("lying_resting", 0.91, 0.08, 34.6, false),
                    start.plus(index * 10L, ChronoUnit.SECONDS));
        }
        return screen;
    }

    private Map<String, Object> sustainedApprovedLamenessChange(HealthScreeningService service, Instant start) {
        Map<String, Object> screen = null;
        for (int index = 0; index <= 6 * 30; index++) {
            ObjectNode telemetry = telemetry("lying_resting", 0.91, 0.08, 34.6, false);
            ObjectNode lameness = telemetry.putObject("lamenessScreen");
            lameness.put("modelStatus", "deployed");
            lameness.put("candidate", true);
            lameness.put("rejected", false);
            lameness.put("score", 0.81);
            screen = service.evaluate(telemetry, start.plus(index * 10L, ChronoUnit.SECONDS));
        }
        return screen;
    }

    private ObjectNode telemetry(
            String behaviorState,
            double behaviorConfidence,
            double activity,
            double surfaceTemperature,
            boolean vocalizationCandidate) {
        return telemetry(
                behaviorState,
                behaviorConfidence,
                activity,
                surfaceTemperature,
                vocalizationCandidate,
                false,
                false);
    }

    private ObjectNode telemetry(
            String behaviorState,
            double behaviorConfidence,
            double activity,
            double surfaceTemperature,
            boolean vocalizationCandidate,
            boolean modelDeployed,
            boolean respiratoryCandidate) {
        return telemetry(behaviorState, behaviorConfidence, activity, surfaceTemperature,
                vocalizationCandidate, modelDeployed, respiratoryCandidate, false);
    }

    private ObjectNode telemetry(
            String behaviorState,
            double behaviorConfidence,
            double activity,
            double surfaceTemperature,
            boolean vocalizationCandidate,
            boolean modelDeployed,
            boolean respiratoryCandidate,
            boolean abnormalVocalizationCandidate) {
        ObjectNode telemetry = objectMapper.createObjectNode();
        telemetry.put("deviceId", "cattle_01");
        telemetry.put("mpu0", true);
        telemetry.put("adxl345", true);
        telemetry.put("mpu1", true);

        ObjectNode behavior = telemetry.putObject("behavior");
        behavior.put("state", behaviorState);
        behavior.put("confidence", behaviorConfidence);
        behavior.put("bodyActivity", activity);
        behavior.put("legActivity", activity);

        ObjectNode b1 = telemetry.putObject("b1Infrared");
        b1.put("temperatureValid", true);
        b1.put("surfaceTemperature", surfaceTemperature);

        ObjectNode microphone = telemetry.putObject("microphone");
        microphone.put("initialized", true);
        microphone.put("status", "ok");
        microphone.put("vocalizationCandidate", vocalizationCandidate);
        microphone.put("modelStatus", modelDeployed ? "deployed" : "feature_only");
        microphone.put("respiratoryCandidate", respiratoryCandidate);
        microphone.put("abnormalVocalizationCandidate", abnormalVocalizationCandidate);
        return telemetry;
    }
}
