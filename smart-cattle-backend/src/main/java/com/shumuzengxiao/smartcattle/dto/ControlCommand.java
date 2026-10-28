package com.shumuzengxiao.smartcattle.dto;

import jakarta.validation.constraints.NotBlank;

public record ControlCommand(
        @NotBlank String deviceId,
        @NotBlank String action,
        Boolean enabled
) {
}
