package com.shumuzengxiao.smartcattle.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import jakarta.annotation.PostConstruct;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.LinkedHashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/** Optional role-scoped API keys for a constrained on-premises deployment.
 * A TLS identity proxy remains the preferred production identity boundary. */
@Component
public class ApiKeyAccessPolicy {
    @Value("${security.api-key.enabled:false}")
    private boolean enabled;
    @Value("${security.api-key.require-role-keys:false}")
    private boolean requireRoleKeys;
    @Value("${security.api-key.value:}")
    private String legacyAdminKey = "";
    @Value("${security.api-key.viewer:}")
    private String viewerKey = "";
    @Value("${security.api-key.ingest:}")
    private String ingestKey = "";
    @Value("${security.api-key.operator:}")
    private String operatorKey = "";
    @Value("${security.api-key.clinical:}")
    private String clinicalKey = "";
    @Value("${security.api-key.admin:}")
    private String adminKey = "";

    @PostConstruct
    void validateConfiguration() {
        if (requireRoleKeys && !enabled) {
            throw new IllegalStateException("Production API key configuration cannot disable API-key authentication");
        }
        if (!enabled) {
            return;
        }

        Map<String, String> configured = configuredKeys();
        Set<String> seen = new HashSet<>();
        for (Map.Entry<String, String> entry : configured.entrySet()) {
            String key = entry.getValue();
            if (key == null || key.isBlank()) {
                continue;
            }
            if (!seen.add(key)) {
                throw new IllegalStateException("API key values must be unique across roles");
            }
        }
        if (seen.isEmpty()) {
            throw new IllegalStateException("API_KEY_ENABLED requires at least one configured API key");
        }
        if (requireRoleKeys) {
            for (Map.Entry<String, String> entry : configured.entrySet()) {
                if (entry.getValue() == null || entry.getValue().isBlank()) {
                    throw new IllegalStateException("Production API key configuration requires every role key: "
                            + entry.getKey());
                }
            }
        }
    }

    public boolean enabled() {
        return enabled;
    }

    public String roleFor(String key) {
        if (!enabled) {
            return "local";
        }
        if (key == null || key.isBlank()) {
            return null;
        }
        for (Map.Entry<String, String> entry : configuredKeys().entrySet()) {
            if (!entry.getValue().isBlank() && constantTimeEquals(entry.getValue(), key)) {
                return entry.getKey();
            }
        }
        return null;
    }

    public boolean allowsRest(String role, String method, String path) {
        if (!enabled || "local".equals(role)) {
            return true;
        }
        if (role == null) {
            return false;
        }
        if ("OPTIONS".equalsIgnoreCase(method)) {
            return true;
        }
        // Risk records are created only by HealthRiskLedgerService after an
        // evidence-qualified screening evaluation. Audio edge events arrive
        // only from the serial ingestion path, not from a generic REST write.
        if (("/api/events/health-risks".equals(path) || "/api/events/audio".equals(path))
                && !"GET".equalsIgnoreCase(method)) {
            return false;
        }
        if ("/api/events/vision".equals(path) && "POST".equalsIgnoreCase(method)) {
            return "ingest".equals(role) || isOperator(role);
        }
        if (path.startsWith("/api/events/vision/") && path.endsWith("/snapshot")
                && "PUT".equalsIgnoreCase(method)) {
            return "ingest".equals(role) || isOperator(role);
        }
        if ("/api/telemetry/ingest".equals(path) && "POST".equalsIgnoreCase(method)) {
            return "ingest".equals(role) || isOperator(role);
        }
        if (path.startsWith("/api/model-releases")) {
            return "admin".equals(role);
        }
        if (path.startsWith("/api/mobile-support/")) {
            return isViewer(role) && ("GET".equalsIgnoreCase(method) || "POST".equalsIgnoreCase(method));
        }
        // Audio clips, raw IMU recordings, clinical observations, FMD handoffs,
        // and their audit history can identify an animal and its health state.
        // They remain outside the operational read-only dashboard role.
        if (isClinicalEvidencePath(path)) {
            return isClinical(role);
        }
        if (path.startsWith("/api/devices/command")) {
            return isOperator(role);
        }
        if ("GET".equalsIgnoreCase(method)) {
            return isViewer(role);
        }
        return "admin".equals(role);
    }

    public boolean allowsWebSocket(String role) {
        return !enabled || "local".equals(role) || isViewer(role);
    }

    public static String bearer(String authorization) {
        if (authorization == null || !authorization.startsWith("Bearer ")) {
            return "";
        }
        return authorization.substring("Bearer ".length()).trim();
    }

    private Map<String, String> configuredKeys() {
        Map<String, String> keys = new LinkedHashMap<>();
        keys.put("admin", firstNonBlank(adminKey, legacyAdminKey));
        keys.put("clinical", clinicalKey);
        keys.put("operator", operatorKey);
        keys.put("viewer", viewerKey);
        keys.put("ingest", ingestKey);
        return keys;
    }

    private static boolean isViewer(String role) {
        return "viewer".equals(role) || "operator".equals(role)
                || "clinical".equals(role) || "admin".equals(role);
    }

    private static boolean isOperator(String role) {
        return "operator".equals(role) || "clinical".equals(role) || "admin".equals(role);
    }

    private static boolean isClinical(String role) {
        return "clinical".equals(role) || "admin".equals(role);
    }

    private static boolean isClinicalEvidencePath(String path) {
        return path.startsWith("/api/clinical-checks")
                || path.startsWith("/api/motion-captures")
                || path.startsWith("/api/fmd-triage-cases")
                || path.startsWith("/api/audit-records")
                || path.startsWith("/api/audio-clips")
                || path.startsWith("/api/vision-snapshots")
                || path.startsWith("/api/events/audio")
                || path.startsWith("/api/events/vision");
    }

    private static String firstNonBlank(String primary, String fallback) {
        return primary != null && !primary.isBlank() ? primary : (fallback == null ? "" : fallback);
    }

    private static boolean constantTimeEquals(String expected, String supplied) {
        return MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8), supplied.getBytes(StandardCharsets.UTF_8));
    }
}
