package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.shumuzengxiao.smartcattle.domain.MotionCaptureSession;
import com.shumuzengxiao.smartcattle.domain.MotionCaptureClinicalReview;
import com.shumuzengxiao.smartcattle.dto.MotionCaptureClinicalReviewDto;
import com.shumuzengxiao.smartcattle.dto.MotionCaptureClinicalReviewRequest;
import com.shumuzengxiao.smartcattle.dto.MotionCaptureRequest;
import com.shumuzengxiao.smartcattle.dto.MotionCaptureTrainingLineageDto;
import com.shumuzengxiao.smartcattle.repository.MotionCaptureClinicalReviewRepository;
import com.shumuzengxiao.smartcattle.repository.MotionCaptureSessionRepository;
import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/** Archives raw IMU rows as NDJSON, with session metadata in the database. */
@Service
public class MotionCaptureService {
    private static final int SAMPLE_RATE_HZ = 20;
    private static final double MINIMUM_COMPLETENESS_RATIO = 0.95;
    private final MotionCaptureSessionRepository sessions;
    private final MotionCaptureClinicalReviewRepository clinicalReviews;
    private final ObjectMapper objectMapper;
    private final AuditTrailService audit;
    private final Map<String, Long> counters = new ConcurrentHashMap<>();
    private final Map<String, Long> lastMonotonicMs = new ConcurrentHashMap<>();

    @Value("${app.motion-capture.storage-dir:../motion-captures}")
    private String storageDirectory = "../motion-captures";

    @Value("${app.motion-capture.expiry-grace-ms:30000}")
    private long expiryGraceMs = 30_000L;

    private Path storageRoot;

    public MotionCaptureService(MotionCaptureSessionRepository sessions, ObjectMapper objectMapper) {
        this(sessions, null, objectMapper, null);
    }

    public MotionCaptureService(
            MotionCaptureSessionRepository sessions,
            ObjectMapper objectMapper,
            AuditTrailService audit
    ) {
        this(sessions, null, objectMapper, audit);
    }

    @Autowired
    public MotionCaptureService(
            MotionCaptureSessionRepository sessions,
            MotionCaptureClinicalReviewRepository clinicalReviews,
            ObjectMapper objectMapper,
            AuditTrailService audit
    ) {
        this.sessions = sessions;
        this.clinicalReviews = clinicalReviews;
        this.objectMapper = objectMapper;
        this.audit = audit;
    }

    @PostConstruct
    void prepareStorage() {
        try {
            storageRoot = Path.of(storageDirectory).toAbsolutePath().normalize();
            Files.createDirectories(storageRoot);
        } catch (IOException exception) {
            throw new IllegalStateException("Cannot create motion capture storage", exception);
        }
    }

    public MotionCaptureSession create(MotionCaptureRequest request) {
        String sessionId = safeSessionId(request.sessionId());
        if (sessions.findBySessionId(sessionId).isPresent()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Motion capture session already exists");
        }
        MotionCaptureSession session = new MotionCaptureSession();
        session.setSessionId(sessionId);
        session.setCattleId(request.cattleId().trim());
        session.setDeviceId(request.deviceId().trim());
        session.setBarnId(request.barnId().trim());
        session.setDurationMs(request.durationMs());
        session.setSampleRateHz(SAMPLE_RATE_HZ);
        session.setReceivedSamples(0L);
        session.setExpectedSamples(expectedSamples(request.durationMs(), SAMPLE_RATE_HZ));
        session.setAttemptedSamples(0L);
        session.setDroppedBackpressureSamples(0L);
        session.setDroppedSensorSamples(0L);
        session.setCompletenessRatio(0.0);
        session.setQualityStatus("pending");
        session.setStatus("queued");
        session.setRawDataPath(sessionId + ".jsonl");
        session.setVideoReference(blankToNull(request.videoReference()));
        session.setNotes(blankToNull(request.notes()));
        session.setOperatorName(request.operatorName().trim());
        session.setRequestedAt(Instant.now());
        MotionCaptureSession saved = sessions.save(session);
        Map<String, Object> requestedDetails = new java.util.LinkedHashMap<>();
        requestedDetails.put("durationMs", saved.getDurationMs());
        requestedDetails.put("videoReference", saved.getVideoReference());
        audit("motion_capture_requested", saved, saved.getOperatorName(), requestedDetails);
        return saved;
    }

