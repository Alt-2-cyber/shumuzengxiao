package com.shumuzengxiao.smartcattle.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Lob;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import java.time.Instant;

/** Approval evidence for a disease-screening model. A record describes a
 * screening release only; it cannot convert a candidate into a diagnosis. */
@Entity
@Table(uniqueConstraints = @UniqueConstraint(name = "uk_model_release_family_version", columnNames = {"modelFamily", "modelVersion"}))
public class ModelRelease {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(nullable = false, length = 32)
    private String modelFamily;
    @Column(nullable = false, length = 120)
    private String modelVersion;
    @Column(nullable = false, length = 24)
    private String approvalState;
    @Column(nullable = false, length = 64)
    private String datasetManifestSha256;
    @Column(nullable = false, length = 64)
    private String modelCardSha256;
    @Column(nullable = false, length = 64)
    private String firmwareSha256;
    @Column(length = 64)
    private String sourceLineageSha256;
    @Lob
    @Column(columnDefinition = "LONGTEXT")
    private String sourceLineageJson;
    @Column(nullable = false, length = 1200)
    private String evidenceReference;
    @Column(nullable = false, length = 120)
    private String approvedBy;
    private Instant approvedAt;
    @Column(length = 120)
    private String revokedBy;
    private Instant revokedAt;
    @Column(length = 1200)
    private String revocationEvidenceReference;
    @Column(length = 1200)
    private String revocationNotes;
    @Lob
    @Column(columnDefinition = "LONGTEXT")
    private String validationSummary;
    @Column(length = 1200)
    private String notes;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getModelFamily() { return modelFamily; }
    public void setModelFamily(String modelFamily) { this.modelFamily = modelFamily; }
    public String getModelVersion() { return modelVersion; }
    public void setModelVersion(String modelVersion) { this.modelVersion = modelVersion; }
    public String getApprovalState() { return approvalState; }
    public void setApprovalState(String approvalState) { this.approvalState = approvalState; }
    public String getDatasetManifestSha256() { return datasetManifestSha256; }
    public void setDatasetManifestSha256(String datasetManifestSha256) { this.datasetManifestSha256 = datasetManifestSha256; }
    public String getModelCardSha256() { return modelCardSha256; }
    public void setModelCardSha256(String modelCardSha256) { this.modelCardSha256 = modelCardSha256; }
    public String getFirmwareSha256() { return firmwareSha256; }
    public void setFirmwareSha256(String firmwareSha256) { this.firmwareSha256 = firmwareSha256; }
    public String getSourceLineageSha256() { return sourceLineageSha256; }
    public void setSourceLineageSha256(String sourceLineageSha256) { this.sourceLineageSha256 = sourceLineageSha256; }
    public String getSourceLineageJson() { return sourceLineageJson; }
    public void setSourceLineageJson(String sourceLineageJson) { this.sourceLineageJson = sourceLineageJson; }
    public String getEvidenceReference() { return evidenceReference; }
    public void setEvidenceReference(String evidenceReference) { this.evidenceReference = evidenceReference; }
    public String getApprovedBy() { return approvedBy; }
    public void setApprovedBy(String approvedBy) { this.approvedBy = approvedBy; }
    public Instant getApprovedAt() { return approvedAt; }
    public void setApprovedAt(Instant approvedAt) { this.approvedAt = approvedAt; }
    public String getRevokedBy() { return revokedBy; }
    public void setRevokedBy(String revokedBy) { this.revokedBy = revokedBy; }
    public Instant getRevokedAt() { return revokedAt; }
    public void setRevokedAt(Instant revokedAt) { this.revokedAt = revokedAt; }
    public String getRevocationEvidenceReference() { return revocationEvidenceReference; }
    public void setRevocationEvidenceReference(String revocationEvidenceReference) { this.revocationEvidenceReference = revocationEvidenceReference; }
    public String getRevocationNotes() { return revocationNotes; }
    public void setRevocationNotes(String revocationNotes) { this.revocationNotes = revocationNotes; }
    public String getValidationSummary() { return validationSummary; }
    public void setValidationSummary(String validationSummary) { this.validationSummary = validationSummary; }
    public String getNotes() { return notes; }
    public void setNotes(String notes) { this.notes = notes; }
}
