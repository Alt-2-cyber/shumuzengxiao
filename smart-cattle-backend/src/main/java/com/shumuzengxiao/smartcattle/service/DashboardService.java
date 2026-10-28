package com.shumuzengxiao.smartcattle.service;

import com.shumuzengxiao.smartcattle.domain.*;
import com.shumuzengxiao.smartcattle.dto.DashboardDto;
import com.shumuzengxiao.smartcattle.repository.*;
import org.springframework.stereotype.Service;

import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class DashboardService {
    private final EnvironmentReadingRepository readings;
    private final DeviceRepository devices;
    private final HealthRiskRepository healthRisks;
    private final AlertRecordRepository alerts;

    public DashboardService(
            EnvironmentReadingRepository readings,
            DeviceRepository devices,
            HealthRiskRepository healthRisks,
            AlertRecordRepository alerts
    ) {
        this.readings = readings;
        this.devices = devices;
        this.healthRisks = healthRisks;
        this.alerts = alerts;
    }

    public DashboardDto dashboard(String barnId) {
        EnvironmentReading latest = readings.findTopByBarnIdOrderByRecordedAtDesc(barnId);
        List<EnvironmentReading> trend = readings.findTop48ByBarnIdOrderByRecordedAtDesc(barnId).stream()
                .sorted(Comparator.comparing(EnvironmentReading::getRecordedAt))
                .toList();
        List<Device> deviceList = devices.findByBarnId(barnId);
        List<HealthRisk> risks = healthRisks.findTop20ByBarnIdOrderByRecordedAtDesc(barnId);
        List<AlertRecord> alertList = alerts.findTop30ByBarnIdOrderByCreatedAtDesc(barnId);

        Map<String, Object> metrics = new HashMap<>();
        metrics.put("cattleCount", risks.stream()
                .map(HealthRisk::getTargetId)
                .filter(target -> target != null && !target.isBlank())
                .distinct()
                .count());
        metrics.put("onlineDevices", deviceList.stream().filter(d -> d.getStatus() == DeviceStatus.ONLINE).count());
        metrics.put("openAlerts", alertList.stream().filter(a -> "open".equals(a.getStatus())).count());
        metrics.put("healthWarnings", risks.stream().filter(r -> r.getRiskLevel() == Severity.WARNING || r.getRiskLevel() == Severity.URGENT).count());
        metrics.put("modelVersion", "cattle-yolov8-coco-v1 / posture-binary-rf-v2");
        metrics.put("edgeFps", null);

        return new DashboardDto(latest, trend, deviceList, risks, alertList, metrics);
    }
}
