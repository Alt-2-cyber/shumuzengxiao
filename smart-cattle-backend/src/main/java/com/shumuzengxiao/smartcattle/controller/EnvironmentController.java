package com.shumuzengxiao.smartcattle.controller;

import com.shumuzengxiao.smartcattle.domain.EnvironmentReading;
import com.shumuzengxiao.smartcattle.repository.EnvironmentReadingRepository;
import com.shumuzengxiao.smartcattle.service.TelemetryService;
import org.springframework.web.bind.annotation.*;

import java.util.Comparator;
import java.util.List;

@RestController
@RequestMapping("/api/environment")
public class EnvironmentController {
    private final EnvironmentReadingRepository readings;
    private final TelemetryService telemetryService;

    public EnvironmentController(EnvironmentReadingRepository readings, TelemetryService telemetryService) {
        this.readings = readings;
        this.telemetryService = telemetryService;
    }

    @GetMapping("/latest")
    public EnvironmentReading latest(@RequestParam(defaultValue = "barn_01") String barnId) {
        return readings.findTopByBarnIdOrderByRecordedAtDesc(barnId);
    }

    @GetMapping("/trend")
    public List<EnvironmentReading> trend(@RequestParam(defaultValue = "barn_01") String barnId) {
        return readings.findTop48ByBarnIdOrderByRecordedAtDesc(barnId).stream()
                .sorted(Comparator.comparing(EnvironmentReading::getRecordedAt))
                .toList();
    }

    @PostMapping
    public EnvironmentReading ingest(@RequestBody EnvironmentReading reading) {
        return telemetryService.ingestEnvironmentReading(reading);
    }
}
