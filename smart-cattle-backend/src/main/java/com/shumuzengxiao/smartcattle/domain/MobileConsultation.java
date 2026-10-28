package com.shumuzengxiao.smartcattle.domain;

import com.shumuzengxiao.smartcattle.dto.MobileSupport.ConsultationRequest;
import com.shumuzengxiao.smartcattle.dto.MobileSupport.ConsultationView;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import java.time.Instant;

@Entity
public class MobileConsultation {
    @Id @Column(length = 64)
    private String id;
    @Column(nullable = false, length = 64)
    private String ownerHash;
    @Column(nullable = false, length = 20)
    private String category;
    @Column(nullable = false, length = 20)
    private String priority;
    @Column(nullable = false, length = 80)
    private String subject;
    @Column(nullable = false, length = 2000)
    private String description;
    @Column(length = 80)
    private String cattleId;
    @Column(length = 80)
    private String contact;
    @Column(nullable = false, length = 20)
    private String status;
    @Column(nullable = false)
    private Instant createdAt;
    @Column(nullable = false)
    private Instant updatedAt;

    protected MobileConsultation() {}

    public MobileConsultation(String ownerHash, ConsultationRequest request) {
        id = request.requestId();
        this.ownerHash = ownerHash;
        category = request.category();
        priority = request.priority();
        subject = request.subject().trim();
        description = request.description().trim();
        cattleId = request.cattleId() == null ? "" : request.cattleId().trim();
        contact = request.contact() == null ? "" : request.contact().trim();
        status = "pending";
        createdAt = Instant.now();
        updatedAt = createdAt;
    }

    public boolean ownedBy(String hash) { return ownerHash.equals(hash); }

    public boolean sameRequest(ConsultationRequest request) {
        return category.equals(request.category()) && priority.equals(request.priority())
                && subject.equals(request.subject().trim()) && description.equals(request.description().trim())
                && cattleId.equals(request.cattleId() == null ? "" : request.cattleId().trim())
                && contact.equals(request.contact() == null ? "" : request.contact().trim());
    }

    public void cancel() {
        status = "cancelled";
        updatedAt = Instant.now();
    }

    public ConsultationView view() {
        return new ConsultationView(id, category, priority, subject, description, cattleId, contact,
                status, createdAt, updatedAt);
    }
}
