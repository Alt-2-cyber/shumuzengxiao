package com.shumuzengxiao.smartcattle.controller;

import com.shumuzengxiao.smartcattle.domain.*;
import com.shumuzengxiao.smartcattle.dto.AudioEventDto;
import com.shumuzengxiao.smartcattle.dto.AudioReviewRequest;
import com.shumuzengxiao.smartcattle.dto.AudioTrainingLineageDto;
import com.shumuzengxiao.smartcattle.dto.VisionEventDto;
import com.shumuzengxiao.smartcattle.dto.VisionEventRequest;
import com.shumuzengxiao.smartcattle.dto.VisionEventReviewRequest;
import com.shumuzengxiao.smartcattle.dto.VisionTrainingLineageDto;
import com.shumuzengxiao.smartcattle.repository.*;
import com.shumuzengxiao.smartcattle.service.AudioEventService;
import com.shumuzengxiao.smartcattle.service.VisionEventService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/events")
public class EventController {
    private final VisionEventRepository visionEvents;
    private final AudioEventService audioEventService;
    private final HealthRiskRepository healthRisks;
    private final AlertRecordRepository alerts;
    private final VisionEventService visionEventService;

    public EventController(
            VisionEventRepository visionEvents,
            AudioEventService audioEventService,
            HealthRiskRepository healthRisks,
            AlertRecordRepository alerts,
            VisionEventService visionEventService
    ) {
        this.visionEvents = visionEvents;
        this.audioEventService = audioEventService;
        this.healthRisks = healthRisks;
        this.alerts = alerts;
        this.visionEventService = visionEventService;
    }

    @GetMapping("/vision")
    public List<VisionEventDto> vision(
            @RequestParam(defaultValue = "barn_01") String barnId
    ) {
        return visionEventService.recentEvents(barnId);
    }

    @PostMapping("/vision")
    public VisionEvent addVision(@Valid @RequestBody VisionEventRequest event) {
        return visionEventService.ingest(event);
    }

    @PutMapping(value = "/vision/{eventId}/snapshot", consumes = "multipart/form-data")
    public VisionEventDto uploadVisionSnapshot(
            @PathVariable Long eventId,
            @RequestPart("file") org.springframework.web.multipart.MultipartFile file,
            @RequestHeader(value = "X-Snapshot-Sha256", required = false) String expectedSha256
    ) {
        return visionEventService.uploadSnapshot(eventId, file, expectedSha256);
    }

    @PutMapping("/vision/{eventId}/review")
    public VisionEventReview reviewVision(
            @PathVariable Long eventId,
            @Valid @RequestBody VisionEventReviewRequest request
    ) {
        return visionEventService.review(eventId, request);
    }

    @GetMapping("/vision/{eventId}/training-lineage")
    public VisionTrainingLineageDto visionTrainingLineage(@PathVariable Long eventId) {
        return visionEventService.trainingLineage(eventId);
    }

    @GetMapping("/audio")
    public List<AudioEventDto> audio(
            @RequestParam(defaultValue = "barn_01") String barnId
    ) {
        return audioEventService.recentEvents(barnId);
    }

    @PutMapping("/audio/{eventId}/review")
    public AudioEventDto reviewAudio(
            @PathVariable Long eventId,
            @Valid @RequestBody AudioReviewRequest request
    ) {
        return audioEventService.review(eventId, request);
    }

    @GetMapping("/audio/{eventId}/training-lineage")
    public AudioTrainingLineageDto audioTrainingLineage(@PathVariable Long eventId) {
        return audioEventService.trainingLineage(eventId);
    }

    @GetMapping("/health-risks")
    public List<HealthRisk> healthRisks(
            @RequestParam(defaultValue = "barn_01") String barnId
    ) {
        return healthRisks.findTop20ByBarnIdOrderByRecordedAtDesc(barnId);
    }

    @GetMapping("/alerts")
    public List<AlertRecord> alerts(
            @RequestParam(defaultValue = "barn_01") String barnId
    ) {
        return alerts.findTop30ByBarnIdOrderByCreatedAtDesc(barnId);
    }
}
