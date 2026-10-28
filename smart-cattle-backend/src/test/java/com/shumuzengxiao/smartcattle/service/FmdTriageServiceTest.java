package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.shumuzengxiao.smartcattle.domain.FmdTriageCase;
import com.shumuzengxiao.smartcattle.domain.HealthRisk;
import com.shumuzengxiao.smartcattle.domain.Severity;
import com.shumuzengxiao.smartcattle.dto.FmdTriageActionRequest;
import com.shumuzengxiao.smartcattle.dto.FmdTriageOpenRequest;
import com.shumuzengxiao.smartcattle.repository.AuditRecordRepository;
import com.shumuzengxiao.smartcattle.repository.FmdTriageCaseRepository;
import com.shumuzengxiao.smartcattle.repository.HealthRiskRepository;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class FmdTriageServiceTest {
    private final HealthRiskRepository healthRisks = mock(HealthRiskRepository.class);
    private final FmdTriageCaseRepository cases = mock(FmdTriageCaseRepository.class);
    private final AuditRecordRepository auditRecords = mock(AuditRecordRepository.class);
    private final FmdTriageService service = new FmdTriageService(
            healthRisks, cases, new AuditTrailService(auditRecords, new ObjectMapper()));

    @Test
    void onlyAnOpenFmdScreenCanBeHandedOff() {
        HealthRisk other = risk("brd_suspect", "open");
        when(healthRisks.findById(1L)).thenReturn(Optional.of(other));

        assertThatThrownBy(() -> service.open(openRequest()))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("only an open FMD");
    }

    @Test
    void closureRequiresExplicitAuthorityAuthorization() {
        FmdTriageActionRequest invalid = new FmdTriageActionRequest(
                "closed_by_authority", "operator", "vet", "", "lab-ref", "note", false);

        assertThat(invalid.hasAuthorizedClosure()).isFalse();
    }

    @Test
    void authorizedClosureClosesTheOriginalRiskOnlyThroughTheAction() {
        HealthRisk risk = risk("fmd_suspect_triage", "open");
        risk.setId(7L);
        FmdTriageCase triage = new FmdTriageCase();
        triage.setId(3L);
        triage.setHealthRiskId(7L);
        triage.setCattleId("cow_001");
        triage.setBarnId("barn_01");
        triage.setStatus("authority_notified");
        when(cases.findById(3L)).thenReturn(Optional.of(triage));
        when(healthRisks.findById(7L)).thenReturn(Optional.of(risk));
        when(cases.save(any(FmdTriageCase.class))).thenAnswer(call -> call.getArgument(0));
        when(healthRisks.save(any(HealthRisk.class))).thenAnswer(call -> call.getArgument(0));
        when(auditRecords.findTop1ByOrderByIdDesc()).thenReturn(Optional.empty());
        when(auditRecords.save(any())).thenAnswer(call -> call.getArgument(0));

        FmdTriageCase saved = service.action(3L, new FmdTriageActionRequest(
                "closed_by_authority", "operator", "vet", "authority-ref", "lab-ref", "note", true));

        assertThat(saved.getStatus()).isEqualTo("closed_by_authority");
        assertThat(risk.getStatus()).isEqualTo("closed_by_authority");
    }

    private static FmdTriageOpenRequest openRequest() {
        return new FmdTriageOpenRequest(1L, "operator", "vet", "evidence", "note");
    }

    private static HealthRisk risk(String type, String status) {
        HealthRisk risk = new HealthRisk();
        risk.setRiskType(type);
        risk.setStatus(status);
        risk.setTargetId("cow_001");
        risk.setBarnId("barn_01");
        risk.setRiskLevel(Severity.WARNING);
        return risk;
    }
}
