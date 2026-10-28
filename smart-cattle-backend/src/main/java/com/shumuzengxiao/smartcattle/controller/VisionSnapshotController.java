package com.shumuzengxiao.smartcattle.controller;

import com.shumuzengxiao.smartcattle.service.VisionEventService;
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
import java.util.Locale;

@RestController
@RequestMapping("/api/vision-snapshots")
public class VisionSnapshotController {
    private final VisionEventService visionEvents;

    public VisionSnapshotController(VisionEventService visionEvents) {
        this.visionEvents = visionEvents;
    }

    @GetMapping("/{fileName:.+}")
    public ResponseEntity<Resource> snapshot(@PathVariable String fileName) {
        Path path = visionEvents.resolveSnapshot(fileName);
        return ResponseEntity.ok()
                .contentType(contentType(fileName))
                .cacheControl(CacheControl.noStore())
                .body(new FileSystemResource(path));
    }

    private static MediaType contentType(String fileName) {
        String lower = fileName.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".png")) {
            return MediaType.IMAGE_PNG;
        }
        if (lower.endsWith(".webp")) {
            return MediaType.parseMediaType("image/webp");
        }
        return MediaType.IMAGE_JPEG;
    }
}
