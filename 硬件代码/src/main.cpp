#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Adafruit_SHT31.h>
#include <BH1750.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <math.h>

#include "config.h"

struct RuntimeConfig {
  String barnId = DEFAULT_BARN_ID;
  String deviceId = DEFAULT_DEVICE_ID;
  String wifiSsid = DEFAULT_WIFI_SSID;
  String wifiPass = DEFAULT_WIFI_PASS;
  String mqttHost = DEFAULT_MQTT_HOST;
  uint16_t mqttPort = DEFAULT_MQTT_PORT;
  String mqttUser = DEFAULT_MQTT_USER;
  String mqttPass = DEFAULT_MQTT_PASS;
  String backendUrl = DEFAULT_BACKEND_URL;
};

struct SensorReading {
  uint32_t seq = 0;
  float temperature = NAN;
  float humidity = NAN;
  float ammoniaPpm = NAN;
  float lightLux = NAN;
  float smokePercent = NAN;
  int nh3Raw = -1;
  int smokeRaw = -1;
  bool flameDetected = false;
  int rssi = 0;
};

enum OverrideMode {
  MODE_AUTO,
  MODE_FORCE_OFF,
  MODE_FORCE_ON
};

struct ActuatorState {
  bool fan = false;
  bool atomizer = false;
  bool alarm = false;
  OverrideMode fanMode = MODE_AUTO;
  OverrideMode atomizerMode = MODE_AUTO;
  OverrideMode alarmMode = MODE_AUTO;
  uint32_t remoteAlarmUntil = 0;
};

RuntimeConfig cfg;
SensorReading latest;
ActuatorState actuators;

Preferences preferences;
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
Adafruit_SHT31 sht31 = Adafruit_SHT31();
BH1750 lightMeter;
Adafruit_SSD1306 display(128, 64, &Wire, -1);
HardwareSerial MaixSerial(1);

bool sht31Ok = false;
bool bh1750Ok = false;
bool oledOk = false;
bool timeConfigured = false;
uint32_t lastSensorMs = 0;
uint32_t lastTelemetryMs = 0;
uint32_t lastStatusMs = 0;
uint32_t lastCommandPollMs = 0;
uint32_t lastWifiAttemptMs = 0;
uint32_t lastMqttAttemptMs = 0;
uint32_t lastDisplayMs = 0;
uint32_t lastBuzzerToggleMs = 0;
uint32_t lastCaptureMs = 0;
uint32_t lastHttpCommandId = 0;
bool buzzerLevel = false;
bool buzzerPwmReady = false;
String consoleLine;
String maixLine;

String topicFor(const String &suffix) {
  return "cattle/" + cfg.barnId + "/" + cfg.deviceId + "/" + suffix;
}

String relayCmdTopic() {
  return "cattle/" + cfg.barnId + "/relay_01/cmd";
}

String deviceCmdTopic() {
  return topicFor("cmd");
}

bool hasWifiConfig() {
  return cfg.wifiSsid.length() > 0;
}

bool wifiConnected() {
  return WiFi.status() == WL_CONNECTED;
}

bool hasMqttConfig() {
  return cfg.mqttHost.length() > 0;
}

bool hasBackendConfig() {
  return cfg.backendUrl.length() > 0;
}

String cleanBackendBase() {
  String base = cfg.backendUrl;
  base.trim();
  while (base.endsWith("/")) {
    base.remove(base.length() - 1);
  }
  return base;
}

String apiUrl(const char *path) {
  return cleanBackendBase() + path;
}

float round1(float value) {
  return roundf(value * 10.0f) / 10.0f;
}

float rawToPpm(int raw) {
  if (raw < 0) {
    return NAN;
  }
  float ppm = (static_cast<float>(raw - NH3_RAW_ZERO) * NH3_PPM_FULL) /
              static_cast<float>(NH3_RAW_FULL - NH3_RAW_ZERO);
  if (ppm < 0.0f) {
    ppm = 0.0f;
  }
  return ppm;
}

float rawToPercent(int raw) {
  if (raw < 0) {
    return NAN;
  }
  float percent = static_cast<float>(raw) * 100.0f / 4095.0f;
  if (percent < 0.0f) {
    percent = 0.0f;
  }
  if (percent > 100.0f) {
    percent = 100.0f;
  }
  return percent;
}

uint32_t nowEpoch() {
  time_t now = time(nullptr);
  if (now > 1700000000) {
    return static_cast<uint32_t>(now);
  }
  return millis() / 1000UL;
}

