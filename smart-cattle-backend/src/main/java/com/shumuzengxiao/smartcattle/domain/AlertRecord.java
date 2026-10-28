package com.shumuzengxiao.smartcattle.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
public class AlertRecord {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String barnId;
    private String title;
    @Enumerated(EnumType.STRING)
    private Severity severity;
    @Column(length = 800)
    private String message;
    private String source;
    private String status;
    private Instant createdAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getBarnId() { return barnId; }
    public void setBarnId(String barnId) { this.barnId = barnId; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public Severity getSeverity() { return severity; }
    public void setSeverity(Severity severity) { this.severity = severity; }
    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