    public MotionCaptureSession markDispatch(Long id, String dispatchStatus) {
        MotionCaptureSession session = get(id);
        if ("sent".equals(dispatchStatus)) {
            session.setStatus("queued");
        } else {
            session.setStatus("dispatch_" + safeStatus(dispatchStatus));
            session.setQualityStatus("not_collected");
            session.setCompletedAt(Instant.now());
        }
        MotionCaptureSession saved = sessions.save(session);
        if (!"sent".equals(dispatchStatus)) {
            audit("motion_capture_dispatch_failed", saved, "system", Map.of("dispatchStatus", dispatchStatus));
        }
        return saved;
    }

    public void ingestSample(ObjectNode row, Instant receivedAt) {
        ObjectNode normalized = normalizeSample(row);
        if (normalized == null) {
            rejectMalformedSample(row, receivedAt);
            return;
        }
        String sessionId = text(normalized, "sessionId");
        if (sessionId == null) {
            return;
        }
        MotionCaptureSession session = sessions.findBySessionId(sessionId).orElse(null);
        if (session == null || !acceptsIdentity(session, normalized)) {
            return;
        }
        if (!"capturing".equals(session.getStatus()) && !"queued".equals(session.getStatus())) {
            return;
        }
        try {
            long sampleIndex = normalized.path("sampleIndex").asLong(-1L);
            long monotonicMs = normalized.path("monotonicMs").asLong(-1L);
            if (sampleIndex < 0L || !acceptsNextSampleIndex(session, sampleIndex)
                    || !acceptsMonotonicTime(session, monotonicMs)) {
                rejectIntegrity(session, receivedAt, "sample_index");
                return;
            }
            ObjectNode archived = normalized.deepCopy();
            archived.put("receivedAt", receivedAt.toString());
            append(session, objectMapper.writeValueAsString(archived));
            long count = counters.merge(sessionId, 1L, Long::sum);
            lastMonotonicMs.put(sessionId, monotonicMs);
            if ("queued".equals(session.getStatus())) {
                session.setStatus("capturing");
                session.setQualityStatus("collecting");
                session.setStartedAt(receivedAt);
            }
            session.setReceivedSamples(count);
            if (count % SAMPLE_RATE_HZ == 0) {
                sessions.save(session);
            }
        } catch (IOException exception) {
            session.setStatus("storage_error");
            session.setQualityStatus("rejected_storage_error");
            session.setCompletedAt(receivedAt);
            sessions.save(session);
        }
    }

