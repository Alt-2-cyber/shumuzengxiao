package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.shumuzengxiao.smartcattle.domain.HealthRisk;
import com.shumuzengxiao.smartcattle.domain.Severity;
import com.shumuzengxiao.smartcattle.repository.HealthRiskRepository;
import jakarta.transaction.Transactional;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Maintains one open risk record per cattle/risk pair instead of flooding the
 * database with repeated telemetry windows. A record is evidence for review,
 * never a diagnosis or treatment decision. */
@Service
public class HealthRiskLedgerService {
    private static final String OPEN = "open";
    private static final String RESOLVED = "resolved_by_screening";
    private final HealthRiskRepository healthRisks;
    private final ObjectMapper objectMapper;

    public HealthRiskLedgerService(HealthRiskRepository healthRisks, ObjectMapper objectMapper) {
        this.healthRisks = healthRisks;
        this.objectMapper = objectMapper;
    }

    @Transactional
    @SuppressWarnings("unchecked")
    public void synchronize(String barnId, String targetId, Map<String, Object> screen, Instant observedAt) {
        if (targetId == null || targetId.isBlank() || screen == null ||
                !"SCREENING".equals(screen.get("mode"))) {
            return;
        }
        Object rawRisks = screen.get("risks");
        if (!(rawRisks instanceof List<?> list)) {
            return;
        }

        Set<String> activeTypes = new HashSet<>();
        for (Object item : list) {
            if (!(item instanceof Map<?, ?> genericRisk)) {
                continue;
            }
            Map<String, Object> risk = (Map<String, Object>) genericRisk;
            String type = text(risk.get("type"));
            if (type == null) {
                continue;
            }
            activeTypes.add(type);
            String normalizedBarn = barnId == null || barnId.isBlank() ? "barn_01" : barnId.trim();
            HealthRisk record = healthRisks.findFirstByBarnIdAndTargetIdAndRiskTypeAndStatusOrderByRecordedAtDesc(
                    normalizedBarn, targetId, type, OPEN).orElseGet(HealthRisk::new);
            record.setBarnId(normalizedBarn);
            record.setTargetId(targetId.trim());
            record.setRiskType(type);
            record.setRiskLevel(severity(risk.get("level")));
            record.setScore(number(risk.get("score")));
            record.setEvidence(json(risk.get("evidence"), 1200));
            record.setSuggestion(truncate(text(risk.get("suggestion")), 500));
            record.setStatus(OPEN);
            record.setRecordedAt(observedAt);
            healthRisks.save(record);
        }

        String normalizedBarn = barnId == null || barnId.isBlank() ? "barn_01" : barnId.trim();
        for (HealthRisk open : healthRisks.findByBarnIdAndTargetIdAndStatusOrderByRecordedAtDesc(
                normalizedBarn, targetId.trim(), OPEN)) {
            // A notifiable-disease triage must be closed by an authorized
            // clinical/regulatory workflow, never because a later sensor
            // window looks normal.
            if ("fmd_suspect_triage".equals(open.getRiskType())) {
                continue;
            }
            if (!activeTypes.contains(open.getRiskType())) {
                open.setStatus(RESOLVED);
                open.setRecordedAt(observedAt);
                healthRisks.save(open);
            }
        }
    }

    private static Severity severity(Object value) {
        try {
            return Severity.valueOf(String.valueOf(value));
        } catch (IllegalArgumentException exception) {
            return Severity.OBSERVE;
        }
    }

    private static Double number(Object value) {
        if (!(value instanceof Number number)) {
            return null;
        }
        double parsed = number.doubleValue();
        return Double.isFinite(parsed) ? Math.max(0.0, Math.min(1.0, parsed)) : null;
    }

    private String json(Object value, int maximumLength) {
        if (value == null) {
            return null;
        }
        try {
            return truncate(objectMapper.writeValueAsString(value), maximumLength);
        } catch (JsonProcessingException exception) {
            return truncate(String.valueOf(value), maximumLength);
        }
    }

    private static String text(Object value) {
        if (value == null) {
            return null;
        }
        String text = String.valueOf(value).trim();
        return text.isEmpty() ? null : text;
    }

    private static String truncate(String value, int maximumLength) {
        if (value == null || value.length() <= maximumLength) {
            return value;
        }
        return value.substring(0, maximumLength);
    }
}
