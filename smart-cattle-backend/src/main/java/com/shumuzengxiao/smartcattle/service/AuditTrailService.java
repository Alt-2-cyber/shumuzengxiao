package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.shumuzengxiao.smartcattle.domain.AuditRecord;
import com.shumuzengxiao.smartcattle.repository.AuditRecordRepository;
import jakarta.transaction.Transactional;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

@Service
public class AuditTrailService {
    private static final int MAX_PAYLOAD_LENGTH = 16_000;
    private final AuditRecordRepository records;
    private final ObjectMapper objectMapper;

    public AuditTrailService(AuditRecordRepository records, ObjectMapper objectMapper) {
        this.records = records;
        this.objectMapper = objectMapper;
    }

    /** A single local backend is the supported writer topology. The hash chain
     * makes alteration detectable; database administrators still need backups
     * and access controls for a regulatory retention guarantee. */
    @Transactional
    public synchronized AuditRecord record(
            String eventType,
            String actor,
            String targetType,
            String targetId,
            Map<String, ?> details
    ) {
        Instant recordedAt = Instant.now();
        String payload = payload(details);
        String previous = records.findTop1ByOrderByIdDesc().map(AuditRecord::getEntryHash).orElse("");
        AuditRecord record = new AuditRecord();
        record.setEventType(token(eventType, 80));
        record.setActor(token(actor, 120));
        record.setTargetType(token(targetType, 80));
        record.setTargetId(token(targetId, 120));
        record.setPayloadJson(payload);
        record.setRecordedAt(recordedAt);
        record.setPreviousHash(previous.isEmpty() ? null : previous);
        record.setEntryHash(sha256(String.join("|", previous, record.getEventType(), record.getActor(),
                record.getTargetType(), record.getTargetId(), recordedAt.toString(), payload)));
        return records.save(record);
    }

    public List<AuditRecord> recent() {
        return records.findTop100ByOrderByIdDesc();
    }

    public List<AuditRecord> targetHistory(String targetType, String targetId) {
        return records.findTop100ByTargetTypeAndTargetIdOrderByIdDesc(token(targetType, 80), token(targetId, 120));
    }

    private String payload(Map<String, ?> details) {
        try {
            String value = objectMapper.writeValueAsString(new TreeMap<>(details == null ? Map.of() : details));
            return value.length() <= MAX_PAYLOAD_LENGTH ? value : value.substring(0, MAX_PAYLOAD_LENGTH);
        } catch (JsonProcessingException exception) {
            return "{\"serializationError\":true}";
        }
    }

    private static String token(String value, int maximum) {
        String normalized = value == null ? "unknown" : value.trim();
        if (normalized.isEmpty()) {
            normalized = "unknown";
        }
        return normalized.length() <= maximum ? normalized : normalized.substring(0, maximum);
    }

    private static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            return java.util.HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }
}
