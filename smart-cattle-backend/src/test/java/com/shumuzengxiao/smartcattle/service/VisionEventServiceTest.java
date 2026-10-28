package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.shumuzengxiao.smartcattle.domain.VisionEvent;
import com.shumuzengxiao.smartcattle.dto.VisionEventRequest;
import com.shumuzengxiao.smartcattle.repository.VisionEventRepository;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Optional;
import java.util.Base64;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class VisionEventServiceTest {
    @Test
    void unapprovedLesionEventIsArchivedButCannotBecomeHealthEvidence() {
        VisionEventRepository repository = mock(VisionEventRepository.class);
        HealthScreeningService health = mock(HealthScreeningService.class);
        ModelApprovalService approval = new ModelApprovalService();
        ReflectionTestUtils.setField(approval, "approvedVisionVersions", "vision-lesion-v1");
        VisionEventService service = new VisionEventService(
                repository, health, approval, new ObjectMapper());
        when(repository.save(any(VisionEvent.class))).thenAnswer(invocation -> invocation.getArgument(0));

        VisionEventRequest request = new VisionEventRequest(
                "cam_01", "barn_01", "hoof_lesion_suspect", "warning", 0.9,
                "cow_001", null, "unreviewed detector", null, null, null, true,
                "cattle-yolov8-coco", "unreleased-vision-v1", "deployed", null, null);

        VisionEvent saved = service.ingest(request);

        assertThat(saved.getModelApprovedByServer()).isFalse();
        assertThat(saved.getScreeningEligible()).isFalse();
        assertThat(saved.getEvidence()).contains("model_not_server_approved");
        verify(health, never()).recordVisionEvidence(any(), any(), any(), any());
    }

    @Test
    void archivesInlineSnapshotAndExposesHashMetadata() throws Exception {
        VisionEventRepository repository = mock(VisionEventRepository.class);
        HealthScreeningService health = mock(HealthScreeningService.class);
        ModelApprovalService approval = new ModelApprovalService();
        VisionEventService service = new VisionEventService(
                repository, health, approval, new ObjectMapper());
        Path storage = Files.createTempDirectory("vision-snapshot-test");
        ReflectionTestUtils.setField(service, "storageRoot", storage);
        when(repository.save(any(VisionEvent.class))).thenAnswer(invocation -> {
            VisionEvent event = invocation.getArgument(0);
            if (event.getId() == null) {
                event.setId(7L);
            }
            return event;
        });

        byte[] image = new byte[] {1, 2, 3, 4, 5};
        VisionEventRequest request = new VisionEventRequest(
                "cam_01", "barn_01", "snapshot_event", "observe", 0.4,
                null, "/root/snapshots/capture.jpg", "camera frame", "edge-7", "boot-1", null,
                true, "cattle-yolov8-coco", "cattle-yolov8-coco-v1", "deployed",
                Base64.getEncoder().encodeToString(image), "image/jpeg");

        VisionEvent saved = service.ingest(request);

        assertThat(saved.getSnapshotAvailable()).isTrue();
        assertThat(saved.getSnapshotPath()).startsWith("/api/vision-snapshots/7-");
        assertThat(saved.getSnapshotContentType()).isEqualTo("image/jpeg");
        assertThat(saved.getSnapshotBytes()).isEqualTo(5L);
        assertThat(saved.getSnapshotSha256()).hasSize(64);
        assertThat(Files.list(storage).findFirst()).isPresent();
    }
}
