package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.fazecast.jSerialComm.SerialPort;
import com.fazecast.jSerialComm.SerialPortTimeoutException;
import com.shumuzengxiao.smartcattle.domain.EnvironmentReading;
import com.shumuzengxiao.smartcattle.dto.AudioEventDto;
import com.shumuzengxiao.smartcattle.repository.EnvironmentReadingRepository;
import com.shumuzengxiao.smartcattle.websocket.TelemetryWebSocketHandler;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.SmartLifecycle;
import org.springframework.stereotype.Service;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Locale;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicReference;
import java.util.Set;

@Service
public class TelemetryService implements SmartLifecycle {
    // Raw IMU collections must always carry a server-created session ID. They
    // are intentionally excluded from the generic device-control endpoint.
    private static final Set<String> SUPPORTED_COMMANDS = Set.of("fan", "fan_auto", "alarm", "audio_capture");
    private static final int DEFAULT_MAX_SERIAL_LINE_BYTES = 32 * 1024;
    private static final Duration NETWORK_STALE_AFTER = Duration.ofSeconds(30);
    private static final Duration DATA_FRESH_AFTER = Duration.ofSeconds(7);
    private final ObjectMapper objectMapper;
    private final TelemetryWebSocketHandler webSocketHandler;
    private final HealthScreeningService healthScreeningService;
    private final AudioEventService audioEventService;
    private final MotionCaptureService motionCaptureService;
    private final HealthRiskLedgerService healthRiskLedgerService;
    private final ModelApprovalService modelApprovalService;
    private final EnvironmentReadingRepository environmentReadings;
    private final AtomicReference<ObjectNode> latest = new AtomicReference<>();
    private final AtomicReference<ObjectNode> latestCattle = new AtomicReference<>();
    private final AtomicReference<ObjectNode> latestEnvironment = new AtomicReference<>();
    private final AtomicReference<ObjectNode> lastCommandAck = new AtomicReference<>();
    private final Deque<ObjectNode> history = new ArrayDeque<>();
    private final Map<String, ObjectNode> latestByDevice = new ConcurrentHashMap<>();
    private final Object commandWriteLock = new Object();

    @Value("${hardware.serial.enabled:true}")
    private boolean enabled = true;

    @Value("${hardware.serial.port:COM18}")
    private String portName = "COM18";

    @Value("${hardware.serial.ports:}")
    private String portsConfig = "";

    @Value("${hardware.serial.env-port:COM5}")
    private String environmentPort = "COM5";

    @Value("${hardware.serial.cow-port:COM9}")
    private String cattlePort = "COM9";

    @Value("${hardware.serial.env-system-path:}")
    private String environmentSystemPath = "";

    @Value("${hardware.serial.cow-system-path:}")
    private String cattleSystemPath = "";

    @Value("${hardware.serial.baud-rate:115200}")
    private int baudRate = 115200;

    @Value("${hardware.serial.reconnect-ms:3000}")
    private long reconnectMs = 3000;

    @Value("${hardware.serial.history-limit:120}")
    private int historyLimit = 120;

    @Value("${hardware.serial.max-line-bytes:32768}")
    private int maxSerialLineBytes = DEFAULT_MAX_SERIAL_LINE_BYTES;

    private volatile boolean running;
    private volatile boolean connected;
    private volatile String status = "starting";
    private volatile String lastError;
    private volatile Instant connectedAt;
    private volatile Instant lastReceivedAt;
    private volatile Instant lastNetworkReceivedAt;
    private final Map<String, SerialPort> activePorts = new ConcurrentHashMap<>();
    private final Map<String, PortState> portStates = new ConcurrentHashMap<>();
    private final Map<String, String> devicePortRoutes = new ConcurrentHashMap<>();
    private final Map<String, Instant> networkDeviceSeenAt = new ConcurrentHashMap<>();
    private ExecutorService readerExecutor;

    private static final class PortState {
        private volatile boolean connected;
        private volatile String status = "starting";
        private volatile String lastError;
        private volatile Instant connectedAt;
    }

