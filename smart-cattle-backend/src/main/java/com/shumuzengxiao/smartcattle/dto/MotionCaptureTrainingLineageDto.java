package com.shumuzengxiao.smartcattle.dto;

import java.time.Instant;

/**
 * Immutable provenance for a three-position IMU archive. The service only
 * returns this record after it rechecks the raw NDJSON hash and continuity.
 */
public record MotionCaptureTrainingLineageDto(
        String sessionId,
        String cattleId,
        String deviceId,
        String barnId,
        String rawDataReference,
        String rawDataSha256,
        boolean archiveIntegrityVerified,
        Instant integrityVerifiedAt,
        String status,
        String qualityStatus,
        Integer sampleRateHz,
        Long receivedSamples,
        Long expectedSamples,
        Long attemptedSamples,
        Long droppedBackpressureSamples,
        Long droppedSensorSamples,
        Double completenessRatio,
        String videoReference,
        String operatorName,
        Instant requestedAt,
        Instant startedAt,
        Instant completedAt,
        String clinicalReviewStatus,
        Integer lamenessScore,
        String gaitReviewer,
        String hoofExaminer,
        String veterinarian,
        String hoofFinding,
        String clinicalEvidenceReference,
        Instant clinicallyVerifiedAt
) {
}
