package com.shumuzengxiao.smartcattle.service;

import com.shumuzengxiao.smartcattle.domain.FmdTriageCase;
import com.shumuzengxiao.smartcattle.domain.HealthRisk;
import com.shumuzengxiao.smartcattle.dto.FmdTriageActionRequest;
import com.shumuzengxiao.smartcattle.dto.FmdTriageOpenRequest;
import com.shumuzengxiao.smartcattle.repository.FmdTriageCaseRepository;
import com.shumuzengxiao.smartcattle.repository.HealthRiskRepository;
import jakarta.transaction.Transactional;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Handles human handoff of an FMD screening triage. It deliberately never
 * stores a positive/negative result and never infers closure from telemetry. */
@Service
public class FmdTriageService {
    private final HealthRiskRepository healthRisks;
    private final FmdTriageCaseRepository cases;
    private final AuditTrailService audit;

    public FmdTriageService(
            HealthRiskRepository healthRisks,
            FmdTriageCaseRepository cases,
            AuditTrailService audit
    ) {
        this.healthRisks = healthRisks;
        this.cases = cases;
        this.audit = audit;
    }

    @Transactional
    public FmdTriageCase open(FmdTriageOpenRequest request) {
        HealthRisk risk = risk(request.healthRiskId());
        FmdTriageCase current = cases.findByHealthRiskId(risk.getId()).orElse(null);
        if (current != null) {
            return current;
        }
        FmdTriageCase triage = new FmdTriageCase();
        triage.setHealthRiskId(risk.getId());
        triage.setCattleId(required(risk.getTargetId(), "risk has no cattle ID", 120));
        triage.setBarnId(required(risk.getBarnId(), "risk has no barn ID", 80));
        triage.setStatus("open_veterinary_handoff");
        triage.setOpenedBy(required(request.actor(), "actor", 120));
        triage.setVeterinarian(required(request.veterinarian(), "veterinarian", 80));
        triage.setEvidenceReference(required(request.evidenceReference(), "evidence reference", 1200));
        triage.setOpenedAt(Instant.now());
        triage = cases.save(triage);
        audit.record("fmd_triage_opened", request.actor(), "fmd_triage_case", String.valueOf(triage.getId()), details(
                risk, triage, request.veterinarian(), request.evidenceReference(), null, request.note(), false));
        return triage;
    }

    @Transactional
    public FmdTriageCase action(Long caseId, FmdTriageActionRequest request) {
        FmdTriageCase triage = cases.findById(caseId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "FMD triage case not found"));
        if (triage.getClosedAt() != null) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "FMD triage case is already closed by authority");
        }
        String action = request.action();
        triage.setVeterinarian(required(request.veterinarian(), "veterinarian", 80));
        triage.setEvidenceReference(required(request.evidenceReference(), "evidence reference", 1200));
        if ("closed_by_authority".equals(action)) {
            triage.setStatus("closed_by_authority");
            triage.setClosedAt(Instant.now());
            HealthRisk risk = healthRisks.findById(triage.getHealthRiskId())
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "health risk not found"));
            risk.setStatus("closed_by_authority");
            risk.setRecordedAt(Instant.now());
            healthRisks.save(risk);
        } else {
            triage.setStatus(action);
        }
        triage = cases.save(triage);
        audit.record("fmd_triage_" + action, request.actor(), "fmd_triage_case", String.valueOf(triage.getId()), details(
                null, triage, request.veterinarian(), request.evidenceReference(), request.authorityReference(),
                request.note(), Boolean.TRUE.equals(request.closureAuthorized())));
        return triage;
    }

    public List<FmdTriageCase> recent(String cattleId) {
        return cattleId == null || cattleId.isBlank()
                ? cases.findTop100ByOrderByOpenedAtDesc()
                : cases.findTop100ByCattleIdOrderByOpenedAtDesc(cattleId.trim());
    }

    private HealthRisk risk(Long riskId) {
        HealthRisk risk = healthRisks.findById(riskId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "health risk not found"));
        if (!"fmd_suspect_triage".equals(risk.getRiskType()) || !"open".equals(risk.getStatus())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "only an open FMD screening triage can be handed off");
        }
        return risk;
    }

    private static String required(String value, String name, int maximum) {
        String normalized = blank(value);
        if (normalized == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, name + " is required");
        }
        return normalized.length() <= maximum ? normalized : normalized.substring(0, maximum);
    }

    private static String blank(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private static Map<String, Object> details(
            HealthRisk risk,
            FmdTriageCase triage,
            String veterinarian,
            String evidenceReference,
            String authorityReference,
            String note,
            boolean closureAuthorized
    ) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("healthRiskId", risk == null ? triage.getHealthRiskId() : risk.getId());
        details.put("cattleId", triage.getCattleId());
        details.put("barnId", triage.getBarnId());
        details.put("veterinarian", blank(veterinarian));
        details.put("evidenceReference", blank(evidenceReference));
        details.put("authorityReference", blank(authorityReference));
        details.put("note", blank(note));
        details.put("closureAuthorized", closureAuthorized);
        return details;
    }
}