    public TelemetryService(
            ObjectMapper objectMapper,
            TelemetryWebSocketHandler webSocketHandler,
            HealthScreeningService healthScreeningService,
            AudioEventService audioEventService,
            MotionCaptureService motionCaptureService,
            HealthRiskLedgerService healthRiskLedgerService,
            ModelApprovalService modelApprovalService,
            EnvironmentReadingRepository environmentReadings
    ) {
        this.objectMapper = objectMapper;
        this.webSocketHandler = webSocketHandler;
        this.healthScreeningService = healthScreeningService;
        this.audioEventService = audioEventService;
        this.motionCaptureService = motionCaptureService;
        this.healthRiskLedgerService = healthRiskLedgerService;
        this.modelApprovalService = modelApprovalService;
        this.environmentReadings = environmentReadings;
    }

    @Override
    public synchronized void start() {
        if (running) {
            return;
        }
        running = true;
        if (!enabled) {
            status = "disabled";
            return;
        }
        List<String> configuredPorts = configuredPortNames();
        readerExecutor = Executors.newFixedThreadPool(configuredPorts.size(), runnable -> {
            Thread thread = new Thread(runnable, "esp32-serial-reader");
            thread.setDaemon(true);
            return thread;
        });
        for (String configuredPort : configuredPorts) {
            portStates.putIfAbsent(configuredPort, new PortState());
            readerExecutor.submit(() -> readLoop(configuredPort));
        }
    }

    @Override
    public synchronized void stop() {
        running = false;
        connected = false;
        for (SerialPort port : activePorts.values()) {
            if (port.isOpen()) {
                port.closePort();
            }
        }
        activePorts.clear();
        if (readerExecutor != null) {
            readerExecutor.shutdownNow();
            readerExecutor = null;
        }
        status = "stopped";
    }

    @Override
    public boolean isRunning() {
        return running;
    }

    @Override
    public boolean isAutoStartup() {
        return true;
    }

    @Override
    public int getPhase() {
        return Integer.MAX_VALUE;
    }

