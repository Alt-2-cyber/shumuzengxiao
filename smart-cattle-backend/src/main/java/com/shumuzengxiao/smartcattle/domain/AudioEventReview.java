package com.shumuzengxiao.smartcattle.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Lob;

import java.time.Instant;

@Entity
public class AudioEventReview {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private Long audioEventId;

    @Column(length = 20)
    private String status;
    @Column(length = 80)
    private String label;
    @Column(length = 80)
    private String reviewer;

    @Column(length = 120)
    private String animalId;
    @Column(length = 120)
    private String recordingSessionId;
    @Column(length = 80)
    private String veterinarian;
    @Column(length = 1200)
    private String clinicalEvidenceReference;
    private Instant clinicallyVerifiedAt;

    @Lob
    @Column(columnDefinition = "LONGTEXT")
    private String note;

    private Instant reviewedAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getAudioEventId() { return audioEventId; }
    public void setAudioEventId(Long audioEventId) { this.audioEventId = audioEventId; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getLabel() { return label; }
    public void setLabel(String label) { this.label = label; }
    public String getReviewer() { return reviewer; }
    public void setReviewer(String reviewer) { this.reviewer = reviewer; }
    public String getAnimalId() { return animalId; }
    public void setAnimalId(String animalId) { this.animalId = animalId; }
    public String getRecordingSessionId() { return recordingSessionId; }
    public void setRecordingSessionId(String recordingSessionId) { this.recordingSessionId = recordingSessionId; }
    public String getVeterinarian() { return veterinarian; }
    public void setVeterinarian(String veterinarian) { this.veterinarian = veterinarian; }
    public String getClinicalEvidenceReference() { return clinicalEvidenceReference; }
    public void setClinicalEvidenceReference(String clinicalEvidenceReference) { this.clinicalEvidenceReference = clinicalEvidenceReference; }
    public Instant getClinicallyVerifiedAt() { return clinicallyVerifiedAt; }
    public void setClinicallyVerifiedAt(Instant clinicallyVerifiedAt) { this.clinicallyVerifiedAt = clinicallyVerifiedAt; }
    public String getNote() { return note; }
    public void setNote(String note) { this.note = note; }
    public Instant getReviewedAt() { return reviewedAt; }
    public void setReviewedAt(Instant reviewedAt) { this.reviewedAt = reviewedAt; }
}
