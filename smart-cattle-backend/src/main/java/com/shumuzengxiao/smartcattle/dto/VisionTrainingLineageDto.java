package com.shumuzengxiao.smartcattle.dto;

import java.time.Instant;

/** Server-rehashed visual archive metadata used by the release trainer. */
public record VisionTrainingLineageDto(
        Long sourceEventId,
        String cameraId,
        String barnId,
        String clinicalAnimalId,
        String snapshotPath,
        String snapshotSha256,
        boolean snapshotIntegrityVerified,
        Instant integrityVerifiedAt,
        String reviewStatus,
        String reviewLabel,
        String veterinarian,
        String clinicalEvidenceReference,
        Instant clinicallyVerifiedAt,
        Instant recordedAt
) {
}
