package com.shumuzengxiao.smartcattle.dto;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record FmdTriageActionRequest(
        @NotBlank
        @Pattern(regexp = "veterinarian_assigned|authority_notified|isolation_decision_recorded|sample_submitted|laboratory_reference_recorded|closed_by_authority")
        String action,
        @NotBlank @Size(max = 120) String actor,
        @NotBlank @Size(max = 80) String veterinarian,
        @Size(max = 1200) String authorityReference,
        @NotBlank @Size(max = 1200) String evidenceReference,
        @Size(max = 1200) String note,
        Boolean closureAuthorized
) {
    @AssertTrue(message = "closure requires an authority reference and explicit authorization")
    public boolean hasAuthorizedClosure() {
        return !"closed_by_authority".equals(action)
                || (Boolean.TRUE.equals(closureAuthorized)
                && authorityReference != null && !authorityReference.isBlank());
    }
}