    public Map<String, Object> snapshot(int requestedLimit) {
        motionCaptureService.expireStaleSessions(Instant.now());
        Instant now = Instant.now();
        boolean serialConnected = !activePorts.isEmpty();
        boolean networkConnected = lastNetworkReceivedAt != null
                && Duration.between(lastNetworkReceivedAt, now).compareTo(NETWORK_STALE_AFTER) <= 0;
        boolean dataFresh = lastReceivedAt != null
                && Duration.between(lastReceivedAt, now).compareTo(DATA_FRESH_AFTER) <= 0;
        boolean hasDirectTelemetry = "streaming".equals(status) && lastNetworkReceivedAt == null;
        int limit = Math.max(1, Math.min(requestedLimit, historyLimit));
        List<ObjectNode> rows;
        synchronized (history) {
            int skip = Math.max(0, history.size() - limit);
            rows = new ArrayList<>(history).subList(skip, history.size()).stream()
                    .map(ObjectNode::deepCopy)
                    .toList();
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("connected", serialConnected || networkConnected);
        result.put("serialConnected", serialConnected);
        result.put("networkConnected", networkConnected);
        result.put("port", configuredPortSummary());
        result.put("baudRate", baudRate);
        result.put("status", serialConnected || networkConnected || hasDirectTelemetry ? status : "offline");
        result.put("lastError", lastError);
        result.put("connectedAt", connectedAt);
        result.put("lastReceivedAt", lastReceivedAt);
        result.put("dataFresh", dataFresh);
        result.put("dataAgeMs", dataAgeMs(now));
        result.put("lastNetworkReceivedAt", lastNetworkReceivedAt);
        result.put("networkDevices", networkDeviceSeenAt.entrySet().stream()
                .filter(entry -> Duration.between(entry.getValue(), now).compareTo(NETWORK_STALE_AFTER) <= 0)
                .map(Map.Entry::getKey)
                .sorted()
                .toList());
        ObjectNode current = latest.get();
        result.put("latest", current == null ? null : current.deepCopy());
        ObjectNode currentCattle = latestCattle.get();
        result.put("latestCattle", currentCattle == null ? null : currentCattle.deepCopy());
        ObjectNode currentEnvironment = latestEnvironment.get();
        result.put("latestEnvironment", currentEnvironment == null ? null : currentEnvironment.deepCopy());
        Map<String, ObjectNode> deviceSnapshot = new LinkedHashMap<>();
        latestByDevice.forEach((deviceId, payload) -> deviceSnapshot.put(deviceId, payload.deepCopy()));
        result.put("latestByDevice", deviceSnapshot);
        ObjectNode commandAck = lastCommandAck.get();
        result.put("lastCommandAck", commandAck == null ? null : commandAck.deepCopy());
        Map<String, Object> portSnapshot = new LinkedHashMap<>();
        for (String configuredPort : configuredPortNames()) {
            PortState state = portStates.get(configuredPort);
            if (state == null) {
                continue;
            }
            Map<String, Object> stateSnapshot = new LinkedHashMap<>();
            stateSnapshot.put("connected", state.connected);
            stateSnapshot.put("status", state.status);
            stateSnapshot.put("lastError", state.lastError);
            stateSnapshot.put("connectedAt", state.connectedAt);
            portSnapshot.put(configuredPort, stateSnapshot);
        }
        result.put("ports", portSnapshot);
        result.put("history", rows);
        return result;
    }

    public String sendCommand(long commandId, String action, Boolean enabled) {
        return sendCommand(commandId, null, action, enabled);
    }

    public String sendCommand(long commandId, String targetDeviceId, String action, Boolean enabled) {
        if (!SUPPORTED_COMMANDS.contains(action)) {
            return "unsupported";
        }
        ObjectNode command = objectMapper.createObjectNode();
        command.put("type", "command");
        command.put("commandId", commandId);
        command.put("action", action);
        command.put("enabled", Boolean.TRUE.equals(enabled));
        return writeCommand(command, targetDeviceId);
    }

    public String sendMotionCaptureCommand(long commandId, String sessionId, Integer durationMs) {
        return sendMotionCaptureCommand(commandId, null, sessionId, durationMs);
    }

    public String sendMotionCaptureCommand(long commandId, String targetDeviceId,
                                           String sessionId, Integer durationMs) {
        ObjectNode command = objectMapper.createObjectNode();
        command.put("type", "command");
        command.put("commandId", commandId);
        command.put("action", "motion_capture");
        command.put("enabled", true);
        command.put("sessionId", sessionId);
        command.put("durationMs", durationMs == null ? 60_000 : durationMs);
        return writeCommand(command, targetDeviceId);
    }

    private String writeCommand(ObjectNode command, String targetDeviceId) {
        SerialPort port = findCommandPort(targetDeviceId);
        if (port == null || !port.isOpen()) {
            // The environment node polls the command queue over HTTP. A
            // missing USB port must not turn a valid WiFi command into a false
            // failure in the web UI.
            return supportsHttpCommands(targetDeviceId) ? "queued" : "failed";
        }
        byte[] payload = (command + "\n").getBytes(StandardCharsets.UTF_8);
        synchronized (commandWriteLock) {
            return port.writeBytes(payload, payload.length) == payload.length ? "sent" : "failed";
        }
    }

    private boolean supportsHttpCommands(String targetDeviceId) {
        if (targetDeviceId == null || targetDeviceId.isBlank()) {
            return false;
        }
        String target = targetDeviceId.trim().toLowerCase(Locale.ROOT);
        return target.startsWith("env") || target.startsWith("relay") || target.contains("environment");
    }

    private List<String> configuredPortNames() {
        String configured = portsConfig == null ? "" : portsConfig.trim();
        String source = configured.isBlank() ? portName : configured;
        List<String> names = new ArrayList<>();
        for (String value : source.split(",")) {
            String name = value.trim();
            if (!name.isBlank() && names.stream().noneMatch(existing -> existing.equalsIgnoreCase(name))) {
                names.add(name);
            }
        }
        return names.isEmpty() ? List.of("COM18") : List.copyOf(names);
    }

    private String configuredPortSummary() {
        return String.join(",", configuredPortNames());
    }

    private String normalizePortName(String value) {
        return value == null ? "" : value.trim().toUpperCase(Locale.ROOT);
    }

    private String preferredPortForDevice(String targetDeviceId) {
        if (targetDeviceId == null || targetDeviceId.isBlank()) {
            return null;
        }
        String target = targetDeviceId.trim().toLowerCase(Locale.ROOT);
        if (target.startsWith("cow") || target.startsWith("cattle") || target.contains("collar")) {
            return normalizePortName(cattlePort);
        }
        if (target.startsWith("env") || target.startsWith("relay") || target.contains("environment")) {
            return normalizePortName(environmentPort);
        }
        return normalizePortName(devicePortRoutes.get(targetDeviceId));
    }

    private SerialPort findCommandPort(String targetDeviceId) {
        String route = normalizePortName(devicePortRoutes.get(targetDeviceId));
        if (route.isBlank()) {
            route = preferredPortForDevice(targetDeviceId);
        }
        if (!route.isBlank()) {
            SerialPort routed = activePorts.get(route);
            if (routed != null && routed.isOpen()) {
                return routed;
            }
        }
        if ((targetDeviceId == null || targetDeviceId.isBlank()) && activePorts.size() == 1) {
            return activePorts.values().iterator().next();
        }
        return null;
    }

    boolean acceptLine(String line) {
        return acceptLine(line, null, false);
    }

    /** Accept one device JSON frame received over the LAN instead of USB serial. */
    public boolean acceptNetworkPayload(JsonNode payload) {
        if (payload == null || !payload.isObject()) {
            return false;
        }
        try {
            boolean accepted = acceptLine(objectMapper.writeValueAsString(payload), null, true);
            if (accepted && payload.hasNonNull("deviceId")) {
                Instant receivedAt = Instant.now();
                lastNetworkReceivedAt = receivedAt;
                networkDeviceSeenAt.put(payload.path("deviceId").asText(), receivedAt);
            }
            return accepted;
        } catch (JsonProcessingException exception) {
            return false;
        }
    }

    /**
     * Persists the environment endpoint payload and emits the same live event
     * used by serial/WiFi telemetry, so polling and WebSocket clients converge.
     */
    public EnvironmentReading ingestEnvironmentReading(EnvironmentReading reading) {
        if (reading.getBarnId() == null || reading.getBarnId().isBlank()) {
            reading.setBarnId("barn_01");
        }
        if (reading.getDeviceId() == null || reading.getDeviceId().isBlank()) {
            reading.setDeviceId("env_01");
        }
        Instant receivedAt = Instant.now();
        if (reading.getRecordedAt() == null) {
            reading.setRecordedAt(receivedAt);
        }
        EnvironmentReading saved = environmentReadings.save(reading);
        ObjectNode payload = objectMapper.valueToTree(saved);
        payload.put("receivedAt", receivedAt.toString());
        payload.put("receivedVia", "wifi_http");
        latestEnvironment.set(payload);
        latestByDevice.put(reading.getDeviceId(), payload.deepCopy());
        lastReceivedAt = receivedAt;
        lastNetworkReceivedAt = receivedAt;
        networkDeviceSeenAt.put(reading.getDeviceId(), receivedAt);
        status = "streaming";
        lastError = null;

        ObjectNode event = objectMapper.createObjectNode();
        event.put("type", "environment");
        event.set("data", payload);
        webSocketHandler.broadcast(event);
        return saved;
    }

    boolean acceptLine(String line, String sourcePort) {
        return acceptLine(line, sourcePort, false);
    }

    private boolean acceptLine(String line, String sourcePort, boolean networkTransport) {
        if (line == null) {
            return false;
        }
        String candidate = line.trim();
        if (!candidate.startsWith("{") || !candidate.endsWith("}")) {
            return false;
        }

        final JsonNode parsed;
        try {
            parsed = objectMapper.readTree(candidate);
        } catch (JsonProcessingException exception) {
            return false;
        }
        if (!parsed.isObject()) {
            return false;
        }

        if (sourcePort != null && parsed.hasNonNull("deviceId")) {
            devicePortRoutes.put(parsed.path("deviceId").asText(), normalizePortName(sourcePort));
        }

        String type = parsed.path("type").asText();
        if ("command_ack".equals(type) && parsed.has("commandId")) {
            ObjectNode ack = ((ObjectNode) parsed).deepCopy();
            ack.put("receivedAt", Instant.now().toString());
            lastCommandAck.set(ack);
            ObjectNode event = objectMapper.createObjectNode();
            event.put("type", "command_ack");
            event.set("data", ack);
            webSocketHandler.broadcast(event);
            return true;
        }
        if ("audio_event".equals(type) && parsed.hasNonNull("deviceId")) {
            try {
                ModelApprovalService.AudioDecision audioDecision =
                        modelApprovalService.enforceAudioEvent((ObjectNode) parsed);
                Instant audioReceivedAt = Instant.now();
                AudioEventDto audioDto = audioEventService.ingestEdgeEvent(
                        (ObjectNode) parsed, audioReceivedAt);
                if (audioDecision.screeningEligible()) {
                    String cattleId = parsed.path("cattleId").asText("").trim();
                    if (!cattleId.isBlank()) {
                        healthScreeningService.recordAudioEvidence(
                                cattleId,
                                audioDecision.normalizedLabel(),
                                parsed.path("score").isNumber() ? parsed.path("score").doubleValue() : null,
                                true,
                                audioReceivedAt,
                                audioEvidenceId(parsed, audioDto));
                    }
                }
                ObjectNode event = objectMapper.createObjectNode();
                event.put("type", "audio_event");
                event.set("data", objectMapper.valueToTree(audioDto));
                webSocketHandler.broadcast(event);
                return true;
            } catch (RuntimeException exception) {
                return false;
            }
        }
        if ("motion_capture_sample".equals(type) || "mcs".equals(type)) {
            motionCaptureService.ingestSample((ObjectNode) parsed, Instant.now());
            return true;
        }
        if ("motion_capture".equals(type)) {
            motionCaptureService.ingestState((ObjectNode) parsed, Instant.now());
            return true;
        }
        if (!parsed.hasNonNull("deviceId")) {
            return false;
        }

        Instant receivedAt = Instant.now();
        ObjectNode telemetry = ((ObjectNode) parsed).deepCopy();
        telemetry.put("receivedAt", receivedAt.toString());
        boolean environmentTelemetry = isEnvironmentTelemetry(telemetry);
        telemetry.put("receivedVia", networkTransport ? "wifi_http" : "usb_serial");
        if (sourcePort != null) {
            telemetry.put("serialPort", sourcePort);
        }
        modelApprovalService.enforce(telemetry);
        Map<String, Object> healthScreen = healthScreeningService.evaluate(telemetry, receivedAt);
        telemetry.set("healthScreen", objectMapper.valueToTree(healthScreen));
        healthRiskLedgerService.synchronize(
                telemetry.path("barnId").asText("barn_01"),
                telemetry.path("cattleId").asText(telemetry.path("deviceId").asText("unknown-cattle")),
                healthScreen,
                receivedAt);
        lastError = null;
        latest.set(telemetry);
        latestByDevice.put(telemetry.path("deviceId").asText(), telemetry.deepCopy());
        if (environmentTelemetry) {
            latestEnvironment.set(telemetry.deepCopy());
            persistEnvironmentTelemetry(telemetry, receivedAt);
        } else if (isCattleTelemetry(telemetry)) {
            latestCattle.set(telemetry.deepCopy());
        }
        lastReceivedAt = receivedAt;
        status = "streaming";
        synchronized (history) {
            history.addLast(telemetry);
            while (history.size() > historyLimit) {
                history.removeFirst();
            }
        }

        ObjectNode event = objectMapper.createObjectNode();
        event.put("type", "telemetry");
        event.set("data", telemetry);
        webSocketHandler.broadcast(event);
        return true;
    }

    private String audioEvidenceId(JsonNode payload, AudioEventDto saved) {
        String edgeEventId = payload.path("edgeEventId").asText("").trim();
        if (!edgeEventId.isBlank()) {
            String bootId = payload.path("bootId").asText("").trim();
            return bootId.isBlank() ? edgeEventId : bootId + ":" + edgeEventId;
        }
        return saved.id() == null ? null : "audio:" + saved.id();
    }

    private boolean isEnvironmentTelemetry(JsonNode payload) {
        String deviceId = payload.path("deviceId").asText("").toLowerCase(Locale.ROOT);
        String type = payload.path("type").asText("").toLowerCase(Locale.ROOT);
        return "environment".equals(type)
                || deviceId.startsWith("env")
                || (payload.has("lightLux") && !isCattleTelemetry(payload));
    }

    private boolean isCattleTelemetry(JsonNode payload) {
        String deviceId = payload.path("deviceId").asText("").toLowerCase(Locale.ROOT);
        return deviceId.startsWith("cow")
                || deviceId.startsWith("cattle")
                || payload.has("behavior")
                || payload.has("mpu0")
                || payload.has("mpu1")
                || payload.has("adxl345")
                || payload.has("b1Infrared")
                || payload.has("microphone");
    }

    private void persistEnvironmentTelemetry(ObjectNode telemetry, Instant receivedAt) {
        if (environmentReadings == null) {
            return;
        }
        try {
            EnvironmentReading reading = new EnvironmentReading();
            reading.setBarnId(telemetry.path("barnId").asText("barn_01"));
            reading.setDeviceId(telemetry.path("deviceId").asText("env_01"));
            reading.setTemperature(numberOrNull(telemetry, "temperature"));
            reading.setHumidity(numberOrNull(telemetry, "humidity"));
            reading.setAmmonia(numberOrNull(telemetry, "ammonia"));
            reading.setNh3Raw(integerOrNull(telemetry, "nh3Raw"));
            reading.setLightLux(numberOrNull(telemetry, "lightLux"));
            reading.setSmoke(numberOrNull(telemetry, "smoke"));
            reading.setSmokeRaw(integerOrNull(telemetry, "smokeRaw"));
            reading.setFlame(booleanOrNull(telemetry, "flame"));
            reading.setFanOn(booleanOrNull(telemetry, "fanOn", "fan"));
            reading.setFanMode(textOrNull(telemetry, "fanMode"));
            reading.setAtomizerOn(booleanOrNull(telemetry, "atomizerOn", "atomizer"));
            reading.setAtomizerMode(textOrNull(telemetry, "atomizerMode"));
            reading.setAlarmMode(textOrNull(telemetry, "alarmMode"));
            reading.setRssi(integerOrNull(telemetry, "rssi"));
            reading.setRecordedAt(receivedAt);
            environmentReadings.save(reading);
        } catch (RuntimeException exception) {
            lastError = "环境数据写入失败: " + exception.getMessage();
        }
    }

    private Double numberOrNull(JsonNode payload, String field) {
        JsonNode value = payload.get(field);
        return value != null && value.isNumber() ? value.doubleValue() : null;
    }

    private Integer integerOrNull(JsonNode payload, String field) {
        JsonNode value = payload.get(field);
        return value != null && value.isIntegralNumber() ? value.intValue() : null;
    }

    private String textOrNull(JsonNode payload, String field) {
        JsonNode value = payload.get(field);
        if (value == null || !value.isTextual() || value.asText().isBlank()) {
            return null;
        }
        String text = value.asText().trim();
        return text.length() <= 32 ? text : text.substring(0, 32);
    }

    private Boolean booleanOrNull(JsonNode payload, String... fields) {
        for (String field : fields) {
            JsonNode value = payload.get(field);
            if (value != null && value.isBoolean()) {
                return value.booleanValue();
            }
        }
        return null;
    }

    private void readLoop(String requestedPortName) {
        while (running) {
            SerialPort port = resolvePort(requestedPortName);
            port.setComPortParameters(baudRate, 8, SerialPort.ONE_STOP_BIT, SerialPort.NO_PARITY);
            port.setFlowControl(SerialPort.FLOW_CONTROL_DISABLED);
            port.setComPortTimeouts(SerialPort.TIMEOUT_READ_SEMI_BLOCKING, 500, 0);

            if (!port.openPort()) {
                updateConnection(requestedPortName, false, "waiting_for_port", "无法打开串口，可能被其他程序占用");
                sleepBeforeReconnect();
                continue;
            }

            String actualPortName = logicalPortName(requestedPortName, port.getSystemPortName());
            activePorts.put(actualPortName, port);
            updateConnection(requestedPortName, true, "connected_waiting_data", null);
            try (InputStream input = port.getInputStream()) {
                byte[] readBuffer = new byte[4096];
                int lineLimit = Math.max(1024, Math.min(maxSerialLineBytes, 64 * 1024));
                ByteArrayOutputStream lineBuffer = new ByteArrayOutputStream(Math.min(lineLimit, 4096));
                while (running && port.isOpen()) {
                    final int bytesRead;
                    try {
                        bytesRead = input.read(readBuffer);
                    } catch (SerialPortTimeoutException exception) {
                        continue;
                    }
                    if (bytesRead < 0) {
                        if (port.isOpen()) {
                            continue;
                        }
                        break;
                    }
                    for (int index = 0; index < bytesRead; index++) {
                        int value = readBuffer[index] & 0xFF;
                        if (value == '\n') {
                            acceptLine(lineBuffer.toString(StandardCharsets.UTF_8), actualPortName);
                            lineBuffer.reset();
                        } else if (value != '\r') {
                            if (lineBuffer.size() < lineLimit) {
                                lineBuffer.write(value);
                            } else {
                                lineBuffer.reset();
                            }
                        }
                    }
                }
            } catch (IOException exception) {
                if (running) {
                    updateConnection(requestedPortName, false, "serial_error", exception.getMessage());
                }
            } finally {
                if (port.isOpen()) {
                    port.closePort();
                }
                activePorts.remove(actualPortName, port);
                updateConnection(requestedPortName, false, "reconnecting", "串口连接已断开");
            }
            sleepBeforeReconnect();
        }
    }

    private SerialPort resolvePort(String requestedPortName) {
        String systemPath = systemPathForPort(requestedPortName);
        if (!systemPath.isBlank()) {
            return SerialPort.getCommPort(systemPath);
        }
        SerialPort[] ports = SerialPort.getCommPorts();
        for (SerialPort port : ports) {
            if (port.getSystemPortName().equalsIgnoreCase(requestedPortName)) {
                return port;
            }
        }
        // Only use automatic discovery for the legacy single-port setting. With
        // an explicit multi-port list, never redirect COM5's reader to COM9.
        if (portsConfig == null || portsConfig.isBlank()) {
            if (ports.length == 1) {
                return ports[0];
            }
            for (SerialPort port : ports) {
                String description = (port.getDescriptivePortName() + " " + port.getPortDescription())
                        .toLowerCase();
                if (description.contains("usb") || description.contains("uart") ||
                        description.contains("cp210") || description.contains("ch340") ||
                        description.contains("silicon labs")) {
                    return port;
                }
            }
        }
        return SerialPort.getCommPort(requestedPortName);
    }

    String systemPathForPort(String requestedPortName) {
        String requested = normalizePortName(requestedPortName);
        if (requested.equals(normalizePortName(environmentPort))) {
            return environmentSystemPath == null ? "" : environmentSystemPath.trim();
        }
        if (requested.equals(normalizePortName(cattlePort))) {
            return cattleSystemPath == null ? "" : cattleSystemPath.trim();
        }
        return "";
    }

    String logicalPortName(String requestedPortName, String nativePortName) {
        return normalizePortName(systemPathForPort(requestedPortName).isBlank() ? nativePortName : requestedPortName);
    }

    private void updateConnection(String requestedPortName, boolean isConnected,
                                   String newStatus, String error) {
        PortState state = portStates.computeIfAbsent(requestedPortName, ignored -> new PortState());
        state.connected = isConnected;
        state.status = newStatus;
        state.lastError = error;
        if (isConnected) {
            state.connectedAt = Instant.now();
            connectedAt = state.connectedAt;
        }

        boolean serialConnected = !activePorts.isEmpty();
        boolean networkConnected = isNetworkConnected(Instant.now());
        connected = serialConnected || networkConnected;
        if (connected) {
            lastError = null;
            if (networkConnected) {
                status = "streaming";
            } else if (!"streaming".equals(status)) {
                status = "connected_waiting_data";
            }
        } else {
            status = newStatus;
            lastError = error;
        }

        ObjectNode event = objectMapper.createObjectNode();
        event.put("type", "status");
        event.put("connected", connected);
        event.put("serialConnected", serialConnected);
        event.put("networkConnected", networkConnected);
        event.put("port", configuredPortSummary());
        event.put("portConnected", isConnected);
        event.put("portName", requestedPortName);
        event.put("baudRate", baudRate);
        event.put("status", status);
        event.put("dataFresh", lastReceivedAt != null
                && Duration.between(lastReceivedAt, Instant.now()).compareTo(DATA_FRESH_AFTER) <= 0);
        if (lastReceivedAt == null) {
            event.putNull("dataAgeMs");
            event.putNull("lastReceivedAt");
        } else {
            event.put("dataAgeMs", dataAgeMs(Instant.now()));
            event.put("lastReceivedAt", lastReceivedAt.toString());
        }
        if (lastError == null) {
            event.putNull("lastError");
        } else {
            event.put("lastError", lastError);
        }
        webSocketHandler.broadcast(event);
    }

    private boolean isNetworkConnected(Instant now) {
        return lastNetworkReceivedAt != null
                && Duration.between(lastNetworkReceivedAt, now).compareTo(NETWORK_STALE_AFTER) <= 0;
    }

    private Long dataAgeMs(Instant now) {
        if (lastReceivedAt == null) {
            return null;
        }
        return Math.max(0L, Duration.between(lastReceivedAt, now).toMillis());
    }

    private void sleepBeforeReconnect() {
        if (!running) {
            return;
        }
        try {
            Thread.sleep(reconnectMs);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
        }
    }
}
