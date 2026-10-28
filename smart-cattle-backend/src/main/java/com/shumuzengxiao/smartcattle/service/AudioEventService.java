package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.shumuzengxiao.smartcattle.domain.AudioEvent;
import com.shumuzengxiao.smartcattle.domain.AudioEventMetadata;
import com.shumuzengxiao.smartcattle.domain.AudioEventReview;
import com.shumuzengxiao.smartcattle.dto.AudioEventDto;
import com.shumuzengxiao.smartcattle.dto.AudioTrainingLineageDto;
import com.shumuzengxiao.smartcattle.dto.AudioReviewRequest;
import com.shumuzengxiao.smartcattle.repository.AudioEventMetadataRepository;
import com.shumuzengxiao.smartcattle.repository.AudioEventRepository;
import com.shumuzengxiao.smartcattle.repository.AudioEventReviewRepository;
import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.DigestOutputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.Base64;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.regex.Pattern;

@Service
public class AudioEventService {
    private static final Pattern SAFE_FILE_NAME = Pattern.compile("[A-Za-z0-9._-]+");
    // 2 s of 8 kHz signed PCM is 16,000 bytes before the WAV header.
    private static final int DEFAULT_MAX_CLIP_BYTES = 20_000;

    private final AudioEventRepository audioEvents;
    private final AudioEventMetadataRepository metadataRepository;
    private final AudioEventReviewRepository reviewRepository;
    private final ObjectMapper objectMapper;
    private final AuditTrailService audit;

    @Value("${app.audio.storage-dir:../audio-clips}")
    private String storageDirectory = "../audio-clips";

    @Value("${app.audio.max-clip-bytes:20000}")
    private int maxClipBytes = DEFAULT_MAX_CLIP_BYTES;

    private Path storageRoot;

    public AudioEventService(
            AudioEventRepository audioEvents,
            AudioEventMetadataRepository metadataRepository,
            AudioEventReviewRepository reviewRepository,
            ObjectMapper objectMapper
    ) {
        this(audioEvents, metadataRepository, reviewRepository, objectMapper, null);
    }

