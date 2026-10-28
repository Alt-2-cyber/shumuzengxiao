package com.shumuzengxiao.smartcattle.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record ModelReleaseRevocationRequest(
        @NotBlank @Size(max = 120) String revokedBy,
        @NotBlank @Size(max = 1200) String evidenceReference,
        @Size(max = 1200) String notes
) {
}
