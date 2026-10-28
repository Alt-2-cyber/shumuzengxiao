package com.shumuzengxiao.smartcattle.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record FmdTriageOpenRequest(
        @NotNull Long healthRiskId,
        @NotBlank @Size(max = 120) String actor,
        @NotBlank @Size(max = 80) String veterinarian,
        @NotBlank @Size(max = 1200) String evidenceReference,
        @Size(max = 1200) String note
) {
}
