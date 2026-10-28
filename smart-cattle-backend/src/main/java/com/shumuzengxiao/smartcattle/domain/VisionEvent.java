package com.shumuzengxiao.smartcattle.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
public class VisionEvent {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String cameraId;
    private String barnId;
    private String eventType;
    @Enumerated(EnumType.STRING)
    private Severity severity;
    private Double score;
    private String targetId;
    @Column(length = 190, unique = true)
    private String sourceKey;
    /** Path supplied by the edge device; it is not a server-side archive. */
    @Column(length = 255)
    private String sourceSnapshotPath;
    /** Server-side immutable archive path once an image has been uploaded. */
    private String snapshotPath;
    @Column(length = 64)
    private String snapshotSha256;
    private Boolean snapshotAvailable;
    @Column(length = 64)
    private String snapshotContentType;
    private Long snapshotBytes;
    @Column(length = 1000)
    private String evidence;
    @Column(length = 120)
    private String modelName;
    @Column(length = 120)
    private String modelVersion;
    @Column(length = 40)
    private String modelStatus;
    private Boolean modelApprovedByServer;
    private Boolean screeningEligible;
    private Instant recordedAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getCameraId() { return cameraId; }
    public void setCameraId(String cameraId) { this.cameraId = cameraId; }
    public String getBarnId() { return barnId; }
    public void setBarnId(String barnId) { this.barnId = barnId; }
    public String getEventType() { return eventType; }
    public void setEventType(String eventType) { this.eventType = eventType; }
    public Severity getSeverity() { return severity; }
    public void setSeverity(Severity severity) { this.severity = severity; }
    public Double getScore() { return score; }
    public void setScore(Double score) { this.score = score; }
    public String getTargetId() { return targetId; }
    public void setTargetId(String targetId) { this.targetId = targetId; }
    public String getSourceKey() { return sourceKey; }
    public void setSourceKey(String sourceKey) { this.sourceKey = sourceKey; }
    public String getSourceSnapshotPath() { return sourceSnapshotPath; }
    public void setSourceSnapshotPath(String sourceSnapshotPath) { this.sourceSnapshotPath = sourceSnapshotPath; }
    public String getSnapshotPath() { return snapshotPath; }
    public void setSnapshotPath(String snapshotPath) { this.snapshotPath = snapshotPath; }
    public String getSnapshotSha256() { return snapshotSha256; }
    public void setSnapshotSha256(String snapshotSha256) { this.snapshotSha256 = snapshotSha256; }
    public Boolean getSnapshotAvailable() { return snapshotAvailable; }
    public void setSnapshotAvailable(Boolean snapshotAvailable) { this.snapshotAvailable = snapshotAvailable; }
    public String getSnapshotContentType() { return snapshotContentType; }
    public void setSnapshotContentType(String snapshotContentType) { this.snapshotContentType = snapshotContentType; }
    public Long getSnapshotBytes() { return snapshotBytes; }
    public void setSnapshotBytes(Long snapshotBytes) { this.snapshotBytes = snapshotBytes; }
    public String getEvidence() { return evidence; }
    public void setEvidence(String evidence) { this.evidence = evidence; }
    public String getModelName() { return modelName; }
    public void setModelName(String modelName) { this.modelName = modelName; }
    public String getModelVersion() { return modelVersion; }
    public void setModelVersion(String modelVersion) { this.modelVersion = modelVersion; }
    public String getModelStatus() { return modelStatus; }
    public void setModelStatus(String modelStatus) { this.modelStatus = modelStatus; }
    public Boolean getModelApprovedByServer() { return modelApprovedByServer; }
    public void setModelApprovedByServer(Boolean modelApprovedByServer) { this.modelApprovedByServer = modelApprovedByServer; }
    public Boolean getScreeningEligible() { return screeningEligible; }
    public void setScreeningEligible(Boolean screeningEligible) { this.screeningEligible = screeningEligible; }
    public Instant getRecordedAt() { return recordedAt; }
    public void setRecordedAt(Instant recordedAt) { this.recordedAt = recordedAt; }
}
