package com.shumuzengxiao.smartcattle.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
public class CattleArticle {
    @Id @Column(length = 64) private String id;
    @Column(nullable = false, length = 16) private String kind;
    @Column(nullable = false, length = 24) private String category;
    @Column(nullable = false, length = 240) private String title;
    @Column(nullable = false, length = 400) private String summary;
    @Column(nullable = false, columnDefinition = "LONGTEXT") private String content;
    @Column(nullable = false, length = 120) private String sourceName;
    @Column(nullable = false, length = 600) private String sourceUrl;
    @Column(nullable = false) private Instant publishedAt;
    @Column(nullable = false) private Instant collectedAt;

    protected CattleArticle() {}
    public CattleArticle(String id, String kind, String category, String title, String summary, String content,
                         String sourceName, String sourceUrl, Instant publishedAt) {
        this.id = id; this.kind = kind; this.category = category; this.title = title;
        this.summary = summary; this.content = content; this.sourceName = sourceName;
        this.sourceUrl = sourceUrl; this.publishedAt = publishedAt; this.collectedAt = Instant.now();
    }
    public String getId() { return id; }
    public String getKind() { return kind; }
    public String getCategory() { return category; }
    public String getTitle() { return title; }
    public String getSummary() { return summary; }
    public String getContent() { return content; }
    public String getSourceName() { return sourceName; }
    public String getSourceUrl() { return sourceUrl; }
    public Instant getPublishedAt() { return publishedAt; }
    public String getPublishedDate() { return publishedAt.atZone(java.time.ZoneId.of("Asia/Shanghai")).toLocalDate().toString(); }
    public Instant getCollectedAt() { return collectedAt; }
}
