package com.shumuzengxiao.smartcattle.service;

import com.shumuzengxiao.smartcattle.domain.ClinicalCheck;
import com.shumuzengxiao.smartcattle.dto.ClinicalCheckRequest;
import com.shumuzengxiao.smartcattle.repository.ClinicalCheckRepository;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class ClinicalCheckService {
    private final ClinicalCheckRepository checks;
    private final HealthScreeningService healthScreeningService;
    private final AuditTrailService audit;

    public ClinicalCheckService(
            ClinicalCheckRepository checks,
            HealthScreeningService healthScreeningService,
            AuditTrailService audit
    ) {
        this.checks = checks;
        this.healthScreeningService = healthScreeningService;
        this.audit = audit;
    }

    public ClinicalCheck record(ClinicalCheckRequest request) {
        ClinicalCheck check = new ClinicalCheck();
        check.setCattleId(request.cattleId().trim());
        check.setCheckType(request.checkType());
        check.setVerified(Boolean.TRUE.equals(request.verified()));
        check.setAlert(Boolean.TRUE.equals(request.alert()));
        check.setValue(request.value());
        check.setExaminer(request.examiner().trim());
        check.setEvidenceReference(blankToNull(request.evidenceReference()));
        check.setFindings(blankToNull(request.findings()));
        check.setEvidenceType(blankToNull(request.evidenceType()));
        check.setRecordedAt(Instant.now());
        ClinicalCheck saved = checks.save(check);

        healthScreeningService.recordClinicalCheck(
                saved.getCattleId(),
                saved.getCheckType(),
                Boolean.TRUE.equals(saved.getVerified()),
                Boolean.TRUE.equals(saved.getAlert()),
                saved.getValue(),
                saved.getEvidenceType(),
                saved.getRecordedAt());
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("checkType", saved.getCheckType());
        details.put("verified", saved.getVerified());
        details.put("alert", saved.getAlert());
        details.put("value", saved.getValue());
        details.put("evidenceType", saved.getEvidenceType());
        details.put("evidenceReference", saved.getEvidenceReference());
        audit.record("clinical_check_recorded", saved.getExaminer(), "cattle", saved.getCattleId(), details);
        return saved;
    }

    public List<ClinicalCheck> recent(String cattleId) {
        if (cattleId == null || cattleId.isBlank()) {
            return checks.findTop500ByOrderByRecordedAtDesc();
        }
        return checks.findTop100ByCattleIdOrderByRecordedAtDesc(cattleId.trim());
    }

    private static String blankToNull(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }
}
