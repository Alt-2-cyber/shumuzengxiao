package com.shumuzengxiao.smartcattle.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.List;

public final class MobileSupport {
    private MobileSupport() {}

    public record Reference(String title, String url) {}
    public record Message(@NotBlank @Pattern(regexp = "user|assistant") String role,
                          @NotBlank @Size(max = 2000) String content) {}
    public record Question(@NotBlank @Size(max = 1000) String question,
                           @Size(max = 8) List<@NotNull @Valid Message> history) {}
    public record Answer(String answer, String mode, String model, String notice,
                         String category, List<Reference> references) {}
    public record Category(String id, String name, String scope) {}
    public record Catalog(String mode, List<Category> categories) {}
    public record ConsultationRequest(
            @NotBlank @Pattern(regexp = "[a-zA-Z0-9_-]{16,64}") String requestId,
            @NotBlank @Pattern(regexp = "health|nutrition|equipment|other") String category,
            @NotBlank @Pattern(regexp = "normal|soon|urgent") String priority,
            @NotBlank @Size(min = 5, max = 80) String subject,
            @NotBlank @Size(min = 10, max = 2000) String description,
            @Size(max = 80) String cattleId,
            @Size(max = 80) String contact) {}
    public record ConsultationView(String id, String category, String priority, String subject,
                                   String description, String cattleId, String contact,
                                   String status, Instant createdAt, Instant updatedAt) {}
}
