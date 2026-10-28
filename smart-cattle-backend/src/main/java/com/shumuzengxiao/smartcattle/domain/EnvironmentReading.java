package com.shumuzengxiao.smartcattle.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
public class EnvironmentReading {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String barnId;
    private String deviceId;
    private Double temperature;
    private Double humidity;
    private Double ammonia;
    @Column(name = "nh3_raw")
    private Integer nh3Raw;
    private Double lightLux;
    private Double smoke;
    @Column(name = "smoke_raw")
    private Integer smokeRaw;
    private Boolean flame;
    private Boolean fanOn;
    @Column(name = "fan_mode")
    private String fanMode;
    private Boolean atomizerOn;
    @Column(name = "atomizer_mode")
    private String atomizerMode;
    @Column(name = "alarm_mode")
    private String alarmMode;
    private Integer rssi;
    private Instant recordedAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getBarnId() { return barnId; }
    public void setBarnId(String barnId) { this.barnId = barnId; }
    public String getDeviceId() { return deviceId; }
    public void setDeviceId(String deviceId) { this.deviceId = deviceId; }
    public Double getTemperature() { return temperature; }
    public void setTemperature(Double temperature) { this.temperature = temperature; }
    public Double getHumidity() { return humidity; }
    public void setHumidity(Double humidity) { this.humidity = humidity; }
    public Double getAmmonia() { return ammonia; }
    public void setAmmonia(Double ammonia) { this.ammonia = ammonia; }
    public Integer getNh3Raw() { return nh3Raw; }
    public void setNh3Raw(Integer nh3Raw) { this.nh3Raw = nh3Raw; }
    public Double getLightLux() { return lightLux; }
    public void setLightLux(Double lightLux) { this.lightLux = lightLux; }
    public Double getSmoke() { return smoke; }
    public void setSmoke(Double smoke) { this.smoke = smoke; }
    public Integer getSmokeRaw() { return smokeRaw; }
    public void setSmokeRaw(Integer smokeRaw) { this.smokeRaw = smokeRaw; }
    public Boolean getFlame() { return flame; }
    public void setFlame(Boolean flame) { this.flame = flame; }
    public Boolean getFanOn() { return fanOn; }
    public void setFanOn(Boolean fanOn) { this.fanOn = fanOn; }
    public String getFanMode() { return fanMode; }
    public void setFanMode(String fanMode) { this.fanMode = fanMode; }
    public Boolean getAtomizerOn() { return atomizerOn; }
    public void setAtomizerOn(Boolean atomizerOn) { this.atomizerOn = atomizerOn; }
    public String getAtomizerMode() { return atomizerMode; }
    public void setAtomizerMode(String atomizerMode) { this.atomizerMode = atomizerMode; }
    public String getAlarmMode() { return alarmMode; }
    public void setAlarmMode(String alarmMode) { this.alarmMode = alarmMode; }
    public Integer getRssi() { return rssi; }
    public void setRssi(Integer rssi) { this.rssi = rssi; }
    public Instant getRecordedAt() { return recordedAt; }
    public void setRecordedAt(Instant recordedAt) { this.recordedAt = recordedAt; }
}
