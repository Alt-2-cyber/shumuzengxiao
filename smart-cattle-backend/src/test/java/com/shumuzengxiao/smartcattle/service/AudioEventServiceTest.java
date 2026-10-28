package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.shumuzengxiao.smartcattle.domain.AudioEvent;
import com.shumuzengxiao.smartcattle.domain.AudioEventMetadata;
import com.shumuzengxiao.smartcattle.domain.AudioEventReview;
import com.shumuzengxiao.smartcattle.dto.AudioEventDto;
import com.shumuzengxiao.smartcattle.dto.AudioTrainingLineageDto;
import com.shumuzengxiao.smartcattle.repository.AudioEventMetadataRepository;
import com.shumuzengxiao.smartcattle.repository.AudioEventRepository;
import com.shumuzengxiao.smartcattle.repository.AudioEventReviewRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.server.ResponseStatusException;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.Base64;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class AudioEventServiceTest {
    @TempDir
    Path storage;

    @Test
    void archivesAndVerifiesTheAudioClipHashBeforeServingIt() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        AudioEventRepository events = mock(AudioEventRepository.class);
        AudioEventMetadataRepository metadata = mock(AudioEventMetadataRepository.class);
        AudioEventReviewRepository reviews = mock(AudioEventReviewRepository.class);
        AudioEventService service = new AudioEventService(events, metadata, reviews, mapper);
        ReflectionTestUtils.setField(service, "storageDirectory", storage.toString());
        service.prepareStorage();

        AtomicReference<AudioEvent> savedEvent = new AtomicReference<>();
        AtomicReference<AudioEventMetadata> savedMetadata = new AtomicReference<>();
        when(events.save(any(AudioEvent.class))).thenAnswer(invocation -> {
            AudioEvent event = invocation.getArgument(0);
            event.setId(7L);
            savedEvent.set(event);
            return event;
        });
        when(metadata.save(any(AudioEventMetadata.class))).thenAnswer(invocation -> {
            AudioEventMetadata item = invocation.getArgument(0);
            savedMetadata.set(item);
            return item;
        });

        AudioEventDto dto = service.ingestEdgeEvent(edgeEvent(mapper), Instant.parse("2026-07-19T12:00:00Z"));
        assertThat(dto.clipSha256()).hasSize(64);
        assertThat(savedMetadata.get().getClipSha256()).isEqualTo(dto.clipSha256());

        when(events.findByAudioClipPath(dto.audioClipPath())).thenReturn(Optional.of(savedEvent.get()));
        when(metadata.findByAudioEventId(7L)).thenReturn(Optional.of(savedMetadata.get()));
        String fileName = dto.audioClipPath().substring(dto.audioClipPath().lastIndexOf('/') + 1);
        Path clip = service.resolveClip(fileName);
        assertThat(clip).isRegularFile();

        Files.writeString(clip, "tampered", java.nio.file.StandardOpenOption.APPEND);
        assertThatThrownBy(() -> service.resolveClip(fileName))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("integrity check failed");
    }

    @Test
    void returnsOnlyRehashedClinicalTrainingLineage() {
        ObjectMapper mapper = new ObjectMapper();
        AudioEventRepository events = mock(AudioEventRepository.class);
        AudioEventMetadataRepository metadata = mock(AudioEventMetadataRepository.class);
        AudioEventReviewRepository reviews = mock(AudioEventReviewRepository.class);
        AudioEventService service = new AudioEventService(events, metadata, reviews, mapper);
        ReflectionTestUtils.setField(service, "storageDirectory", storage.toString());
        service.prepareStorage();

        AtomicReference<AudioEvent> savedEvent = new AtomicReference<>();
        AtomicReference<AudioEventMetadata> savedMetadata = new AtomicReference<>();
        when(events.save(any(AudioEvent.class))).thenAnswer(invocation -> {
            AudioEvent event = invocation.getArgument(0);
            event.setId(9L);
            savedEvent.set(event);
            return event;
        });
        when(metadata.save(any(AudioEventMetadata.class))).thenAnswer(invocation -> {
            AudioEventMetadata item = invocation.getArgument(0);
            savedMetadata.set(item);
            return item;
        });
        service.ingestEdgeEvent(edgeEvent(mapper), Instant.parse("2026-07-19T12:00:00Z"));

        AudioEventReview review = new AudioEventReview();
        review.setStatus("confirmed");
        review.setLabel("cough_suspect");
        review.setAnimalId("cow_001");
        review.setRecordingSessionId("session_001");
        review.setVeterinarian("vet_001");
        review.setClinicalEvidenceReference("clinical-ref-001");
        review.setClinicallyVerifiedAt(Instant.parse("2026-07-19T12:01:00Z"));
        when(events.findById(9L)).thenReturn(Optional.of(savedEvent.get()));
        when(metadata.findByAudioEventId(9L)).thenReturn(Optional.of(savedMetadata.get()));
        when(reviews.findByAudioEventId(9L)).thenReturn(Optional.of(review));

        AudioTrainingLineageDto lineage = service.trainingLineage(9L);

        assertThat(lineage.sourceEventId()).isEqualTo(9L);
        assertThat(lineage.clipIntegrityVerified()).isTrue();
        assertThat(lineage.clipSha256()).isEqualTo(savedMetadata.get().getClipSha256());
        assertThat(lineage.reviewLabel()).isEqualTo("cough_suspect");
        assertThat(lineage.clinicalAnimalId()).isEqualTo("cow_001");
    }

    private static ObjectNode edgeEvent(ObjectMapper mapper) {
        ObjectNode event = mapper.createObjectNode();
        event.put("deviceId", "edge-audio-01");
        event.put("barnId", "barn_01");
        event.put("cattleId", "cow_001");
        event.put("eventType", "acoustic_candidate");
        event.put("label", "moo");
        event.put("score", 0.82);
        event.put("durationMs", 1_000);
        event.put("snr", 12.0);
        ObjectNode recording = event.putObject("recording");
        recording.put("sampleRate", 8_000);
        recording.put("encoding", "pcm_s8le");
        recording.put("pcm8", Base64.getEncoder().encodeToString(new byte[]{0, 1, -1, 2}));
        return event;
    }
}
