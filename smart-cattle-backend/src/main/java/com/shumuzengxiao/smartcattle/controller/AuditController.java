package com.shumuzengxiao.smartcattle.controller;

import com.shumuzengxiao.smartcattle.domain.AuditRecord;
import com.shumuzengxiao.smartcattle.service.AuditTrailService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/audit-records")
public class AuditController {
    private final AuditTrailService audit;

    public AuditController(AuditTrailService audit) {
        this.audit = audit;
    }

    @GetMapping
    public List<AuditRecord> recent(
            @RequestParam(required = false) String targetType,
            @RequestParam(required = false) String targetId
    ) {
        if (targetType != null && !targetType.isBlank() && targetId != null && !targetId.isBlank()) {
            return audit.targetHistory(targetType, targetId);
        }
        return audit.recent();
    }
}
