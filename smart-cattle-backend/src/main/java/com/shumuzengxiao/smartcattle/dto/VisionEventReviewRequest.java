package com.shumuzengxiao.smartcattle.dto;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/** Human/clinical review for an archived visual event. */
public record VisionEventReviewRequest(
        @NotBlank @Pattern(regexp = "pending|confirmed|rejected|normal") String status,
        @Size(max = 96)
        @Pattern(regexp = "normal|gait_abnormal_suspect|hoof_lesion_suspect|oral_lesion_suspect|nasal_discharge_suspect|fall_suspect|person_enter|snapshot_event")
        String label,
        @NotBlank @Size(max = 80) String reviewer,
        @Size(max = 120) String animalId,
        @Size(max = 80) String veterinarian,
        @Size(max = 1200) String clinicalEvidenceReference,
        @Size(max = 1200) String note,
        Boolean clinicallyVerified
) {
    @AssertTrue(message = "clinical verification requires confirmed/normal status, animal, veterinarian, and evidence reference")
    public boolean hasCompleteClinicalVerification() {
        if (!Boolean.TRUE.equals(clinicallyVerified)) {
            return true;
        }
        return ("confirmed".equals(status) || "normal".equals(status))
                && present(animalId) && present(veterinarian) && present(clinicalEvidenceReference)
                && present(label);
    }

    @AssertTrue(message = "normal review must use the normal label")
    public boolean hasConsistentNormalLabel() {
        return !"normal".equals(status) || "normal".equals(label);
    }

    private static boolean present(String value) {
        return value != null && !value.isBlank();
    }
}