const char *modeName(OverrideMode mode) {
  switch (mode) {
    case MODE_FORCE_OFF:
      return "force_off";
    case MODE_FORCE_ON:
      return "force_on";
    default:
      return "auto";
  }
}

void setJsonFloat(JsonDocument &doc, const char *key, float value) {
  if (isfinite(value)) {
    doc[key] = round1(value);
  } else {
    doc[key] = nullptr;
  }
}

void writeDigitalOutput(int pin, bool enabled, bool activeLow) {
  if (pin < 0) {
    return;
  }
  bool level = activeLow ? !enabled : enabled;
  digitalWrite(pin, level ? HIGH : LOW);
}

void setBuzzer(bool enabled) {
  if (PIN_BUZZER < 0) {
    return;
  }
  if (!enabled) {
    buzzerLevel = false;
    if (BUZZER_ACTIVE_MODULE || !buzzerPwmReady) {
      digitalWrite(PIN_BUZZER, BUZZER_ACTIVE_HIGH ? LOW : HIGH);
    } else {
      ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
    }
    return;
  }

  uint32_t now = millis();
  if (now - lastBuzzerToggleMs >= 250UL) {
    lastBuzzerToggleMs = now;
    buzzerLevel = !buzzerLevel;
    if (BUZZER_ACTIVE_MODULE || !buzzerPwmReady) {
      bool activeLevel = BUZZER_ACTIVE_HIGH ? buzzerLevel : !buzzerLevel;
      digitalWrite(PIN_BUZZER, activeLevel ? HIGH : LOW);
    } else {
      ledcWriteTone(BUZZER_LEDC_CHANNEL,
                    buzzerLevel ? BUZZER_FREQUENCY_HZ : 0);
    }
  }
}

void applyOutputs() {
  writeDigitalOutput(PIN_FAN_RELAY, actuators.fan, RELAY_ACTIVE_LOW);
  writeDigitalOutput(PIN_ATOMIZER_RELAY, actuators.atomizer, RELAY_ACTIVE_LOW);
  writeDigitalOutput(PIN_ALARM_LIGHT, actuators.alarm, RELAY_ACTIVE_LOW);
  if (PIN_STATUS_LED >= 0) {
    digitalWrite(PIN_STATUS_LED, wifiConnected() ? HIGH : LOW);
  }
  setBuzzer(actuators.alarm);
}

void loadConfig() {
  preferences.begin("cattle", false);
  cfg.barnId = preferences.isKey("barn_id") ? preferences.getString("barn_id") : DEFAULT_BARN_ID;
  cfg.deviceId = preferences.isKey("device_id") ? preferences.getString("device_id") : DEFAULT_DEVICE_ID;
  cfg.wifiSsid = preferences.isKey("wifi_ssid") ? preferences.getString("wifi_ssid") : DEFAULT_WIFI_SSID;
  cfg.wifiPass = preferences.isKey("wifi_pass") ? preferences.getString("wifi_pass") : DEFAULT_WIFI_PASS;
  cfg.mqttHost = preferences.isKey("mqtt_host") ? preferences.getString("mqtt_host") : DEFAULT_MQTT_HOST;
  cfg.mqttPort = preferences.isKey("mqtt_port") ? preferences.getUShort("mqtt_port") : DEFAULT_MQTT_PORT;
  cfg.mqttUser = preferences.isKey("mqtt_user") ? preferences.getString("mqtt_user") : DEFAULT_MQTT_USER;
  cfg.mqttPass = preferences.isKey("mqtt_pass") ? preferences.getString("mqtt_pass") : DEFAULT_MQTT_PASS;
  cfg.backendUrl = preferences.isKey("backend_url") ? preferences.getString("backend_url") : DEFAULT_BACKEND_URL;
}

void saveConfigValue(const String &key, const String &value) {
  if (key == "barn_id") {
    cfg.barnId = value;
    preferences.putString("barn_id", value);
  } else if (key == "device_id") {
    cfg.deviceId = value;
    preferences.putString("device_id", value);
  } else if (key == "wifi_ssid") {
    cfg.wifiSsid = value;
    preferences.putString("wifi_ssid", value);
  } else if (key == "wifi_pass") {
    cfg.wifiPass = value;
    preferences.putString("wifi_pass", value);
  } else if (key == "mqtt_host") {
    cfg.mqttHost = value;
    preferences.putString("mqtt_host", value);
    mqttClient.setServer(cfg.mqttHost.c_str(), cfg.mqttPort);
  } else if (key == "mqtt_port") {
    cfg.mqttPort = static_cast<uint16_t>(value.toInt());
    preferences.putUShort("mqtt_port", cfg.mqttPort);
    mqttClient.setServer(cfg.mqttHost.c_str(), cfg.mqttPort);
  } else if (key == "mqtt_user") {
    cfg.mqttUser = value;
    preferences.putString("mqtt_user", value);
  } else if (key == "mqtt_pass") {
    cfg.mqttPass = value;
    preferences.putString("mqtt_pass", value);
  } else if (key == "backend_url") {
    cfg.backendUrl = value;
    preferences.putString("backend_url", value);
  } else {
    Serial.println(F("Unknown config key"));
  }
}

