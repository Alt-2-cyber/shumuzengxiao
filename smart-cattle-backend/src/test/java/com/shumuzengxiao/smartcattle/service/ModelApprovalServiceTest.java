package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;

class ModelApprovalServiceTest {
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void unapprovedAudioCannotEnterIndividualScreening() {
        ModelApprovalService service = new ModelApprovalService();
        ObjectNode event = objectMapper.createObjectNode();
        event.put("cattleId", "cow_001");
        event.put("label", "cough_suspect");
        ObjectNode model = event.putObject("model");
        model.put("status", "deployed");
        model.put("version", "unreleased-audio-v1");

        ModelApprovalService.AudioDecision decision = service.enforceAudioEvent(event);

        assertThat(decision.approvedByServer()).isFalse();
        assertThat(decision.screeningEligible()).isFalse();
        assertThat(event.path("model").path("status").asText()).isEqualTo("feature_only");
        assertThat(event.path("model").path("approvalReason").asText())
                .isEqualTo("model_not_server_approved");
    }

    @Test
    void approvedAbnormalVocalizationCanEnterIndividualScreening() {
        ModelApprovalService service = new ModelApprovalService();
        ReflectionTestUtils.setField(service, "approvedAudioVersions", "audio-vocal-v1");
        ObjectNode event = objectMapper.createObjectNode();
        event.put("cattleId", "cow_001");
        event.put("label", "abnormal_vocalization_suspect");
        ObjectNode model = event.putObject("model");
        model.put("status", "deployed");
        model.put("version", "audio-vocal-v1");

        ModelApprovalService.AudioDecision decision = service.enforceAudioEvent(event);

        assertThat(decision.approvedByServer()).isTrue();
        assertThat(decision.screeningEligible()).isTrue();
        assertThat(decision.normalizedLabel()).isEqualTo("abnormal_vocalization_suspect");
    }

    @Test
    void unapprovedTelemetryCannotCarryAbnormalVocalizationCandidate() {
        ModelApprovalService service = new ModelApprovalService();
        ObjectNode telemetry = objectMapper.createObjectNode();
        ObjectNode microphone = telemetry.putObject("microphone");
        microphone.put("modelStatus", "deployed");
        microphone.put("modelVersion", "unreleased-audio-v1");
        microphone.put("abnormalVocalizationCandidate", true);

        service.enforce(telemetry);

        assertThat(microphone.path("modelStatus").asText()).isEqualTo("feature_only");
        assertThat(microphone.path("abnormalVocalizationCandidate").asBoolean()).isFalse();
    }

    @Test
    void approvedVisionStillRequiresARealCattleId() {
        ModelApprovalService service = new ModelApprovalService();
        ReflectionTestUtils.setField(service, "approvedVisionVersions", "vision-lesion-v1");

        ModelApprovalService.VisionDecision decision = service.enforceVisionEvent(
                "hoof_lesion_suspect", "deployed", "vision-lesion-v1", "");

        assertThat(decision.approvedByServer()).isTrue();
        assertThat(decision.screeningEvent()).isTrue();
        assertThat(decision.modelApprovalRequired()).isTrue();
        assertThat(decision.screeningEligible()).isFalse();
        assertThat(decision.approvalReason()).isEqualTo("missing_verified_cattle_id");
    }

    @Test
    void approvedNasalDischargeVisionCanEnterIndividualScreening() {
        ModelApprovalService service = new ModelApprovalService();
        ReflectionTestUtils.setField(service, "approvedVisionVersions", "vision-respiratory-v1");

        ModelApprovalService.VisionDecision decision = service.enforceVisionEvent(
                "nasal_discharge_suspect", "deployed", "vision-respiratory-v1", "cow_001");

        assertThat(decision.approvedByServer()).isTrue();
        assertThat(decision.screeningEvent()).isTrue();
        assertThat(decision.modelApprovalRequired()).isTrue();
        assertThat(decision.screeningEligible()).isTrue();
        assertThat(decision.approvalReason()).isEqualTo("approved_for_screening");
    }

    @Test
    void ordinaryOperationalVisionEventDoesNotNeedDiseaseModelApproval() {
        ModelApprovalService service = new ModelApprovalService();

        ModelApprovalService.VisionDecision decision = service.enforceVisionEvent(
                "snapshot_event", null, null, null);

        assertThat(decision.approvedByServer()).isFalse();
        assertThat(decision.screeningEvent()).isFalse();
        assertThat(decision.modelApprovalRequired()).isFalse();
        assertThat(decision.screeningEligible()).isFalse();
        assertThat(decision.approvalReason()).isEqualTo("non_screening_event");
    }
}
