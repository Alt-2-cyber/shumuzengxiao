package com.shumuzengxiao.smartcattle.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

import java.time.Instant;

/** Clinical label bound to one archived visual event. */
@Entity
public class VisionEventReview {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private Long visionEventId;

    @Column(length = 20)
    private String status;

    @Column(length = 96)
    private String label;

    @Column(length = 80)
    private String reviewer;

    @Column(length = 120)
    private String animalId;

    @Column(length = 80)
    private String veterinarian;

    @Column(length = 1200)
    private String clinicalEvidenceReference;

    @Column(length = 1200)
    private String note;

    private Instant clinicallyVerifiedAt;
    private Instant reviewedAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getVisionEventId() { return visionEventId; }
    public void setVisionEventId(Long visionEventId) { this.visionEventId = visionEventId; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getLabel() { return label; }
    public void setLabel(String label) { this.label = label; }
    public String getReviewer() { return reviewer; }
    public void setReviewer(String reviewer) { this.reviewer = reviewer; }
    public String getAnimalId() { return animalId; }
    public void setAnimalId(String animalId) { this.animalId = animalId; }
    public String getVeterinarian() { return veterinarian; }
    public void setVeterinarian(String veterinarian) { this.veterinarian = veterinarian; }
    public String getClinicalEvidenceReference() { return clinicalEvidenceReference; }
    public void setClinicalEvidenceReference(String clinicalEvidenceReference) { this.clinicalEvidenceReference = clinicalEvidenceReference; }
    public String getNote() { return note; }
    public void setNote(String note) { this.note = note; }
    public Instant getClinicallyVerifiedAt() { return clinicallyVerifiedAt; }
    public void setClinicallyVerifiedAt(Instant clinicallyVerifiedAt) { this.clinicallyVerifiedAt = clinicallyVerifiedAt; }
    public Instant getReviewedAt() { return reviewedAt; }
    public void setReviewedAt(Instant reviewedAt) { this.reviewedAt = reviewedAt; }
}
