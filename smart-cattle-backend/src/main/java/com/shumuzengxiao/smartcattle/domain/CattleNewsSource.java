package com.shumuzengxiao.smartcattle.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
public class CattleNewsSource {
    @Id @Column(length = 32) private String id;
    @Column(nullable = false, length = 120) private String name;
    @Column(nullable = false, length = 600) private String url;
    @Column(nullable = false, length = 20) private String status;
    private Instant lastAttemptAt;
    private Instant lastSuccessAt;
    private int articleCount;

    protected CattleNewsSource() {}
    public CattleNewsSource(String id, String name, String url) {
        this.id = id; this.name = name; this.url = url; this.status = "pending";
    }
    public void update(boolean success, int count) {
        lastAttemptAt = Instant.now();
        status = success ? "ok" : "unavailable";
        if (success) { lastSuccessAt = lastAttemptAt; articleCount = count; }
    }
    public String getId() { return id; }
    public String getName() { return name; }
    public String getUrl() { return url; }
    public String getStatus() { return status; }
    public Instant getLastAttemptAt() { return lastAttemptAt; }
    public Instant getLastSuccessAt() { return lastSuccessAt; }
    public int getArticleCount() { return articleCount; }
}
