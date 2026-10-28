package com.shumuzengxiao.smartcattle.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

import java.time.Instant;

/**
 * A human-performed observation. It is deliberately kept separate from edge
 * telemetry so a device cannot claim that a clinical measurement was verified.
 */
@Entity
public class ClinicalCheck {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 120)
    private String cattleId;

    @Column(nullable = false, length = 32)
    private String checkType;

    private Boolean verified;
    private Boolean alert;
    @Column(name = "measured_value")
    private Double value;

    @Column(length = 80)
    private String examiner;

    @Column(length = 1200)
    private String evidenceReference;

    @Column(length = 1200)
    private String findings;

    @Column(length = 96)
    private String evidenceType;

    @Column(nullable = false)
    private Instant recordedAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getCattleId() { return cattleId; }
    public void setCattleId(String cattleId) { this.cattleId = cattleId; }
    public String getCheckType() { return checkType; }
    public void setCheckType(String checkType) { this.checkType = checkType; }
    public Boolean getVerified() { return verified; }
    public void setVerified(Boolean verified) { this.verified = verified; }
    public Boolean getAlert() { return alert; }
    public void setAlert(Boolean alert) { this.alert = alert; }
    public Double getValue() { return value; }
    public void setValue(Double value) { this.value = value; }
    public String getExaminer() { return examiner; }
    public void setExaminer(String examiner) { this.examiner = examiner; }
    public String getEvidenceReference() { return evidenceReference; }
    public void setEvidenceReference(String evidenceReference) { this.evidenceReference = evidenceReference; }
    public String getFindings() { return findings; }
    public void setFindings(String findings) { this.findings = findings; }
    public String getEvidenceType() { return evidenceType; }
    public void setEvidenceType(String evidenceType) { this.evidenceType = evidenceType; }
    public Instant getRecordedAt() { return recordedAt; }
    public void setRecordedAt(Instant recordedAt) { this.recordedAt = recordedAt; }
}
