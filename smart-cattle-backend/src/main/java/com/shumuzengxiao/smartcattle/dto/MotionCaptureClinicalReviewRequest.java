package com.shumuzengxiao.smartcattle.dto;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

/** Final veterinary/clinical sign-off for a captured gait recording. */
public record MotionCaptureClinicalReviewRequest(
        @NotNull @Min(0) @Max(3) Integer lamenessScore,
        @NotBlank @Size(max = 80) String gaitReviewer,
        @NotBlank @Size(max = 80) String hoofExaminer,
        @NotBlank @Size(max = 80) String veterinarian,
        @NotBlank @Size(max = 1200) String hoofFinding,
        @NotBlank @Size(max = 1200) String clinicalEvidenceReference,
        Boolean clinicallyVerified
) {
    @AssertTrue(message = "a release-eligible lameness review must be explicitly clinically verified")
    public boolean isClinicallyVerified() {
        return Boolean.TRUE.equals(clinicallyVerified);
    }
}
