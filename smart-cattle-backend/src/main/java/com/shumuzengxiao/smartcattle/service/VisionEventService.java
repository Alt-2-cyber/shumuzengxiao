package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.shumuzengxiao.smartcattle.domain.Severity;
import com.shumuzengxiao.smartcattle.domain.VisionEvent;
import com.shumuzengxiao.smartcattle.domain.VisionEventReview;
import com.shumuzengxiao.smartcattle.dto.VisionEventDto;
import com.shumuzengxiao.smartcattle.dto.VisionEventRequest;
import com.shumuzengxiao.smartcattle.dto.VisionEventReviewRequest;
import com.shumuzengxiao.smartcattle.dto.VisionTrainingLineageDto;
import com.shumuzengxiao.smartcattle.repository.VisionEventReviewRepository;
import com.shumuzengxiao.smartcattle.repository.VisionEventRepository;
import jakarta.annotation.PostConstruct;
import jakarta.transaction.Transactional;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.DigestOutputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.Collection;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.List;
import java.util.regex.Pattern;

@Service
public class VisionEventService {
    private static final Pattern SAFE_FILE_NAME = Pattern.compile("[A-Za-z0-9._-]+");
    private static final Pattern SHA256 = Pattern.compile("[a-fA-F0-9]{64}");
    private static final int DEFAULT_MAX_SNAPSHOT_BYTES = 2_000_000;

    private final VisionEventRepository visionEvents;
    private final HealthScreeningService healthScreeningService;
    private final ModelApprovalService modelApprovalService;
    private final VisionEventReviewRepository reviewRepository;
    private final ObjectMapper objectMapper;
    private final AuditTrailService audit;

    @Value("${app.vision.storage-dir:../vision-snapshots}")
    private String storageDirectory = "../vision-snapshots";

    @Value("${app.vision.max-snapshot-bytes:2000000}")
    private int maxSnapshotBytes = DEFAULT_MAX_SNAPSHOT_BYTES;

    private Path storageRoot;

    public VisionEventService(
            VisionEventRepository visionEvents,
            HealthScreeningService healthScreeningService,
            ModelApprovalService modelApprovalService,
            ObjectMapper objectMapper
    ) {
        this(visionEvents, healthScreeningService, modelApprovalService, null, objectMapper, null);
    }

    @Autowired
    public VisionEventService(
            VisionEventRepository visionEvents,
            HealthScreeningService healthScreeningService,
            ModelApprovalService modelApprovalService,
            VisionEventReviewRepository reviewRepository,
            ObjectMapper objectMapper,
            AuditTrailService audit
    ) {
        this.visionEvents = visionEvents;
        this.healthScreeningService = healthScreeningService;
        this.modelApprovalService = modelApprovalService;
        this.reviewRepository = reviewRepository;
        this.objectMapper = objectMapper;
        this.audit = audit;
    }

    @PostConstruct
    void prepareStorage() {
        try {
            storageRoot = Path.of(storageDirectory).toAbsolutePath().normalize();
            Files.createDirectories(storageRoot);
        } catch (IOException exception) {
            throw new IllegalStateException("Cannot create vision snapshot storage", exception);
        }
    }

    public VisionEvent ingest(VisionEventRequest request) {
        byte[] inlineSnapshot = decodeInlineSnapshot(request);
        String inlineContentType = inlineSnapshot == null ? null : snapshotContentType(request);
        String sourceKey = sourceKey(request);
        if (sourceKey != null) {
            Optional<VisionEvent> existing = visionEvents.findBySourceKey(sourceKey);
            if (existing.isPresent()) {
                VisionEvent event = existing.get();
                if (inlineSnapshot != null && !Boolean.TRUE.equals(event.getSnapshotAvailable())) {
                    archiveInlineSnapshot(event, inlineSnapshot, inlineContentType);
                }
                return event;
            }
        }

        VisionEvent event = new VisionEvent();
        event.setCameraId(request.cameraId().trim());
        event.setBarnId(request.barnId().trim());
        event.setEventType(request.eventType());
        event.setSeverity(Severity.valueOf(request.level().trim().toUpperCase(Locale.ROOT)));
        event.setScore(request.score());
        event.setTargetId(blankToNull(request.targetId()));
        event.setSourceSnapshotPath(blankToNull(request.snapshotPath()));
        event.setSnapshotPath(blankToNull(request.snapshotPath()));
        event.setSnapshotAvailable(false);
        ModelApprovalService.VisionDecision decision = modelApprovalService.enforceVisionEvent(
                request.eventType(), request.modelStatus(), request.modelVersion(), request.targetId());
        event.setModelName(blankToNull(request.modelName()));
        event.setModelVersion(blankToNull(request.modelVersion()));
        event.setModelStatus(blankToNull(request.modelStatus()));
        event.setModelApprovedByServer(decision.approvedByServer());
        event.setScreeningEligible(decision.screeningEligible());
        event.setEvidence(combineEvidence(request, decision));
        event.setSourceKey(sourceKey);
        event.setRecordedAt(timestamp(request.ts()));
        VisionEvent saved = visionEvents.save(event);
        if (inlineSnapshot != null) {
            archiveInlineSnapshot(saved, inlineSnapshot, inlineContentType);
        }
        if (decision.screeningEligible()) {
            healthScreeningService.recordVisionEvidence(
                    saved.getTargetId(), saved.getEventType(), saved.getScore(), saved.getRecordedAt());
        }
        return saved;
    }