    @Autowired
    public AudioEventService(
            AudioEventRepository audioEvents,
            AudioEventMetadataRepository metadataRepository,
            AudioEventReviewRepository reviewRepository,
            ObjectMapper objectMapper,
            AuditTrailService audit
    ) {
        this.audioEvents = audioEvents;
        this.metadataRepository = metadataRepository;
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
            throw new IllegalStateException("Cannot create audio clip storage", exception);
        }
    }

    public List<AudioEventDto> recentEvents() {
        return recentEvents(null);
    }

    public List<AudioEventDto> recentEvents(String barnId) {
        List<AudioEvent> events = (barnId == null || barnId.isBlank()
                ? audioEvents.findTop100ByOrderByRecordedAtDesc()
                : audioEvents.findTop100ByBarnIdOrderByRecordedAtDesc(barnId.trim())).stream()
                .filter(event -> !isMockEvent(event))
                .limit(20)
                .toList();
        Collection<Long> ids = events.stream().map(AudioEvent::getId).toList();
        Map<Long, AudioEventMetadata> metadata = new LinkedHashMap<>();
        metadataRepository.findByAudioEventIdIn(ids)
                .forEach(item -> metadata.put(item.getAudioEventId(), item));
        Map<Long, AudioEventReview> reviews = new LinkedHashMap<>();
        reviewRepository.findByAudioEventIdIn(ids)
                .forEach(item -> reviews.put(item.getAudioEventId(), item));
        return events.stream()
                .map(event -> toDto(event, metadata.get(event.getId()), reviews.get(event.getId())))
                .toList();
    }

    public AudioEventDto ingestEdgeEvent(ObjectNode message, Instant receivedAt) {
        String deviceId = boundedText(message.path("deviceId").asText("edge_audio"), 80);
        String edgeEventId = boundedText(message.path("edgeEventId").asText(""), 80);
        String bootId = token(message.path("bootId").asText(""), "");
        String sourceKey = edgeEventId.isBlank() ? null
                : bootId.isBlank() ? deviceId + ":" + edgeEventId
                : deviceId + ":" + bootId + ":" + edgeEventId;
        if (sourceKey != null) {
            Optional<AudioEventMetadata> existing = metadataRepository.findBySourceKey(sourceKey);
            if (existing.isPresent()) {
                return audioEvents.findById(existing.get().getAudioEventId())
                        .map(event -> toDto(event, existing.get(),
                                reviewRepository.findByAudioEventId(event.getId()).orElse(null)))
                        .orElseThrow(() -> new IllegalStateException("Audio event metadata points to a missing event"));
            }
        }

        AudioEvent event = new AudioEvent();
        event.setDeviceId(deviceId);
        event.setBarnId(boundedText(message.path("barnId").asText("barn_01"), 80));
        event.setEventType(token(message.path("eventType").asText("acoustic_candidate"), "acoustic_candidate"));
        event.setScore(score(message.path("score")));
        event.setDurationMs(duration(message.path("durationMs").asInt(0)));
        event.setSnr(number(message.path("snr"), -120.0, 120.0));
        event.setRecordedAt(receivedAt);

        Recording recording = decodeRecording(message.path("recording"));
        StoredRecording storedRecording = null;
        if (recording != null) {
            storedRecording = writeWav(recording, deviceId, receivedAt);
            event.setAudioClipPath(storedRecording.path());
        }
        event = audioEvents.save(event);

        JsonNode features = message.path("features");
        JsonNode model = message.path("model");
        AudioEventMetadata metadata = new AudioEventMetadata();
        metadata.setAudioEventId(event.getId());
        metadata.setSourceKey(sourceKey);
        metadata.setCattleId(blankToNull(boundedText(message.path("cattleId").asText(""), 80)));
        metadata.setModelVersion(boundedText(model.path("version").asText("unknown"), 120));
        metadata.setModelStatus(token(model.path("status").asText("feature_only"), "feature_only"));
        metadata.setApprovedByServer(model.path("approvedByServer").asBoolean(false));
        metadata.setScreeningEligible(model.path("screeningEligible").asBoolean(false));
        metadata.setApprovalReason(token(model.path("approvalReason").asText("unknown"), "unknown"));
        metadata.setPredictedLabel(token(message.path("label").asText("unclassified"), "unclassified"));
        metadata.setClipAvailable(recording != null);
        metadata.setClipSha256(storedRecording == null ? null : storedRecording.sha256());
        metadata.setRms(number(features.path("rms"), 0.0, 1.0));
        metadata.setDbfs(number(features.path("dbfs"), -160.0, 20.0));
        metadata.setZeroCrossingRate(number(features.path("zcr"), 0.0, 1.0));
        metadata.setLowBandRatio(number(features.path("lowBand"), 0.0, 1.0));
        metadata.setMidBandRatio(number(features.path("midBand"), 0.0, 1.0));
        metadata.setHighBandRatio(number(features.path("highBand"), 0.0, 1.0));
        metadata.setSaturationRatio(number(features.path("saturation"), 0.0, 1.0));
        metadata.setFeaturesJson(featuresJson(features));
        metadata = metadataRepository.save(metadata);
        auditArchivedEvent(event, metadata);
        return toDto(event, metadata, null);
    }

    public AudioEventDto review(Long eventId, AudioReviewRequest request) {
        AudioEvent event = audioEvents.findById(eventId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Audio event not found"));
        AudioEventReview review = reviewRepository.findByAudioEventId(eventId)
                .orElseGet(AudioEventReview::new);
        review.setAudioEventId(eventId);
        review.setStatus(request.status());
        review.setLabel(boundedText(request.label(), 80));
        review.setNote(boundedText(request.note(), 1200));
        review.setReviewer(boundedText(request.reviewer(), 80));
        if (Boolean.TRUE.equals(request.clinicallyVerified())) {
            review.setAnimalId(boundedText(request.animalId(), 120));
            review.setRecordingSessionId(boundedText(request.recordingSessionId(), 120));
            review.setVeterinarian(boundedText(request.veterinarian(), 80));
            review.setClinicalEvidenceReference(boundedText(request.clinicalEvidenceReference(), 1200));
            review.setClinicallyVerifiedAt(Instant.now());
        } else {
            review.setAnimalId(null);
            review.setRecordingSessionId(null);
            review.setVeterinarian(null);
            review.setClinicalEvidenceReference(null);
            review.setClinicallyVerifiedAt(null);
        }
        review.setReviewedAt(Instant.now());
        review = reviewRepository.save(review);
        if (audit != null) {
            Map<String, Object> details = new LinkedHashMap<>();
            details.put("eventId", eventId);
            details.put("status", review.getStatus());
            details.put("label", review.getLabel());
            details.put("clinicalAnimalId", review.getAnimalId());
            details.put("recordingSessionId", review.getRecordingSessionId());
            details.put("veterinarian", review.getVeterinarian());
            details.put("clinicallyVerifiedAt", review.getClinicallyVerifiedAt());
            audit.record("audio_event_reviewed", review.getReviewer(), "audio_event", String.valueOf(eventId), details);
        }
        return toDto(event, metadataRepository.findByAudioEventId(eventId).orElse(null), review);
    }

    /**
     * Rechecks the immutable audio archive immediately before a release trainer
     * consumes it. The trainer compares this response with its local manifest;
     * a locally edited manifest therefore cannot create an approved disease label.
     */
    public AudioTrainingLineageDto trainingLineage(Long eventId) {
        AudioEvent event = audioEvents.findById(eventId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Audio event not found"));
        AudioEventMetadata metadata = metadataRepository.findByAudioEventId(eventId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.CONFLICT, "Audio event metadata is incomplete"));
        AudioEventReview review = reviewRepository.findByAudioEventId(eventId).orElse(null);
        verifiedClipPath(event, metadata);

        return new AudioTrainingLineageDto(
                event.getId(),
                event.getDeviceId(),
                event.getBarnId(),
                metadata.getCattleId(),
                event.getAudioClipPath(),
                metadata.getClipSha256(),
                true,
                Instant.now(),
                review == null ? "pending" : review.getStatus(),
                review == null ? null : review.getLabel(),
                review == null ? null : review.getAnimalId(),
                review == null ? null : review.getRecordingSessionId(),
                review == null ? null : review.getVeterinarian(),
                review == null ? null : review.getClinicalEvidenceReference(),
                review == null ? null : review.getClinicallyVerifiedAt(),
                event.getRecordedAt());
    }

    public Path resolveClip(String fileName) {
        if (fileName == null || !SAFE_FILE_NAME.matcher(fileName).matches()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Audio clip not found");
        }
        Path candidate = storageRoot.resolve(fileName).normalize();
        if (!candidate.startsWith(storageRoot) || !Files.isRegularFile(candidate)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Audio clip not found");
        }
        String apiPath = "/api/audio-clips/" + fileName;
        AudioEvent event = audioEvents.findByAudioClipPath(apiPath)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Audio clip metadata not found"));
        AudioEventMetadata metadata = metadataRepository.findByAudioEventId(event.getId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.CONFLICT, "Audio clip metadata is incomplete"));
        return verifiedClipPath(event, metadata);
    }

    private Path verifiedClipPath(AudioEvent event, AudioEventMetadata metadata) {
        String apiPath = event.getAudioClipPath();
        if (apiPath == null || !apiPath.startsWith("/api/audio-clips/")) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Audio clip metadata is incomplete");
        }
        String fileName = apiPath.substring("/api/audio-clips/".length());
        if (!SAFE_FILE_NAME.matcher(fileName).matches()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Audio clip metadata is incomplete");
        }
        Path candidate = storageRoot.resolve(fileName).normalize();
        if (!candidate.startsWith(storageRoot) || !Files.isRegularFile(candidate)
                || !Boolean.TRUE.equals(metadata.getClipAvailable()) || metadata.getClipSha256() == null
                || !constantTimeEquals(metadata.getClipSha256(), sha256(candidate))) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Audio clip integrity check failed");
        }
        return candidate;
    }

    private AudioEventDto toDto(AudioEvent event, AudioEventMetadata metadata, AudioEventReview review) {
        boolean clipAvailable = metadata != null
                ? Boolean.TRUE.equals(metadata.getClipAvailable())
                : event.getAudioClipPath() != null && !event.getAudioClipPath().startsWith("/mock/");
        return new AudioEventDto(
                event.getId(),
                event.getDeviceId(),
                event.getBarnId(),
                metadata == null ? null : metadata.getCattleId(),
                event.getEventType(),
                metadata == null ? event.getEventType() : metadata.getPredictedLabel(),
                event.getScore(),
                event.getDurationMs(),
                event.getSnr(),
                event.getAudioClipPath(),
                clipAvailable,
                metadata == null ? null : metadata.getClipSha256(),
                metadata == null ? null : metadata.getModelVersion(),
                metadata == null ? null : metadata.getModelStatus(),
                metadata == null ? null : metadata.getApprovedByServer(),
                metadata == null ? null : metadata.getScreeningEligible(),
                metadata == null ? null : metadata.getApprovalReason(),
                metadata == null ? null : metadata.getRms(),
                metadata == null ? null : metadata.getDbfs(),
                metadata == null ? null : metadata.getZeroCrossingRate(),
                metadata == null ? null : metadata.getLowBandRatio(),
                metadata == null ? null : metadata.getMidBandRatio(),
                metadata == null ? null : metadata.getHighBandRatio(),
                metadata == null ? null : metadata.getSaturationRatio(),
                review == null ? "pending" : review.getStatus(),
                review == null ? null : review.getLabel(),
                review == null ? null : review.getNote(),
                review == null ? null : review.getReviewer(),
                review == null ? null : review.getReviewedAt(),
                review == null ? null : review.getAnimalId(),
                review == null ? null : review.getRecordingSessionId(),
                review == null ? null : review.getVeterinarian(),
                review == null ? null : review.getClinicalEvidenceReference(),
                review == null ? null : review.getClinicallyVerifiedAt(),
                event.getRecordedAt());
    }

    private Recording decodeRecording(JsonNode recording) {
        if (recording == null || !recording.isObject() ||
                !"pcm_s8le".equals(recording.path("encoding").asText())) {
            return null;
        }
        int sampleRate = recording.path("sampleRate").asInt(0);
        String encoded = recording.path("pcm8").asText("");
        if (sampleRate < 4_000 || sampleRate > 16_000 || encoded.isBlank() ||
                encoded.length() > maximumBase64Length(maxClipBytes)) {
            return null;
        }
        try {
            byte[] pcm = Base64.getDecoder().decode(encoded);
            if (pcm.length == 0 || pcm.length > maxClipBytes) {
                return null;
            }
            return new Recording(sampleRate, pcm);
        } catch (IllegalArgumentException exception) {
            return null;
        }
    }

    private StoredRecording writeWav(Recording recording, String deviceId, Instant receivedAt) {
        String fileName = receivedAt.toEpochMilli() + "-" + token(deviceId, "edge") + ".wav";
        Path destination = storageRoot.resolve(fileName);
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (OutputStream output = new DigestOutputStream(Files.newOutputStream(destination,
                    StandardOpenOption.CREATE_NEW), digest)) {
            int dataLength = recording.pcm().length;
            writeAscii(output, "RIFF");
            writeLittleEndianInt(output, 36 + dataLength);
            writeAscii(output, "WAVEfmt ");
            writeLittleEndianInt(output, 16);
            writeLittleEndianShort(output, 1);
            writeLittleEndianShort(output, 1);
            writeLittleEndianInt(output, recording.sampleRate());
            writeLittleEndianInt(output, recording.sampleRate());
            writeLittleEndianShort(output, 1);
            writeLittleEndianShort(output, 8);
            writeAscii(output, "data");
            writeLittleEndianInt(output, dataLength);
            for (byte sample : recording.pcm()) {
                output.write((sample + 128) & 0xFF);
            }
            }
            return new StoredRecording("/api/audio-clips/" + fileName,
                    java.util.HexFormat.of().formatHex(digest.digest()));
        } catch (IOException | NoSuchAlgorithmException exception) {
            throw new IllegalStateException("Cannot save audio clip", exception);
        }
    }

    private void auditArchivedEvent(AudioEvent event, AudioEventMetadata metadata) {
        if (audit == null) {
            return;
        }
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("eventId", event.getId());
        details.put("sourceKey", metadata.getSourceKey());
        details.put("cattleId", metadata.getCattleId());
        details.put("modelVersion", metadata.getModelVersion());
        details.put("modelStatus", metadata.getModelStatus());
        details.put("predictedLabel", metadata.getPredictedLabel());
        details.put("clipAvailable", metadata.getClipAvailable());
        details.put("clipSha256", metadata.getClipSha256());
        audit.record("audio_event_archived", "device:" + event.getDeviceId(), "audio_event",
                String.valueOf(event.getId()), details);
    }

    private static String sha256(Path path) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (var input = Files.newInputStream(path)) {
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
        return actual != null && MessageDigest.isEqual(
                expected.getBytes(java.nio.charset.StandardCharsets.US_ASCII),
                actual.getBytes(java.nio.charset.StandardCharsets.US_ASCII));
    }

    private static void writeAscii(OutputStream output, String value) throws IOException {
        output.write(value.getBytes(java.nio.charset.StandardCharsets.US_ASCII));
    }

    private static void writeLittleEndianInt(OutputStream output, int value) throws IOException {
        output.write(value & 0xFF);
        output.write((value >>> 8) & 0xFF);
        output.write((value >>> 16) & 0xFF);
        output.write((value >>> 24) & 0xFF);
    }

    private static void writeLittleEndianShort(OutputStream output, int value) throws IOException {
        output.write(value & 0xFF);
        output.write((value >>> 8) & 0xFF);
    }

    private String featuresJson(JsonNode features) {
        if (features == null || !features.isObject()) {
            return null;
        }
        try {
            String value = objectMapper.writeValueAsString(features);
            return value.length() <= 4096 ? value : value.substring(0, 4096);
        } catch (JsonProcessingException exception) {
            return null;
        }
    }

    private static Double score(JsonNode node) {
        return number(node, 0.0, 1.0);
    }

    private static Double number(JsonNode node, double minimum, double maximum) {
        if (node == null || !node.isNumber()) {
            return null;
        }
        double value = node.asDouble();
        return Double.isFinite(value) && value >= minimum && value <= maximum ? value : null;
    }

    private static Integer duration(int value) {
        return value > 0 && value <= 120_000 ? value : null;
    }

    private static int maximumBase64Length(int byteCount) {
        return ((Math.max(0, byteCount) + 2) / 3) * 4;
    }

    private static String token(String value, String fallback) {
        String cleaned = boundedText(value, 80).replaceAll("[^A-Za-z0-9_.-]", "_");
        return cleaned.isBlank() ? fallback : cleaned;
    }

    private static String boundedText(String value, int maximumLength) {
        if (value == null) {
            return "";
        }
        String trimmed = value.trim();
        return trimmed.length() <= maximumLength ? trimmed : trimmed.substring(0, maximumLength);
    }

    private static String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private static boolean isMockEvent(AudioEvent event) {
        return event.getAudioClipPath() != null && event.getAudioClipPath().startsWith("/mock/");
    }

    private record Recording(int sampleRate, byte[] pcm) {
    }

    private record StoredRecording(String path, String sha256) {
    }
}
