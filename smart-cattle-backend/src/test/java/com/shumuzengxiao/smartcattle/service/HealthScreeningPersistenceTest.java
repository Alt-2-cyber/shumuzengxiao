package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.shumuzengxiao.smartcattle.domain.HealthScreeningObservation;
import com.shumuzengxiao.smartcattle.repository.HealthScreeningObservationRepository;
import org.junit.jupiter.api.Test;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

class HealthScreeningPersistenceTest {
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void persistsCattleObservationsButDoesNotTurnEnvironmentFramesIntoIndividualBaseline() {
        HealthScreeningObservationRepository observations = mock(HealthScreeningObservationRepository.class);
        HealthScreeningService service = new HealthScreeningService(observations);
        Instant at = Instant.parse("2026-09-18T05:00:00Z");

        service.evaluate(cattleTelemetry(), at);
        service.evaluate(environmentTelemetry(), at.plusSeconds(2));

        verify(observations, times(1)).save(any(HealthScreeningObservation.class));
        verify(observations).save(org.mockito.ArgumentMatchers.argThat(row ->
                "cow_001".equals(row.getTargetId())
                        && Boolean.TRUE.equals(row.getMotionAvailable())
                        && "grazing".equals(row.getBehavior())));
    }

    private ObjectNode cattleTelemetry() {
        ObjectNode telemetry = objectMapper.createObjectNode();
        telemetry.put("deviceId", "cow_node_01");
        telemetry.put("cattleId", "cow_001");
        telemetry.put("mpu0", true);
        telemetry.put("adxl345", true);
        telemetry.put("mpu1", true);
        ObjectNode behavior = telemetry.putObject("behavior");
        behavior.put("state", "grazing");
        behavior.put("confidence", 0.9);
        behavior.put("bodyActivity", 0.06);
        behavior.put("legActivity", 0.07);
        ObjectNode microphone = telemetry.putObject("microphone");
        microphone.put("initialized", true);
        microphone.put("status", "ok");
        return telemetry;
    }

    private ObjectNode environmentTelemetry() {
        ObjectNode telemetry = objectMapper.createObjectNode();
        telemetry.put("deviceId", "env_01");
        telemetry.put("temperature", 25.0);
        telemetry.put("humidity", 55.0);
        telemetry.put("lightLux", 6.0);
        return telemetry;
    }
}
