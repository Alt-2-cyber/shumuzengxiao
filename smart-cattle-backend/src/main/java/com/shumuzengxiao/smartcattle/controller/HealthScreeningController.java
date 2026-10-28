package com.shumuzengxiao.smartcattle.controller;

import com.shumuzengxiao.smartcattle.service.HealthScreeningService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/health-screen")
public class HealthScreeningController {
    private final HealthScreeningService healthScreeningService;

    public HealthScreeningController(HealthScreeningService healthScreeningService) {
        this.healthScreeningService = healthScreeningService;
    }

    @GetMapping
    public Map<String, Object> current(@RequestParam(required = false) String targetId) {
        return healthScreeningService.snapshot(targetId);
    }
}
