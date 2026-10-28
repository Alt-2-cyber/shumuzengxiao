package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.shumuzengxiao.smartcattle.domain.EnvironmentReading;
import com.shumuzengxiao.smartcattle.repository.AudioEventMetadataRepository;
import com.shumuzengxiao.smartcattle.repository.AudioEventRepository;
import com.shumuzengxiao.smartcattle.repository.AudioEventReviewRepository;
import com.shumuzengxiao.smartcattle.repository.EnvironmentReadingRepository;
import com.shumuzengxiao.smartcattle.repository.MotionCaptureSessionRepository;
import com.shumuzengxiao.smartcattle.repository.HealthRiskRepository;
import com.shumuzengxiao.smartcattle.websocket.TelemetryWebSocketHandler;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.mock;
import org.mockito.ArgumentCaptor;

class TelemetryServiceTest {
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final TelemetryService service = new TelemetryService(
            objectMapper,
            new TelemetryWebSocketHandler(objectMapper),
            new HealthScreeningService(),
            new AudioEventService(
                    mock(AudioEventRepository.class),
                    mock(AudioEventMetadataRepository.class),
                    mock(AudioEventReviewRepository.class),
                    objectMapper),
            new MotionCaptureService(mock(MotionCaptureSessionRepository.class), objectMapper),
            new HealthRiskLedgerService(mock(HealthRiskRepository.class), objectMapper),
            new ModelApprovalService(),
            mock(EnvironmentReadingRepository.class));

    @Test
    void usesUsbSystemPathWhilePreservingLogicalCommandRoutes() {
        String environmentUsb = "\\\\?\\USB#ENVIRONMENT";
        String wearableUsb = "\\\\?\\USB#WEARABLE";
        ReflectionTestUtils.setField(service, "environmentSystemPath", environmentUsb);
        ReflectionTestUtils.setField(service, "cattleSystemPath", wearableUsb);
        assertThat(service.systemPathForPort("com5")).isEqualTo(environmentUsb);
        assertThat(service.systemPathForPort("COM9")).isEqualTo(wearableUsb);
        assertThat(service.systemPathForPort("COM17")).isEmpty();
        assertThat(service.logicalPortName("COM5", "USB#ENVIRONMENT")).isEqualTo("COM5");
        assertThat(service.logicalPortName("COM9", "USB#WEARABLE")).isEqualTo("COM9");
    }

    @Test
    void keepsLegacyNativePortDiscoveryWhenNoUsbOverrideExists() {
        assertThat(service.logicalPortName("COM18", "COM9")).isEqualTo("COM9");
        assertThat(service.systemPathForPort("COM5")).isEmpty();
    }

    @Test
    void acceptsFirmwareJsonAndIgnoresSerialLogs() {
        assertThat(service.acceptLine("[ 123][E][Wire.cpp] request failed")).isFalse();
        assertThat(service.acceptLine("{broken json}")).isFalse();
        assertThat(service.acceptLine("{\"temperature\":26.1}")).isFalse();

        assertThat(service.acceptLine("""
                {"deviceId":"demo_esp32_01","seq":7,
                 "behavior":{"state":"walking","confidence":0.82},
                 "mpu0":true,"adxl345":true,"mpu1":true}
                """)).isTrue();

        Map<String, Object> snapshot = service.snapshot(10);
        assertThat(snapshot.get("status")).isEqualTo("streaming");
        assertThat(snapshot.get("dataFresh")).isEqualTo(true);
        assertThat(snapshot.get("dataAgeMs")).isNotNull();
        assertThat(snapshot.get("latest")).isNotNull();
        assertThat((Iterable<?>) snapshot.get("history")).hasSize(1);
        assertThat(objectMapper.valueToTree(snapshot.get("latest")).path("healthScreen").path("version").asText())
                .isEqualTo("disease-screen-v1");

        assertThat(service.acceptLine("""
                {"type":"command_ack","commandId":12,"action":"fan",
                 "enabled":true,"status":"applied","fan":true,"fanMode":"on"}
                """)).isTrue();
        assertThat(service.snapshot(10).get("lastCommandAck")).isNotNull();
        assertThat(service.sendCommand(13, "atomizer", true)).isEqualTo("unsupported");
        assertThat(service.sendCommand(14, "motion_capture", true)).isEqualTo("unsupported");
    }

