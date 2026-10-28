package com.shumuzengxiao.smartcattle.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

import java.time.Instant;

/**
 * A signed clinical label bound to one immutable three-position IMU session.
 * It is deliberately separate from general clinical checks so a release can
 * prove exactly which raw archive received the gait and hoof assessment.
 */
@Entity
public class MotionCaptureClinicalReview {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 120)
    private String sessionId;
    @Column(nullable = false, length = 120)
    private String cattleId;
    private Integer lamenessScore;
    @Column(length = 80)
    private String gaitReviewer;
    @Column(length = 80)
    private String hoofExaminer;
    @Column(length = 80)
    private String veterinarian;
    @Column(length = 1200)
    private String hoofFinding;
    @Column(length = 1200)
    private String clinicalEvidenceReference;
    private Instant clinicallyVerifiedAt;
    private Instant reviewedAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getSessionId() { return sessionId; }
    public void setSessionId(String sessionId) { this.sessionId = sessionId; }
    public String getCattleId() { return cattleId; }
    public void setCattleId(String cattleId) { this.cattleId = cattleId; }
    public Integer getLamenessScore() { return lamenessScore; }
    public void setLamenessScore(Integer lamenessScore) { this.lamenessScore = lamenessScore; }
    public String getGaitReviewer() { return gaitReviewer; }
    public void setGaitReviewer(String gaitReviewer) { this.gaitReviewer = gaitReviewer; }
    public String getHoofExaminer() { return hoofExaminer; }
    public void setHoofExaminer(String hoofExaminer) { this.hoofExaminer = hoofExaminer; }
    public String getVeterinarian() { return veterinarian; }
    public void setVeterinarian(String veterinarian) { this.veterinarian = veterinarian; }
    public String getHoofFinding() { return hoofFinding; }
    public void setHoofFinding(String hoofFinding) { this.hoofFinding = hoofFinding; }
    public String getClinicalEvidenceReference() { return clinicalEvidenceReference; }
    public void setClinicalEvidenceReference(String clinicalEvidenceReference) { this.clinicalEvidenceReference = clinicalEvidenceReference; }
    public Instant getClinicallyVerifiedAt() { return clinicallyVerifiedAt; }
    public void setClinicallyVerifiedAt(Instant clinicallyVerifiedAt) { this.clinicallyVerifiedAt = clinicallyVerifiedAt; }
    public Instant getReviewedAt() { return reviewedAt; }
    public void setReviewedAt(Instant reviewedAt) { this.reviewedAt = reviewedAt; }
}