void printHelp() {
  Serial.println(F("Commands:"));
  Serial.println(F("  show"));
  Serial.println(F("  set wifi_ssid <value>"));
  Serial.println(F("  set wifi_pass <value>"));
  Serial.println(F("  set mqtt_host <ip-or-host>"));
  Serial.println(F("  set mqtt_port <port>"));
  Serial.println(F("  set backend_url http://host:8080"));
  Serial.println(F("  fan on|off|auto"));
  Serial.println(F("  atomizer on|off|auto"));
  Serial.println(F("  alarm on|off|auto"));
  Serial.println(F("  capture <reason>"));
  Serial.println(F("  clear_config"));
  Serial.println(F("  reboot"));
}

void printConfig() {
  Serial.println(F("--- device config ---"));
  Serial.printf("barn_id=%s\n", cfg.barnId.c_str());
  Serial.printf("device_id=%s\n", cfg.deviceId.c_str());
  Serial.printf("wifi_ssid=%s\n", cfg.wifiSsid.c_str());
  Serial.printf("mqtt_host=%s\n", cfg.mqttHost.c_str());
  Serial.printf("mqtt_port=%u\n", cfg.mqttPort);
  Serial.printf("backend_url=%s\n", cfg.backendUrl.c_str());
  Serial.printf("wifi=%s rssi=%d\n", wifiConnected() ? "connected" : "offline", WiFi.RSSI());
  Serial.printf("mqtt=%s\n", mqttClient.connected() ? "connected" : "offline");
  Serial.printf("fan=%s mode=%s atomizer=%s mode=%s alarm=%s mode=%s\n",
                actuators.fan ? "on" : "off", modeName(actuators.fanMode),
                actuators.atomizer ? "on" : "off", modeName(actuators.atomizerMode),
                actuators.alarm ? "on" : "off", modeName(actuators.alarmMode));
}

void sendMaixCaptureRequest(const String &reason) {
  uint32_t now = millis();
  if (now - lastCaptureMs < MAIX_CAPTURE_COOLDOWN_MS) {
    return;
  }
  lastCaptureMs = now;

  JsonDocument doc;
  doc["type"] = "capture_request";
  doc["reason"] = reason;
  doc["durationMs"] = 3000;
  serializeJson(doc, MaixSerial);
  MaixSerial.println();
  Serial.printf("MaixCam capture_request reason=%s\n", reason.c_str());
}

void setOverride(OverrideMode &mode, const String &value) {
  if (value == "on") {
    mode = MODE_FORCE_ON;
  } else if (value == "off") {
    mode = MODE_FORCE_OFF;
  } else {
    mode = MODE_AUTO;
  }
}

void applyCommand(const String &action, bool enabled, const String &source) {
  Serial.printf("command source=%s action=%s enabled=%s\n",
                source.c_str(), action.c_str(), enabled ? "true" : "false");

  if (action == "fan") {
    actuators.fanMode = enabled ? MODE_FORCE_ON : MODE_FORCE_OFF;
  } else if (action == "fan_auto") {
    actuators.fanMode = MODE_AUTO;
  } else if (action == "atomizer" || action == "mist") {
    actuators.atomizerMode = enabled ? MODE_FORCE_ON : MODE_FORCE_OFF;
  } else if (action == "atomizer_auto" || action == "mist_auto") {
    actuators.atomizerMode = MODE_AUTO;
  } else if (action == "alarm") {
    actuators.alarmMode = enabled ? MODE_FORCE_ON : MODE_FORCE_OFF;
  } else if (action == "alarm_auto") {
    actuators.alarmMode = MODE_AUTO;
  } else if (action == "auto") {
    if (enabled) {
      actuators.fanMode = MODE_AUTO;
      actuators.atomizerMode = MODE_AUTO;
      actuators.alarmMode = MODE_AUTO;
    }
  } else if (action == "capture") {
    sendMaixCaptureRequest(source);
  }
}