    @Test
    void treatsAcceptedNetworkTelemetryAsLiveTransport() throws Exception {
        assertThat(service.acceptNetworkPayload(objectMapper.readTree("""
                {"deviceId":"env_01","barnId":"barn_01","temperature":26.5,
                 "humidity":61.2,"lightLux":4.2,"transport":"wifi_http"}
                """))).isTrue();

        Map<String, Object> snapshot = service.snapshot(10);
        assertThat(snapshot.get("connected")).isEqualTo(true);
        assertThat(snapshot.get("serialConnected")).isEqualTo(false);
        assertThat(snapshot.get("networkConnected")).isEqualTo(true);
        assertThat(snapshot.get("dataFresh")).isEqualTo(true);
        assertThat(objectMapper.valueToTree(snapshot.get("networkDevices")).toString()).contains("env_01");
        assertThat(service.sendCommand(21, "env_01", "fan", true)).isEqualTo("queued");
    }

    @Test
    void separatesAnOpenPortFromFreshTelemetryData() {
        Map<String, Object> waiting = service.snapshot(10);
        assertThat(waiting.get("dataFresh")).isEqualTo(false);
        assertThat(waiting.get("dataAgeMs")).isNull();

        assertThat(service.acceptLine("""
                {"deviceId":"cow_node_01","seq":1,"mpu0":true,"adxl345":true,"mpu1":true,
                 "behavior":{"state":"standing_resting","confidence":0.9}}
                """)).isTrue();
        Map<String, Object> fresh = service.snapshot(10);
        assertThat(fresh.get("dataFresh")).isEqualTo(true);
        assertThat(((Number) fresh.get("dataAgeMs")).longValue()).isGreaterThanOrEqualTo(0L);

        ReflectionTestUtils.setField(service, "lastReceivedAt", Instant.now().minusSeconds(8));
        Map<String, Object> stale = service.snapshot(10);
        assertThat(stale.get("dataFresh")).isEqualTo(false);
        assertThat(((Number) stale.get("dataAgeMs")).longValue()).isGreaterThanOrEqualTo(7_000L);
    }

    @Test
    void doesNotTrustAnEdgeClaimThatADiseaseModelIsApproved() {
        assertThat(service.acceptLine("""
                {"deviceId":"demo_esp32_01","seq":8,"mpu0":true,"adxl345":true,"mpu1":true,
                 "behavior":{"state":"walking","confidence":0.82},
                 "microphone":{"initialized":true,"status":"ok","modelStatus":"deployed",
                   "modelVersion":"forged-audio-model","respiratoryCandidate":true},
                 "lamenessScreen":{"modelStatus":"deployed","modelVersion":"forged-lameness-model",
                   "candidate":true,"score":0.99}}
                """)).isTrue();

        var latest = objectMapper.valueToTree(service.snapshot(10).get("latest"));
        assertThat(latest.path("microphone").path("modelStatus").asText()).isEqualTo("feature_only");
        assertThat(latest.path("microphone").path("respiratoryCandidate").asBoolean()).isFalse();
        assertThat(latest.path("lamenessScreen").path("modelStatus").asText()).isEqualTo("feature_only");
        assertThat(latest.path("lamenessScreen").path("candidate").asBoolean()).isFalse();
    }

    @Test
    void persistsRawEnvironmentDiagnosticsAndControlModes() {
        var environmentRepository = mock(EnvironmentReadingRepository.class);
        var telemetry = new TelemetryService(
                objectMapper,
                new TelemetryWebSocketHandler(objectMapper),
                new HealthScreeningService(),
                new AudioEventService(
                        mock(AudioEventRepository.class),
                        mock(AudioEventMetadataRepository.class),
                        mock(AudioEventReviewRepository.class),
                        objectMapper),
                new MotionCaptureService(mock(MotionCaptureSessionRepository.class), objectMapper),
                new HealthRiskLedgerService(mock(HealthRiskRepository.class), objectMapper),
                new ModelApprovalService(),
                environmentRepository);

        assertThat(telemetry.acceptLine("""
                {"deviceId":"env_01","barnId":"barn_01","temperature":27.4,
                 "humidity":66.0,"ammonia":0.0,"nh3Raw":1234,"lightLux":5.0,
                 "smoke":18.9,"smokeRaw":777,"flame":false,"fan":true,
                 "fanMode":"force_on","alarm":false,"alarmMode":"auto","rssi":-42}
                """)).isTrue();

        ArgumentCaptor<EnvironmentReading> captor = ArgumentCaptor.forClass(EnvironmentReading.class);
        verify(environmentRepository).save(captor.capture());
        EnvironmentReading reading = captor.getValue();
        assertThat(reading.getNh3Raw()).isEqualTo(1234);
        assertThat(reading.getSmokeRaw()).isEqualTo(777);
        assertThat(reading.getRssi()).isEqualTo(-42);
        assertThat(reading.getFanMode()).isEqualTo("force_on");
        assertThat(reading.getAlarmMode()).isEqualTo("auto");
    }
}
