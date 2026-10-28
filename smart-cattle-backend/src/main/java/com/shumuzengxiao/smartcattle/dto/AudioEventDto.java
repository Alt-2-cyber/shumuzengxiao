package com.shumuzengxiao.smartcattle.dto;

import java.time.Instant;

public record AudioEventDto(
        Long id,
        String deviceId,
        String barnId,
        String cattleId,
        String eventType,
        String label,
        Double score,
        Integer durationMs,
        Double snr,
        String audioClipPath,
        Boolean clipAvailable,
        String clipSha256,
        String modelVersion,
        String modelStatus,
        Boolean approvedByServer,
        Boolean screeningEligible,
        String approvalReason,
        Double rms,
        Double dbfs,
        Double zeroCrossingRate,
        Double lowBandRatio,
        Double midBandRatio,
        Double highBandRatio,
        Double saturationRatio,
        String reviewStatus,
        String reviewLabel,
        String reviewNote,
        String reviewer,
        Instant reviewedAt,
        String clinicalAnimalId,
        String recordingSessionId,
        String veterinarian,
        String clinicalEvidenceReference,
        Instant clinicallyVerifiedAt,
        Instant recordedAt
) {
}
