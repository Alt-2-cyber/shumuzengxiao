package com.shumuzengxiao.smartcattle.service;

import com.shumuzengxiao.smartcattle.domain.ClinicalCheck;
import com.shumuzengxiao.smartcattle.domain.AudioEvent;
import com.shumuzengxiao.smartcattle.domain.AudioEventMetadata;
import com.shumuzengxiao.smartcattle.domain.VisionEvent;
import com.shumuzengxiao.smartcattle.repository.AudioEventMetadataRepository;
import com.shumuzengxiao.smartcattle.repository.AudioEventRepository;
import com.shumuzengxiao.smartcattle.repository.ClinicalCheckRepository;
import com.shumuzengxiao.smartcattle.repository.VisionEventRepository;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

/** Reloads recent evidence after a process restart; expired evidence is still
 * rejected by the screening window itself. */
@Service
public class EvidenceHydrationService {
    private final ClinicalCheckRepository clinicalChecks;
    private final VisionEventRepository visionEvents;
    private final AudioEventRepository audioEvents;
    private final AudioEventMetadataRepository audioMetadata;
    private final HealthScreeningService healthScreeningService;

    public EvidenceHydrationService(
            ClinicalCheckRepository clinicalChecks,
            VisionEventRepository visionEvents,
            AudioEventRepository audioEvents,
            AudioEventMetadataRepository audioMetadata,
            HealthScreeningService healthScreeningService
    ) {
        this.clinicalChecks = clinicalChecks;
        this.visionEvents = visionEvents;
        this.audioEvents = audioEvents;
        this.audioMetadata = audioMetadata;
        this.healthScreeningService = healthScreeningService;
    }

    @PostConstruct
    void hydrate() {
        for (ClinicalCheck check : clinicalChecks.findTop500ByOrderByRecordedAtDesc()) {
            healthScreeningService.recordClinicalCheck(
                    check.getCattleId(), check.getCheckType(),
                    Boolean.TRUE.equals(check.getVerified()),
                    Boolean.TRUE.equals(check.getAlert()),
                    check.getValue(), check.getEvidenceType(), check.getRecordedAt());
        }
        for (VisionEvent event : visionEvents.findTop500ByOrderByRecordedAtDesc()) {
            if (Boolean.TRUE.equals(event.getScreeningEligible())) {
                healthScreeningService.recordVisionEvidence(
                        event.getTargetId(), event.getEventType(), event.getScore(), event.getRecordedAt());
            }
        }

        List<AudioEvent> events = audioEvents.findTop100ByOrderByRecordedAtDesc();
        if (events.isEmpty()) {
            return;
        }
        Map<Long, AudioEventMetadata> metadataByEvent = audioMetadata.findByAudioEventIdIn(
                        events.stream().map(AudioEvent::getId).toList())
                .stream()
                .collect(Collectors.toMap(AudioEventMetadata::getAudioEventId, Function.identity()));
        for (AudioEvent event : events) {
            AudioEventMetadata metadata = metadataByEvent.get(event.getId());
            if (metadata == null || !Boolean.TRUE.equals(metadata.getScreeningEligible())
                    || metadata.getCattleId() == null || metadata.getCattleId().isBlank()) {
                continue;
            }
            String evidenceId = metadata.getSourceKey() == null || metadata.getSourceKey().isBlank()
                    ? "audio:" + event.getId()
                    : metadata.getSourceKey();
            healthScreeningService.recordAudioEvidence(
                    metadata.getCattleId(),
                    metadata.getPredictedLabel(),
                    event.getScore(),
                    true,
                    event.getRecordedAt(),
                    evidenceId);
        }
    }
}