bool handleHostJsonCommand(const String &line) {
  if (!line.startsWith("{")) {
    return false;
  }

  JsonDocument command;
  DeserializationError error = deserializeJson(command, line);
  if (error || command["type"] != "command") {
    return false;
  }

  uint32_t commandId = command["commandId"] | 0;
  String action = command["action"] | "";
  bool enabled = command["enabled"] | false;
  bool supported = action == "fan" || action == "fan_auto" ||
                   action == "alarm" || action == "alarm_auto";
  String status = supported ? "applied" : "unsupported";
  if (supported) {
    applyCommand(action, enabled, "usb_json");
  }

  JsonDocument ack;
  ack["type"] = "command_ack";
  ack["commandId"] = commandId;
  ack["action"] = action;
  ack["enabled"] = enabled;
  ack["status"] = status;
  ack["fan"] = actuators.fan;
  ack["fanMode"] = modeName(actuators.fanMode);
  ack["alarm"] = actuators.alarm;
  ack["alarmMode"] = modeName(actuators.alarmMode);
  serializeJson(ack, Serial);
  Serial.println();
  return true;
}

void handleConsoleCommand(String line) {
  line.trim();
  if (line.length() == 0) {
    return;
  }
  if (handleHostJsonCommand(line)) {
    return;
  }
  if (line == "help" || line == "?") {
    printHelp();
    return;
  }
  if (line == "show") {
    printConfig();
    return;
  }
  if (line == "reboot") {
    ESP.restart();
    return;
  }
  if (line == "clear_config") {
    preferences.clear();
    Serial.println(F("Config cleared. Rebooting."));
    delay(250);
    ESP.restart();
    return;
  }
  if (line.startsWith("set ")) {
    int sep = line.indexOf(' ', 4);
    if (sep < 0) {
      Serial.println(F("Usage: set <key> <value>"));
      return;
    }
    String key = line.substring(4, sep);
    String value = line.substring(sep + 1);
    value.trim();
    saveConfigValue(key, value);
    if (key.startsWith("wifi_")) {
      WiFi.disconnect();
      lastWifiAttemptMs = 0;
    }
    Serial.println(F("OK"));
    return;
  }

  int sep = line.indexOf(' ');
  String cmd = sep >= 0 ? line.substring(0, sep) : line;
  String arg = sep >= 0 ? line.substring(sep + 1) : "";
  arg.trim();

  if (cmd == "fan") {
    setOverride(actuators.fanMode, arg);
  } else if (cmd == "atomizer") {
    setOverride(actuators.atomizerMode, arg);
  } else if (cmd == "alarm") {
    setOverride(actuators.alarmMode, arg);
  } else if (cmd == "capture") {
    sendMaixCaptureRequest(arg.length() ? arg : "manual");
  } else {
    Serial.println(F("Unknown command. Type help."));
  }
}

void handleSerialConsole() {
  while (Serial.available()) {
    char c = static_cast<char>(Serial.read());
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      handleConsoleCommand(consoleLine);
      consoleLine = "";
    } else if (consoleLine.length() < 240) {
      consoleLine += c;
    }
  }
}

void mqttCallback(char *topic, byte *payload, unsigned int length) {
  String body;
  body.reserve(length + 1);
  for (unsigned int i = 0; i < length; i++) {
    body += static_cast<char>(payload[i]);
  }

  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, body);
  if (error) {
    Serial.printf("MQTT command JSON error: %s\n", error.c_str());
    return;
  }

  String action = doc["action"] | "";
  bool enabled = doc["enabled"] | true;
  if (action.length() == 0) {
    Serial.println(F("MQTT command missing action"));
    return;
  }
  applyCommand(action, enabled, String("mqtt:") + topic);
}

void ensureWifi() {
  if (!hasWifiConfig()) {
    return;
  }
  if (wifiConnected()) {
    if (!timeConfigured) {
      configTime(8 * 3600, 0, "ntp.aliyun.com", "pool.ntp.org");
      timeConfigured = true;
    }
    return;
  }

  uint32_t now = millis();
  // Try immediately after boot, then back off while the hotspot is absent.
  // The old zero-initialized timestamp delayed the first connection by 10 s.
  if (lastWifiAttemptMs != 0 && now - lastWifiAttemptMs < 10000UL) {
    return;
  }
  lastWifiAttemptMs = now;
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.setSleep(false);
  WiFi.begin(cfg.wifiSsid.c_str(), cfg.wifiPass.c_str());
  Serial.printf("WiFi connecting to %s\n", cfg.wifiSsid.c_str());
}

