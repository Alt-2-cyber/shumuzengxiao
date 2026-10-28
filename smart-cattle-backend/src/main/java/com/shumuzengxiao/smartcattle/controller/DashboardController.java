package com.shumuzengxiao.smartcattle.controller;

import com.shumuzengxiao.smartcattle.dto.DashboardDto;
import com.shumuzengxiao.smartcattle.service.DashboardService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/dashboard")
public class DashboardController {
    private final DashboardService dashboardService;

    public DashboardController(DashboardService dashboardService) {
        this.dashboardService = dashboardService;
    }

    @GetMapping
    public DashboardDto dashboard(@RequestParam(defaultValue = "barn_01") String barnId) {
        return dashboardService.dashboard(barnId);
    }
}
