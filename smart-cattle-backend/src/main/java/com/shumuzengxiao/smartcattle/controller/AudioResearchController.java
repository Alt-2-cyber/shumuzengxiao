package com.shumuzengxiao.smartcattle.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.shumuzengxiao.smartcattle.service.AudioEventService;
import com.shumuzengxiao.smartcattle.service.AudioResearchInferenceService;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/audio-clips")
public class AudioResearchController {
    private final AudioEventService events;
    private final AudioResearchInferenceService inference;

    public AudioResearchController(AudioEventService events, AudioResearchInferenceService inference) {
        this.events = events;
        this.inference = inference;
    }

    @GetMapping("/{fileName:.+}/research")
    public ResponseEntity<JsonNode> analyze(@PathVariable String fileName) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore())
                .body(inference.analyze(events.resolveClip(fileName)));
    }
}
