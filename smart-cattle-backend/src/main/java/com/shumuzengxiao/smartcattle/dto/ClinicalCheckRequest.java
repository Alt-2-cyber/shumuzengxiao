package com.shumuzengxiao.smartcattle.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.AssertTrue;

public record ClinicalCheckRequest(
        @NotBlank @Size(max = 120) String cattleId,
        @NotBlank @Pattern(regexp = "core_temperature|gait_exam|lesion_exam") String checkType,
        Boolean verified,
        Boolean alert,
        @DecimalMin("-20.0") @DecimalMax("100.0")
        Double value,
        @NotBlank @Size(max = 80) String examiner,
        @Size(max = 1200) String evidenceReference,
        @Size(max = 1200) String findings,
        @Pattern(regexp = "gait_abnormal_suspect|hoof_lesion_suspect|oral_lesion_suspect|nasal_discharge_suspect")
        String evidenceType
) {
    @AssertTrue(message = "core_temperature requires a plausible measured value")
    public boolean hasCoreTemperatureValue() {
        return !"core_temperature".equals(checkType)
                || (value != null && value >= 30.0 && value <= 45.0);
    }

    @AssertTrue(message = "evidenceType must match a verified abnormal gait or lesion check")
    public boolean hasConsistentEvidenceType() {
        if (evidenceType == null || evidenceType.isBlank()) {
            return true;
        }
        if (!Boolean.TRUE.equals(verified()) || !Boolean.TRUE.equals(alert())) {
            return false;
        }
        return "gait_exam".equals(checkType())
                ? "gait_abnormal_suspect".equals(evidenceType())
                : "lesion_exam".equals(checkType());
    }
}
