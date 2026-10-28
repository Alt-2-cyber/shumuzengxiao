package com.shumuzengxiao.smartcattle.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.shumuzengxiao.smartcattle.service.TelemetryService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/telemetry")
public class TelemetryController {
    private final TelemetryService telemetryService;

    public TelemetryController(TelemetryService telemetryService) {
        this.telemetryService = telemetryService;
    }

    @GetMapping("/snapshot")
    public Map<String, Object> snapshot(@RequestParam(defaultValue = "60") int limit) {
        return telemetryService.snapshot(limit);
    }

    @PostMapping("/ingest")
    public ResponseEntity<Map<String, Object>> ingest(@RequestBody JsonNode payload) {
        boolean accepted = telemetryService.acceptNetworkPayload(payload);
        if (!accepted) {
            return ResponseEntity.badRequest().body(Map.of("accepted", false));
        }
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(Map.of("accepted", true));
    }
}
