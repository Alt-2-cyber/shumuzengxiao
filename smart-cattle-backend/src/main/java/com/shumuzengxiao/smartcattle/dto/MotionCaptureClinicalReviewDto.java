package com.shumuzengxiao.smartcattle.dto;

import java.time.Instant;

public record MotionCaptureClinicalReviewDto(
        String sessionId,
        String cattleId,
        Integer lamenessScore,
        String gaitReviewer,
        String hoofExaminer,
        String veterinarian,
        String hoofFinding,
        String clinicalEvidenceReference,
        Instant clinicallyVerifiedAt,
        Instant reviewedAt
) {
}
