package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.shumuzengxiao.smartcattle.domain.MotionCaptureClinicalReview;
import com.shumuzengxiao.smartcattle.domain.MotionCaptureSession;
import com.shumuzengxiao.smartcattle.dto.MotionCaptureClinicalReviewRequest;
import com.shumuzengxiao.smartcattle.dto.MotionCaptureTrainingLineageDto;
import com.shumuzengxiao.smartcattle.repository.MotionCaptureClinicalReviewRepository;
import com.shumuzengxiao.smartcattle.repository.MotionCaptureSessionRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class MotionCaptureServiceTest {
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final MotionCaptureSessionRepository repository = mock(MotionCaptureSessionRepository.class);
    private final MotionCaptureClinicalReviewRepository clinicalReviews = mock(MotionCaptureClinicalReviewRepository.class);
    private final MotionCaptureService service = new MotionCaptureService(
            repository, clinicalReviews, objectMapper, null);
    private final Path storage = Path.of("../motion-captures").toAbsolutePath().normalize();

    @AfterEach
    void cleanUp() throws Exception {
        Files.deleteIfExists(storage.resolve("test-session.jsonl"));
        Files.deleteIfExists(storage.resolve("quality-session.jsonl"));
        Files.deleteIfExists(storage.resolve("gap-session.jsonl"));
        Files.deleteIfExists(storage.resolve("accepted-session.jsonl"));
        Files.deleteIfExists(storage.resolve("signed-session.jsonl"));
    }

    @Test
    void normalizesCompactFirmwareRowsBeforeArchiving() throws Exception {
        MotionCaptureSession session = new MotionCaptureSession();
        session.setSessionId("test-session");
        session.setCattleId("cow_001");
        session.setDeviceId("demo_esp32_01");
        session.setBarnId("barn_01");
        session.setStatus("queued");
        session.setRawDataPath("test-session.jsonl");
        when(repository.findBySessionId("test-session")).thenReturn(Optional.of(session));
        when(repository.save(any(MotionCaptureSession.class))).thenAnswer(invocation -> invocation.getArgument(0));
        service.prepareStorage();

        service.ingestSample(compactRow(), Instant.parse("2026-07-19T12:00:00Z"));

        Path raw = storage.resolve("test-session.jsonl");
        ObjectNode saved = (ObjectNode) objectMapper.readTree(Files.readString(raw));
        assertThat(saved.path("type").asText()).isEqualTo("motion_capture_sample");
        assertThat(saved.path("neck").path("gx").asDouble()).isEqualTo(0.4);
        assertThat(saved.path("body").path("az").asDouble()).isEqualTo(1.2);
        assertThat(session.getStatus()).isEqualTo("capturing");
    }

    @Test
    void rejectsACompletedCaptureWhenFirmwareReportsLostSamples() throws Exception {
        MotionCaptureSession session = new MotionCaptureSession();
        session.setSessionId("quality-session");
        session.setCattleId("cow_001");
        session.setDeviceId("demo_esp32_01");
        session.setBarnId("barn_01");
        session.setDurationMs(1_000);
        session.setSampleRateHz(20);
        session.setReceivedSamples(0L);
        session.setStatus("queued");
        session.setRawDataPath("quality-session.jsonl");
        when(repository.findBySessionId("quality-session")).thenReturn(Optional.of(session));
        when(repository.save(any(MotionCaptureSession.class))).thenAnswer(invocation -> invocation.getArgument(0));
        service.prepareStorage();

        service.ingestSample(qualityRow(), Instant.parse("2026-07-19T12:00:00Z"));
        ObjectNode completed = objectMapper.createObjectNode();
        completed.put("type", "motion_capture");
        completed.put("status", "completed");
        completed.put("sessionId", "quality-session");
        completed.put("deviceId", "demo_esp32_01");
        completed.put("cattleId", "cow_001");
        completed.put("barnId", "barn_01");
        completed.put("sampleRateHz", 20);
        completed.put("expectedSamples", 20);
        completed.put("attemptedSamples", 20);
        completed.put("droppedBackpressureSamples", 19);
        completed.put("droppedSensorSamples", 0);

        service.ingestState(completed, Instant.parse("2026-07-19T12:00:01Z"));

        assertThat(session.getStatus()).isEqualTo("completed_incomplete");
        assertThat(session.getQualityStatus()).isEqualTo("rejected_transport_backpressure");
        assertThat(session.getCompletenessRatio()).isEqualTo(0.05);
    }

    @Test
    void ignoresAStateFrameWithTheWrongCaptureIdentity() throws Exception {
        MotionCaptureSession session = new MotionCaptureSession();
        session.setSessionId("identity-session");
        session.setCattleId("cow_001");
        session.setDeviceId("demo_esp32_01");
        session.setBarnId("barn_01");
        session.setStatus("queued");
        when(repository.findBySessionId("identity-session")).thenReturn(Optional.of(session));

        ObjectNode started = objectMapper.createObjectNode();
        started.put("type", "motion_capture");
        started.put("status", "started");
        started.put("sessionId", "identity-session");
        started.put("deviceId", "other-device");
        started.put("cattleId", "cow_001");
        started.put("barnId", "barn_01");

        service.ingestState(started, Instant.parse("2026-07-19T12:00:00Z"));

        assertThat(session.getStatus()).isEqualTo("queued");
    }

    @Test
    void rejectsDuplicateOrGappedFirmwareSampleIndexesBeforeTheyCanBeAccepted() throws Exception {
        MotionCaptureSession session = new MotionCaptureSession();
        session.setSessionId("gap-session");
        session.setCattleId("cow_001");
        session.setDeviceId("demo_esp32_01");
        session.setBarnId("barn_01");
        session.setStatus("queued");
        session.setRawDataPath("gap-session.jsonl");
        when(repository.findBySessionId("gap-session")).thenReturn(Optional.of(session));
        when(repository.save(any(MotionCaptureSession.class))).thenAnswer(invocation -> invocation.getArgument(0));
        service.prepareStorage();

        ObjectNode first = compactRow();
        first.put("s", "gap-session");
        service.ingestSample(first, Instant.parse("2026-07-19T12:00:00Z"));

        ObjectNode skipped = compactRow();
        skipped.put("s", "gap-session");
        skipped.put("i", 2);
        service.ingestSample(skipped, Instant.parse("2026-07-19T12:00:00.050Z"));

        assertThat(session.getStatus()).isEqualTo("rejected_integrity");
        assertThat(session.getQualityStatus()).isEqualTo("rejected_sample_index");
        assertThatThrownBy(() -> service.resolveRawData("gap-session"))
                .hasMessageContaining("not accepted for export");
    }

    @Test
    void acceptsOnlyAnUntamperedCompleteArchive() throws Exception {
        MotionCaptureSession session = new MotionCaptureSession();
        session.setSessionId("accepted-session");
        session.setCattleId("cow_001");
        session.setDeviceId("demo_esp32_01");
        session.setBarnId("barn_01");
        session.setDurationMs(1_000);
        session.setSampleRateHz(20);
        session.setReceivedSamples(0L);
        session.setStatus("queued");
        session.setRawDataPath("accepted-session.jsonl");
        session.setVideoReference("video://accepted-session");
        when(repository.findBySessionId("accepted-session")).thenReturn(Optional.of(session));
        when(repository.save(any(MotionCaptureSession.class))).thenAnswer(invocation -> invocation.getArgument(0));
        service.prepareStorage();

        for (int index = 0; index < 20; index++) {
            ObjectNode row = compactRow();
            row.put("s", "accepted-session");
            row.put("i", index);
            row.put("m", 1_000 + index * 50);
            service.ingestSample(row, Instant.parse("2026-07-19T12:00:00Z").plusMillis(index * 50L));
        }
        service.ingestState(completedState("accepted-session", 20, 0, 0),
                Instant.parse("2026-07-19T12:00:01Z"));

        assertThat(session.getStatus()).isEqualTo("completed");
        assertThat(session.getQualityStatus()).isEqualTo("accepted");
        assertThat(service.resolveRawData("accepted-session"))
                .isEqualTo(storage.resolve("accepted-session.jsonl"));

        MotionCaptureTrainingLineageDto lineage = service.trainingLineage("accepted-session");
        assertThat(lineage.sessionId()).isEqualTo("accepted-session");
        assertThat(lineage.cattleId()).isEqualTo("cow_001");
        assertThat(lineage.rawDataSha256()).isEqualTo(session.getRawDataSha256());
        assertThat(lineage.archiveIntegrityVerified()).isTrue();
        assertThat(lineage.rawDataReference()).isEqualTo("/api/motion-captures/accepted-session/raw");
        assertThat(lineage.clinicalReviewStatus()).isEqualTo("not_signed");

        Files.writeString(storage.resolve("accepted-session.jsonl"), "{}\n", java.nio.file.StandardOpenOption.APPEND);
        assertThatThrownBy(() -> service.resolveRawData("accepted-session"))
                .hasMessageContaining("archive integrity check failed");
        assertThatThrownBy(() -> service.trainingLineage("accepted-session"))
                .hasMessageContaining("archive integrity check failed");
    }

    @Test
    void bindsClinicalGaitAndHoofSignoffToAnAcceptedArchive() throws Exception {
        MotionCaptureSession session = new MotionCaptureSession();
        session.setSessionId("signed-session");
        session.setCattleId("cow_001");
        session.setDeviceId("demo_esp32_01");
        session.setBarnId("barn_01");
        session.setDurationMs(1_000);
        session.setSampleRateHz(20);
        session.setReceivedSamples(0L);
        session.setStatus("queued");
        session.setRawDataPath("signed-session.jsonl");
        session.setVideoReference("video://signed-session");
        when(repository.findBySessionId("signed-session")).thenReturn(Optional.of(session));
        when(repository.save(any(MotionCaptureSession.class))).thenAnswer(invocation -> invocation.getArgument(0));
        when(clinicalReviews.findBySessionId("signed-session")).thenReturn(Optional.empty());
        when(clinicalReviews.save(any(MotionCaptureClinicalReview.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        service.prepareStorage();

        for (int index = 0; index < 20; index++) {
            ObjectNode row = compactRow();
            row.put("s", "signed-session");
            row.put("i", index);
            row.put("m", 1_000 + index * 50);
            service.ingestSample(row, Instant.parse("2026-07-19T12:00:00Z").plusMillis(index * 50L));
        }
        service.ingestState(completedState("signed-session", 20, 0, 0),
                Instant.parse("2026-07-19T12:00:01Z"));

        var saved = service.reviewClinical("signed-session", new MotionCaptureClinicalReviewRequest(
                2, "gait_001", "hoof_001", "vet_001", "sole-lesion-observed", "case-001", true));
        assertThat(saved.lamenessScore()).isEqualTo(2);
        assertThat(saved.clinicallyVerifiedAt()).isNotNull();

        MotionCaptureClinicalReview review = new MotionCaptureClinicalReview();
        review.setSessionId("signed-session");
        review.setCattleId("cow_001");
        review.setLamenessScore(2);
        review.setGaitReviewer("gait_001");
        review.setHoofExaminer("hoof_001");
        review.setVeterinarian("vet_001");
        review.setHoofFinding("sole-lesion-observed");
        review.setClinicalEvidenceReference("case-001");
        review.setClinicallyVerifiedAt(saved.clinicallyVerifiedAt());
        when(clinicalReviews.findBySessionId("signed-session")).thenReturn(Optional.of(review));

        MotionCaptureTrainingLineageDto lineage = service.trainingLineage("signed-session");
        assertThat(lineage.clinicalReviewStatus()).isEqualTo("verified");
        assertThat(lineage.lamenessScore()).isEqualTo(2);
        assertThat(lineage.gaitReviewer()).isEqualTo("gait_001");
        assertThat(lineage.hoofExaminer()).isEqualTo("hoof_001");
        assertThat(lineage.veterinarian()).isEqualTo("vet_001");
    }

    @Test
    void expiresAStaleCaptureInsteadOfLeavingItCollecting() throws Exception {
        MotionCaptureSession session = new MotionCaptureSession();
        session.setSessionId("stale-session");
        session.setCattleId("cow_001");
        session.setDeviceId("demo_esp32_01");
        session.setBarnId("barn_01");
        session.setDurationMs(1_000);
        session.setStatus("capturing");
        session.setRawDataPath("stale-session.jsonl");
        session.setRequestedAt(Instant.parse("2026-07-19T11:59:00Z"));
        session.setStartedAt(Instant.parse("2026-07-19T12:00:00Z"));
        when(repository.findByStatusInAndRequestedAtBefore(any(), any()))
                .thenReturn(List.of(session));
        when(repository.save(any(MotionCaptureSession.class))).thenAnswer(invocation -> invocation.getArgument(0));
        service.prepareStorage();
        org.springframework.test.util.ReflectionTestUtils.setField(service, "expiryGraceMs", 0L);

        service.expireStaleSessions(Instant.parse("2026-07-19T12:00:02Z"));

        assertThat(session.getStatus()).isEqualTo("expired");
        assertThat(session.getQualityStatus()).isEqualTo("rejected_timeout");
    }

    private ObjectNode compactRow() {
        ObjectNode row = objectMapper.createObjectNode();
        row.put("type", "mcs");
        row.put("s", "test-session");
        row.put("d", "demo_esp32_01");
        row.put("c", "cow_001");
        row.put("b", "barn_01");
        row.put("i", 0);
        row.put("m", 1000);
        row.put("r", 20);
        numbers(row.putArray("n"), 1.0, 1.1, 1.2, 0.4, 0.5, 0.6);
        numbers(row.putArray("u"), 1.0, 1.1, 1.2);
        numbers(row.putArray("l"), 1.0, 1.1, 1.2, 0.4, 0.5, 0.6);
        return row;
    }

    private ObjectNode qualityRow() {
        ObjectNode row = compactRow();
        row.put("s", "quality-session");
        return row;
    }

    private ObjectNode completedState(String sessionId, int attempted, int backpressure, int sensor) {
        ObjectNode completed = objectMapper.createObjectNode();
        completed.put("type", "motion_capture");
        completed.put("status", "completed");
        completed.put("sessionId", sessionId);
        completed.put("deviceId", "demo_esp32_01");
        completed.put("cattleId", "cow_001");
        completed.put("barnId", "barn_01");
        completed.put("sampleRateHz", 20);
        completed.put("expectedSamples", 20);
        completed.put("attemptedSamples", attempted);
        completed.put("droppedBackpressureSamples", backpressure);
        completed.put("droppedSensorSamples", sensor);
        return completed;
    }

    private static void numbers(ArrayNode array, double... values) {
        for (double value : values) {
            array.add(value);
        }
    }
}