    public void ingestState(ObjectNode message, Instant receivedAt) {
        String sessionId = text(message, "sessionId");
        if (sessionId == null) {
            return;
        }
        MotionCaptureSession session = sessions.findBySessionId(sessionId).orElse(null);
        if (session == null) {
            return;
        }
        if (!acceptsIdentity(session, message) || session.getStatus().startsWith("rejected_")) {
            return;
        }
        String status = text(message, "status");
        if ("started".equals(status)) {
            StateMetadata metadata = mergeDeviceCounts(session, message);
            if (!metadata.valid()) {
                rejectIntegrity(session, receivedAt, metadata.reason());
                return;
            }
            session.setStatus("capturing");
            session.setQualityStatus("collecting");
            session.setStartedAt(receivedAt);
        } else if ("completed".equals(status) || "cancelled".equals(status) || "sensor_failure".equals(status)
                || "serial_backpressure".equals(status)) {
            StateMetadata metadata = mergeDeviceCounts(session, message);
            session.setCompletedAt(receivedAt);
            long received = counters.getOrDefault(sessionId, session.getReceivedSamples() == null ? 0L : session.getReceivedSamples());
            session.setReceivedSamples(received);
            session.setCompletenessRatio(completeness(session));
            if ("completed".equals(status)) {
                CaptureIntegrity integrity = captureIntegrity(session);
                String rejection = completionRejection(metadata, session, integrity);
                boolean accepted = rejection == null;
                session.setStatus(accepted ? "completed" : "completed_incomplete");
                session.setQualityStatus(accepted ? "accepted" : "rejected_" + rejection);
            } else {
                session.setStatus(status);
                session.setQualityStatus("sensor_failure".equals(status) ? "rejected_sensor_failure"
                        : "serial_backpressure".equals(status) ? "rejected_transport_backpressure" : "cancelled");
            }
            session.setRawDataSha256(sha256(session));
            counters.remove(sessionId);
            lastMonotonicMs.remove(sessionId);
        }
        MotionCaptureSession saved = sessions.save(session);
        if ("completed".equals(status) || "cancelled".equals(status) || "sensor_failure".equals(status)
                || "serial_backpressure".equals(status)) {
            Map<String, Object> details = new java.util.LinkedHashMap<>();
            details.put("status", saved.getStatus());
            details.put("qualityStatus", saved.getQualityStatus());
            details.put("receivedSamples", saved.getReceivedSamples());
            details.put("expectedSamples", saved.getExpectedSamples());
            details.put("completenessRatio", saved.getCompletenessRatio());
            details.put("droppedBackpressureSamples", saved.getDroppedBackpressureSamples());
            details.put("droppedSensorSamples", saved.getDroppedSensorSamples());
            details.put("rawDataSha256", saved.getRawDataSha256());
            audit("motion_capture_finalized", saved, "device:" + saved.getDeviceId(), details);
        }
    }

    public List<MotionCaptureSession> recent(String cattleId) {
        expireStaleSessions(Instant.now());
        if (cattleId == null || cattleId.isBlank()) {
            return sessions.findTop100ByOrderByRequestedAtDesc();
        }
        return sessions.findTop100ByCattleIdOrderByRequestedAtDesc(cattleId.trim());
    }

    public Path resolveRawData(String sessionId) {
        expireStaleSessions(Instant.now());
        MotionCaptureSession session = sessions.findBySessionId(sessionId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Motion capture session not found"));
        Path path = storageRoot.resolve(session.getRawDataPath()).normalize();
        if (!path.startsWith(storageRoot) || !Files.isRegularFile(path)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Motion capture data not found");
        }
        if (!"completed".equals(session.getStatus()) || !"accepted".equals(session.getQualityStatus())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Motion capture is not accepted for export");
        }
        String actualHash = sha256(session);
        if (actualHash == null || session.getRawDataSha256() == null
                || !MessageDigest.isEqual(actualHash.getBytes(StandardCharsets.US_ASCII),
                session.getRawDataSha256().getBytes(StandardCharsets.US_ASCII))) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Motion capture archive integrity check failed");
        }
        CaptureIntegrity integrity = captureIntegrity(session);
        if (!integrity.complete()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Motion capture sample integrity check failed");
        }
        return path;
    }

