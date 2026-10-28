package com.shumuzengxiao.smartcattle.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;

import java.time.Instant;

/** Compact cattle telemetry used to restore individualized screening baselines. */
@Entity
@Table(name = "health_screening_observation", indexes = {
        @Index(name = "idx_health_screen_observation_target_time", columnList = "target_id,received_at"),
        @Index(name = "idx_health_screen_observation_time", columnList = "received_at")
})
public class HealthScreeningObservation {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "target_id", nullable = false, length = 120)
    private String targetId;

    @Column(name = "received_at", nullable = false)
    private Instant receivedAt;

    @Column(name = "motion_available")
    private Boolean motionAvailable;

    @Column(length = 64)
    private String behavior;

    @Column(name = "behavior_confidence")
    private Double behaviorConfidence;

    private Double activity;

    @Column(name = "surface_temperature")
    private Double surfaceTemperature;

    @Column(name = "lameness_model_deployed")
    private Boolean lamenessModelDeployed;

    @Column(name = "lameness_candidate")
    private Boolean lamenessCandidate;

    @Column(name = "lameness_rejected")
    private Boolean lamenessRejected;

    @Column(name = "lameness_score")
    private Double lamenessScore;

    @Column(name = "microphone_available")
    private Boolean microphoneAvailable;

    @Column(name = "vocalization_candidate")
    private Boolean vocalizationCandidate;

    @Column(name = "audio_model_deployed")
    private Boolean audioModelDeployed;

    @Column(name = "respiratory_candidate")
    private Boolean respiratoryCandidate;

    @Column(name = "abnormal_vocalization_candidate")
    private Boolean abnormalVocalizationCandidate;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getTargetId() { return targetId; }
    public void setTargetId(String targetId) { this.targetId = targetId; }
    public Instant getReceivedAt() { return receivedAt; }
    public void setReceivedAt(Instant receivedAt) { this.receivedAt = receivedAt; }
    public Boolean getMotionAvailable() { return motionAvailable; }
    public void setMotionAvailable(Boolean motionAvailable) { this.motionAvailable = motionAvailable; }
    public String getBehavior() { return behavior; }
    public void setBehavior(String behavior) { this.behavior = behavior; }
    public Double getBehaviorConfidence() { return behaviorConfidence; }
    public void setBehaviorConfidence(Double behaviorConfidence) { this.behaviorConfidence = behaviorConfidence; }
    public Double getActivity() { return activity; }
    public void setActivity(Double activity) { this.activity = activity; }
    public Double getSurfaceTemperature() { return surfaceTemperature; }
    public void setSurfaceTemperature(Double surfaceTemperature) { this.surfaceTemperature = surfaceTemperature; }
    public Boolean getLamenessModelDeployed() { return lamenessModelDeployed; }
    public void setLamenessModelDeployed(Boolean lamenessModelDeployed) { this.lamenessModelDeployed = lamenessModelDeployed; }
    public Boolean getLamenessCandidate() { return lamenessCandidate; }
    public void setLamenessCandidate(Boolean lamenessCandidate) { this.lamenessCandidate = lamenessCandidate; }
    public Boolean getLamenessRejected() { return lamenessRejected; }
    public void setLamenessRejected(Boolean lamenessRejected) { this.lamenessRejected = lamenessRejected; }
    public Double getLamenessScore() { return lamenessScore; }
    public void setLamenessScore(Double lamenessScore) { this.lamenessScore = lamenessScore; }
    public Boolean getMicrophoneAvailable() { return microphoneAvailable; }
    public void setMicrophoneAvailable(Boolean microphoneAvailable) { this.microphoneAvailable = microphoneAvailable; }
    public Boolean getVocalizationCandidate() { return vocalizationCandidate; }
    public void setVocalizationCandidate(Boolean vocalizationCandidate) { this.vocalizationCandidate = vocalizationCandidate; }
    public Boolean getAudioModelDeployed() { return audioModelDeployed; }
    public void setAudioModelDeployed(Boolean audioModelDeployed) { this.audioModelDeployed = audioModelDeployed; }
    public Boolean getRespiratoryCandidate() { return respiratoryCandidate; }
    public void setRespiratoryCandidate(Boolean respiratoryCandidate) { this.respiratoryCandidate = respiratoryCandidate; }
    public Boolean getAbnormalVocalizationCandidate() { return abnormalVocalizationCandidate; }
    public void setAbnormalVocalizationCandidate(Boolean abnormalVocalizationCandidate) { this.abnormalVocalizationCandidate = abnormalVocalizationCandidate; }
}
