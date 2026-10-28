package com.shumuzengxiao.smartcattle.dto;

import java.time.Instant;

/**
 * Immutable lineage returned only to the clinical role before a training run.
 * Reaching this DTO means the server re-hashed the archived WAV at request time.
 */
public record AudioTrainingLineageDto(
        Long sourceEventId,
        String deviceId,
        String barnId,
        String cattleId,
        String audioClipPath,
        String clipSha256,
        boolean clipIntegrityVerified,
        Instant integrityVerifiedAt,
        String reviewStatus,
        String reviewLabel,
        String clinicalAnimalId,
        String recordingSessionId,
        String veterinarian,
        String clinicalEvidenceReference,
        Instant clinicallyVerifiedAt,
        Instant recordedAt
) {
}
