package com.shumuzengxiao.smartcattle.config;

import com.shumuzengxiao.smartcattle.domain.*;
import com.shumuzengxiao.smartcattle.repository.*;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;

@Configuration
public class DataSeeder {
    @Bean
    @ConditionalOnProperty(name = "app.seed-demo-data", havingValue = "true")
    CommandLineRunner seedData(
            DeviceRepository devices,
            EnvironmentReadingRepository readings,
            VisionEventRepository visionEvents,
            AudioEventRepository audioEvents,
            HealthRiskRepository healthRisks,
            AlertRecordRepository alerts
    ) {
        return args -> {
            if (devices.count() > 0) {
                return;
            }
            Instant now = Instant.now();

            devices.saveAll(List.of(
                    device("env_01", "ESP32-S3 环境控制箱", "environment", "barn_01", DeviceStatus.ONLINE, 92, -58, now.minusSeconds(12)),
                    device("cam_01", "MaixCam 视觉 AI 节点", "vision", "barn_01", DeviceStatus.ONLINE, 88, -61, now.minusSeconds(16)),
                    device("mic_01", "I2S 声音采集节点", "audio", "barn_01", DeviceStatus.ONLINE, 84, -65, now.minusSeconds(22)),
                    device("relay_01", "执行器控制模块", "actuator", "barn_01", DeviceStatus.ONLINE, 100, -54, now.minusSeconds(8))
            ));

            for (int i = 47; i >= 0; i--) {
                double wave = Math.sin(i / 5.0);
                EnvironmentReading reading = new EnvironmentReading();
                reading.setBarnId("barn_01");
                reading.setDeviceId("env_01");
                reading.setTemperature(round(26.5 + wave * 2.2 + (i % 4) * 0.1));
                reading.setHumidity(round(67.0 + Math.cos(i / 6.0) * 6.0));
                reading.setAmmonia(round(16.0 + Math.max(0, wave) * 8.0 + (i % 7 == 0 ? 5 : 0)));
                reading.setLightLux(round(220.0 + Math.sin(i / 3.0) * 60.0));
                reading.setSmoke(round(0.09 + Math.max(0, Math.cos(i / 8.0)) * 0.05));
                reading.setFanOn(reading.getAmmonia() > 20 || reading.getTemperature() > 28);
                reading.setAtomizerOn(reading.getTemperature() > 29 && reading.getHumidity() < 72);
                reading.setRecordedAt(now.minus(47 - i, ChronoUnit.HOURS));
                readings.save(reading);
            }

            visionEvents.saveAll(List.of(
                    vision("cam_01", "barn_01", "fall_suspect", Severity.WARNING, 0.82, "track_03", "卧倒持续 184 秒，活动量低", now.minus(18, ChronoUnit.MINUTES)),
                    vision("cam_01", "barn_01", "nasal_discharge_suspect", Severity.OBSERVE, 0.68, "track_05", "鼻部区域疑似分泌物，建议复核", now.minus(43, ChronoUnit.MINUTES)),
                    vision("cam_01", "barn_01", "skin_lesion_suspect", Severity.OBSERVE, 0.63, "track_02", "侧腹局部皮肤纹理异常", now.minus(72, ChronoUnit.MINUTES))
            ));

            audioEvents.saveAll(List.of(
                    audio("mic_01", "barn_01", "cough_suspect", 0.79, 1180, 14.3, now.minus(14, ChronoUnit.MINUTES)),
                    audio("mic_01", "barn_01", "wheeze_suspect", 0.71, 2100, 11.6, now.minus(35, ChronoUnit.MINUTES)),
                    audio("mic_01", "barn_01", "normal_moo", 0.88, 920, 18.1, now.minus(58, ChronoUnit.MINUTES))
            ));

            healthRisks.saveAll(List.of(
                    risk("barn_01", "track_05", "respiratory_risk", Severity.WARNING, 0.78,
                            "咳嗽疑似 3 次、鼻部异常疑似、湿度偏高", "建议复核该栏位呼吸道症状，检查鼻液和体温", now.minus(11, ChronoUnit.MINUTES)),
                    risk("barn_01", "track_03", "low_activity_risk", Severity.OBSERVE, 0.64,
                            "卧地时长偏高，活动量低于 24h 均值 42%", "建议观察采食和起立情况", now.minus(26, ChronoUnit.MINUTES))
            ));

            alerts.saveAll(List.of(
                    alert("barn_01", "呼吸道风险预警", Severity.WARNING, "track_05 存在咳嗽和鼻部异常证据，建议人工复核。", "health", "open", now.minus(10, ChronoUnit.MINUTES)),
                    alert("barn_01", "氨气趋势偏高", Severity.OBSERVE, "NH3 趋势达到 24ppm，风扇已自动开启。", "environment", "open", now.minus(36, ChronoUnit.MINUTES)),
                    alert("barn_01", "视觉节点在线", Severity.NORMAL, "MaixCAM 牛只检测节点已配置，模型 cattle-yolov8-coco-v1；仅支持 cow 目标检测。", "device", "closed", now.minus(55, ChronoUnit.MINUTES))
            ));
        };
    }

    private Device device(String id, String name, String type, String barn, DeviceStatus status, int battery, int signal, Instant lastSeen) {
        Device d = new Device();
        d.setDeviceId(id);
        d.setName(name);
        d.setType(type);
        d.setBarnId(barn);
        d.setStatus(status);
        d.setBattery(battery);
        d.setSignalStrength(signal);
        d.setLastSeen(lastSeen);
        return d;
    }

    private VisionEvent vision(String camera, String barn, String type, Severity severity, double score, String target, String evidence, Instant time) {
        VisionEvent e = new VisionEvent();
        e.setCameraId(camera);
        e.setBarnId(barn);
        e.setEventType(type);
        e.setSeverity(severity);
        e.setScore(score);
        e.setTargetId(target);
        e.setSnapshotPath("/mock/snapshots/" + type + ".jpg");
        e.setEvidence(evidence);
        e.setRecordedAt(time);
        return e;
    }

    private AudioEvent audio(String device, String barn, String type, double score, int duration, double snr, Instant time) {
        AudioEvent e = new AudioEvent();
        e.setDeviceId(device);
        e.setBarnId(barn);
        e.setEventType(type);
        e.setScore(score);
        e.setDurationMs(duration);
        e.setSnr(snr);
        e.setAudioClipPath("/mock/audio/" + type + ".wav");
        e.setRecordedAt(time);
        return e;
    }

    private HealthRisk risk(String barn, String target, String type, Severity level, double score, String evidence, String suggestion, Instant time) {
        HealthRisk r = new HealthRisk();
        r.setBarnId(barn);
        r.setTargetId(target);
        r.setRiskType(type);
        r.setRiskLevel(level);
        r.setScore(score);
        r.setEvidence(evidence);
        r.setSuggestion(suggestion);
        r.setStatus("open");
        r.setRecordedAt(time);
        return r;
    }

    private AlertRecord alert(String barn, String title, Severity severity, String message, String source, String status, Instant time) {
        AlertRecord a = new AlertRecord();
        a.setBarnId(barn);
        a.setTitle(title);
        a.setSeverity(severity);
        a.setMessage(message);
        a.setSource(source);
        a.setStatus(status);
        a.setCreatedAt(time);
        return a;
    }

    private double round(double value) {
        return Math.round(value * 10.0) / 10.0;
    }
}
