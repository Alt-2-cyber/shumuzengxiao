package com.shumuzengxiao.smartcattle.controller;

import com.shumuzengxiao.smartcattle.domain.ControlCommandRecord;
import com.shumuzengxiao.smartcattle.domain.Device;
import com.shumuzengxiao.smartcattle.dto.ControlCommand;
import com.shumuzengxiao.smartcattle.repository.ControlCommandRecordRepository;
import com.shumuzengxiao.smartcattle.repository.DeviceRepository;
import com.shumuzengxiao.smartcattle.service.TelemetryService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/devices")
public class DeviceController {
    private final DeviceRepository devices;
    private final ControlCommandRecordRepository commands;
    private final TelemetryService telemetryService;

    public DeviceController(DeviceRepository devices, ControlCommandRecordRepository commands,
                            TelemetryService telemetryService) {
        this.devices = devices;
        this.commands = commands;
        this.telemetryService = telemetryService;
    }

    @GetMapping
    public List<Device> list(@RequestParam(defaultValue = "barn_01") String barnId) {
        return devices.findByBarnId(barnId);
    }

    @PostMapping("/command")
    public ControlCommandRecord command(@Valid @RequestBody ControlCommand command) {
        ControlCommandRecord record = new ControlCommandRecord();
        record.setDeviceId(command.deviceId());
        record.setAction(command.action());
        record.setEnabled(command.enabled());
        record.setStatus("queued");
        record.setQueuedAt(Instant.now());
        record = commands.save(record);
        record.setStatus(telemetryService.sendCommand(
                record.getId(), command.deviceId(), command.action(), command.enabled()));
        return commands.save(record);
    }

    @GetMapping("/commands")
    public List<ControlCommandRecord> commands() {
        return commands.findTop20ByOrderByQueuedAtDesc();
    }
}
