package com.shumuzengxiao.smartcattle.controller;

import com.shumuzengxiao.smartcattle.domain.MotionCaptureSession;
import com.shumuzengxiao.smartcattle.dto.MotionCaptureRequest;
import com.shumuzengxiao.smartcattle.dto.MotionCaptureClinicalReviewDto;
import com.shumuzengxiao.smartcattle.dto.MotionCaptureClinicalReviewRequest;
import com.shumuzengxiao.smartcattle.dto.MotionCaptureTrainingLineageDto;
import com.shumuzengxiao.smartcattle.service.MotionCaptureService;
import com.shumuzengxiao.smartcattle.service.TelemetryService;
import jakarta.validation.Valid;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.nio.file.Path;
import java.util.List;

@RestController
@RequestMapping("/api/motion-captures")
public class MotionCaptureController {
    private final MotionCaptureService motionCaptures;
    private final TelemetryService telemetryService;

    public MotionCaptureController(MotionCaptureService motionCaptures, TelemetryService telemetryService) {
        this.motionCaptures = motionCaptures;
        this.telemetryService = telemetryService;
    }

    @PostMapping
    public MotionCaptureSession start(@Valid @RequestBody MotionCaptureRequest request) {
        MotionCaptureSession session = motionCaptures.create(request);
        String status = telemetryService.sendMotionCaptureCommand(
                session.getId(), session.getDeviceId(), session.getSessionId(), session.getDurationMs());
        return motionCaptures.markDispatch(session.getId(), status);
    }

    @GetMapping
    public List<MotionCaptureSession> recent(@RequestParam(required = false) String cattleId) {
        return motionCaptures.recent(cattleId);
    }

    @GetMapping("/{sessionId}/raw")
    public ResponseEntity<Resource> raw(@PathVariable String sessionId) {
        Path path = motionCaptures.resolveRawData(sessionId);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType("application/x-ndjson"))
                .cacheControl(CacheControl.noStore())
                .body(new FileSystemResource(path));
    }

    @GetMapping("/{sessionId}/training-lineage")
    public ResponseEntity<MotionCaptureTrainingLineageDto> trainingLineage(@PathVariable String sessionId) {
        return ResponseEntity.ok()
                .cacheControl(CacheControl.noStore())
                .body(motionCaptures.trainingLineage(sessionId));
    }

    @PutMapping("/{sessionId}/clinical-review")
    public MotionCaptureClinicalReviewDto reviewClinical(
            @PathVariable String sessionId,
            @Valid @RequestBody MotionCaptureClinicalReviewRequest request
    ) {
        return motionCaptures.reviewClinical(sessionId, request);
    }
}
