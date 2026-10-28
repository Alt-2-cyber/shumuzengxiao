package com.shumuzengxiao.smartcattle.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

import java.time.Instant;

/** Metadata for a deliberately initiated three-position IMU recording. */
@Entity
public class MotionCaptureSession {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 120)
    private String sessionId;
    @Column(nullable = false, length = 120)
    private String cattleId;
    @Column(nullable = false, length = 80)
    private String deviceId;
    @Column(nullable = false, length = 80)
    private String barnId;
    private Integer durationMs;
    private Integer sampleRateHz;
    private Long receivedSamples;
    private Long expectedSamples;
    private Long attemptedSamples;
    private Long droppedBackpressureSamples;
    private Long droppedSensorSamples;
    private Double completenessRatio;
    @Column(length = 32)
    private String qualityStatus;
    @Column(length = 32)
    private String status;
    @Column(length = 255)
    private String rawDataPath;
    @Column(length = 128)
    private String rawDataSha256;
    @Column(length = 1200)
    private String videoReference;
    @Column(length = 1200)
    private String notes;
    @Column(length = 80)
    private String operatorName;
    private Instant requestedAt;
    private Instant startedAt;
    private Instant completedAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getSessionId() { return sessionId; }
    public void setSessionId(String sessionId) { this.sessionId = sessionId; }
    public String getCattleId() { return cattleId; }
    public void setCattleId(String cattleId) { this.cattleId = cattleId; }
    public String getDeviceId() { return deviceId; }
    public void setDeviceId(String deviceId) { this.deviceId = deviceId; }
    public String getBarnId() { return barnId; }
    public void setBarnId(String barnId) { this.barnId = barnId; }
    public Integer getDurationMs() { return durationMs; }
    public void setDurationMs(Integer durationMs) { this.durationMs = durationMs; }
    public Integer getSampleRateHz() { return sampleRateHz; }
    public void setSampleRateHz(Integer sampleRateHz) { this.sampleRateHz = sampleRateHz; }
    public Long getReceivedSamples() { return receivedSamples; }
    public void setReceivedSamples(Long receivedSamples) { this.receivedSamples = receivedSamples; }
    public Long getExpectedSamples() { return expectedSamples; }
    public void setExpectedSamples(Long expectedSamples) { this.expectedSamples = expectedSamples; }
    public Long getAttemptedSamples() { return attemptedSamples; }
    public void setAttemptedSamples(Long attemptedSamples) { this.attemptedSamples = attemptedSamples; }
    public Long getDroppedBackpressureSamples() { return droppedBackpressureSamples; }
    public void setDroppedBackpressureSamples(Long droppedBackpressureSamples) { this.droppedBackpressureSamples = droppedBackpressureSamples; }
    public Long getDroppedSensorSamples() { return droppedSensorSamples; }
    public void setDroppedSensorSamples(Long droppedSensorSamples) { this.droppedSensorSamples = droppedSensorSamples; }
    public Double getCompletenessRatio() { return completenessRatio; }
    public void setCompletenessRatio(Double completenessRatio) { this.completenessRatio = completenessRatio; }
    public String getQualityStatus() { return qualityStatus; }
    public void setQualityStatus(String qualityStatus) { this.qualityStatus = qualityStatus; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getRawDataPath() { return rawDataPath; }
    public void setRawDataPath(String rawDataPath) { this.rawDataPath = rawDataPath; }
    public String getRawDataSha256() { return rawDataSha256; }
    public void setRawDataSha256(String rawDataSha256) { this.rawDataSha256 = rawDataSha256; }
    public String getVideoReference() { return videoReference; }
    public void setVideoReference(String videoReference) { this.videoReference = videoReference; }
    public String getNotes() { return notes; }
    public void setNotes(String notes) { this.notes = notes; }
    public String getOperatorName() { return operatorName; }
    public void setOperatorName(String operatorName) { this.operatorName = operatorName; }
    public Instant getRequestedAt() { return requestedAt; }
    public void setRequestedAt(Instant requestedAt) { this.requestedAt = requestedAt; }
    public Instant getStartedAt() { return startedAt; }
    public void setStartedAt(Instant startedAt) { this.startedAt = startedAt; }
    public Instant getCompletedAt() { return completedAt; }
    public void setCompletedAt(Instant completedAt) { this.completedAt = completedAt; }
}