    private byte[] decodeInlineSnapshot(VisionEventRequest request) {
        if (request.snapshotBase64() == null || request.snapshotBase64().isBlank()) {
            return null;
        }
        try {
            byte[] bytes = Base64.getDecoder().decode(request.snapshotBase64());
            if (bytes.length == 0 || bytes.length > maxSnapshotBytes) {
                throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE,
                        "inline vision snapshot exceeds configured size limit");
            }
            return bytes;
        } catch (IllegalArgumentException exception) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "inline vision snapshot is not valid Base64", exception);
        }
    }

    private String snapshotContentType(VisionEventRequest request) {
        String contentType = blankToNull(request.snapshotContentType());
        return contentType == null ? "image/jpeg" : contentType;
    }

    private void archiveInlineSnapshot(VisionEvent event, byte[] bytes, String contentType) {
        StoredSnapshot stored = writeSnapshotBytes(bytes, contentType, event.getId());
        event.setSnapshotPath(stored.apiPath());
        event.setSnapshotSha256(stored.sha256());
        event.setSnapshotAvailable(true);
        event.setSnapshotContentType(stored.contentType());
        event.setSnapshotBytes(stored.bytes());
        VisionEvent saved = visionEvents.save(event);
        auditSnapshot(saved, stored);
        event.setSnapshotPath(saved.getSnapshotPath());
    }

    public List<VisionEventDto> recentEvents(String barnId) {
        List<VisionEvent> events = barnId == null || barnId.isBlank()
                ? visionEvents.findTop20ByOrderByRecordedAtDesc()
                : visionEvents.findTop20ByBarnIdOrderByRecordedAtDesc(barnId.trim());
        if (reviewRepository == null) {
            return events.stream().map(event -> toDto(event, null)).toList();
        }
        Collection<Long> ids = events.stream().map(VisionEvent::getId).toList();
        Map<Long, VisionEventReview> reviews = new LinkedHashMap<>();
        reviewRepository.findByVisionEventIdIn(ids)
                .forEach(review -> reviews.put(review.getVisionEventId(), review));
        return events.stream().map(event -> toDto(event, reviews.get(event.getId()))).toList();
    }

    @Transactional
    public VisionEventDto uploadSnapshot(Long eventId, MultipartFile file, String expectedSha256) {
        VisionEvent event = visionEvents.findById(eventId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Vision event not found"));
        if (Boolean.TRUE.equals(event.getSnapshotAvailable())
                && event.getSnapshotPath() != null
                && event.getSnapshotPath().startsWith("/api/vision-snapshots/")) {
            if (expectedSha256 != null && !expectedSha256.isBlank()
                    && !constantTimeEquals(event.getSnapshotSha256(), expectedSha256.trim())) {
                throw conflict("vision snapshot is immutable and has a different hash");
            }
            return toDto(event, review(eventId));
        }

        StoredSnapshot stored = writeSnapshot(file, eventId, expectedSha256);
        event.setSnapshotPath(stored.apiPath());
        event.setSnapshotSha256(stored.sha256());
        event.setSnapshotAvailable(true);
        event.setSnapshotContentType(stored.contentType());
        event.setSnapshotBytes(stored.bytes());
        VisionEvent saved = visionEvents.save(event);
        auditSnapshot(saved, stored);
        return toDto(saved, review(eventId));
    }

    public VisionEventReview review(Long eventId, VisionEventReviewRequest request) {
        visionEvents.findById(eventId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Vision event not found"));
        if (reviewRepository == null) {
            throw new IllegalStateException("Vision review repository is not configured");
        }
        VisionEventReview review = reviewRepository.findByVisionEventId(eventId)
                .orElseGet(VisionEventReview::new);
        review.setVisionEventId(eventId);
        review.setStatus(request.status().trim());
        review.setLabel(blankToNull(request.label()));
        review.setReviewer(request.reviewer().trim());
        review.setNote(blankToNull(request.note()));
        if (Boolean.TRUE.equals(request.clinicallyVerified())) {
            review.setAnimalId(blankToNull(request.animalId()));
            review.setVeterinarian(blankToNull(request.veterinarian()));
            review.setClinicalEvidenceReference(blankToNull(request.clinicalEvidenceReference()));
            review.setClinicallyVerifiedAt(Instant.now());
        } else {
            review.setAnimalId(null);
            review.setVeterinarian(null);
            review.setClinicalEvidenceReference(null);
            review.setClinicallyVerifiedAt(null);
        }
        review.setReviewedAt(Instant.now());
        VisionEventReview saved = reviewRepository.save(review);
        if (audit != null) {
            Map<String, Object> details = new LinkedHashMap<>();
            details.put("eventId", eventId);
            details.put("status", saved.getStatus());
            details.put("label", saved.getLabel());
            details.put("clinicalAnimalId", saved.getAnimalId());
            details.put("veterinarian", saved.getVeterinarian());
            details.put("clinicalEvidenceReference", saved.getClinicalEvidenceReference());
            details.put("clinicallyVerifiedAt", saved.getClinicallyVerifiedAt());
            audit.record("vision_event_reviewed", saved.getReviewer(), "vision_event",
                    String.valueOf(eventId), details);
        }
        return saved;
    }

    /** Re-hashes the image immediately before it is consumed by a trainer. */
    public VisionTrainingLineageDto trainingLineage(Long eventId) {
        VisionEvent event = visionEvents.findById(eventId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Vision event not found"));
        Path snapshot = verifiedSnapshotPath(event);
        VisionEventReview review = review(eventId);
        return new VisionTrainingLineageDto(
                event.getId(), event.getCameraId(), event.getBarnId(),
                review == null ? null : review.getAnimalId(),
                event.getSnapshotPath(), event.getSnapshotSha256(), true, Instant.now(),
                review == null ? "pending" : review.getStatus(),
                review == null ? null : review.getLabel(),
                review == null ? null : review.getVeterinarian(),
                review == null ? null : review.getClinicalEvidenceReference(),
                review == null ? null : review.getClinicallyVerifiedAt(), event.getRecordedAt());
    }

    public Path resolveSnapshot(String fileName) {
        if (fileName == null || !SAFE_FILE_NAME.matcher(fileName).matches()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Vision snapshot not found");
        }
        String apiPath = "/api/vision-snapshots/" + fileName;
        VisionEvent event = visionEvents.findBySnapshotPath(apiPath)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Vision snapshot metadata not found"));
        return verifiedSnapshotPath(event);
    }

    private static Instant timestamp(Long seconds) {
        if (seconds == null || seconds < 1_600_000_000L || seconds > 4_102_444_800L) {
            return Instant.now();
        }
        return Instant.ofEpochSecond(seconds);
    }

    private static String sourceKey(VisionEventRequest request) {
        String eventId = blankToNull(request.edgeEventId());
        if (eventId == null) {
            return null;
        }
        String boot = blankToNull(request.bootId());
        String key = request.cameraId().trim() + ":" + (boot == null ? "" : boot + ":") + eventId;
        return key.length() <= 190 ? key : key.substring(0, 190);
    }

    private String combineEvidence(VisionEventRequest request, ModelApprovalService.VisionDecision decision) {
        Map<String, Object> evidence = new LinkedHashMap<>();
        if (request.evidence() != null && !request.evidence().isBlank()) {
            evidence.put("message", request.evidence().trim());
        }
        evidence.put("screeningOnly", !Boolean.FALSE.equals(request.screeningOnly()));
        evidence.put("modelName", blankToNull(request.modelName()));
        evidence.put("modelVersion", blankToNull(request.modelVersion()));
        evidence.put("modelStatus", blankToNull(request.modelStatus()));
        evidence.put("approvedByServer", decision.approvedByServer());
        evidence.put("modelApprovalRequired", decision.modelApprovalRequired());
        evidence.put("screeningEligible", decision.screeningEligible());
        evidence.put("approvalReason", decision.approvalReason());
        evidence.put("identityRequired", "targetId must be a verified cattle ID, not a tracker ID");
        try {
            String json = objectMapper.writeValueAsString(evidence);
            return json.length() <= 1000 ? json : json.substring(0, 1000);
        } catch (JsonProcessingException exception) {
            return "screeningOnly=true";
        }
    }

    private VisionEventReview review(Long eventId) {
        return reviewRepository == null ? null : reviewRepository.findByVisionEventId(eventId).orElse(null);
    }

    private VisionEventDto toDto(VisionEvent event, VisionEventReview review) {
        return new VisionEventDto(
                event.getId(), event.getCameraId(), event.getBarnId(), event.getEventType(), event.getSeverity(),
                event.getScore(), event.getTargetId(), event.getSourceKey(), event.getSourceSnapshotPath(),
                event.getSnapshotPath(), event.getSnapshotSha256(), event.getSnapshotAvailable(),
                event.getSnapshotContentType(), event.getSnapshotBytes(), event.getEvidence(), event.getModelName(),
                event.getModelVersion(), event.getModelStatus(), event.getModelApprovedByServer(),
                event.getScreeningEligible(), review == null ? "pending" : review.getStatus(),
                review == null ? null : review.getLabel(), review == null ? null : review.getNote(),
                review == null ? null : review.getReviewer(), review == null ? null : review.getAnimalId(),
                review == null ? null : review.getVeterinarian(),
                review == null ? null : review.getClinicalEvidenceReference(),
                review == null ? null : review.getClinicallyVerifiedAt(), review == null ? null : review.getReviewedAt(),
                event.getRecordedAt());
    }

    private StoredSnapshot writeSnapshot(MultipartFile file, Long eventId, String expectedSha256) {
        if (file == null || file.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "snapshot file is required");
        }
        String contentType = file.getContentType() == null ? "" : file.getContentType().toLowerCase(Locale.ROOT);
        String extension = switch (contentType) {
            case "image/jpeg", "image/jpg" -> ".jpg";
            case "image/png" -> ".png";
            case "image/webp" -> ".webp";
            default -> throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "snapshot must be JPEG, PNG, or WebP");
        };
        long declared = file.getSize();
        if (declared > maxSnapshotBytes) {
            throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE, "snapshot exceeds configured size limit");
        }
        if (storageRoot == null) {
            prepareStorage();
        }
        String name = eventId + "-" + UUID.randomUUID() + extension;
        Path destination = storageRoot.resolve(name).normalize();
        if (!destination.startsWith(storageRoot)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "invalid snapshot destination");
        }
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            long bytes = 0L;
            try (InputStream input = file.getInputStream();
                 OutputStream raw = Files.newOutputStream(destination, StandardOpenOption.CREATE_NEW);
                 DigestOutputStream output = new DigestOutputStream(raw, digest)) {
                byte[] buffer = new byte[8192];
                for (int count; (count = input.read(buffer)) >= 0;) {
                    if (count == 0) {
                        continue;
                    }
                    bytes += count;
                    if (bytes > maxSnapshotBytes) {
                        throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE,
                                "snapshot exceeds configured size limit");
                    }
                    output.write(buffer, 0, count);
                }
            }
            String hash = java.util.HexFormat.of().formatHex(digest.digest());
            if (expectedSha256 != null && !expectedSha256.isBlank()) {
                if (!SHA256.matcher(expectedSha256.trim()).matches()
                        || !constantTimeEquals(hash, expectedSha256.trim())) {
                    Files.deleteIfExists(destination);
                    throw conflict("snapshot SHA-256 does not match the uploaded bytes");
                }
            }
            return new StoredSnapshot("/api/vision-snapshots/" + name, hash, contentType, bytes);
        } catch (ResponseStatusException exception) {
            try { Files.deleteIfExists(destination); } catch (IOException ignored) { }
            throw exception;
        } catch (IOException | NoSuchAlgorithmException exception) {
            try { Files.deleteIfExists(destination); } catch (IOException ignored) { }
            throw new IllegalStateException("Cannot save vision snapshot", exception);
        }
    }

    private StoredSnapshot writeSnapshotBytes(byte[] content, String requestedContentType, Long eventId) {
        if (content == null || content.length == 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "inline snapshot is empty");
        }
        if (content.length > maxSnapshotBytes) {
            throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE,
                    "inline snapshot exceeds configured size limit");
        }
        String contentType = requestedContentType == null
                ? "image/jpeg" : requestedContentType.toLowerCase(Locale.ROOT);
        String extension = switch (contentType) {
            case "image/jpeg", "image/jpg" -> ".jpg";
            case "image/png" -> ".png";
            case "image/webp" -> ".webp";
            default -> throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "inline snapshot must be JPEG, PNG, or WebP");
        };
        if (storageRoot == null) {
            prepareStorage();
        }
        String name = eventId + "-" + UUID.randomUUID() + extension;
        Path destination = storageRoot.resolve(name).normalize();
        if (!destination.startsWith(storageRoot)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "invalid snapshot destination");
        }
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (OutputStream raw = Files.newOutputStream(destination, StandardOpenOption.CREATE_NEW);
                 DigestOutputStream output = new DigestOutputStream(raw, digest)) {
                output.write(content);
            }
            return new StoredSnapshot(
                    "/api/vision-snapshots/" + name,
                    java.util.HexFormat.of().formatHex(digest.digest()),
                    contentType,
                    content.length);
        } catch (IOException | NoSuchAlgorithmException exception) {
            try { Files.deleteIfExists(destination); } catch (IOException ignored) { }
            throw new IllegalStateException("Cannot save inline vision snapshot", exception);
        }
    }

    private Path verifiedSnapshotPath(VisionEvent event) {
        String apiPath = event.getSnapshotPath();
        if (apiPath == null || !apiPath.startsWith("/api/vision-snapshots/")) {
            throw conflict("vision snapshot archive is missing");
        }
        String fileName = apiPath.substring("/api/vision-snapshots/".length());
        if (!SAFE_FILE_NAME.matcher(fileName).matches() || storageRoot == null) {
            throw conflict("vision snapshot archive metadata is invalid");
        }
        Path candidate = storageRoot.resolve(fileName).normalize();
        if (!candidate.startsWith(storageRoot) || !Files.isRegularFile(candidate)
                || !Boolean.TRUE.equals(event.getSnapshotAvailable())
                || event.getSnapshotSha256() == null
                || !SHA256.matcher(event.getSnapshotSha256()).matches()
                || !constantTimeEquals(event.getSnapshotSha256(), sha256(candidate))) {
            throw conflict("vision snapshot integrity check failed");
        }
        return candidate;
    }

    private void auditSnapshot(VisionEvent event, StoredSnapshot snapshot) {
        if (audit == null) {
            return;
        }
        audit.record("vision_snapshot_archived", "uploader", "vision_event",
                String.valueOf(event.getId()), Map.of(
                        "snapshotPath", snapshot.apiPath(),
                        "snapshotSha256", snapshot.sha256(),
                        "contentType", snapshot.contentType(),
                        "bytes", snapshot.bytes()));
    }

    private static String sha256(Path path) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream input = Files.newInputStream(path)) {
                byte[] buffer = new byte[8192];
                for (int count; (count = input.read(buffer)) > 0;) {
                    digest.update(buffer, 0, count);
                }
            }
            return java.util.HexFormat.of().formatHex(digest.digest());
        } catch (IOException | NoSuchAlgorithmException exception) {
            return "";
        }
    }

    private static boolean constantTimeEquals(String expected, String actual) {
        return expected != null && actual != null && MessageDigest.isEqual(
                expected.toLowerCase(Locale.ROOT).getBytes(java.nio.charset.StandardCharsets.US_ASCII),
                actual.toLowerCase(Locale.ROOT).getBytes(java.nio.charset.StandardCharsets.US_ASCII));
    }

    private static ResponseStatusException conflict(String message) {
        return new ResponseStatusException(HttpStatus.CONFLICT, message);
    }

    private static String blankToNull(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }

    private record StoredSnapshot(String apiPath, String sha256, String contentType, long bytes) {
    }
}
