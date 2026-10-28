package com.shumuzengxiao.smartcattle.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record MotionCaptureRequest(
        @NotBlank @Size(max = 120) String cattleId,
        @NotBlank @Size(max = 80) String deviceId,
        @NotBlank @Size(max = 80) String barnId,
        @Min(1_000) @Max(300_000) Integer durationMs,
        @Size(max = 120) String sessionId,
        @NotBlank @Size(max = 80) String operatorName,
        @Size(max = 1200) String videoReference,
        @Size(max = 1200) String notes
) {
}
