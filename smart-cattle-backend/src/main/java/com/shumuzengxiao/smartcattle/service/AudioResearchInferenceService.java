package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.annotation.PreDestroy;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

/** Archived audio is analyzed separately from edge labels and clinical evidence. */
@Service
public class AudioResearchInferenceService {
    private static final Set<String> LABELS = Set.of("cough", "non_cough");
    private final ObjectMapper mapper;
    private record Inputs(String clip, String model, String script) {}
    private final Map<Inputs, CompletableFuture<JsonNode>> cache = new LinkedHashMap<>();
    private final ThreadPoolExecutor worker = new ThreadPoolExecutor(1, 1, 0L, TimeUnit.MILLISECONDS,
            new ArrayBlockingQueue<>(24), task -> {
                Thread thread = new Thread(task, "audio-research-inference");
                thread.setDaemon(true);
                return thread;
            });

    @Value("${app.audio.research.enabled:true}")
    private boolean enabled = true;
    @Value("${app.audio.research.python:python}")
    private String pythonExecutable = "python";
    @Value("${app.audio.research.script:../scripts/audio_expand_retrain_20261026.py}")
    private String scriptFile = "../scripts/audio_expand_retrain_20261026.py";
    @Value("${app.audio.research.model:../audio-training-data/artifacts/calf-cough-expanded-20261026/model.json}")
    private String modelFile = "../audio-training-data/artifacts/calf-cough-expanded-20261026/model.json";
    @Value("${app.audio.research.timeout-seconds:30}")
    private int timeoutSeconds = 30;

    public AudioResearchInferenceService(ObjectMapper mapper) {
        this.mapper = mapper;
    }

    public synchronized JsonNode analyze(Path verifiedClip) {
        if (!enabled) return state("disabled");
        Path model = Path.of(modelFile).toAbsolutePath().normalize();
        Path script = Path.of(scriptFile).toAbsolutePath().normalize();
        if (!Files.isRegularFile(model) || !Files.isRegularFile(script)) return state("model_unavailable");
        if (!Files.isRegularFile(verifiedClip)) return state("clip_unavailable");
        try {
            Inputs key = new Inputs(digest(verifiedClip), digest(model), digest(script));
            CompletableFuture<JsonNode> existing = cache.get(key);
            if (existing != null) return existing.isDone() ? existing.join().deepCopy() : state("pending");
            if (cache.size() >= 128) {
                cache.entrySet().removeIf(entry -> entry.getValue().isDone());
                if (cache.size() >= 128) return state("busy");
            }
            CompletableFuture<JsonNode> result = new CompletableFuture<>();
            cache.put(key, result);
            try {
                worker.execute(() -> {
                    try {
                        requireUnchanged(key, verifiedClip, model, script);
                        ObjectNode prediction = validate(executePrediction(verifiedClip, model, script));
                        requireUnchanged(key, verifiedClip, model, script);
                        prediction.put("clip_sha256", key.clip()).put("model_sha256", key.model());
                        result.complete(prediction);
                    } catch (Exception failure) {
                        result.complete(state("inference_failed"));
                    }
                });
            } catch (RejectedExecutionException busy) {
                cache.remove(key);
                return state("busy");
            }
            return state("pending");
        } catch (IOException failure) {
            return state("clip_unavailable");
        }
    }

    protected JsonNode executePrediction(Path clip, Path model, Path script) throws Exception {
        Path output = Files.createTempFile("cattle-audio-research-", ".json");
        Path errors = Files.createTempFile("cattle-audio-research-", ".log");
        Process process = null;
        try {
            process = new ProcessBuilder(pythonExecutable, script.toString(), "predict", clip.toString(),
                    "--model", model.toString()).redirectOutput(output.toFile()).redirectError(errors.toFile()).start();
            if (!process.waitFor(Math.max(1, Math.min(60, timeoutSeconds)), TimeUnit.SECONDS)) {
                throw new IOException("Research inference timed out");
            }
            if (process.exitValue() != 0 || Files.size(output) > 65_536) {
                throw new IOException("Research predictor did not return a bounded result");
            }
            return mapper.readTree(Files.readString(output));
        } finally {
            if (process != null && process.isAlive()) {
                process.destroyForcibly();
                process.waitFor(2, TimeUnit.SECONDS);
            }
            Files.deleteIfExists(output);
            Files.deleteIfExists(errors);
        }
    }

    private ObjectNode validate(JsonNode raw) {
        if (!raw.path("research_only").asBoolean(false) || raw.path("clinical_diagnosis").asBoolean(false)
                || !raw.path("windows").isArray() || raw.path("windows").size() > 32) {
            throw new IllegalArgumentException("Research output contract mismatch");
        }
        ObjectNode result = state("ready");
        result.put("score_semantics", "uncalibrated_cough_event_score");
        String version = raw.path("model_version").asText("unversioned");
        result.put("model_version", version.substring(0, Math.min(120, version.length())));
        ArrayNode windows = result.putArray("windows");
        for (JsonNode input : raw.path("windows")) {
            String status = input.path("status").asText("");
            double start = input.path("start_seconds").asDouble(Double.NaN);
            double end = input.path("end_seconds").asDouble(Double.NaN);
            if (!Double.isFinite(start) || !Double.isFinite(end) || start < 0 || end <= start || end > 120) {
                throw new IllegalArgumentException("Invalid audio window range");
            }
            ObjectNode window = windows.addObject();
            window.put("start_seconds", start).put("end_seconds", end).put("status", status);
            if ("scored".equals(status)) {
                String label = input.path("label").asText("");
                double score = input.path("score").asDouble(Double.NaN);
                if (!LABELS.contains(label) || !input.path("score").isNumber() || !Double.isFinite(score)
                        || score < 0 || score > 1) throw new IllegalArgumentException("Invalid acoustic event score");
                window.put("label", label).put("score", score);
            } else if (status.matches("abstain_[a-z_]{1,48}")) {
                window.putNull("label").putNull("score");
            } else {
                throw new IllegalArgumentException("Invalid acoustic window status");
            }
        }
        return result;
    }

    private ObjectNode state(String status) {
        return mapper.createObjectNode().put("status", status).put("research_only", true)
                .put("clinical_diagnosis", false).put("screeningEligible", false);
    }

    private static String digest(Path path) throws IOException {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    private static void requireUnchanged(Inputs expected, Path clip, Path model, Path script) throws IOException {
        if (!expected.equals(new Inputs(digest(clip), digest(model), digest(script)))) {
            throw new IOException("Research inference inputs changed during execution");
        }
    }

    @PreDestroy
    public void close() {
        worker.shutdownNow();
    }
}
