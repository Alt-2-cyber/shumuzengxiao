package com.shumuzengxiao.smartcattle.controller;

import com.shumuzengxiao.smartcattle.domain.ClinicalCheck;
import com.shumuzengxiao.smartcattle.dto.ClinicalCheckRequest;
import com.shumuzengxiao.smartcattle.service.ClinicalCheckService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * Captures human-performed checks. These records are intentionally distinct
 * from sensor readings because a B-1 surface-temperature reading cannot be
 * treated as verified core temperature.
 */
@RestController
@RequestMapping("/api/clinical-checks")
public class ClinicalCheckController {
    private final ClinicalCheckService clinicalChecks;

    public ClinicalCheckController(ClinicalCheckService clinicalChecks) {
        this.clinicalChecks = clinicalChecks;
    }

    @PostMapping
    public ClinicalCheck record(@Valid @RequestBody ClinicalCheckRequest request) {
        return clinicalChecks.record(request);
    }

    @GetMapping
    public List<ClinicalCheck> recent(@RequestParam(required = false) String cattleId) {
        return clinicalChecks.recent(cattleId);
    }
}
