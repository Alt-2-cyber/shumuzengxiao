package com.shumuzengxiao.smartcattle.dto;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/** Payload sent by the MaixCam HTTP bridge. targetId must be a real ear-tag or
 * management ID resolved by the deployment, never an anonymous tracker ID. */
public record VisionEventRequest(
        @NotBlank @Size(max = 64) String cameraId,
        @NotBlank @Size(max = 64) String barnId,
        @NotBlank @Size(max = 96)
        @Pattern(regexp = "fall_suspect|person_enter|snapshot_event|gait_abnormal_suspect|hoof_lesion_suspect|oral_lesion_suspect|nasal_discharge_suspect")
        String eventType,
        @NotBlank @Pattern(regexp = "normal|observe|warning|urgent") String level,
        @DecimalMin("0.0") @DecimalMax("1.0") Double score,
        @Size(max = 120) String targetId,
        @Size(max = 255) String snapshotPath,
        @Size(max = 1200) String evidence,
        @Size(max = 120) String edgeEventId,
        @Size(max = 120) String bootId,
        Long ts,
        Boolean screeningOnly,
        @Size(max = 120) String modelName,
        @Size(max = 120) String modelVersion,
        @Size(max = 40) String modelStatus,
        @Size(max = 2_700_000) String snapshotBase64,
        @Pattern(regexp = "image/jpeg|image/png|image/webp") String snapshotContentType
) {
}
