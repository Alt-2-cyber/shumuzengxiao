package com.shumuzengxiao.smartcattle.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

import java.time.Instant;

/** An administrative handoff for an FMD screening triage. It does not encode
 * a disease result and cannot be created from a normal sensor reading. */
@Entity
public class FmdTriageCase {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(nullable = false, unique = true)
    private Long healthRiskId;
    @Column(nullable = false, length = 120)
    private String cattleId;
    @Column(nullable = false, length = 80)
    private String barnId;
    @Column(nullable = false, length = 48)
    private String status;
    @Column(nullable = false, length = 120)
    private String openedBy;
    @Column(nullable = false, length = 80)
    private String veterinarian;
    @Column(nullable = false, length = 1200)
    private String evidenceReference;
    private Instant openedAt;
    private Instant closedAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getHealthRiskId() { return healthRiskId; }
    public void setHealthRiskId(Long healthRiskId) { this.healthRiskId = healthRiskId; }
    public String getCattleId() { return cattleId; }
    public void setCattleId(String cattleId) { this.cattleId = cattleId; }
    public String getBarnId() { return barnId; }
    public void setBarnId(String barnId) { this.barnId = barnId; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getOpenedBy() { return openedBy; }
    public void setOpenedBy(String openedBy) { this.openedBy = openedBy; }
    public String getVeterinarian() { return veterinarian; }
    public void setVeterinarian(String veterinarian) { this.veterinarian = veterinarian; }
    public String getEvidenceReference() { return evidenceReference; }
    public void setEvidenceReference(String evidenceReference) { this.evidenceReference = evidenceReference; }
    public Instant getOpenedAt() { return openedAt; }
    public void setOpenedAt(Instant openedAt) { this.openedAt = openedAt; }
    public Instant getClosedAt() { return closedAt; }
    public void setClosedAt(Instant closedAt) { this.closedAt = closedAt; }
}
