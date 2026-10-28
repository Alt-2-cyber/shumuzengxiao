package com.shumuzengxiao.smartcattle.controller;

import com.shumuzengxiao.smartcattle.domain.FmdTriageCase;
import com.shumuzengxiao.smartcattle.dto.FmdTriageActionRequest;
import com.shumuzengxiao.smartcattle.dto.FmdTriageOpenRequest;
import com.shumuzengxiao.smartcattle.service.FmdTriageService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/fmd-triage-cases")
public class FmdTriageController {
    private final FmdTriageService triage;

    public FmdTriageController(FmdTriageService triage) {
        this.triage = triage;
    }

    @PostMapping
    public FmdTriageCase open(@Valid @RequestBody FmdTriageOpenRequest request) {
        return triage.open(request);
    }

    @PostMapping("/{caseId}/actions")
    public FmdTriageCase action(
            @PathVariable Long caseId,
            @Valid @RequestBody FmdTriageActionRequest request
    ) {
        return triage.action(caseId, request);
    }

    @GetMapping
    public List<FmdTriageCase> recent(@RequestParam(required = false) String cattleId) {
        return triage.recent(cattleId);
    }
}