void ensureMqtt() {
  if (!wifiConnected() || !hasMqttConfig()) {
    return;
  }
  if (mqttClient.connected()) {
    return;
  }

  uint32_t now = millis();
  if (now - lastMqttAttemptMs < 5000UL) {
    return;
  }
  lastMqttAttemptMs = now;

  mqttClient.setServer(cfg.mqttHost.c_str(), cfg.mqttPort);
  String clientId = cfg.deviceId + "-" + String(static_cast<uint32_t>(ESP.getEfuseMac()), HEX);
  bool ok;
  if (cfg.mqttUser.length() > 0) {
    ok = mqttClient.connect(clientId.c_str(), cfg.mqttUser.c_str(), cfg.mqttPass.c_str());
  } else {
    ok = mqttClient.connect(clientId.c_str());
  }

  if (ok) {
    mqttClient.subscribe(deviceCmdTopic().c_str());
    mqttClient.subscribe(relayCmdTopic().c_str());
    Serial.printf("MQTT connected. cmd topics: %s, %s\n",
                  deviceCmdTopic().c_str(), relayCmdTopic().c_str());
  } else {
    Serial.printf("MQTT connect failed rc=%d\n", mqttClient.state());
  }
}

void publishJson(const String &topic, JsonDocument &doc, bool retained = false) {
  if (!mqttClient.connected()) {
    return;
  }
  String payload;
  serializeJson(doc, payload);
  mqttClient.publish(topic.c_str(), payload.c_str(), retained);
}

void publishStatus() {
  JsonDocument doc;
  doc["deviceId"] = cfg.deviceId;
  doc["barnId"] = cfg.barnId;
  doc["ts"] = nowEpoch();
  doc["wifi"] = wifiConnected();
  doc["mqtt"] = mqttClient.connected();
  doc["rssi"] = wifiConnected() ? WiFi.RSSI() : 0;
  doc["sht31"] = sht31Ok;
  doc["bh1750"] = bh1750Ok;
  doc["oled"] = oledOk;
  doc["uptimeSec"] = millis() / 1000UL;
  doc["fan"] = actuators.fan;
  doc["atomizer"] = actuators.atomizer;
  doc["alarm"] = actuators.alarm;
  doc["fanMode"] = modeName(actuators.fanMode);
  doc["atomizerMode"] = modeName(actuators.atomizerMode);
  doc["alarmMode"] = modeName(actuators.alarmMode);
  publishJson(topicFor("status"), doc, true);
}

void buildTelemetry(JsonDocument &doc) {
  doc["deviceId"] = cfg.deviceId;
  doc["barnId"] = cfg.barnId;
  doc["ts"] = nowEpoch();
  doc["seq"] = latest.seq;
  setJsonFloat(doc, "temperature", latest.temperature);
  setJsonFloat(doc, "humidity", latest.humidity);
  setJsonFloat(doc, "ammonia", latest.ammoniaPpm);
  setJsonFloat(doc, "lightLux", latest.lightLux);
  setJsonFloat(doc, "smoke", latest.smokePercent);
  doc["nh3Raw"] = latest.nh3Raw;
  doc["smokeRaw"] = latest.smokeRaw;
  doc["flame"] = latest.flameDetected;
  doc["fan"] = actuators.fan;
  doc["atomizer"] = actuators.atomizer;
  doc["alarm"] = actuators.alarm;
  doc["fanMode"] = modeName(actuators.fanMode);
  doc["atomizerMode"] = modeName(actuators.atomizerMode);
  doc["alarmMode"] = modeName(actuators.alarmMode);
  doc["rssi"] = wifiConnected() ? WiFi.RSSI() : 0;
}

void publishTelemetry() {
  JsonDocument doc;
  buildTelemetry(doc);
  publishJson(topicFor("telemetry"), doc);
  String payload;
  serializeJson(doc, payload);
  Serial.println(payload);
}

void publishAlert(const String &type, const String &level, const String &message) {
  JsonDocument doc;
  doc["deviceId"] = cfg.deviceId;
  doc["barnId"] = cfg.barnId;
  doc["ts"] = nowEpoch();
  doc["type"] = type;
  doc["level"] = level;
  doc["message"] = message;
  setJsonFloat(doc, "temperature", latest.temperature);
  setJsonFloat(doc, "humidity", latest.humidity);
  setJsonFloat(doc, "ammonia", latest.ammoniaPpm);
  setJsonFloat(doc, "smoke", latest.smokePercent);
  doc["flame"] = latest.flameDetected;
  publishJson(topicFor("alert"), doc);
}

