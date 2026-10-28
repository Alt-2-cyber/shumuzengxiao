package com.shumuzengxiao.smartcattle.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * Identifies one platform archive used by a disease-screening release.
 * For audio, sourceId is the numeric audio event id. For lameness, sourceId
 * is the motion-capture session id and recordingId is the trainer's stable
 * dataset-record identifier.
 */
public record ModelReleaseLineageSourceRequest(
        @NotBlank @Size(max = 120) String sourceId,
        @Size(max = 120) String recordingId
) {
}
