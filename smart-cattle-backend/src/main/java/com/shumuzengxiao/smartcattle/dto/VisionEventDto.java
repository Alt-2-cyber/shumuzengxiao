package com.shumuzengxiao.smartcattle.dto;

import com.shumuzengxiao.smartcattle.domain.Severity;

import java.time.Instant;

/** Public shape for clinical visual evidence; no internal entity is exposed. */
public record VisionEventDto(
        Long id,
        String cameraId,
        String barnId,
        String eventType,
        Severity severity,
        Double score,
        String targetId,
        String sourceKey,
        String sourceSnapshotPath,
        String snapshotPath,
        String snapshotSha256,
        Boolean snapshotAvailable,
        String snapshotContentType,
        Long snapshotBytes,
        String evidence,
        String modelName,
        String modelVersion,
        String modelStatus,
        Boolean modelApprovedByServer,
        Boolean screeningEligible,
        String reviewStatus,
        String reviewLabel,
        String reviewNote,
        String reviewer,
        String clinicalAnimalId,
        String veterinarian,
        String clinicalEvidenceReference,
        Instant clinicallyVerifiedAt,
        Instant reviewedAt,
        Instant recordedAt
) {
}
