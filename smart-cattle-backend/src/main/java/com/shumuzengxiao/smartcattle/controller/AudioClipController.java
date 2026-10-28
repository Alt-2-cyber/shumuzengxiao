package com.shumuzengxiao.smartcattle.controller;

import com.shumuzengxiao.smartcattle.service.AudioEventService;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.nio.file.Path;

@RestController
@RequestMapping("/api/audio-clips")
public class AudioClipController {
    private final AudioEventService audioEventService;

    public AudioClipController(AudioEventService audioEventService) {
        this.audioEventService = audioEventService;
    }

    @GetMapping("/{fileName:.+}")
    public ResponseEntity<Resource> clip(@PathVariable String fileName) {
        Path clip = audioEventService.resolveClip(fileName);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType("audio/wav"))
                .cacheControl(CacheControl.noStore())
                .body(new FileSystemResource(clip));
    }
}