    /**
     * Rechecks the accepted archive immediately before a release trainer or
     * release registrar consumes it. A local manifest cannot substitute a
     * different IMU file because the caller must compare this current hash and
     * capture identity with its own training record.
     */
    public MotionCaptureTrainingLineageDto trainingLineage(String sessionId) {
        expireStaleSessions(Instant.now());
        MotionCaptureSession session = sessions.findBySessionId(sessionId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Motion capture session not found"));
        resolveRawData(sessionId);
        MotionCaptureClinicalReview review = clinicalReviews == null
                ? null : clinicalReviews.findBySessionId(sessionId).orElse(null);
        boolean completeClinicalReview = completeClinicalReview(review);
        return new MotionCaptureTrainingLineageDto(
                session.getSessionId(),
                session.getCattleId(),
                session.getDeviceId(),
                session.getBarnId(),
                "/api/motion-captures/" + session.getSessionId() + "/raw",
                session.getRawDataSha256(),
                true,
                Instant.now(),
                session.getStatus(),
                session.getQualityStatus(),
                session.getSampleRateHz(),
                session.getReceivedSamples(),
                session.getExpectedSamples(),
                session.getAttemptedSamples(),
                session.getDroppedBackpressureSamples(),
                session.getDroppedSensorSamples(),
                session.getCompletenessRatio(),
                session.getVideoReference(),
                session.getOperatorName(),
                session.getRequestedAt(),
                session.getStartedAt(),
                session.getCompletedAt(),
                review == null ? "not_signed" : completeClinicalReview ? "verified" : "incomplete",
                review == null ? null : review.getLamenessScore(),
                review == null ? null : review.getGaitReviewer(),
                review == null ? null : review.getHoofExaminer(),
                review == null ? null : review.getVeterinarian(),
                review == null ? null : review.getHoofFinding(),
                review == null ? null : review.getClinicalEvidenceReference(),
                review == null ? null : review.getClinicallyVerifiedAt());
    }

    /**
     * Binds the standard gait score and hoof assessment to one already
     * accepted, hash-verified IMU archive. A generic clinical-check record is
     * not sufficient because it cannot prove which capture it labels.
     */
    public MotionCaptureClinicalReviewDto reviewClinical(
            String sessionId,
            MotionCaptureClinicalReviewRequest request
    ) {
        if (clinicalReviews == null) {
            throw new IllegalStateException("Motion capture clinical review storage is unavailable");
        }
        MotionCaptureSession session = sessions.findBySessionId(sessionId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Motion capture session not found"));
        if (session.getVideoReference() == null || session.getVideoReference().isBlank()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Motion capture requires a synchronized video reference");
        }
        resolveRawData(sessionId);

        MotionCaptureClinicalReview current = clinicalReviews.findBySessionId(sessionId).orElse(null);
        MotionCaptureClinicalReview review = current == null ? new MotionCaptureClinicalReview() : current;
        review.setSessionId(session.getSessionId());
        review.setCattleId(session.getCattleId());
        review.setLamenessScore(request.lamenessScore());
        review.setGaitReviewer(request.gaitReviewer().trim());
        review.setHoofExaminer(request.hoofExaminer().trim());
        review.setVeterinarian(request.veterinarian().trim());
        review.setHoofFinding(request.hoofFinding().trim());
        review.setClinicalEvidenceReference(request.clinicalEvidenceReference().trim());
        Instant now = Instant.now();
        review.setClinicallyVerifiedAt(now);
        review.setReviewedAt(now);
        review = clinicalReviews.save(review);

        Map<String, Object> details = new java.util.LinkedHashMap<>();
        details.put("previousLamenessScore", current == null ? null : current.getLamenessScore());
        details.put("lamenessScore", review.getLamenessScore());
        details.put("gaitReviewer", review.getGaitReviewer());
        details.put("hoofExaminer", review.getHoofExaminer());
        details.put("veterinarian", review.getVeterinarian());
        details.put("hoofFinding", review.getHoofFinding());
        details.put("clinicalEvidenceReference", review.getClinicalEvidenceReference());
        details.put("clinicallyVerifiedAt", review.getClinicallyVerifiedAt());
        audit("motion_capture_clinical_reviewed", session, "veterinarian:" + review.getVeterinarian(), details);
        return toClinicalReviewDto(review);
    }

    /** A disconnected node must not leave an apparently active recording that
     * could later be mistaken for a complete clinical capture. */
    @Scheduled(fixedDelayString = "${app.motion-capture.expiry-sweep-ms:10000}")
    public void expireStaleCaptureSessions() {
        expireStaleSessions(Instant.now());
    }

    public synchronized void expireStaleSessions(Instant now) {
        long grace = Math.max(0L, expiryGraceMs);
        Instant cutoff = now.minusMillis(Math.max(1_000L, grace));
        for (MotionCaptureSession session : sessions.findByStatusInAndRequestedAtBefore(
                List.of("queued", "capturing"), cutoff)) {
            Instant started = session.getStartedAt();
            long allowedMs = Math.max(1_000L, (session.getDurationMs() == null ? 0L : session.getDurationMs()) + grace);
            Instant reference = started == null ? session.getRequestedAt() : started;
            if (reference == null || !reference.plusMillis(allowedMs).isBefore(now)) {
                continue;
            }
            session.setStatus("expired");
            session.setQualityStatus("rejected_timeout");
            session.setCompletedAt(now);
            session.setRawDataSha256(sha256(session));
            counters.remove(session.getSessionId());
            lastMonotonicMs.remove(session.getSessionId());
            sessions.save(session);
            audit("motion_capture_expired", session, "system", Map.of("expiryGraceMs", grace));
        }
    }

    private MotionCaptureSession get(Long id) {
        return sessions.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Motion capture session not found"));
    }

    private boolean acceptsIdentity(MotionCaptureSession session, JsonNode row) {
        return session.getCattleId().equals(text(row, "cattleId"))
                && session.getDeviceId().equals(text(row, "deviceId"))
                && session.getBarnId().equals(text(row, "barnId"));
    }

    private ObjectNode normalizeSample(ObjectNode row) {
        String type = text(row, "type");
        if ("motion_capture_sample".equals(type)) {
            ObjectNode normalized = row.deepCopy();
            return validCanonicalSample(normalized) ? normalized : null;
        }
        if (!"mcs".equals(type)) {
            return null;
        }
        ObjectNode result = objectMapper.createObjectNode();
        String sessionId = text(row, "s");
        String deviceId = text(row, "d");
        String cattleId = text(row, "c");
        String barnId = text(row, "b");
        if (sessionId == null || deviceId == null || cattleId == null || barnId == null) {
            return null;
        }
        result.put("type", "motion_capture_sample");
        result.put("sessionId", sessionId);
        result.put("deviceId", deviceId);
        result.put("cattleId", cattleId);
        result.put("barnId", barnId);
        result.put("sampleIndex", row.path("i").asLong(-1));
        result.put("monotonicMs", row.path("m").asLong(-1));
        result.put("sampleRateHz", row.path("r").asInt(SAMPLE_RATE_HZ));
        if (!copyAxes(row.path("n"), result.putObject("neck"), true)
                || !copyAxes(row.path("u"), result.putObject("body"), false)
                || !copyAxes(row.path("l"), result.putObject("leg"), true)) {
            return null;
        }
        return validCanonicalSample(result) ? result : null;
    }

    private static boolean validCanonicalSample(ObjectNode row) {
        if (text(row, "sessionId") == null || text(row, "deviceId") == null
                || text(row, "cattleId") == null || text(row, "barnId") == null) {
            return false;
        }
        if (!isNonNegativeInteger(row.path("sampleIndex"))
                || !isNonNegativeInteger(row.path("monotonicMs"))
                || !row.path("sampleRateHz").isIntegralNumber()
                || row.path("sampleRateHz").asInt() != SAMPLE_RATE_HZ) {
            return false;
        }
        return validAxes(row.path("neck"), true)
                && validAxes(row.path("body"), false)
                && validAxes(row.path("leg"), true);
    }

    private static boolean validAxes(JsonNode source, boolean includesGyroscope) {
        if (!source.isObject()) {
            return false;
        }
        // The current wearable uses ADXL345 modules and therefore has only
        // acceleration. Keep accepting the older 6-axis MPU captures so the
        // archive and lineage format remain backward compatible.
        boolean hasGyroscope = includesGyroscope
                && source.path("gx").isNumber()
                && source.path("gy").isNumber()
                && source.path("gz").isNumber();
        String[] names = hasGyroscope
                ? new String[]{"ax", "ay", "az", "gx", "gy", "gz"}
                : new String[]{"ax", "ay", "az"};
        for (String name : names) {
            JsonNode value = source.path(name);
            if (!value.isNumber() || !Double.isFinite(value.asDouble())) {
                return false;
            }
        }
        return true;
    }

    private static boolean copyAxes(JsonNode source, ObjectNode target, boolean includesGyroscope) {
        if (!source.isArray()) {
            return false;
        }
        boolean hasGyroscope = includesGyroscope && source.size() == 6;
        int expected = hasGyroscope ? 6 : 3;
        if (source.size() != expected) {
            return false;
        }
        String[] names = hasGyroscope
                ? new String[]{"ax", "ay", "az", "gx", "gy", "gz"}
                : new String[]{"ax", "ay", "az"};
        for (int index = 0; index < expected; index++) {
            JsonNode value = source.get(index);
            if (value == null || !value.isNumber() || !Double.isFinite(value.asDouble())) {
                return false;
            }
            target.put(names[index], value.asDouble());
        }
        return true;
    }

    private void append(MotionCaptureSession session, String row) throws IOException {
        Path path = storageRoot.resolve(session.getRawDataPath()).normalize();
        if (!path.startsWith(storageRoot)) {
            throw new IOException("Invalid capture destination");
        }
        try (OutputStream output = Files.newOutputStream(path,
                StandardOpenOption.CREATE, StandardOpenOption.WRITE, StandardOpenOption.APPEND)) {
            output.write(row.getBytes(StandardCharsets.UTF_8));
            output.write('\n');
        }
    }

    private boolean acceptsNextSampleIndex(MotionCaptureSession session, long sampleIndex) {
        long expected = counters.getOrDefault(
                session.getSessionId(), session.getReceivedSamples() == null ? 0L : session.getReceivedSamples());
        return sampleIndex == expected;
    }

    private boolean acceptsMonotonicTime(MotionCaptureSession session, long monotonicMs) {
        if (monotonicMs < 0L) {
            return false;
        }
        Long previous = lastMonotonicMs.get(session.getSessionId());
        return previous == null || monotonicMs > previous;
    }

    private void rejectIntegrity(MotionCaptureSession session, Instant receivedAt, String reason) {
        session.setStatus("rejected_integrity");
        session.setQualityStatus("rejected_" + reason);
        session.setCompletedAt(receivedAt);
        session.setRawDataSha256(sha256(session));
        counters.remove(session.getSessionId());
        lastMonotonicMs.remove(session.getSessionId());
        sessions.save(session);
        audit("motion_capture_integrity_rejected", session, "device:" + session.getDeviceId(),
                Map.of("reason", reason));
    }

    private CaptureIntegrity captureIntegrity(MotionCaptureSession session) {
        Path path = storageRoot.resolve(session.getRawDataPath()).normalize();
        if (!path.startsWith(storageRoot) || !Files.isRegularFile(path)) {
            return new CaptureIntegrity(false, "missing_archive");
        }
        long expectedIndex = 0L;
        long previousMonotonicMs = -1L;
        long rows = 0L;
        try (var reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            for (String line; (line = reader.readLine()) != null;) {
                if (line == null || line.isBlank()) {
                    continue;
                }
                JsonNode row = objectMapper.readTree(line);
                if (!row.isObject() || !validCanonicalSample((ObjectNode) row)
                        || !acceptsIdentity(session, row)) {
                    return new CaptureIntegrity(false, "invalid_row");
                }
                if (row.path("sampleIndex").asLong(-1L) != expectedIndex) {
                    return new CaptureIntegrity(false, "sample_index");
                }
                long monotonicMs = row.path("monotonicMs").asLong(-1L);
                if (monotonicMs <= previousMonotonicMs) {
                    return new CaptureIntegrity(false, "monotonic_time");
                }
                previousMonotonicMs = monotonicMs;
                expectedIndex++;
                rows++;
            }
        } catch (IOException exception) {
            return new CaptureIntegrity(false, "unreadable_archive");
        }
        long received = session.getReceivedSamples() == null ? 0L : session.getReceivedSamples();
        long expected = serverExpectedSamples(session);
        if (rows == 0L || rows != received) {
            return new CaptureIntegrity(false, "row_count");
        }
        if (expected <= 0L || rows / (double) expected < MINIMUM_COMPLETENESS_RATIO) {
            return new CaptureIntegrity(false, "incomplete");
        }
        return new CaptureIntegrity(true, "accepted");
    }

    private String sha256(MotionCaptureSession session) {
        try {
            Path path = storageRoot.resolve(session.getRawDataPath()).normalize();
            if (!path.startsWith(storageRoot) || !Files.isRegularFile(path)) {
                return null;
            }
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (var stream = Files.newInputStream(path)) {
                byte[] buffer = new byte[8192];
                for (int count; (count = stream.read(buffer)) > 0;) {
                    digest.update(buffer, 0, count);
                }
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (IOException | NoSuchAlgorithmException exception) {
            return null;
        }
    }

    private static String safeSessionId(String candidate) {
        String value = candidate == null ? "" : candidate.trim();
        if (value.isEmpty()) {
            return "motion-" + UUID.randomUUID();
        }
        if (!value.matches("[A-Za-z0-9_.-]{1,120}")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "sessionId contains unsupported characters");
        }
        return value;
    }

    private static String safeStatus(String value) {
        return value == null ? "failed" : value.replaceAll("[^A-Za-z0-9_.-]", "_");
    }

    private static String text(JsonNode node, String name) {
        String value = node.path(name).asText("").trim();
        return value.isEmpty() ? null : value;
    }

    private static String blankToNull(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }

    private static long expectedSamples(Integer durationMs, Integer sampleRateHz) {
        if (durationMs == null || sampleRateHz == null || durationMs <= 0 || sampleRateHz <= 0) {
            return 0L;
        }
        // Match the ESP32's integer `durationMs / samplePeriodMs` contract.
        return Math.max(1L, (durationMs.longValue() * sampleRateHz) / 1_000L);
    }

    private static boolean zeroOrNull(Long value) {
        return value == null || value == 0L;
    }

    private static Long longValue(JsonNode node, String name) {
        JsonNode value = node.path(name);
        return value.isIntegralNumber() && value.asLong() >= 0L ? value.asLong() : null;
    }

    private static Integer intValue(JsonNode node, String name) {
        JsonNode value = node.path(name);
        return value.isIntegralNumber() && value.asInt() > 0 ? value.asInt() : null;
    }

    private StateMetadata mergeDeviceCounts(MotionCaptureSession session, ObjectNode message) {
        long expected = serverExpectedSamples(session);
        session.setSampleRateHz(SAMPLE_RATE_HZ);
        session.setExpectedSamples(expected);
        Integer deviceRate = intValue(message, "sampleRateHz");
        Long deviceExpected = longValue(message, "expectedSamples");
        Long attempted = longValue(message, "attemptedSamples");
        Long backpressure = longValue(message, "droppedBackpressureSamples");
        Long sensor = longValue(message, "droppedSensorSamples");
        if (deviceRate == null || deviceRate != SAMPLE_RATE_HZ || deviceExpected == null || deviceExpected != expected) {
            return new StateMetadata(false, "state_metadata");
        }
        if (attempted == null || backpressure == null || sensor == null || attempted < backpressure + sensor) {
            return new StateMetadata(false, "state_counts");
        }
        session.setAttemptedSamples(attempted);
        session.setDroppedBackpressureSamples(backpressure);
        session.setDroppedSensorSamples(sensor);
        return new StateMetadata(true, "accepted");
    }

    private static boolean isNonNegativeInteger(JsonNode node) {
        return node.isIntegralNumber() && node.asLong() >= 0L;
    }

    private static long serverExpectedSamples(MotionCaptureSession session) {
        return expectedSamples(session.getDurationMs(), SAMPLE_RATE_HZ);
    }

    private static String completionRejection(
            StateMetadata metadata,
            MotionCaptureSession session,
            CaptureIntegrity integrity
    ) {
        if (!metadata.valid()) {
            return metadata.reason();
        }
        long expected = serverExpectedSamples(session);
        if (session.getAttemptedSamples() == null || session.getAttemptedSamples() != expected) {
            return "attempt_count";
        }
        if (!zeroOrNull(session.getDroppedSensorSamples())) {
            return "sensor_loss";
        }
        if (!zeroOrNull(session.getDroppedBackpressureSamples())) {
            return "transport_backpressure";
        }
        if (session.getCompletenessRatio() < MINIMUM_COMPLETENESS_RATIO) {
            return "incomplete";
        }
        return integrity.complete() ? null : integrity.reason();
    }

    private void rejectMalformedSample(ObjectNode row, Instant receivedAt) {
        String sessionId = text(row, "sessionId");
        if (sessionId == null) {
            sessionId = text(row, "s");
        }
        if (sessionId == null) {
            return;
        }
        MotionCaptureSession session = sessions.findBySessionId(sessionId).orElse(null);
        if (session != null && ("queued".equals(session.getStatus()) || "capturing".equals(session.getStatus()))) {
            rejectIntegrity(session, receivedAt, "invalid_sample");
        }
    }

    private static double completeness(MotionCaptureSession session) {
        long expected = session.getExpectedSamples() == null ? 0L : session.getExpectedSamples();
        long received = session.getReceivedSamples() == null ? 0L : session.getReceivedSamples();
        if (expected <= 0L) {
            return 0.0;
        }
        return Math.max(0.0, Math.min(1.0, received / (double) expected));
    }

    private void audit(String eventType, MotionCaptureSession session, String actor, Map<String, ?> details) {
        if (audit == null) {
            return;
        }
        Map<String, Object> payload = new java.util.LinkedHashMap<>();
        payload.put("sessionId", session.getSessionId());
        payload.put("cattleId", session.getCattleId());
        payload.put("deviceId", session.getDeviceId());
        payload.put("barnId", session.getBarnId());
        payload.putAll(details);
        audit.record(eventType, actor, "motion_capture_session", session.getSessionId(), payload);
    }

    private static MotionCaptureClinicalReviewDto toClinicalReviewDto(MotionCaptureClinicalReview review) {
        return new MotionCaptureClinicalReviewDto(
                review.getSessionId(),
                review.getCattleId(),
                review.getLamenessScore(),
                review.getGaitReviewer(),
                review.getHoofExaminer(),
                review.getVeterinarian(),
                review.getHoofFinding(),
                review.getClinicalEvidenceReference(),
                review.getClinicallyVerifiedAt(),
                review.getReviewedAt());
    }

    private static boolean completeClinicalReview(MotionCaptureClinicalReview review) {
        return review != null
                && review.getLamenessScore() != null
                && review.getLamenessScore() >= 0
                && review.getLamenessScore() <= 3
                && present(review.getGaitReviewer())
                && present(review.getHoofExaminer())
                && present(review.getVeterinarian())
                && present(review.getHoofFinding())
                && present(review.getClinicalEvidenceReference())
                && review.getClinicallyVerifiedAt() != null;
    }

    private static boolean present(String value) {
        return value != null && !value.isBlank();
    }

    private record CaptureIntegrity(boolean complete, String reason) {
    }

    private record StateMetadata(boolean valid, String reason) {
    }
}
