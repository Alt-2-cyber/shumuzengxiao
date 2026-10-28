package com.shumuzengxiao.smartcattle.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import jakarta.validation.constraints.AssertTrue;

public record AudioReviewRequest(
        @NotBlank
        @Pattern(regexp = "pending|confirmed|rejected|normal") String status,
        @Size(max = 80) String label,
        @Size(max = 1200) String note,
        @Size(max = 80) String reviewer,
        @Size(max = 120) String animalId,
        @Size(max = 120) String recordingSessionId,
        @Size(max = 80) String veterinarian,
        @Size(max = 1200) String clinicalEvidenceReference,
        Boolean clinicallyVerified
) {
    @AssertTrue(message = "clinical verification requires animal, session, veterinarian, and evidence reference")
    public boolean hasCompleteClinicalVerification() {
        if (!Boolean.TRUE.equals(clinicallyVerified)) {
            return true;
        }
        return present(animalId) && present(recordingSessionId)
                && present(veterinarian) && present(clinicalEvidenceReference)
                && ("confirmed".equals(status) || "normal".equals(status));
    }

    private static boolean present(String value) {
        return value != null && !value.isBlank();
    }
}
