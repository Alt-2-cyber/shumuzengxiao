package com.shumuzengxiao.smartcattle.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.List;

public record ModelReleaseRequest(
        @NotBlank @Pattern(regexp = "audio|lameness|vision") String modelFamily,
        @NotBlank @Size(max = 120) String modelVersion,
        @NotBlank @Pattern(regexp = "[A-Fa-f0-9]{64}") String datasetManifestSha256,
        @NotBlank @Pattern(regexp = "[A-Fa-f0-9]{64}") String modelCardSha256,
        @NotBlank @Pattern(regexp = "[A-Fa-f0-9]{64}") String firmwareSha256,
        @NotBlank @Size(max = 1200) String evidenceReference,
        @NotBlank @Size(max = 120) String approvedBy,
        @NotBlank @Size(max = 16_000) String validationSummary,
        @Size(max = 1200) String notes,
        @NotBlank @Pattern(regexp = "[A-Fa-f0-9]{64}") String sourceLineageSha256,
        @NotEmpty @Size(max = 5000) List<@Valid ModelReleaseLineageSourceRequest> sourceLineage
) {
}
