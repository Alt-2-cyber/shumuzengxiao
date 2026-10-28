package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.util.ReflectionTestUtils;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class AudioResearchInferenceServiceTest {
    @TempDir Path temporary;
    private AudioResearchInferenceService service;
    private final ObjectMapper mapper = new ObjectMapper();

    @AfterEach
    void close() {
        if (service != null) service.close();
    }

    private Path prepare() throws Exception {
        service = spy(new AudioResearchInferenceService(mapper));
        Path model = temporary.resolve("model.json");
        Path script = temporary.resolve("predict.py");
        Files.writeString(model, "{}");
        Files.writeString(script, "# test-only predictor");
        ReflectionTestUtils.setField(service, "modelFile", model.toString());
        ReflectionTestUtils.setField(service, "scriptFile", script.toString());
        Path clip = temporary.resolve("clip.wav");
        Files.writeString(clip, "real-file-fixture");
        return clip;
    }

    private JsonNode prediction() throws Exception {
        return mapper.readTree("""
                {"research_only":true,"clinical_diagnosis":false,"model_version":"candidate-test",
                 "windows":[{"start_seconds":0,"end_seconds":1,"status":"scored","label":"cough","score":0.81}]}
                """);
    }

    @Test
    void cachesByActualClipAndModelContentAndForcesResearchScope() throws Exception {
        Path clip = prepare();
        doReturn(prediction()).when(service).executePrediction(any(Path.class), any(Path.class), any(Path.class));
        await().atMost(Duration.ofSeconds(3)).until(() -> "ready".equals(service.analyze(clip).path("status").asText()));
        JsonNode result = service.analyze(clip);
        assertThat(result.path("windows").get(0).path("label").asText()).isEqualTo("cough");
        assertThat(result.path("clinical_diagnosis").asBoolean()).isFalse();
        assertThat(result.path("screeningEligible").asBoolean()).isFalse();
        verify(service, times(1)).executePrediction(any(), any(), any());
        Files.writeString(clip, "different-real-file-fixture");
        await().atMost(Duration.ofSeconds(3)).until(() -> "ready".equals(service.analyze(clip).path("status").asText()));
        verify(service, times(2)).executePrediction(any(), any(), any());
    }

    @Test
    void missingModelDoesNotPretendToHaveAnalyzedAudio() throws Exception {
        Path clip = prepare();
        ReflectionTestUtils.setField(service, "modelFile", temporary.resolve("missing.json").toString());
        assertThat(service.analyze(clip).path("status").asText()).isEqualTo("model_unavailable");
        verify(service, never()).executePrediction(any(), any(), any());
    }

    @Test
    void rejectsDiseaseLabelsOrNonfiniteAndOutOfRangeScores() throws Exception {
        Path clip = prepare();
        JsonNode invalid = mapper.readTree("""
                {"research_only":true,"windows":[{"status":"scored","label":"FMD","score":1.2}]}
                """);
        doReturn(invalid).when(service).executePrediction(any(), any(), any());
        await().atMost(Duration.ofSeconds(3)).until(() -> "inference_failed".equals(service.analyze(clip).path("status").asText()));
        assertThat(service.analyze(clip).has("windows")).isFalse();
    }

    @Test
    void preservesAbstentionWithoutInventingNormalOrHealthy() throws Exception {
        Path clip = prepare();
        JsonNode quiet = mapper.readTree("""
                {"research_only":true,"model_version":"candidate-test",
                 "windows":[{"start_seconds":0,"end_seconds":1,"status":"abstain_silence","label":null,"score":null}]}
                """);
        doReturn(quiet).when(service).executePrediction(any(), any(), any());
        await().atMost(Duration.ofSeconds(3)).until(() -> "ready".equals(service.analyze(clip).path("status").asText()));
        JsonNode window = service.analyze(clip).path("windows").get(0);
        assertThat(window.path("status").asText()).isEqualTo("abstain_silence");
        assertThat(window.path("label").isNull()).isTrue();
    }
}