void postEnvironment() {
  if (!wifiConnected() || !hasBackendConfig()) {
    return;
  }

  HTTPClient http;
  String url = apiUrl("/api/environment");
  if (!http.begin(url)) {
    Serial.println(F("HTTP begin failed"));
    return;
  }
  http.setConnectTimeout(2000);
  http.setTimeout(3000);

  JsonDocument doc;
  doc["barnId"] = cfg.barnId;
  doc["deviceId"] = cfg.deviceId;
  setJsonFloat(doc, "temperature", latest.temperature);
  setJsonFloat(doc, "humidity", latest.humidity);
  setJsonFloat(doc, "ammonia", latest.ammoniaPpm);
  setJsonFloat(doc, "lightLux", latest.lightLux);
  setJsonFloat(doc, "smoke", latest.smokePercent);
  doc["fanOn"] = actuators.fan;
  doc["atomizerOn"] = actuators.atomizer;
  doc["flame"] = latest.flameDetected;

  String payload;
  serializeJson(doc, payload);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(payload);
  if (code < 200 || code >= 300) {
    Serial.printf("HTTP POST /api/environment failed code=%d\n", code);
  }
  http.end();
}

bool commandDeviceMatches(const String &deviceId) {
  return deviceId == cfg.deviceId || deviceId == "relay_01" || deviceId == "all";
}

void pollBackendCommands() {
  if (!wifiConnected() || !hasBackendConfig()) {
    return;
  }

  HTTPClient http;
  if (!http.begin(apiUrl("/api/devices/commands"))) {
    return;
  }
  http.setConnectTimeout(2000);
  http.setTimeout(3000);
  int code = http.GET();
  if (code != 200) {
    http.end();
    return;
  }

  String payload = http.getString();
  http.end();

  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, payload);
  if (error || !doc.is<JsonArray>()) {
    Serial.printf("Command poll JSON error: %s\n", error.c_str());
    return;
  }

  JsonArray arr = doc.as<JsonArray>();
  uint32_t maxSeen = lastHttpCommandId;
  for (int i = static_cast<int>(arr.size()) - 1; i >= 0; i--) {
    JsonObject item = arr[i];
    uint32_t id = item["id"] | 0;
    if (id <= lastHttpCommandId) {
      continue;
    }
    if (id > maxSeen) {
      maxSeen = id;
    }
    String deviceId = item["deviceId"] | "";
    if (!commandDeviceMatches(deviceId)) {
      continue;
    }
    String action = item["action"] | "";
    bool enabled = item["enabled"] | true;
    if (action.length() > 0) {
      applyCommand(action, enabled, "http");
    }
  }
  lastHttpCommandId = maxSeen;
}

void readSensors() {
  latest.seq++;

  if (sht31Ok) {
    float t = sht31.readTemperature();
    float h = sht31.readHumidity();
    latest.temperature = isfinite(t) ? t : NAN;
    latest.humidity = isfinite(h) ? h : NAN;
  }

  if (bh1750Ok) {
    float lux = lightMeter.readLightLevel();
    latest.lightLux = lux >= 0 ? lux : NAN;
  }

#if ENABLE_MQ_SENSORS
  latest.nh3Raw = analogRead(PIN_NH3_ADC);
  latest.smokeRaw = analogRead(PIN_SMOKE_ADC);
  latest.ammoniaPpm = rawToPpm(latest.nh3Raw);
  latest.smokePercent = rawToPercent(latest.smokeRaw);
#else
  latest.nh3Raw = -1;
  latest.smokeRaw = -1;
  latest.ammoniaPpm = NAN;
  latest.smokePercent = NAN;
#endif

  bool flameLevel = digitalRead(PIN_FLAME_DIGITAL) == HIGH;
  latest.flameDetected = FLAME_ACTIVE_LOW ? !flameLevel : flameLevel;
  latest.rssi = wifiConnected() ? WiFi.RSSI() : 0;
}

bool highTemperature() {
  return isfinite(latest.temperature) && latest.temperature >= TEMP_ALARM_C;
}

bool fanNeeded() {
  bool temp = isfinite(latest.temperature) && latest.temperature >= TEMP_FAN_ON_C;
  bool nh3 = isfinite(latest.ammoniaPpm) && latest.ammoniaPpm >= NH3_FAN_ON_PPM;
  bool smoke = isfinite(latest.smokePercent) && latest.smokePercent >= SMOKE_ALARM_PERCENT;
  return temp || nh3 || smoke || latest.flameDetected;
}

