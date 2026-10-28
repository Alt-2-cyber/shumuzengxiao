package com.shumuzengxiao.smartcattle.dto;

import com.shumuzengxiao.smartcattle.domain.*;

import java.util.List;
import java.util.Map;

public record DashboardDto(
        EnvironmentReading latestEnvironment,
        List<EnvironmentReading> environmentTrend,
        List<Device> devices,
        List<HealthRisk> healthRisks,
        List<AlertRecord> alerts,
        Map<String, Object> metrics
) {
}
