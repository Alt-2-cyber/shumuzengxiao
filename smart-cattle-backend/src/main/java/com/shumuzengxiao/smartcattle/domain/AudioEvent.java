package com.shumuzengxiao.smartcattle.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
public class AudioEvent {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String deviceId;
    private String barnId;
    private String eventType;
    private Double score;
    private Integer durationMs;
    private Double snr;
    private String audioClipPath;
    private Instant recordedAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getDeviceId() { return deviceId; }
    public void setDeviceId(String deviceId) { this.deviceId = deviceId; }
    public String getBarnId() { return barnId; }
    public void setBarnId(String barnId) { this.barnId = barnId; }
    public String getEventType() { return eventType; }
    public void setEventType(String eventType) { this.eventType = eventType; }
    public Double getScore() { return score; }
    public void setScore(Double score) { this.score = score; }
    public Integer getDurationMs() { return durationMs; }
    public void setDurationMs(Integer durationMs) { this.durationMs = durationMs; }
    public Double getSnr() { return snr; }
    public void setSnr(Double snr) { this.snr = snr; }
    public String getAudioClipPath() { return audioClipPath; }
    public void setAudioClipPath(String audioClipPath) { this.audioClipPath = audioClipPath; }
    public Instant getRecordedAt() { return recordedAt; }
    public void setRecordedAt(Instant recordedAt) { this.recordedAt = recordedAt; }
}