bool atomizerNeeded() {
  bool hot = isfinite(latest.temperature) && latest.temperature >= ATOMIZER_TEMP_ON_C;
  bool dryEnough = !isfinite(latest.humidity) || latest.humidity <= ATOMIZER_MAX_HUMIDITY_PERCENT;
  return hot && dryEnough && !latest.flameDetected;
}

bool alarmNeeded() {
  bool nh3 = isfinite(latest.ammoniaPpm) && latest.ammoniaPpm >= NH3_ALARM_PPM;
  bool smoke = isfinite(latest.smokePercent) && latest.smokePercent >= SMOKE_ALARM_PERCENT;
  return highTemperature() || nh3 || smoke || latest.flameDetected ||
         millis() < actuators.remoteAlarmUntil;
}

bool resolveMode(OverrideMode mode, bool automaticValue) {
  if (mode == MODE_FORCE_ON) {
    return true;
  }
  if (mode == MODE_FORCE_OFF) {
    return false;
  }
  return automaticValue;
}

void applyRules() {
  bool oldFan = actuators.fan;
  bool oldAtomizer = actuators.atomizer;
  bool oldAlarm = actuators.alarm;

  actuators.fan = resolveMode(actuators.fanMode, fanNeeded());
  actuators.atomizer = resolveMode(actuators.atomizerMode, atomizerNeeded());
  actuators.alarm = resolveMode(actuators.alarmMode, alarmNeeded());

  if (!oldAlarm && actuators.alarm) {
    String reason = "env_alert";
    if (latest.flameDetected) {
      reason = "flame";
    } else if (isfinite(latest.smokePercent) && latest.smokePercent >= SMOKE_ALARM_PERCENT) {
      reason = "smoke";
    } else if (isfinite(latest.ammoniaPpm) && latest.ammoniaPpm >= NH3_ALARM_PPM) {
      reason = "nh3_high";
    } else if (highTemperature()) {
      reason = "temp_high";
    }
    publishAlert(reason, "warning", "Local rule triggered actuator alarm");
    sendMaixCaptureRequest(reason);
  }

  if (oldFan != actuators.fan || oldAtomizer != actuators.atomizer || oldAlarm != actuators.alarm) {
    Serial.printf("actuators fan=%d atomizer=%d alarm=%d\n",
                  actuators.fan, actuators.atomizer, actuators.alarm);
  }
}

void handleMaixEvent(String line) {
  line.trim();
  if (line.length() == 0) {
    return;
  }

  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, line);
  if (error) {
    Serial.printf("MaixCam JSON error: %s line=%s\n", error.c_str(), line.c_str());
    return;
  }

  String type = doc["type"] | "";
  if (type == "vision_event") {
    String event = doc["event"] | "unknown";
    String level = doc["level"] | "info";
    float score = doc["score"] | 0.0f;
    Serial.printf("MaixCam event=%s level=%s score=%.2f\n", event.c_str(), level.c_str(), score);

    if (level == "warning" || level == "critical" || event == "fall_suspect") {
      actuators.remoteAlarmUntil = millis() + 15000UL;
      publishAlert("vision_" + event, level, "MaixCam vision event triggered local alarm");
    }

    if (mqttClient.connected()) {
      JsonDocument out;
      out["cameraId"] = doc["cameraId"] | "cam_01";
      out["barnId"] = cfg.barnId;
      out["ts"] = nowEpoch();
      out["eventType"] = event;
      out["level"] = level;
      out["score"] = score;
      out["trackId"] = doc["trackId"] | 0;
      publishJson("cattle/" + cfg.barnId + "/cam_01/vision/event", out);
    }
  } else if (type == "status") {
    Serial.printf("MaixCam status: %s\n", line.c_str());
  } else {
    Serial.printf("MaixCam message: %s\n", line.c_str());
  }
}

void handleMaixSerial() {
  while (MaixSerial.available()) {
    char c = static_cast<char>(MaixSerial.read());
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      handleMaixEvent(maixLine);
      maixLine = "";
    } else if (maixLine.length() < 512) {
      maixLine += c;
    } else {
      maixLine = "";
    }
  }
}

void updateDisplay() {
  if (!oledOk) {
    return;
  }
  uint32_t now = millis();
  if (now - lastDisplayMs < 1000UL) {
    return;
  }
  lastDisplayMs = now;

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.printf("%s %s\n", cfg.barnId.c_str(), cfg.deviceId.c_str());
  display.printf("WiFi:%s MQTT:%s\n", wifiConnected() ? "on" : "off",
                 mqttClient.connected() ? "on" : "off");
  display.printf("T:");
  if (isfinite(latest.temperature)) {
    display.printf("%.1fC ", latest.temperature);
  } else {
    display.print("-- ");
  }
  display.print("H:");
  if (isfinite(latest.humidity)) {
    display.printf("%.0f%%\n", latest.humidity);
  } else {
    display.print("--\n");
  }
  display.printf("NH3:");
  if (isfinite(latest.ammoniaPpm)) {
    display.printf("%.1fppm\n", latest.ammoniaPpm);
  } else {
    display.print("--\n");
  }
  display.printf("Smoke:");
  if (isfinite(latest.smokePercent)) {
    display.printf("%.0f%% ", latest.smokePercent);
  } else {
    display.print("-- ");
  }
  display.printf("Flame:%d\n", latest.flameDetected);
  display.printf("F:%d M:%d A:%d\n", actuators.fan, actuators.atomizer, actuators.alarm);
  display.display();
}

void setupPins() {
  pinMode(PIN_FAN_RELAY, OUTPUT);
  pinMode(PIN_ATOMIZER_RELAY, OUTPUT);
  pinMode(PIN_ALARM_LIGHT, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_FLAME_DIGITAL, INPUT_PULLUP);
  if (!BUZZER_ACTIVE_MODULE) {
    ledcSetup(BUZZER_LEDC_CHANNEL, BUZZER_FREQUENCY_HZ, BUZZER_LEDC_RESOLUTION);
    ledcAttachPin(PIN_BUZZER, BUZZER_LEDC_CHANNEL);
    buzzerPwmReady = true;
  }
  if (PIN_STATUS_LED >= 0) {
    pinMode(PIN_STATUS_LED, OUTPUT);
  }

  writeDigitalOutput(PIN_FAN_RELAY, false, RELAY_ACTIVE_LOW);
  writeDigitalOutput(PIN_ATOMIZER_RELAY, false, RELAY_ACTIVE_LOW);
  writeDigitalOutput(PIN_ALARM_LIGHT, false, RELAY_ACTIVE_LOW);
  setBuzzer(false);

#if ENABLE_MQ_SENSORS
  analogReadResolution(12);
#if defined(ADC_11db)
  analogSetPinAttenuation(PIN_NH3_ADC, ADC_11db);
  analogSetPinAttenuation(PIN_SMOKE_ADC, ADC_11db);
#endif
#endif
}

void scanI2cBus() {
  Serial.println(F("I2C scan:"));
  for (uint8_t address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) {
      Serial.printf("  found 0x%02X\n", address);
    }
  }
}

void setupSensors() {
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(100000);
  scanI2cBus();
  sht31Ok = sht31.begin(SHT31_I2C_ADDR);
  bh1750Ok = lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE, BH1750_I2C_ADDR, &Wire);
  oledOk = display.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR);

  Serial.printf("SHT31=%s BH1750=%s OLED=%s\n",
                sht31Ok ? "ok" : "missing",
                bh1750Ok ? "ok" : "missing",
                oledOk ? "ok" : "missing");
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println(F("Smart Cattle ESP32 environment node boot"));

  loadConfig();
  setupPins();
  setupSensors();
  MaixSerial.begin(115200, SERIAL_8N1, PIN_MAIX_RX, PIN_MAIX_TX);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(1024);
  mqttClient.setServer(cfg.mqttHost.c_str(), cfg.mqttPort);

  printConfig();
  printHelp();
}

void loop() {
  handleSerialConsole();
  handleMaixSerial();

  ensureWifi();
  ensureMqtt();
  mqttClient.loop();

  uint32_t now = millis();
  if (now - lastSensorMs >= SENSOR_INTERVAL_MS) {
    lastSensorMs = now;
    readSensors();
    applyRules();
  }

  if (now - lastTelemetryMs >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryMs = now;
    publishTelemetry();
    postEnvironment();
  }

  if (now - lastStatusMs >= STATUS_INTERVAL_MS) {
    lastStatusMs = now;
    publishStatus();
  }

  if (now - lastCommandPollMs >= COMMAND_POLL_INTERVAL_MS) {
    lastCommandPollMs = now;
    pollBackendCommands();
  }

  applyOutputs();
  updateDisplay();
}
