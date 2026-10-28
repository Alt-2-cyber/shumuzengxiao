#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <U8g2lib.h>
#include <driver/i2s.h>
#include <esp_system.h>
#include "MAX30105.h"
#include "heartRate.h"
#include "spo2_algorithm.h"

#include "config.h"
#include "cattle_audio_model.h"
#include "cattle_behavior_model.h"
#include "cattle_posture_model.h"
#include "cattle_lameness_model.h"
#include "motion_temporal_stream.h"

DHT dht(PIN_DHT11, DHT_TYPE);
MAX30105 max30102;
U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
HardwareSerial b1Serial(2);
SPIClass adxlSpi(FSPI);
SPISettings adxlSpiSettings(ADXL345_SPI_FREQUENCY_HZ, MSBFIRST, SPI_MODE3);

enum FanMode {
  FAN_AUTO,
  FAN_FORCE_ON,
  FAN_FORCE_OFF
};

enum BehaviorClass : uint8_t {
  BEHAVIOR_GRAZING = 0,
  BEHAVIOR_LYING_RUMINATING = 1,
  BEHAVIOR_LYING_RESTING = 2,
  BEHAVIOR_STANDING_RESTING = 3,
  BEHAVIOR_WALKING = 4,
  BEHAVIOR_STANDING_RUMINATING = 5,
  BEHAVIOR_CLASS_COUNT = 6
};

constexpr uint8_t POSTURE_CLASS_COUNT = 2;

static_assert(cattle_behavior_model::kClassCount == BEHAVIOR_CLASS_COUNT,
              "Behavior model class count mismatch");
static_assert(cattle_posture_model::kClassCount == POSTURE_CLASS_COUNT,
              "Posture model class count mismatch");
static_assert(cattle_lameness_model::kFeatureCount == 12,
              "Lameness feature layout mismatch");
static_assert(1000UL / MOTION_SAMPLE_INTERVAL_MS == MOTION_TEMPORAL_SAMPLE_RATE_HZ,
              "Temporal research model requires uniform 20 Hz sampling");

const char *const BEHAVIOR_LABELS[BEHAVIOR_CLASS_COUNT] = {
    "grazing",
    "lying_ruminating",
    "lying_resting",
    "standing_resting",
    "walking",
    "standing_ruminating"};
const char *const POSTURE_LABELS[POSTURE_CLASS_COUNT] = {
    "lying", "standing"};

struct MotionReading {
  float ax = NAN;
  float ay = NAN;
  float az = NAN;
  float gx = NAN;
  float gy = NAN;
  float gz = NAN;
  float temperature = NAN;
};

struct Adxl345SpiDiagnostics {
  uint8_t deviceId = 0xFF;
  uint8_t dataFormat = 0xFF;
  uint8_t bwRate = 0xFF;
  uint8_t powerCtl = 0xFF;
  bool configVerified = false;
};

struct MotionWindow {
  uint16_t samples = 0;
  uint16_t classifiedSamples = 0;
  uint16_t modelSamples = 0;
  uint16_t classVotes[BEHAVIOR_CLASS_COUNT] = {};
  uint16_t postureModelSamples = 0;
  uint16_t postureClassifiedSamples = 0;
  uint16_t postureClassVotes[POSTURE_CLASS_COUNT] = {};
  float neckActivitySum = 0.0f;
  float bodyActivitySum = 0.0f;
  float legActivitySum = 0.0f;
  float neckActivity = NAN;
  float bodyActivity = NAN;
  float legActivity = NAN;
  float bodyTiltDeg = NAN;
  String behavior = "sensors_missing";
  String posture = "unknown";
  float confidence = 0.0f;
  float postureConfidence = 0.0f;
  String neckModelBehavior = "waiting";
  float neckModelConfidence = 0.0f;
};

struct ScalarStats {
  uint16_t samples = 0;
  uint16_t deltaSamples = 0;
  double sum = 0.0;
  double squareSum = 0.0;
  double deltaSum = 0.0;
  double deltaSquareSum = 0.0;
  float previous = NAN;

  void add(float value) {
    if (!isfinite(value)) {
      return;
    }
    sum += value;
    squareSum += value * value;
    samples++;
    if (isfinite(previous)) {
      float delta = fabsf(value - previous);
      deltaSum += delta;
      deltaSquareSum += delta * delta;
      deltaSamples++;
    }
    previous = value;
  }

  float mean() const {
    return samples ? static_cast<float>(sum / samples) : 0.0f;
  }

  float standardDeviation() const {
    if (!samples) {
      return 0.0f;
    }
    float average = mean();
    return sqrtf(fmaxf(0.0f, static_cast<float>(squareSum / samples) - average * average));
  }

  float deltaMean() const {
    return deltaSamples ? static_cast<float>(deltaSum / deltaSamples) : 0.0f;
  }

  float deltaStandardDeviation() const {
    if (!deltaSamples) {
      return 0.0f;
    }
    float average = deltaMean();
    return sqrtf(fmaxf(0.0f, static_cast<float>(deltaSquareSum / deltaSamples) - average * average));
  }
};

struct LamenessFeatureWindow {
  uint16_t samples = 0;
  ScalarStats neckAcceleration;
  ScalarStats bodyAcceleration;
  ScalarStats legAcceleration;
};

struct LamenessReading {
  uint16_t windowSamples = 0;
  bool candidate = false;
  bool rejected = false;
  float score = NAN;
  String status = "feature_only";
  String modelVersion = cattle_lameness_model::kVersion;
};

struct MotionCaptureSession {
  bool active = false;
  uint32_t id = 0;
  uint32_t startedAtMs = 0;
  uint32_t durationMs = 0;
  uint32_t samples = 0;
  uint32_t expectedSamples = 0;
  uint32_t attemptedSamples = 0;
  uint32_t droppedBackpressureSamples = 0;
  uint32_t droppedSensorSamples = 0;
  String sessionId;
};

struct AudioReading {
  uint32_t samples = 0;
  int32_t rawMin = 0;
  int32_t rawMax = 0;
  float rawMean = NAN;
  float rms = NAN;
  float peak = NAN;
  float dbfs = NAN;
  float saturationRatio = NAN;
  float zeroCrossingRate = NAN;
  float lowBandRatio = NAN;
  float midBandRatio = NAN;
  float highBandRatio = NAN;
  float snrDb = NAN;
  bool soundActive = false;
  bool vocalizationCandidate = false;
  bool respiratoryCandidate = false;
  bool abnormalVocalizationCandidate = false;
  bool captureInProgress = false;
  bool captureAvailable = false;
  uint32_t eventId = 0;
  float eventScore = 0.0f;
  String channel = "calibrating";
  String modelStatus = "untrained";
  String modelVersion = "untrained-audio-profile";
  String eventLabel = "none";
  String status = "not_initialized";
};

struct AudioLaneStats {
  uint32_t frames = 0;
  uint32_t saturated = 0;
  int32_t minimum = INT32_MAX;
  int32_t maximum = INT32_MIN;
  double sum = 0.0;
  double squareSum = 0.0;
};

struct AudioFeatureAccumulator {
  uint32_t samples = 0;
  uint32_t zeroCrossings = 0;
  uint32_t frames = 0;
  double squareSum = 0.0;
  double differenceSquareSum = 0.0;
  double bandEnergy[6] = {};
  float peak = 0.0f;
  float previous = 0.0f;
  bool hasPrevious = false;
};

struct PendingAudioEvent {
  bool pending = false;
  bool includePcm = false;
  uint32_t id = 0;
  float score = 0.0f;
  String type = "acoustic_candidate";
  String label = "unclassified";
};

struct B1Reading {
  uint32_t bytes = 0;
  String rawHex;
  bool receiving = false;
  float surfaceTemperature = NAN;
  float ambientTemperature = NAN;
  bool temperatureValid = false;
  uint8_t measurementType = 0;
  uint32_t lastMeasurementMs = 0;
  uint32_t validFrames = 0;
  uint32_t invalidFrames = 0;
  uint8_t lastCommand = 0;
  bool uartConfigured = false;
  bool debugShell = false;
  String debugAscii;
  String status = "starting";
};

bool maxOk = false;
bool sht31Ok = false;
bool bh1750Ok = false;
bool oledOk = false;
bool adxl345Ok = false;
bool mpu0Ok = false;
bool mpu1Ok = false;
bool microphoneOk = false;
uint8_t bh1750Address = BH1750_I2C_ADDR;
bool fanOn = false;
FanMode fanMode = FAN_AUTO;
uint8_t oledPage = 0;
int lastEncoderClk = HIGH;
int lastEncoderButton = HIGH;
uint32_t lastEncoderButtonMs = 0;
uint32_t lastSampleMs = 0;
uint32_t lastMotionSampleMs = 0;
uint32_t lastMaxSampleMs = 0;
uint32_t lastBuzzerToggleMs = 0;
uint32_t lastDisplayMs = 0;
uint32_t lastI2cRecoveryMs = 0;
uint32_t lastSpiRecoveryMs = 0;
bool buzzerOn = false;
bool manualAlarmOn = false;
uint32_t lastHostCommandId = 0;
String lastHostCommandAction = "none";
String lastHostCommandStatus = "none";
Preferences networkPreferences;
String wifiSsid = DEFAULT_WIFI_SSID;
String wifiPass = DEFAULT_WIFI_PASS;
String backendUrl = DEFAULT_BACKEND_URL;
uint32_t lastWifiAttemptMs = 0;
uint32_t lastWifiPostMs = 0;
bool wifiStateReported = false;
char hostCommandBuffer[256];
size_t hostCommandLength = 0;
uint32_t fingerSinceMs = 0;
uint32_t maxIrSeen = 0;
uint32_t minIrSeen = UINT32_MAX;

double microphoneDcOffset = 0.0;
double microphoneSquareSum = 0.0;
float microphonePeak = 0.0f;
uint32_t microphoneSampleCount = 0;
uint32_t microphoneReadErrors = 0;
int32_t microphoneRawMin = INT32_MAX;
int32_t microphoneRawMax = INT32_MIN;
double microphoneRawSum = 0.0;
uint32_t microphoneSaturatedSamples = 0;
AudioLaneStats microphoneLaneStats[2];
int8_t microphoneSlot = INMP441_FORCE_SLOT;
bool microphoneSlotCalibrated = INMP441_FORCE_SLOT >= 0;
bool microphoneSlotHasSignal = false;
float microphoneNoiseFloor = 0.003f;
float microphoneFeatureFrame[INMP441_FEATURE_FRAME_SAMPLES];
size_t microphoneFeatureFrameLength = 0;
uint8_t microphoneDecimation = 0;
AudioFeatureAccumulator microphoneFeatures;
float microphoneFeatureVector[cattle_audio_model::kFeatureCount] = {};
int8_t microphoneCaptureBuffer[INMP441_CAPTURE_SAMPLES];
uint32_t microphoneCaptureSamples = 0;
bool microphoneCaptureRequested = false;
bool microphoneCaptureActive = false;
String microphoneCaptureReason = "manual_capture";
float microphoneCaptureScore = 0.0f;
uint32_t microphoneEventSequence = 0;
uint32_t deviceBootId = 0;
uint32_t lastAudioEventMs = 0;
uint32_t lastAudioCaptureMs = 0;
PendingAudioEvent pendingAudioEvent;

uint8_t b1RawBuffer[B1_RAW_BUFFER_SIZE];
size_t b1RawCount = 0;
uint32_t b1WindowBytes = 0;
uint32_t b1LastByteMs = 0;
uint32_t b1LastRequestMs = 0;
uint32_t b1StartedMs = 0;
bool b1BodyModeSent = false;
uint8_t b1FrameBuffer[B1_FRAME_BUFFER_SIZE];
size_t b1FrameIndex = 0;
size_t b1ExpectedFrameLength = 0;
uint32_t b1AsciiShift = 0;

static const int OXIMETER_BUFFER_SIZE = 100;
uint32_t irBuffer[OXIMETER_BUFFER_SIZE];
uint32_t redBuffer[OXIMETER_BUFFER_SIZE];
int bufferIndex = 0;
bool bufferFilled = false;

const byte RATE_SIZE = 6;
byte rates[RATE_SIZE];
byte rateSpot = 0;
long lastBeat = 0;

struct Reading {
  uint32_t seq = 0;
  float temperature = NAN;
  float humidity = NAN;
  String climateSource = "none";
  float lightLux = NAN;
  int mqRaw = 0;
  bool flame = false;
  uint32_t ir = 0;
  uint32_t red = 0;
  float heartRate = NAN;
  int spo2 = -1;
  bool heartRateValid = false;
  bool spo2Valid = false;
  bool heartRateEstimated = false;
  bool spo2Estimated = false;
  bool fingerDetected = false;
  String maxStatus = "missing";
  String level = "normal";
};

Reading latest;
MotionReading adxlReading;
MotionReading mpu0Reading;
MotionReading mpu1Reading;
MotionReading previousAdxlReading;
MotionReading previousMpu0Reading;
MotionReading previousMpu1Reading;
Adxl345SpiDiagnostics neckSpiDiagnostics;
Adxl345SpiDiagnostics bodySpiDiagnostics;
Adxl345SpiDiagnostics legSpiDiagnostics;
MotionWindow motionWindow;
MotionTemporalStream motionTemporalResearch;
LamenessFeatureWindow lamenessWindow;
LamenessReading lamenessReading;
MotionCaptureSession motionCapture;
AudioReading audioReading;
B1Reading b1Reading;

bool readAdxl345(MotionReading &reading);
bool readAdxl345Spi(uint8_t chipSelect, MotionReading &reading);
bool setupAdxl345Spi(uint8_t chipSelect);
bool readMpu(uint8_t address, MotionReading &reading);
void applyLed(const String &level);
void sendMotionCaptureState(const char *status);

bool wifiConfigured() {
  return wifiSsid.length() > 0;
}

bool wifiConnected() {
  return WiFi.status() == WL_CONNECTED;
}

String normalizedBackendUrl() {
  String base = backendUrl;
  base.trim();
  while (base.endsWith("/")) {
    base.remove(base.length() - 1);
  }
  return base;
}

void loadNetworkConfig() {
  networkPreferences.begin("cattle-net", false);
  wifiSsid = networkPreferences.isKey("wifi_ssid")
                 ? networkPreferences.getString("wifi_ssid")
                 : DEFAULT_WIFI_SSID;
  wifiPass = networkPreferences.isKey("wifi_pass")
                 ? networkPreferences.getString("wifi_pass")
                 : DEFAULT_WIFI_PASS;
  backendUrl = networkPreferences.isKey("backend_url")
                   ? networkPreferences.getString("backend_url")
                   : DEFAULT_BACKEND_URL;
}

void saveNetworkConfig(const String &key, const String &value) {
  if (key == "wifi_ssid") {
    wifiSsid = value;
    networkPreferences.putString("wifi_ssid", wifiSsid);
    WiFi.disconnect();
    wifiStateReported = false;
    lastWifiAttemptMs = 0;
  } else if (key == "wifi_pass") {
    wifiPass = value;
    networkPreferences.putString("wifi_pass", wifiPass);
    WiFi.disconnect();
    wifiStateReported = false;
    lastWifiAttemptMs = 0;
  } else if (key == "backend_url") {
    backendUrl = value;
    networkPreferences.putString("backend_url", backendUrl);
  } else {
    Serial.println("Unknown network config key");
  }
}

void printNetworkConfig() {
  Serial.println("--- network config ---");
  Serial.printf("wifi_ssid=%s\n", wifiSsid.c_str());
  Serial.printf("backend_url=%s\n", backendUrl.c_str());
  Serial.printf("wifi=%s rssi=%d ip=%s\n",
                wifiConnected() ? "connected" : "offline",
                wifiConnected() ? WiFi.RSSI() : 0,
                wifiConnected() ? WiFi.localIP().toString().c_str() : "-");
}

void ensureWifi() {
  if (!wifiConfigured()) {
    return;
  }
  if (wifiConnected()) {
    if (!wifiStateReported) {
      Serial.printf("WiFi connected ssid=%s ip=%s rssi=%d\n",
                    wifiSsid.c_str(), WiFi.localIP().toString().c_str(), WiFi.RSSI());
      wifiStateReported = true;
    }
    return;
  }

  wifiStateReported = false;
  uint32_t now = millis();
  if (now - lastWifiAttemptMs < WIFI_RETRY_INTERVAL_MS) {
    return;
  }
  lastWifiAttemptMs = now;
  WiFi.mode(WIFI_STA);
  WiFi.begin(wifiSsid.c_str(), wifiPass.c_str());
  Serial.printf("WiFi connecting to %s\n", wifiSsid.c_str());
}

void postTelemetryPayload(const String &payload) {
  String base = normalizedBackendUrl();
  if (!wifiConnected() || base.length() == 0) {
    return;
  }

  WiFiClient client;
  HTTPClient http;
  String url = base + "/api/telemetry/ingest";
  http.setTimeout(WIFI_HTTP_TIMEOUT_MS);
  if (!http.begin(client, url)) {
    Serial.println("WiFi telemetry HTTP begin failed");
    return;
  }
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(payload);
  if (code < 200 || code >= 300) {
    Serial.printf("WiFi telemetry HTTP failed code=%d\n", code);
  }
  http.end();
}

void emitTelemetry(JsonDocument &doc) {
  doc["transport"] = "usb_serial+wifi_http";
  doc["wifiConnected"] = wifiConnected();
  doc["wifiRssi"] = wifiConnected() ? WiFi.RSSI() : 0;

  String payload;
  serializeJson(doc, payload);
  Serial.println(payload);

  uint32_t now = millis();
  if (wifiConnected() && normalizedBackendUrl().length() > 0 &&
      (lastWifiPostMs == 0 || now - lastWifiPostMs >= WIFI_POST_INTERVAL_MS)) {
    lastWifiPostMs = now;
    postTelemetryPayload(payload);
  }
}

bool handleNetworkCommand(const char *line) {
  if (strcmp(line, "show") == 0) {
    printNetworkConfig();
    return true;
  }
  if (strcmp(line, "reboot") == 0) {
    ESP.restart();
    return true;
  }
  if (strcmp(line, "clear_config") == 0) {
    networkPreferences.clear();
    Serial.println("Network config cleared. Rebooting.");
    delay(250);
    ESP.restart();
    return true;
  }
  if (strncmp(line, "set ", 4) != 0) {
    return false;
  }

  String command = line;
  int separator = command.indexOf(' ', 4);
  if (separator < 0) {
    Serial.println("Usage: set wifi_ssid|wifi_pass|backend_url <value>");
    return true;
  }
  String key = command.substring(4, separator);
  String value = command.substring(separator + 1);
  value.trim();
  if (key == "wifi_ssid" || key == "wifi_pass" || key == "backend_url") {
    saveNetworkConfig(key, value);
    Serial.println("OK");
  } else {
    Serial.println("Unknown network config key");
  }
  return true;
}

constexpr uint8_t AUDIO_BAND_COUNT = 6;
const uint8_t AUDIO_GOERTZEL_BINS[AUDIO_BAND_COUNT] = {2, 4, 8, 16, 32, 48};

void resetAudioFeatureAccumulator() {
  microphoneFeatures = AudioFeatureAccumulator();
  microphoneFeatureFrameLength = 0;
}

void resetMicrophoneWindow() {
  microphoneSquareSum = 0.0;
  microphonePeak = 0.0f;
  microphoneSampleCount = 0;
  microphoneRawMin = INT32_MAX;
  microphoneRawMax = INT32_MIN;
  microphoneRawSum = 0.0;
  microphoneSaturatedSamples = 0;
  resetAudioFeatureAccumulator();
}

void observeAudioLane(AudioLaneStats &stats, int32_t sample) {
  stats.frames++;
  stats.minimum = min(stats.minimum, sample);
  stats.maximum = max(stats.maximum, sample);
  stats.sum += sample;
  stats.squareSum += static_cast<double>(sample) * sample;
  if (sample <= -0x7F0000 || sample >= 0x7F0000) {
    stats.saturated++;
  }
}

float audioLaneQuality(const AudioLaneStats &stats) {
  if (stats.frames < 64 || stats.minimum == INT32_MAX) {
    return -1000.0f;
  }
  const double mean = stats.sum / stats.frames;
  const double variance = max(0.0, stats.squareSum / stats.frames - mean * mean);
  const float dynamicRms = static_cast<float>(sqrt(variance) / 8388608.0);
  const float saturation = static_cast<float>(stats.saturated) / stats.frames;
  const int64_t range = static_cast<int64_t>(stats.maximum) - stats.minimum;
  if (saturation >= AUDIO_INVALID_SATURATION_RATIO || dynamicRms >= AUDIO_INVALID_RMS) {
    return -900.0f;
  }
  if (range < 64 || dynamicRms < 0.000002f) {
    return -500.0f;
  }
  return dynamicRms;
}

void resolveAudioSlot() {
  if (microphoneSlotCalibrated) {
    return;
  }
  if (microphoneLaneStats[0].frames < INMP441_SLOT_CALIBRATION_FRAMES ||
      microphoneLaneStats[1].frames < INMP441_SLOT_CALIBRATION_FRAMES) {
    return;
  }

  const float firstQuality = audioLaneQuality(microphoneLaneStats[0]);
  const float secondQuality = audioLaneQuality(microphoneLaneStats[1]);
  microphoneSlot = firstQuality >= secondQuality ? 0 : 1;
  microphoneSlotHasSignal = max(firstQuality, secondQuality) > -100.0f;
  microphoneSlotCalibrated = true;
  const AudioLaneStats &selected = microphoneLaneStats[microphoneSlot];
  microphoneDcOffset = selected.frames == 0 ? 0.0 : selected.sum / selected.frames;
  audioReading.channel = String("slot") + String(microphoneSlot);
  Serial.printf("INMP441 slot calibration: slot0=%.6f slot1=%.6f selected=%d valid=%s\n",
                firstQuality,
                secondQuality,
                microphoneSlot,
                microphoneSlotHasSignal ? "yes" : "no");
}

void accumulateAudioFeatureFrame() {
  if (microphoneFeatureFrameLength != INMP441_FEATURE_FRAME_SAMPLES) {
    return;
  }
  for (uint8_t band = 0; band < AUDIO_BAND_COUNT; band++) {
    const float coefficient = 2.0f * cosf(
        2.0f * PI * AUDIO_GOERTZEL_BINS[band] / INMP441_FEATURE_FRAME_SAMPLES);
    float previous = 0.0f;
    float previousPrevious = 0.0f;
    for (size_t index = 0; index < microphoneFeatureFrameLength; index++) {
      const float current = microphoneFeatureFrame[index] + coefficient * previous - previousPrevious;
      previousPrevious = previous;
      previous = current;
    }
    const float energy = previousPrevious * previousPrevious + previous * previous -
                         coefficient * previous * previousPrevious;
    microphoneFeatures.bandEnergy[band] += max(0.0f, energy);
  }
  microphoneFeatures.frames++;
  microphoneFeatureFrameLength = 0;
}

void startAudioCaptureIfRequested() {
  if (!microphoneCaptureRequested || microphoneCaptureActive) {
    return;
  }
  microphoneCaptureActive = true;
  microphoneCaptureRequested = false;
  microphoneCaptureSamples = 0;
  audioReading.captureInProgress = true;
}

void completeAudioCapture() {
  microphoneCaptureActive = false;
  audioReading.captureInProgress = false;
  audioReading.captureAvailable = microphoneCaptureSamples > 0;
  lastAudioCaptureMs = millis();

  pendingAudioEvent.pending = true;
  pendingAudioEvent.includePcm = true;
  pendingAudioEvent.id = ++microphoneEventSequence;
  pendingAudioEvent.score = microphoneCaptureScore;
  pendingAudioEvent.type = microphoneCaptureReason;
  pendingAudioEvent.label = audioReading.eventLabel;
  audioReading.eventId = pendingAudioEvent.id;
}

void appendAudioCaptureSample(float normalized) {
  startAudioCaptureIfRequested();
  if (!microphoneCaptureActive) {
    return;
  }
  const float amplified = constrain(normalized * INMP441_CAPTURE_GAIN, -1.0f, 0.992f);
  microphoneCaptureBuffer[microphoneCaptureSamples++] =
      static_cast<int8_t>(roundf(amplified * 127.0f));
  if (microphoneCaptureSamples >= INMP441_CAPTURE_SAMPLES) {
    completeAudioCapture();
  }
}

void feedAudioFeatureSample(float normalized) {
  microphoneFeatures.samples++;
  microphoneFeatures.squareSum += static_cast<double>(normalized) * normalized;
  microphoneFeatures.peak = max(microphoneFeatures.peak, fabsf(normalized));
  if (microphoneFeatures.hasPrevious) {
    if ((normalized >= 0.0f) != (microphoneFeatures.previous >= 0.0f)) {
      microphoneFeatures.zeroCrossings++;
    }
    const float difference = normalized - microphoneFeatures.previous;
    microphoneFeatures.differenceSquareSum += static_cast<double>(difference) * difference;
  } else {
    microphoneFeatures.hasPrevious = true;
  }
  microphoneFeatures.previous = normalized;
  microphoneFeatureFrame[microphoneFeatureFrameLength++] = normalized;
  if (microphoneFeatureFrameLength == INMP441_FEATURE_FRAME_SAMPLES) {
    accumulateAudioFeatureFrame();
  }
  appendAudioCaptureSample(normalized);
}

void requestAudioCapture(const char *reason, float score) {
  if (microphoneCaptureActive || microphoneCaptureRequested) {
    return;
  }
  microphoneCaptureReason = reason;
  microphoneCaptureScore = score;
  microphoneCaptureRequested = true;
}

bool setupInmp441() {
  i2s_config_t i2sConfig = {};
  i2sConfig.mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_RX);
  i2sConfig.sample_rate = INMP441_SAMPLE_RATE_HZ;
  i2sConfig.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;
  // Read both slots. A floating or wrongly wired L/R pin otherwise looks like
  // a plausible, but unusable, one-channel signal.
  i2sConfig.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;
  i2sConfig.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  i2sConfig.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  i2sConfig.dma_buf_count = 8;
  i2sConfig.dma_buf_len = INMP441_DMA_SAMPLES;
  i2sConfig.use_apll = false;
  i2sConfig.tx_desc_auto_clear = false;
  i2sConfig.fixed_mclk = 0;

  if (i2s_driver_install(I2S_NUM_0, &i2sConfig, 0, nullptr) != ESP_OK) {
    return false;
  }

  i2s_pin_config_t pinConfig = {};
  pinConfig.bck_io_num = PIN_INMP441_SCK;
  pinConfig.ws_io_num = PIN_INMP441_WS;
  pinConfig.data_out_num = I2S_PIN_NO_CHANGE;
  pinConfig.data_in_num = PIN_INMP441_SD;
  if (i2s_set_pin(I2S_NUM_0, &pinConfig) != ESP_OK) {
    i2s_driver_uninstall(I2S_NUM_0);
    return false;
  }
  microphoneLaneStats[0] = AudioLaneStats();
  microphoneLaneStats[1] = AudioLaneStats();
  microphoneSlot = INMP441_FORCE_SLOT;
  microphoneSlotCalibrated = INMP441_FORCE_SLOT >= 0;
  microphoneSlotHasSignal = INMP441_FORCE_SLOT >= 0;
  audioReading.channel = microphoneSlotCalibrated ? String("slot") + String(microphoneSlot) : "calibrating";
  resetMicrophoneWindow();
  return true;
}

void sampleInmp441() {
  if (!microphoneOk) {
    return;
  }

  static int32_t samples[INMP441_DMA_SAMPLES * 2];
  for (uint8_t block = 0; block < 8; block++) {
    size_t bytesRead = 0;
    esp_err_t result = i2s_read(I2S_NUM_0, samples, sizeof(samples), &bytesRead, 0);
    if (result != ESP_OK) {
      if (result != ESP_ERR_TIMEOUT) {
        microphoneReadErrors++;
      }
      break;
    }
    if (bytesRead == 0) {
      break;
    }

    size_t wordCount = bytesRead / sizeof(samples[0]);
    wordCount -= wordCount % 2;
    for (size_t index = 0; index < wordCount; index += 2) {
      // INMP441 supplies signed 24-bit samples in the high bits of each word.
      const int32_t slot0 = samples[index] >> INMP441_SAMPLE_SHIFT;
      const int32_t slot1 = samples[index + 1] >> INMP441_SAMPLE_SHIFT;
      if (!microphoneSlotCalibrated) {
        observeAudioLane(microphoneLaneStats[0], slot0);
        observeAudioLane(microphoneLaneStats[1], slot1);
        resolveAudioSlot();
        continue;
      }

      const int32_t sample = microphoneSlot == 1 ? slot1 : slot0;
      microphoneRawMin = min(microphoneRawMin, sample);
      microphoneRawMax = max(microphoneRawMax, sample);
      microphoneRawSum += sample;
      if (sample <= -0x7F0000 || sample >= 0x7F0000) {
        microphoneSaturatedSamples++;
      }
      microphoneDcOffset += (static_cast<double>(sample) - microphoneDcOffset) * 0.001f;
      const float normalized = constrain(static_cast<float>(
          (static_cast<double>(sample) - microphoneDcOffset) / 8388608.0), -1.0f, 1.0f);
      microphoneSquareSum += static_cast<double>(normalized) * normalized;
      microphonePeak = max(microphonePeak, fabsf(normalized));
      microphoneSampleCount++;

      // The classifier and PCM capture run at 8 kHz after deterministic 2:1
      // decimation; this keeps CPU, RAM and serial transfer bounded.
      microphoneDecimation++;
      if (microphoneDecimation >= INMP441_SAMPLE_RATE_HZ / INMP441_FEATURE_SAMPLE_RATE_HZ) {
        microphoneDecimation = 0;
        feedAudioFeatureSample(normalized);
      }
    }
  }
}

void finalizeAudioWindow() {
  audioReading.samples = microphoneSampleCount;
  audioReading.modelVersion = cattle_audio_model::kVersion;
  audioReading.modelStatus = cattle_audio_model::kEnabled ? "deployed" : "feature_only";
  audioReading.captureInProgress = microphoneCaptureActive || microphoneCaptureRequested;
  audioReading.respiratoryCandidate = false;
  audioReading.abnormalVocalizationCandidate = false;
  audioReading.eventLabel = "none";
  audioReading.eventScore = 0.0f;
  if (!microphoneOk || microphoneSampleCount == 0) {
    audioReading.rawMin = 0;
    audioReading.rawMax = 0;
    audioReading.rawMean = NAN;
    audioReading.rms = NAN;
    audioReading.peak = NAN;
    audioReading.dbfs = NAN;
    audioReading.saturationRatio = NAN;
    audioReading.zeroCrossingRate = NAN;
    audioReading.lowBandRatio = NAN;
    audioReading.midBandRatio = NAN;
    audioReading.highBandRatio = NAN;
    audioReading.snrDb = NAN;
    audioReading.soundActive = false;
    audioReading.vocalizationCandidate = false;
    audioReading.status = microphoneOk ? "no_samples" : "not_initialized";
  } else {
    audioReading.rawMin = microphoneRawMin;
    audioReading.rawMax = microphoneRawMax;
    audioReading.rawMean = microphoneRawSum / microphoneSampleCount;
    audioReading.rms = sqrt(microphoneSquareSum / microphoneSampleCount);
    audioReading.peak = microphonePeak;
    audioReading.dbfs = 20.0f * log10f(max(audioReading.rms, 0.000000001f));
    audioReading.saturationRatio = static_cast<float>(microphoneSaturatedSamples) /
                                   microphoneSampleCount;
    if (microphoneFeatures.samples > 0) {
      const float spectralTotal = static_cast<float>(
          microphoneFeatures.bandEnergy[0] + microphoneFeatures.bandEnergy[1] +
          microphoneFeatures.bandEnergy[2] + microphoneFeatures.bandEnergy[3] +
          microphoneFeatures.bandEnergy[4] + microphoneFeatures.bandEnergy[5]);
      audioReading.zeroCrossingRate = static_cast<float>(microphoneFeatures.zeroCrossings) /
                                      microphoneFeatures.samples;
      if (spectralTotal > 0.000000001f) {
        audioReading.lowBandRatio = static_cast<float>(
            (microphoneFeatures.bandEnergy[0] + microphoneFeatures.bandEnergy[1]) / spectralTotal);
        audioReading.midBandRatio = static_cast<float>(
            (microphoneFeatures.bandEnergy[2] + microphoneFeatures.bandEnergy[3]) / spectralTotal);
        audioReading.highBandRatio = static_cast<float>(
            (microphoneFeatures.bandEnergy[4] + microphoneFeatures.bandEnergy[5]) / spectralTotal);
      }
    } else {
      audioReading.zeroCrossingRate = NAN;
      audioReading.lowBandRatio = NAN;
      audioReading.midBandRatio = NAN;
      audioReading.highBandRatio = NAN;
    }

    if (!microphoneSlotCalibrated) {
      audioReading.status = "calibrating";
      audioReading.soundActive = false;
      audioReading.vocalizationCandidate = false;
    } else if (!microphoneSlotHasSignal ||
               audioReading.rms >= AUDIO_INVALID_RMS ||
               audioReading.saturationRatio >= AUDIO_INVALID_SATURATION_RATIO) {
      audioReading.soundActive = false;
      audioReading.vocalizationCandidate = false;
      audioReading.status = "signal_invalid";
    } else {
      audioReading.soundActive = audioReading.rms >= AUDIO_ACTIVE_RMS;
      audioReading.vocalizationCandidate =
          audioReading.rms >= AUDIO_VOCALIZATION_RMS &&
          audioReading.peak >= AUDIO_VOCALIZATION_PEAK;
      audioReading.status = "ok";

      if (!audioReading.soundActive) {
        microphoneNoiseFloor = microphoneNoiseFloor * 0.96f + audioReading.rms * 0.04f;
      }
      microphoneNoiseFloor = max(microphoneNoiseFloor, 0.00001f);
      audioReading.snrDb = 20.0f * log10f(max(audioReading.rms, 0.000000001f) /
                                           microphoneNoiseFloor);

      if (audioReading.soundActive && microphoneFeatures.samples > 0 &&
          cattle_audio_model::kEnabled) {
        const float spectralTotal = static_cast<float>(
            microphoneFeatures.bandEnergy[0] + microphoneFeatures.bandEnergy[1] +
            microphoneFeatures.bandEnergy[2] + microphoneFeatures.bandEnergy[3] +
            microphoneFeatures.bandEnergy[4] + microphoneFeatures.bandEnergy[5]);
        microphoneFeatureVector[0] = logf(max(audioReading.rms, 0.00001f));
        microphoneFeatureVector[1] = audioReading.zeroCrossingRate;
        microphoneFeatureVector[2] = min(10.0f, audioReading.peak / max(audioReading.rms, 0.00001f));
        for (uint8_t band = 0; band < AUDIO_BAND_COUNT; band++) {
          microphoneFeatureVector[3 + band] = logf(max(0.000001f,
              static_cast<float>(microphoneFeatures.bandEnergy[band] / max(spectralTotal, 0.000000001f))));
        }
        microphoneFeatureVector[9] = logf(max(0.000001f, sqrtf(static_cast<float>(
            microphoneFeatures.differenceSquareSum / max(microphoneFeatures.squareSum, 0.000000001)))));
        const cattle_audio_model::Prediction prediction =
            cattle_audio_model::predict(microphoneFeatureVector);
        audioReading.eventLabel = prediction.label;
        audioReading.eventScore = prediction.score;
        audioReading.respiratoryCandidate =
            cattle_audio_model::isRespiratoryLabel(prediction.label) &&
            prediction.score >= AUDIO_DISEASE_CANDIDATE_SCORE;
        audioReading.abnormalVocalizationCandidate =
            cattle_audio_model::isAbnormalVocalizationLabel(prediction.label) &&
            prediction.score >= AUDIO_DISEASE_CANDIDATE_SCORE;

        if (cattle_audio_model::isScreeningLabel(prediction.label) &&
            prediction.score >= AUDIO_DISEASE_CANDIDATE_SCORE &&
            millis() - lastAudioEventMs >= AUDIO_EVENT_MIN_INTERVAL_MS) {
          lastAudioEventMs = millis();
          pendingAudioEvent.pending = true;
          pendingAudioEvent.includePcm = false;
          pendingAudioEvent.id = ++microphoneEventSequence;
          pendingAudioEvent.score = prediction.score;
          pendingAudioEvent.type = prediction.label;
          pendingAudioEvent.label = prediction.label;
          audioReading.eventId = pendingAudioEvent.id;
          if (AUDIO_AUTO_CAPTURE_ENABLED &&
              millis() - lastAudioCaptureMs >= AUDIO_AUTO_CAPTURE_MIN_INTERVAL_MS) {
            requestAudioCapture(prediction.label, prediction.score);
          }
        }
      }
    }
  }
  resetMicrophoneWindow();
}

void writeBase64(const int8_t *data, size_t length) {
  static const char alphabet[] =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  for (size_t offset = 0; offset < length; offset += 3) {
    const uint32_t first = static_cast<uint8_t>(data[offset]);
    const bool hasSecond = offset + 1 < length;
    const bool hasThird = offset + 2 < length;
    const uint32_t second = hasSecond ? static_cast<uint8_t>(data[offset + 1]) : 0;
    const uint32_t third = hasThird ? static_cast<uint8_t>(data[offset + 2]) : 0;
    const uint32_t value = (first << 16) | (second << 8) | third;
    Serial.write(alphabet[(value >> 18) & 0x3F]);
    Serial.write(alphabet[(value >> 12) & 0x3F]);
    Serial.write(hasSecond ? alphabet[(value >> 6) & 0x3F] : '=');
    Serial.write(hasThird ? alphabet[value & 0x3F] : '=');
  }
}

void flushPendingAudioEvent() {
  if (!pendingAudioEvent.pending) {
    return;
  }

  Serial.printf("{\"type\":\"audio_event\",\"deviceId\":\"%s\",\"barnId\":\"%s\",\"cattleId\":\"%s\","
                "\"bootId\":\"%08lX\",\"edgeEventId\":%lu,\"eventType\":\"%s\",\"label\":\"%s\",\"score\":%.4f,"
                "\"durationMs\":%lu,\"snr\":%.2f,\"model\":{\"version\":\"%s\",\"status\":\"%s\"},"
                "\"features\":{\"rms\":%.6f,\"dbfs\":%.2f,\"zcr\":%.5f,\"lowBand\":%.5f,\"midBand\":%.5f,\"highBand\":%.5f,\"saturation\":%.5f}",
                DEVICE_ID,
                BARN_ID,
                CATTLE_ID,
                static_cast<unsigned long>(deviceBootId),
                static_cast<unsigned long>(pendingAudioEvent.id),
                pendingAudioEvent.type.c_str(),
                pendingAudioEvent.label.c_str(),
                pendingAudioEvent.score,
                static_cast<unsigned long>(pendingAudioEvent.includePcm ? INMP441_CAPTURE_DURATION_MS : SAMPLE_INTERVAL_MS),
                isfinite(audioReading.snrDb) ? audioReading.snrDb : 0.0f,
                audioReading.modelVersion.c_str(),
                audioReading.modelStatus.c_str(),
                isfinite(audioReading.rms) ? audioReading.rms : 0.0f,
                isfinite(audioReading.dbfs) ? audioReading.dbfs : 0.0f,
                isfinite(audioReading.zeroCrossingRate) ? audioReading.zeroCrossingRate : 0.0f,
                isfinite(audioReading.lowBandRatio) ? audioReading.lowBandRatio : 0.0f,
                isfinite(audioReading.midBandRatio) ? audioReading.midBandRatio : 0.0f,
                isfinite(audioReading.highBandRatio) ? audioReading.highBandRatio : 0.0f,
                isfinite(audioReading.saturationRatio) ? audioReading.saturationRatio : 0.0f);
  if (pendingAudioEvent.includePcm && microphoneCaptureSamples > 0) {
    Serial.printf(",\"recording\":{\"sampleRate\":%u,\"encoding\":\"pcm_s8le\",\"pcm8\":\"",
                  INMP441_FEATURE_SAMPLE_RATE_HZ);
    writeBase64(microphoneCaptureBuffer, microphoneCaptureSamples);
    Serial.print("\"}");
  }
  Serial.println("}");
  pendingAudioEvent = PendingAudioEvent();
}

void sendB1Command(uint8_t command, const uint8_t *parameters, size_t parameterLength) {
  if (parameterLength > B1_FRAME_BUFFER_SIZE - 6) {
    return;
  }

  uint8_t frame[B1_FRAME_BUFFER_SIZE];
  frame[0] = 0xAA;
  frame[1] = 0xA5;
  frame[2] = static_cast<uint8_t>(3 + parameterLength);
  frame[3] = command;
  uint8_t checksum = static_cast<uint8_t>(frame[2] + command);
  for (size_t i = 0; i < parameterLength; i++) {
    frame[4 + i] = parameters[i];
    checksum = static_cast<uint8_t>(checksum + parameters[i]);
  }
  frame[4 + parameterLength] = checksum;
  frame[5 + parameterLength] = 0x55;
  b1Serial.write(frame, parameterLength + 6);
}

void configureB1BodyTemperatureMode() {
  const uint8_t bodyTemperatureMode = 0x02;
  sendB1Command(0x02, &bodyTemperatureMode, 1);
  b1BodyModeSent = true;
  b1Reading.status = "body_mode_sent";
}

void requestB1Temperature() {
  sendB1Command(0x01, nullptr, 0);
  b1LastRequestMs = millis();
}

bool b1ChecksumValid(const uint8_t *frame, size_t length) {
  if (length < 6 || frame[0] != 0xAA || frame[1] != 0xA5 ||
      frame[length - 1] != 0x55 || frame[2] + 3 != length) {
    return false;
  }
  uint8_t checksum = 0;
  for (size_t i = 2; i < length - 2; i++) {
    checksum = static_cast<uint8_t>(checksum + frame[i]);
  }
  return checksum == frame[length - 2];
}

bool acceptB1Measurement(uint8_t type, uint16_t targetRaw, uint16_t ambientRaw) {
  float target = targetRaw / 10.0f;
  float ambient = ambientRaw / 10.0f;
  if ((type != 1 && type != 2) || target <= 0.0f || target > 200.0f ||
      ambient < 0.0f || ambient > 100.0f) {
    b1Reading.invalidFrames++;
    b1Reading.status = target <= 0.0f ? "no_target" : "temperature_range_error";
    return false;
  }

  b1Reading.measurementType = type;
  b1Reading.surfaceTemperature = target;
  b1Reading.ambientTemperature = ambient;
  b1Reading.temperatureValid = true;
  b1Reading.lastMeasurementMs = millis();
  b1Reading.status = "valid";
  return true;
}

void processB1Frame(const uint8_t *frame, size_t length) {
  if (!b1ChecksumValid(frame, length)) {
    b1Reading.invalidFrames++;
    b1Reading.status = "checksum_error";
    return;
  }

  b1Reading.validFrames++;
  uint8_t command = frame[3];
  b1Reading.lastCommand = command;
  if (command != 0x01 || length != 11) {
    b1Reading.status = "frame_received";
    return;
  }

  uint16_t targetRaw = static_cast<uint16_t>(frame[5]) << 8 | frame[6];
  uint16_t ambientRaw = static_cast<uint16_t>(frame[7]) << 8 | frame[8];
  if (acceptB1Measurement(frame[4], targetRaw, ambientRaw)) {
    b1Reading.uartConfigured = true;
  }
}

void processB1Byte(uint8_t value) {
  b1AsciiShift = (b1AsciiShift << 8) | value;
  if (b1AsciiShift == 0x6462673EUL) {
    b1Reading.debugShell = true;
  }

  if (b1FrameIndex == 0) {
    if (value == 0xAA) {
      b1FrameBuffer[b1FrameIndex++] = value;
    }
    return;
  }

  if (b1FrameIndex == 1 && value != 0xA5) {
    b1FrameIndex = value == 0xAA ? 1 : 0;
    if (b1FrameIndex == 1) {
      b1FrameBuffer[0] = value;
    }
    return;
  }

  b1FrameBuffer[b1FrameIndex++] = value;
  if (b1FrameIndex == 3) {
    b1ExpectedFrameLength = static_cast<size_t>(b1FrameBuffer[2]) + 3;
    if (b1ExpectedFrameLength < 6 || b1ExpectedFrameLength > B1_FRAME_BUFFER_SIZE) {
      b1Reading.invalidFrames++;
      b1FrameIndex = 0;
      b1ExpectedFrameLength = 0;
      return;
    }
  }

  if (b1ExpectedFrameLength > 0 && b1FrameIndex >= b1ExpectedFrameLength) {
    processB1Frame(b1FrameBuffer, b1ExpectedFrameLength);
    b1FrameIndex = 0;
    b1ExpectedFrameLength = 0;
  }
}

void readB1Uart() {
  uint16_t handled = 0;
  while (b1Serial.available() && handled < 256) {
    int value = b1Serial.read();
    if (value < 0) {
      break;
    }
    b1WindowBytes++;
    b1LastByteMs = millis();
    if (b1RawCount < B1_RAW_BUFFER_SIZE) {
      b1RawBuffer[b1RawCount++] = static_cast<uint8_t>(value);
    }
    processB1Byte(static_cast<uint8_t>(value));
    handled++;
  }
}

void updateB1Protocol(uint32_t now) {
  if (!b1BodyModeSent && now - b1StartedMs >= B1_BODY_MODE_DELAY_MS) {
    configureB1BodyTemperatureMode();
  }
  if (now - b1LastRequestMs >= B1_REQUEST_INTERVAL_MS) {
    requestB1Temperature();
  }
  if (b1Reading.temperatureValid &&
      now - b1Reading.lastMeasurementMs > B1_READING_STALE_MS) {
    b1Reading.temperatureValid = false;
    b1Reading.status = "stale";
  }
}

void finalizeB1Window() {
  static const char hexDigits[] = "0123456789ABCDEF";
  b1Reading.bytes = b1WindowBytes;
  b1Reading.receiving = b1WindowBytes > 0 ||
                        (b1LastByteMs > 0 && millis() - b1LastByteMs < 5000UL);
  b1Reading.rawHex = "";
  b1Reading.rawHex.reserve(b1RawCount * 3);
  b1Reading.debugAscii = "";
  b1Reading.debugAscii.reserve(b1RawCount);
  for (size_t i = 0; i < b1RawCount; i++) {
    if (i > 0) {
      b1Reading.rawHex += ' ';
    }
    b1Reading.rawHex += hexDigits[b1RawBuffer[i] >> 4];
    b1Reading.rawHex += hexDigits[b1RawBuffer[i] & 0x0F];
    char value = static_cast<char>(b1RawBuffer[i]);
    b1Reading.debugAscii += value >= 32 && value <= 126 ? value : '.';
  }
  if (!b1Reading.temperatureValid && b1WindowBytes == 0) {
    b1Reading.status = "waiting_reply";
  }
  b1WindowBytes = 0;
  b1RawCount = 0;
}

float accelerationMagnitude(const MotionReading &reading) {
  return sqrtf(reading.ax * reading.ax + reading.ay * reading.ay + reading.az * reading.az);
}

float motionDelta(const MotionReading &current, const MotionReading &previous) {
  if (!isfinite(previous.ax)) {
    return 0.0f;
  }
  float dx = current.ax - previous.ax;
  float dy = current.ay - previous.ay;
  float dz = current.az - previous.az;
  return sqrtf(dx * dx + dy * dy + dz * dz);
}

float bodyTilt(const MotionReading &reading) {
  float magnitude = accelerationMagnitude(reading);
  if (magnitude < 0.1f) {
    return NAN;
  }
  float verticalRatio = constrain(fabsf(reading.az) / magnitude, 0.0f, 1.0f);
  return acosf(verticalRatio) * 180.0f / PI;
}

void resetLamenessFeatureWindow() {
  lamenessWindow = LamenessFeatureWindow();
}

void finalizeLamenessWindow() {
  if (lamenessWindow.samples < LAMENESS_WINDOW_SAMPLES) {
    return;
  }
  const float features[cattle_lameness_model::kFeatureCount] = {
      lamenessWindow.neckAcceleration.mean(),
      lamenessWindow.neckAcceleration.standardDeviation(),
      lamenessWindow.neckAcceleration.deltaMean(),
      lamenessWindow.neckAcceleration.deltaStandardDeviation(),
      lamenessWindow.bodyAcceleration.mean(),
      lamenessWindow.bodyAcceleration.standardDeviation(),
      lamenessWindow.bodyAcceleration.deltaMean(),
      lamenessWindow.bodyAcceleration.deltaStandardDeviation(),
      lamenessWindow.legAcceleration.mean(),
      lamenessWindow.legAcceleration.standardDeviation(),
      lamenessWindow.legAcceleration.deltaMean(),
      lamenessWindow.legAcceleration.deltaStandardDeviation(),
  };
  lamenessReading.windowSamples = lamenessWindow.samples;
  lamenessReading.modelVersion = cattle_lameness_model::kVersion;
  if (cattle_lameness_model::kEnabled) {
    cattle_lameness_model::Prediction prediction = cattle_lameness_model::predict(features);
    lamenessReading.candidate = prediction.suspect;
    lamenessReading.rejected = prediction.rejected;
    lamenessReading.score = prediction.score;
    lamenessReading.status = prediction.rejected ? "rejected" : "deployed";
  } else {
    lamenessReading.candidate = false;
    lamenessReading.rejected = false;
    lamenessReading.score = NAN;
    lamenessReading.status = "feature_only";
  }
  resetLamenessFeatureWindow();
}

void resetMotionAccumulator() {
  motionWindow.samples = 0;
  motionWindow.modelSamples = 0;
  motionWindow.postureModelSamples = 0;
  motionWindow.neckActivitySum = 0.0f;
  motionWindow.bodyActivitySum = 0.0f;
  motionWindow.legActivitySum = 0.0f;
  for (uint16_t &votes : motionWindow.classVotes) {
    votes = 0;
  }
  for (uint16_t &votes : motionWindow.postureClassVotes) {
    votes = 0;
  }
}

void resetMotionContinuity() {
  motionWindow = MotionWindow();
  motionTemporalResearch.reset("sensors_missing");
  resetLamenessFeatureWindow();
  lamenessReading = LamenessReading();
  previousMpu0Reading = MotionReading();
  previousAdxlReading = MotionReading();
  previousMpu1Reading = MotionReading();
}

const char *shortBehaviorName(const String &behavior) {
  if (behavior == "lying_ruminating") {
    return "lie_ruminate";
  }
  if (behavior == "lying_resting") {
    return "lie_rest";
  }
  if (behavior == "standing_resting") {
    return "stand_rest";
  }
  if (behavior == "standing_ruminating") {
    return "stand_ruminate";
  }
  if (behavior == "sensors_missing") {
    return "sensor_error";
  }
  return behavior.c_str();
}

const char *postureForBehavior(uint8_t behavior) {
  switch (behavior) {
    case BEHAVIOR_LYING_RUMINATING:
    case BEHAVIOR_LYING_RESTING:
      return "lying";
    case BEHAVIOR_STANDING_RESTING:
    case BEHAVIOR_STANDING_RUMINATING:
      return "standing";
    case BEHAVIOR_WALKING:
      return "standing";
    case BEHAVIOR_GRAZING:
      return "standing";
    default:
      return "unknown";
  }
}

void classifyBehavior() {
  if (!adxl345Ok || !mpu0Ok || !mpu1Ok ||
      motionWindow.samples == 0 || motionWindow.modelSamples == 0) {
    motionWindow.behavior = "sensors_missing";
    motionWindow.posture = "unknown";
    motionWindow.confidence = 0.0f;
    motionWindow.postureConfidence = 0.0f;
    motionWindow.neckModelBehavior = "waiting";
    motionWindow.neckModelConfidence = 0.0f;
    motionWindow.classifiedSamples = 0;
    motionWindow.postureClassifiedSamples = 0;
    resetMotionAccumulator();
    return;
  }

  float count = static_cast<float>(motionWindow.samples);
  motionWindow.neckActivity = motionWindow.neckActivitySum / count;
  motionWindow.bodyActivity = motionWindow.bodyActivitySum / count;
  motionWindow.legActivity = motionWindow.legActivitySum / count;
  motionWindow.bodyTiltDeg = bodyTilt(adxlReading);

  float scores[BEHAVIOR_CLASS_COUNT];
  uint8_t neckBest = 0;
  for (uint8_t label = 0; label < BEHAVIOR_CLASS_COUNT; label++) {
    scores[label] = static_cast<float>(motionWindow.classVotes[label]) /
                    motionWindow.modelSamples;
    if (motionWindow.classVotes[label] > motionWindow.classVotes[neckBest]) {
      neckBest = label;
    }
  }
  motionWindow.neckModelBehavior = BEHAVIOR_LABELS[neckBest];
  motionWindow.neckModelConfidence =
      static_cast<float>(motionWindow.classVotes[neckBest]) /
      motionWindow.modelSamples;

  // Public training data is neck-only. Back posture and leg motion provide
  // conservative physical evidence without pretending they were learned data.
  bool lyingPosture = isfinite(motionWindow.bodyTiltDeg) &&
                      motionWindow.bodyTiltDeg >= BODY_LIE_TILT_DEG;
  if (lyingPosture) {
    scores[BEHAVIOR_LYING_RUMINATING] += 0.18f;
    scores[BEHAVIOR_LYING_RESTING] += 0.18f;
    scores[BEHAVIOR_GRAZING] *= 0.65f;
    scores[BEHAVIOR_STANDING_RESTING] *= 0.45f;
    scores[BEHAVIOR_WALKING] *= 0.35f;
    scores[BEHAVIOR_STANDING_RUMINATING] *= 0.45f;
  } else {
    scores[BEHAVIOR_LYING_RUMINATING] *= 0.60f;
    scores[BEHAVIOR_LYING_RESTING] *= 0.60f;
  }

  if (motionWindow.legActivity >= WALK_LEG_ACTIVITY) {
    float walkingEvidence = 0.25f +
        0.20f * constrain(motionWindow.legActivity / VIGOROUS_LEG_ACTIVITY,
                          0.0f, 1.0f);
    scores[BEHAVIOR_WALKING] += walkingEvidence;
  } else {
    scores[BEHAVIOR_WALKING] *= 0.70f;
  }
  if (motionWindow.bodyActivity >= 0.9f &&
      motionWindow.legActivity >= WALK_LEG_ACTIVITY * 0.5f) {
    scores[BEHAVIOR_WALKING] += 0.10f;
  }
  if (motionWindow.neckActivity >= ACTIVE_NECK_ACTIVITY &&
      motionWindow.legActivity < WALK_LEG_ACTIVITY) {
    scores[BEHAVIOR_GRAZING] += 0.10f;
  }

  uint8_t best = 0;
  float scoreSum = scores[0];
  for (uint8_t label = 1; label < BEHAVIOR_CLASS_COUNT; label++) {
    scoreSum += scores[label];
    if (scores[label] > scores[best]) {
      best = label;
    }
  }
  motionWindow.behavior = BEHAVIOR_LABELS[best];
  motionWindow.confidence = scoreSum > 0.0f ? scores[best] / scoreSum : 0.0f;
  if (motionWindow.postureModelSamples > 0) {
    uint8_t postureBest = 0;
    for (uint8_t label = 1; label < POSTURE_CLASS_COUNT; label++) {
      if (motionWindow.postureClassVotes[label] >
          motionWindow.postureClassVotes[postureBest]) {
        postureBest = label;
      }
    }
    motionWindow.posture = POSTURE_LABELS[postureBest];
    motionWindow.postureConfidence =
        static_cast<float>(motionWindow.postureClassVotes[postureBest]) /
        motionWindow.postureModelSamples;
  } else {
    motionWindow.posture = postureForBehavior(best);
    motionWindow.postureConfidence = motionWindow.confidence;
  }
  // Back-mounted tilt is a physical cross-check for the learned neck posture.
  // It can strengthen a lying result, but it never creates a disease label.
  if (lyingPosture) {
    motionWindow.posture = "lying";
    motionWindow.postureConfidence =
        max(motionWindow.postureConfidence, 0.55f);
  }
  motionWindow.classifiedSamples = motionWindow.samples;
  motionWindow.postureClassifiedSamples = motionWindow.postureModelSamples;

  resetMotionAccumulator();
}

void sampleMotionSensors() {
  bool neckRead = mpu0Ok && readAdxl345Spi(PIN_ADXL_NECK_CS, mpu0Reading);
  bool bodyRead = adxl345Ok && readAdxl345Spi(PIN_ADXL_BODY_CS, adxlReading);
  bool legRead = mpu1Ok && readAdxl345Spi(PIN_ADXL_LEG_CS, mpu1Reading);
  mpu0Ok = neckRead;
  adxl345Ok = bodyRead;
  mpu1Ok = legRead;

  if (!neckRead || !bodyRead || !legRead) {
    resetMotionContinuity();
    if (motionCapture.active) {
      motionCapture.droppedSensorSamples++;
      motionCapture.active = false;
      sendMotionCaptureState("sensor_failure");
    }
    return;
  }

  motionWindow.neckActivitySum += motionDelta(mpu0Reading, previousMpu0Reading);
  motionWindow.bodyActivitySum += motionDelta(adxlReading, previousAdxlReading);
  motionWindow.legActivitySum += motionDelta(mpu1Reading, previousMpu1Reading);
  motionWindow.samples++;

  lamenessWindow.neckAcceleration.add(accelerationMagnitude(mpu0Reading));
  lamenessWindow.bodyAcceleration.add(accelerationMagnitude(adxlReading));
  lamenessWindow.legAcceleration.add(accelerationMagnitude(mpu1Reading));
  lamenessWindow.samples++;
  finalizeLamenessWindow();

  constexpr float gravity = 9.80665f;
  const float neckFeatures[cattle_behavior_model::kFeatureCount] = {
      mpu0Reading.ax / gravity,
      mpu0Reading.ay / gravity,
      mpu0Reading.az / gravity};
  if (MOTION_TEMPORAL_RESEARCH_ENABLED) {
    motionTemporalResearch.add(neckFeatures[0], neckFeatures[1], neckFeatures[2], millis());
  } else {
    motionTemporalResearch.reset("disabled");
  }
  uint8_t predicted = cattle_behavior_model::predict(neckFeatures);
  if (predicted < BEHAVIOR_CLASS_COUNT) {
    motionWindow.classVotes[predicted]++;
    motionWindow.modelSamples++;
  }
  uint8_t posturePredicted = cattle_posture_model::predict(neckFeatures);
  if (posturePredicted < POSTURE_CLASS_COUNT) {
    motionWindow.postureClassVotes[posturePredicted]++;
    motionWindow.postureModelSamples++;
  }
  previousMpu0Reading = mpu0Reading;
  previousAdxlReading = adxlReading;
  previousMpu1Reading = mpu1Reading;
}

float roundedMotionValue(float value) {
  return isfinite(value) ? roundf(value * 1000.0f) / 1000.0f : NAN;
}

void sendMotionCaptureState(const char *status) {
  JsonDocument response;
  response["type"] = "motion_capture";
  response["status"] = status;
  response["captureId"] = motionCapture.id;
  response["sessionId"] = motionCapture.sessionId;
  response["deviceId"] = DEVICE_ID;
  response["cattleId"] = CATTLE_ID;
  response["barnId"] = BARN_ID;
  response["durationMs"] = motionCapture.durationMs;
  response["sampleRateHz"] = 1000UL / MOTION_SAMPLE_INTERVAL_MS;
  response["expectedSamples"] = motionCapture.expectedSamples;
  response["attemptedSamples"] = motionCapture.attemptedSamples;
  response["emittedSamples"] = motionCapture.samples;
  response["droppedBackpressureSamples"] = motionCapture.droppedBackpressureSamples;
  response["droppedSensorSamples"] = motionCapture.droppedSensorSamples;
  response["samples"] = motionCapture.samples;
  serializeJson(response, Serial);
  Serial.println();
}

void emitMotionCaptureSample(uint32_t now) {
  if (!motionCapture.active) {
    return;
  }
  if (now - motionCapture.startedAtMs >= motionCapture.durationMs) {
    motionCapture.active = false;
    sendMotionCaptureState("completed");
    return;
  }
  const uint32_t sampleIndex = motionCapture.attemptedSamples++;

  // Do not silently drop science data. Once the serial transport cannot keep
  // up, end the session so the backend permanently rejects it for training.
  if (Serial.availableForWrite() < 256) {
    motionCapture.droppedBackpressureSamples++;
    motionCapture.active = false;
    sendMotionCaptureState("serial_backpressure");
    return;
  }

  // Compact keys and arrays keep 20 Hz capture below the 115200-baud serial
  // budget. The backend converts this wire row to canonical NDJSON before it
  // is stored and handed to the training pipeline.
  JsonDocument row;
  row["type"] = "mcs";
  row["s"] = motionCapture.sessionId;
  row["d"] = DEVICE_ID;
  row["c"] = CATTLE_ID;
  row["b"] = BARN_ID;
  row["i"] = sampleIndex;
  row["m"] = now;
  row["r"] = 1000UL / MOTION_SAMPLE_INTERVAL_MS;
  JsonArray neck = row["n"].to<JsonArray>();
  neck.add(roundedMotionValue(mpu0Reading.ax));
  neck.add(roundedMotionValue(mpu0Reading.ay));
  neck.add(roundedMotionValue(mpu0Reading.az));
  JsonArray body = row["u"].to<JsonArray>();
  body.add(roundedMotionValue(adxlReading.ax));
  body.add(roundedMotionValue(adxlReading.ay));
  body.add(roundedMotionValue(adxlReading.az));
  JsonArray leg = row["l"].to<JsonArray>();
  leg.add(roundedMotionValue(mpu1Reading.ax));
  leg.add(roundedMotionValue(mpu1Reading.ay));
  leg.add(roundedMotionValue(mpu1Reading.az));
  serializeJson(row, Serial);
  Serial.println();
  motionCapture.samples++;
}

bool i2cDevicePresent(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}

bool i2cWrite(uint8_t address, const uint8_t *data, size_t length) {
  Wire.beginTransmission(address);
  Wire.write(data, length);
  return Wire.endTransmission() == 0;
}

bool i2cWriteRegister(uint8_t address, uint8_t reg, uint8_t value) {
  const uint8_t data[] = {reg, value};
  return i2cWrite(address, data, sizeof(data));
}

bool i2cReadRegisters(uint8_t address, uint8_t reg, uint8_t *data, size_t length) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }
  size_t received = Wire.requestFrom(static_cast<int>(address), static_cast<int>(length));
  if (received != length) {
    while (Wire.available()) {
      Wire.read();
    }
    return false;
  }
  for (size_t i = 0; i < length; i++) {
    data[i] = Wire.read();
  }
  return true;
}

uint8_t shtCrc(const uint8_t *data, size_t length) {
  uint8_t crc = 0xFF;
  for (size_t i = 0; i < length; i++) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; bit++) {
      crc = (crc & 0x80) ? static_cast<uint8_t>((crc << 1) ^ 0x31) : static_cast<uint8_t>(crc << 1);
    }
  }
  return crc;
}

bool readSht31(float &temperature, float &humidity) {
  const uint8_t command[] = {0x24, 0x00};
  if (!i2cWrite(SHT31_I2C_ADDR, command, sizeof(command))) {
    return false;
  }
  delay(20);
  uint8_t data[6];
  size_t received = Wire.requestFrom(static_cast<int>(SHT31_I2C_ADDR), 6);
  if (received != sizeof(data)) {
    return false;
  }
  for (uint8_t &value : data) {
    value = Wire.read();
  }
  if (shtCrc(data, 2) != data[2] || shtCrc(data + 3, 2) != data[5]) {
    return false;
  }
  uint16_t rawTemp = static_cast<uint16_t>(data[0] << 8) | data[1];
  uint16_t rawHumidity = static_cast<uint16_t>(data[3] << 8) | data[4];
  temperature = -45.0f + 175.0f * rawTemp / 65535.0f;
  humidity = 100.0f * rawHumidity / 65535.0f;
  return true;
}

bool readBh1750(float &lux) {
  uint8_t data[2];
  size_t received = Wire.requestFrom(static_cast<int>(bh1750Address), 2);
  if (received != sizeof(data)) {
    return false;
  }
  data[0] = Wire.read();
  data[1] = Wire.read();
  uint16_t raw = static_cast<uint16_t>(data[0] << 8) | data[1];
  lux = raw / 1.2f;
  return true;
}

bool readAdxl345(MotionReading &reading) {
  uint8_t data[6];
  if (!i2cReadRegisters(ADXL345_I2C_ADDR, 0x32, data, sizeof(data))) {
    return false;
  }
  int16_t rawX = static_cast<int16_t>(data[1] << 8 | data[0]);
  int16_t rawY = static_cast<int16_t>(data[3] << 8 | data[2]);
  int16_t rawZ = static_cast<int16_t>(data[5] << 8 | data[4]);
  constexpr float scale = 0.0039f * 9.80665f;
  reading.ax = rawX * scale;
  reading.ay = rawY * scale;
  reading.az = rawZ * scale;
  return true;
}

bool readAdxl345SpiRegisters(uint8_t chipSelect, uint8_t reg,
                             uint8_t *data, size_t length) {
  if (length == 0) {
    return true;
  }
  adxlSpi.beginTransaction(adxlSpiSettings);
  digitalWrite(chipSelect, LOW);
  uint8_t command = static_cast<uint8_t>(0x80U | (reg & 0x3FU));
  if (length > 1) {
    command = static_cast<uint8_t>(command | 0x40U);
  }
  adxlSpi.transfer(command);
  for (size_t index = 0; index < length; index++) {
    data[index] = adxlSpi.transfer(0x00);
  }
  digitalWrite(chipSelect, HIGH);
  adxlSpi.endTransaction();
  return true;
}

bool writeAdxl345SpiRegister(uint8_t chipSelect, uint8_t reg, uint8_t value) {
  adxlSpi.beginTransaction(adxlSpiSettings);
  digitalWrite(chipSelect, LOW);
  adxlSpi.transfer(static_cast<uint8_t>(reg & 0x3FU));
  adxlSpi.transfer(value);
  digitalWrite(chipSelect, HIGH);
  adxlSpi.endTransaction();
  return true;
}

Adxl345SpiDiagnostics &adxl345Diagnostics(uint8_t chipSelect) {
  if (chipSelect == PIN_ADXL_NECK_CS) {
    return neckSpiDiagnostics;
  }
  return chipSelect == PIN_ADXL_BODY_CS ? bodySpiDiagnostics : legSpiDiagnostics;
}

bool readAdxl345SpiConfiguration(uint8_t chipSelect) {
  Adxl345SpiDiagnostics &diagnostics = adxl345Diagnostics(chipSelect);
  bool readOk = readAdxl345SpiRegisters(chipSelect, 0x00, &diagnostics.deviceId, 1);
  readOk = readAdxl345SpiRegisters(chipSelect, 0x31, &diagnostics.dataFormat, 1) && readOk;
  readOk = readAdxl345SpiRegisters(chipSelect, 0x2C, &diagnostics.bwRate, 1) && readOk;
  readOk = readAdxl345SpiRegisters(chipSelect, 0x2D, &diagnostics.powerCtl, 1) && readOk;
  diagnostics.configVerified = readOk && diagnostics.deviceId == 0xE5 &&
                               diagnostics.dataFormat == 0x0B &&
                               diagnostics.bwRate == 0x0A && diagnostics.powerCtl == 0x08;
  return diagnostics.configVerified;
}

void printAdxl345SpiDiagnostics(uint8_t chipSelect) {
  const Adxl345SpiDiagnostics &diagnostics = adxl345Diagnostics(chipSelect);
  const char *position = chipSelect == PIN_ADXL_NECK_CS ? "neck" :
                         chipSelect == PIN_ADXL_BODY_CS ? "body" : "leg";
  Serial.printf("ADXL345_SPI %s csPin=%u deviceId=0x%02X expected=0xE5 "
                "DATA_FORMAT=0x%02X(0x0B) BW_RATE=0x%02X(0x0A) "
                "POWER_CTL=0x%02X(0x08) configVerified=%s clockHz=%lu\n",
                position, chipSelect, diagnostics.deviceId, diagnostics.dataFormat,
                diagnostics.bwRate, diagnostics.powerCtl,
                diagnostics.configVerified ? "true" : "false",
                static_cast<unsigned long>(ADXL345_SPI_FREQUENCY_HZ));
}

bool setupAdxl345Spi(uint8_t chipSelect) {
  pinMode(chipSelect, OUTPUT);
  digitalWrite(chipSelect, HIGH);

  readAdxl345SpiConfiguration(chipSelect);
  if (adxl345Diagnostics(chipSelect).deviceId == 0xE5) {
    // Full-resolution +/-16 g, 100 Hz output data rate, measurement mode.
    writeAdxl345SpiRegister(chipSelect, 0x31, 0x0B);
    writeAdxl345SpiRegister(chipSelect, 0x2C, 0x0A);
    writeAdxl345SpiRegister(chipSelect, 0x2D, 0x08);
    readAdxl345SpiConfiguration(chipSelect);
  }
  printAdxl345SpiDiagnostics(chipSelect);
  return adxl345Diagnostics(chipSelect).configVerified;
}

bool readAdxl345Spi(uint8_t chipSelect, MotionReading &reading) {
  // SPI has no ACK: a completed transfer alone does not prove a sensor exists.
  if (!readAdxl345SpiConfiguration(chipSelect)) {
    reading = MotionReading();
    printAdxl345SpiDiagnostics(chipSelect);
    return false;
  }
  uint8_t data[6];
  if (!readAdxl345SpiRegisters(chipSelect, 0x32, data, sizeof(data))) {
    reading = MotionReading();
    return false;
  }
  int16_t rawX = static_cast<int16_t>(static_cast<uint16_t>(data[1]) << 8 | data[0]);
  int16_t rawY = static_cast<int16_t>(static_cast<uint16_t>(data[3]) << 8 | data[2]);
  int16_t rawZ = static_cast<int16_t>(static_cast<uint16_t>(data[5]) << 8 | data[4]);
  constexpr float scale = 0.0039f * 9.80665f;
  reading.ax = rawX * scale;
  reading.ay = rawY * scale;
  reading.az = rawZ * scale;
  reading.gx = NAN;
  reading.gy = NAN;
  reading.gz = NAN;
  reading.temperature = NAN;
  return true;
}

bool setupMpu(uint8_t address) {
  uint8_t whoAmI = 0;
  if (!i2cReadRegisters(address, 0x75, &whoAmI, 1)) {
    return false;
  }
  bool supported = whoAmI == 0x68 || whoAmI == 0x70 || whoAmI == 0x71 ||
                   whoAmI == 0x73 || whoAmI == 0x75;
  return supported &&
         i2cWriteRegister(address, 0x6B, 0x00) &&
         i2cWriteRegister(address, 0x1B, 0x00) &&
         i2cWriteRegister(address, 0x1C, 0x00);
}

bool readMpu(uint8_t address, MotionReading &reading) {
  uint8_t data[14];
  if (!i2cReadRegisters(address, 0x3B, data, sizeof(data))) {
    return false;
  }
  auto signedWord = [&data](int index) {
    return static_cast<int16_t>(static_cast<uint16_t>(data[index]) << 8 | data[index + 1]);
  };
  constexpr float gravity = 9.80665f;
  reading.ax = signedWord(0) * gravity / 16384.0f;
  reading.ay = signedWord(2) * gravity / 16384.0f;
  reading.az = signedWord(4) * gravity / 16384.0f;
  reading.temperature = signedWord(6) / 333.87f + 21.0f;
  reading.gx = signedWord(8) / 131.0f;
  reading.gy = signedWord(10) / 131.0f;
  reading.gz = signedWord(12) / 131.0f;
  return true;
}

void setLed(bool green, bool yellow, bool red) {
  digitalWrite(PIN_LED_GREEN, green ? HIGH : LOW);
  digitalWrite(PIN_LED_YELLOW, yellow ? HIGH : LOW);
  digitalWrite(PIN_LED_RED, red ? HIGH : LOW);
}

const char *fanModeName() {
  switch (fanMode) {
    case FAN_FORCE_ON:
      return "on";
    case FAN_FORCE_OFF:
      return "off";
    default:
      return "auto";
  }
}

void updateFan() {
#if !ENABLE_ENV_SENSORS
  fanOn = false;
  return;
#else
  bool automatic = !latest.flame &&
                   ((isfinite(latest.temperature) && latest.temperature >= TEMP_FAN_ON_C) ||
                    (isfinite(latest.humidity) && latest.humidity >= HUMIDITY_FAN_ON_PERCENT) ||
                    latest.mqRaw >= MQ_WARN_RAW);
  if (latest.flame) {
    fanOn = false;
  } else if (fanMode == FAN_FORCE_ON) {
    fanOn = true;
  } else if (fanMode == FAN_FORCE_OFF) {
    fanOn = false;
  } else {
    fanOn = automatic;
  }
  if (PIN_FAN_CONTROL >= 0) {
    digitalWrite(PIN_FAN_CONTROL, fanOn == FAN_ACTIVE_HIGH ? HIGH : LOW);
  }
#endif
}

void sendHostCommandAck(uint32_t commandId, const char *action,
                        bool enabled, const char *status) {
  JsonDocument ack;
  ack["type"] = "command_ack";
  ack["commandId"] = commandId;
  ack["action"] = action;
  ack["enabled"] = enabled;
  ack["status"] = status;
  ack["fan"] = fanOn;
  ack["fanMode"] = fanModeName();
  ack["manualAlarm"] = manualAlarmOn;
  serializeJson(ack, Serial);
  Serial.println();
}

void processHostCommand(const char *line) {
  JsonDocument command;
  DeserializationError error = deserializeJson(command, line);
  if (error || command["type"] != "command" ||
      !command["commandId"].is<uint32_t>() || !command["action"].is<const char *>()) {
    return;
  }

  uint32_t commandId = command["commandId"].as<uint32_t>();
  const char *action = command["action"].as<const char *>();
  bool enabled = command["enabled"] | false;
  const char *status = "unsupported";

  if (strcmp(action, "fan") == 0) {
    fanMode = enabled ? FAN_FORCE_ON : FAN_FORCE_OFF;
    updateFan();
    status = "applied";
  } else if (strcmp(action, "fan_auto") == 0) {
    fanMode = FAN_AUTO;
    updateFan();
    status = "applied";
  } else if (strcmp(action, "alarm") == 0) {
    manualAlarmOn = enabled;
    if (manualAlarmOn) {
      setLed(false, false, true);
      lastBuzzerToggleMs = millis() - 300UL;
    } else {
      applyLed(latest.level);
    }
    status = "applied";
  } else if (strcmp(action, "audio_capture") == 0) {
    if (!enabled) {
      microphoneCaptureRequested = false;
      microphoneCaptureActive = false;
      audioReading.captureInProgress = false;
      status = "cancelled";
    } else if (!microphoneOk || !microphoneSlotCalibrated ||
               !microphoneSlotHasSignal || audioReading.status != "ok") {
      status = "mic_signal_invalid";
    } else {
      requestAudioCapture("manual_capture", 0.0f);
      status = "queued";
    }
  } else if (strcmp(action, "motion_capture") == 0) {
    if (!enabled) {
      motionCapture.active = false;
      status = "cancelled";
      sendMotionCaptureState("cancelled");
    } else if (motionCapture.active) {
      status = "motion_capture_busy";
    } else if (!mpu0Ok || !adxl345Ok || !mpu1Ok) {
      status = "motion_sensors_missing";
    } else {
      uint32_t duration = command["durationMs"] | MOTION_CAPTURE_DEFAULT_DURATION_MS;
      duration = constrain(duration, 1000UL, MOTION_CAPTURE_MAX_DURATION_MS);
      const char *session = command["sessionId"] | "";
      if (strlen(session) == 0) {
        status = "invalid_motion_session";
      } else {
        motionCapture.active = true;
        motionCapture.id = commandId;
        motionCapture.startedAtMs = millis();
        motionCapture.durationMs = duration;
        motionCapture.samples = 0;
        motionCapture.expectedSamples = duration / MOTION_SAMPLE_INTERVAL_MS;
        motionCapture.attemptedSamples = 0;
        motionCapture.droppedBackpressureSamples = 0;
        motionCapture.droppedSensorSamples = 0;
        motionCapture.sessionId = session;
        status = "started";
        sendMotionCaptureState("started");
      }
    }
  }

  lastHostCommandId = commandId;
  lastHostCommandAction = action;
  lastHostCommandStatus = status;
  sendHostCommandAck(commandId, action, enabled, status);
}

void readHostCommands() {
  while (Serial.available()) {
    char value = static_cast<char>(Serial.read());
    if (value == '\n') {
      if (hostCommandLength > 0) {
        hostCommandBuffer[hostCommandLength] = '\0';
        if (!handleNetworkCommand(hostCommandBuffer)) {
          processHostCommand(hostCommandBuffer);
        }
        hostCommandLength = 0;
      }
    } else if (value != '\r') {
      if (hostCommandLength < sizeof(hostCommandBuffer) - 1) {
        hostCommandBuffer[hostCommandLength++] = value;
      } else {
        hostCommandLength = 0;
      }
    }
  }
}

void handleEncoder() {
  if (!ENCODER_ENABLED) {
    return;
  }

  int encoderClk = digitalRead(PIN_ENCODER_CLK);
  if (lastEncoderClk == HIGH && encoderClk == LOW) {
    int direction = digitalRead(PIN_ENCODER_DT) == HIGH ? 1 : -1;
    oledPage = static_cast<uint8_t>((oledPage + direction + 4) % 4);
  }
  lastEncoderClk = encoderClk;

  int button = digitalRead(PIN_ENCODER_SW);
  uint32_t now = millis();
  if (lastEncoderButton == HIGH && button == LOW && now - lastEncoderButtonMs > 250UL) {
    lastEncoderButtonMs = now;
    fanMode = static_cast<FanMode>((static_cast<int>(fanMode) + 1) % 3);
    updateFan();
  }
  lastEncoderButton = button;
}

void updateDisplay() {
  if (!oledOk) {
    return;
  }
  uint32_t now = millis();
  if (now - lastDisplayMs < 500UL) {
    return;
  }
  lastDisplayMs = now;
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tf);

  if (oledPage == 0) {
    oled.drawStr(0, 10, "SMART CATTLE NODE");
    oled.setCursor(0, 25);
    oled.printf("T:%.1fC H:%.1f%%", latest.temperature, latest.humidity);
    oled.setCursor(0, 39);
    oled.printf("Light:%.0f lx", latest.lightLux);
    oled.setCursor(0, 53);
    oled.printf("MQ:%d Flame:%d", latest.mqRaw, latest.flame);
    oled.setCursor(0, 64);
    oled.printf("Fan:%s/%s", fanModeName(), fanOn ? "ON" : "OFF");
  } else if (oledPage == 1) {
    oled.drawStr(0, 10, "CATTLE BEHAVIOR");
    oled.setCursor(0, 25);
    oled.printf("State:%s", shortBehaviorName(motionWindow.behavior));
    oled.setCursor(0, 39);
    oled.printf("Tilt:%.0f Leg:%.2f", motionWindow.bodyTiltDeg, motionWindow.legActivity);
    oled.setCursor(0, 53);
    oled.printf("N/B/L:%d/%d/%d", mpu0Ok, adxl345Ok, mpu1Ok);
  } else if (oledPage == 2) {
    oled.drawStr(0, 10, "HEALTH / BUS");
    oled.setCursor(0, 25);
    oled.printf("MAX:%s %s", maxOk ? "OK" : "--", latest.maxStatus.c_str());
    oled.setCursor(0, 39);
    oled.printf("HR:%.0f SpO2:%d", latest.heartRate, latest.spo2);
    oled.setCursor(0, 53);
    oled.printf("SHT:%s BH:%s", sht31Ok ? "OK" : "--", bh1750Ok ? "OK" : "--");
  } else {
    oled.drawStr(0, 10, "AUDIO / IR TEMP");
    oled.setCursor(0, 25);
    if (microphoneOk && isfinite(audioReading.dbfs)) {
      oled.printf("MIC:OK %.0f dBFS", audioReading.dbfs);
    } else {
      oled.printf("MIC:%s", microphoneOk ? "WAIT" : "--");
    }
    oled.setCursor(0, 39);
    oled.printf("RMS:%.3f P:%.3f", audioReading.rms, audioReading.peak);
    oled.setCursor(0, 53);
    if (b1Reading.temperatureValid) {
      oled.printf("B1:%.1fC T:%u", b1Reading.surfaceTemperature,
                  b1Reading.measurementType);
    } else {
      oled.printf("B1:%s %lu B", b1Reading.receiving ? "RX" : "WAIT",
                  static_cast<unsigned long>(b1Reading.bytes));
    }
    oled.setCursor(0, 64);
    if (b1Reading.temperatureValid) {
      oled.printf("Ambient:%.1fC", b1Reading.ambientTemperature);
    } else {
      oled.printf("Status:%s", b1Reading.status.c_str());
    }
  }
  oled.sendBuffer();
}

void updateBuzzer(bool alarm) {
  if (!alarm) {
    if (buzzerOn) {
      if (BUZZER_ACTIVE_MODULE) {
        digitalWrite(PIN_BUZZER, BUZZER_ACTIVE_HIGH ? LOW : HIGH);
      } else {
        ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
      }
      buzzerOn = false;
    }
    return;
  }

  uint32_t now = millis();
  if (now - lastBuzzerToggleMs >= 300UL) {
    lastBuzzerToggleMs = now;
    buzzerOn = !buzzerOn;
    if (BUZZER_ACTIVE_MODULE) {
      digitalWrite(PIN_BUZZER, buzzerOn == BUZZER_ACTIVE_HIGH ? HIGH : LOW);
    } else if (buzzerOn) {
      ledcWriteTone(BUZZER_LEDC_CHANNEL, BUZZER_FREQUENCY_HZ);
    } else {
      ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
    }
  }
}

String judgeLevel(const Reading &r) {
  if (r.flame || r.mqRaw >= MQ_ALARM_RAW) {
    return "alarm";
  }
  if (r.mqRaw >= MQ_WARN_RAW) {
    return "warning";
  }
  return "normal";
}

void applyLed(const String &level) {
  if (level == "alarm") {
    setLed(false, false, true);
  } else if (level == "warning") {
    setLed(false, true, false);
  } else {
    setLed(true, false, false);
  }
}

void updateMax30102() {
  if (!maxOk) {
    return;
  }

  // getIR()/getRed() each wait up to 250 ms for another FIFO sample. Poll the
  // FIFO directly so the 20 Hz motion schedule is never blocked by MAX30102.
  max30102.check();
  if (max30102.available() == 0) {
    return;
  }
  latest.ir = max30102.getFIFOIR();
  latest.red = max30102.getFIFORed();
  max30102.nextSample();
  latest.fingerDetected = latest.ir >= FINGER_IR_THRESHOLD;

  if (latest.ir >= 250000UL || latest.red >= 250000UL) {
    latest.maxStatus = "saturated";
    latest.heartRateValid = false;
    latest.spo2Valid = false;
    latest.heartRateEstimated = false;
    latest.spo2Estimated = false;
    latest.heartRate = NAN;
    latest.spo2 = -1;
    bufferIndex = 0;
    bufferFilled = false;
    return;
  }

  if (!latest.fingerDetected) {
    latest.heartRateValid = false;
    latest.spo2Valid = false;
    latest.heartRateEstimated = false;
    latest.spo2Estimated = false;
    latest.heartRate = NAN;
    latest.spo2 = -1;
    latest.maxStatus = "no_finger";
    bufferIndex = 0;
    bufferFilled = false;
    fingerSinceMs = 0;
    maxIrSeen = 0;
    minIrSeen = UINT32_MAX;
    return;
  }

  if (fingerSinceMs == 0) {
    fingerSinceMs = millis();
    latest.maxStatus = "measuring";
  }
  maxIrSeen = max(maxIrSeen, latest.ir);
  minIrSeen = min(minIrSeen, latest.ir);

  if (checkForBeat(latest.ir)) {
    long delta = millis() - lastBeat;
    lastBeat = millis();
    float bpm = 60.0f / (delta / 1000.0f);
    if (bpm >= 40.0f && bpm <= 180.0f) {
      rates[rateSpot++] = static_cast<byte>(bpm);
      rateSpot %= RATE_SIZE;

      uint16_t total = 0;
      uint8_t count = 0;
      for (byte i = 0; i < RATE_SIZE; i++) {
        if (rates[i] > 0) {
          total += rates[i];
          count++;
        }
      }
      if (count > 0) {
        latest.heartRate = static_cast<float>(total) / count;
        latest.heartRateValid = true;
        latest.heartRateEstimated = false;
      }
    }
  }

  irBuffer[bufferIndex] = latest.ir;
  redBuffer[bufferIndex] = latest.red;
  bufferIndex++;
  if (bufferIndex >= OXIMETER_BUFFER_SIZE) {
    bufferIndex = 0;
    bufferFilled = true;
  }

  if (bufferFilled && bufferIndex == 0) {
    int32_t spo2Value = 0;
    int8_t spo2Valid = 0;
    int32_t hrValue = 0;
    int8_t hrValid = 0;
    maxim_heart_rate_and_oxygen_saturation(
        irBuffer,
        OXIMETER_BUFFER_SIZE,
        redBuffer,
        &spo2Value,
        &spo2Valid,
        &hrValue,
        &hrValid);

    if (spo2Valid && spo2Value >= 70 && spo2Value <= 100) {
      latest.spo2 = spo2Value;
      latest.spo2Valid = true;
      latest.spo2Estimated = false;
    } else {
      latest.spo2Valid = false;
    }

    if (!latest.heartRateValid && hrValid && hrValue >= 40 && hrValue <= 180) {
      latest.heartRate = static_cast<float>(hrValue);
      latest.heartRateValid = true;
      latest.heartRateEstimated = false;
    }
  }

  if (latest.heartRateValid || latest.spo2Valid) {
    latest.maxStatus = "valid";
  } else if (latest.heartRateEstimated || latest.spo2Estimated) {
    latest.maxStatus = "estimated";
  } else {
    latest.maxStatus = "measuring";
  }
}

void readSensors() {
  latest.seq++;
#if ENABLE_ENV_SENSORS
  float shtTemperature = NAN;
  float shtHumidity = NAN;
  if (sht31Ok && readSht31(shtTemperature, shtHumidity)) {
    latest.temperature = shtTemperature;
    latest.humidity = shtHumidity;
    latest.climateSource = "sht31";
  } else {
    latest.temperature = dht.readTemperature();
    latest.humidity = dht.readHumidity();
    latest.climateSource = isfinite(latest.temperature) && isfinite(latest.humidity) ? "dht11" : "none";
  }

  if (bh1750Ok && !readBh1750(latest.lightLux)) {
    latest.lightLux = NAN;
  }
  latest.mqRaw = analogRead(PIN_MQ_AO);

  bool flameLevel = digitalRead(PIN_FLAME_DO) == HIGH;
  latest.flame = FLAME_ACTIVE_LOW ? !flameLevel : flameLevel;
#else
  latest.temperature = NAN;
  latest.humidity = NAN;
  latest.climateSource = "wearable_only";
  latest.lightLux = NAN;
  latest.mqRaw = 0;
  latest.flame = false;
#endif

  latest.level = judgeLevel(latest);
  applyLed(latest.level);
  updateFan();
}

void printReading() {
  JsonDocument doc;
  doc["deviceId"] = DEVICE_ID;
  doc["barnId"] = BARN_ID;
  doc["cattleId"] = CATTLE_ID;
  doc["seq"] = latest.seq;
  if (isfinite(latest.temperature)) {
    doc["temperature"] = roundf(latest.temperature * 10.0f) / 10.0f;
  } else {
    doc["temperature"] = nullptr;
  }
  if (isfinite(latest.humidity)) {
    doc["humidity"] = roundf(latest.humidity * 10.0f) / 10.0f;
  } else {
    doc["humidity"] = nullptr;
  }
  doc["climateSource"] = latest.climateSource;
  if (isfinite(latest.lightLux)) {
    doc["lightLux"] = roundf(latest.lightLux * 10.0f) / 10.0f;
  } else {
    doc["lightLux"] = nullptr;
  }
  doc["mqRaw"] = latest.mqRaw;
  doc["flame"] = latest.flame;
  doc["max30102"] = maxOk;
  doc["maxStatus"] = latest.maxStatus;
  doc["fingerDetected"] = latest.fingerDetected;
  doc["ir"] = latest.ir;
  doc["red"] = latest.red;
  if ((latest.heartRateValid || latest.heartRateEstimated) && isfinite(latest.heartRate)) {
    doc["heartRate"] = roundf(latest.heartRate * 10.0f) / 10.0f;
  } else {
    doc["heartRate"] = nullptr;
  }
  doc["heartRateValid"] = latest.heartRateValid;
  doc["heartRateEstimated"] = latest.heartRateEstimated;
  if (latest.spo2Valid || latest.spo2Estimated) {
    doc["spo2"] = latest.spo2;
  } else {
    doc["spo2"] = nullptr;
  }
  doc["spo2Valid"] = latest.spo2Valid;
  doc["spo2Estimated"] = latest.spo2Estimated;
  doc["motionSensorType"] = "ADXL345";
  doc["motionBus"] = "SPI";
  doc["adxl345Neck"] = mpu0Ok;
  doc["adxl345Body"] = adxl345Ok;
  doc["adxl345Leg"] = mpu1Ok;
  JsonObject spiDiagnostics = doc["motionSpiDiagnostics"].to<JsonObject>();
  spiDiagnostics["clockHz"] = ADXL345_SPI_FREQUENCY_HZ;
  const char *positions[] = {"neck", "body", "leg"};
  const uint8_t chipSelects[] = {PIN_ADXL_NECK_CS, PIN_ADXL_BODY_CS, PIN_ADXL_LEG_CS};
  const bool motionHealthy[] = {mpu0Ok, adxl345Ok, mpu1Ok};
  for (uint8_t index = 0; index < 3; index++) {
    const Adxl345SpiDiagnostics &diagnostics = adxl345Diagnostics(chipSelects[index]);
    JsonObject sensor = spiDiagnostics[positions[index]].to<JsonObject>();
    sensor["csPin"] = chipSelects[index];
    sensor["healthy"] = motionHealthy[index];
    sensor["deviceId"] = diagnostics.deviceId;
    sensor["expectedDeviceId"] = 0xE5;
    sensor["dataFormat"] = diagnostics.dataFormat;
    sensor["bwRate"] = diagnostics.bwRate;
    sensor["powerCtl"] = diagnostics.powerCtl;
    sensor["configVerified"] = diagnostics.configVerified;
  }
  // Keep the original keys so the existing backend and behavior page remain
  // compatible while the explicit ADXL345 keys are adopted.
  doc["adxl345"] = adxl345Ok;
  if (adxl345Ok) {
    JsonObject adxl = doc["adxl"].to<JsonObject>();
    adxl["position"] = "body";
    adxl["sensor"] = "ADXL345";
    adxl["bus"] = "SPI";
    adxl["ax"] = roundf(adxlReading.ax * 100.0f) / 100.0f;
    adxl["ay"] = roundf(adxlReading.ay * 100.0f) / 100.0f;
    adxl["az"] = roundf(adxlReading.az * 100.0f) / 100.0f;
  }
  doc["mpu0"] = mpu0Ok;
  if (mpu0Ok) {
    JsonObject mpu = doc["mpu0Data"].to<JsonObject>();
    mpu["position"] = "neck";
    mpu["sensor"] = "ADXL345";
    mpu["bus"] = "SPI";
    mpu["ax"] = roundf(mpu0Reading.ax * 100.0f) / 100.0f;
    mpu["ay"] = roundf(mpu0Reading.ay * 100.0f) / 100.0f;
    mpu["az"] = roundf(mpu0Reading.az * 100.0f) / 100.0f;
    mpu["gx"] = roundf(mpu0Reading.gx * 10.0f) / 10.0f;
    mpu["gy"] = roundf(mpu0Reading.gy * 10.0f) / 10.0f;
    mpu["gz"] = roundf(mpu0Reading.gz * 10.0f) / 10.0f;
  }
  doc["mpu1"] = mpu1Ok;
  if (mpu1Ok) {
    JsonObject mpu = doc["mpu1Data"].to<JsonObject>();
    mpu["position"] = "leg";
    mpu["sensor"] = "ADXL345";
    mpu["bus"] = "SPI";
    mpu["ax"] = roundf(mpu1Reading.ax * 100.0f) / 100.0f;
    mpu["ay"] = roundf(mpu1Reading.ay * 100.0f) / 100.0f;
    mpu["az"] = roundf(mpu1Reading.az * 100.0f) / 100.0f;
    mpu["gx"] = roundf(mpu1Reading.gx * 10.0f) / 10.0f;
    mpu["gy"] = roundf(mpu1Reading.gy * 10.0f) / 10.0f;
    mpu["gz"] = roundf(mpu1Reading.gz * 10.0f) / 10.0f;
  }
  JsonObject behavior = doc["behavior"].to<JsonObject>();
  behavior["state"] = motionWindow.behavior;
  behavior["confidence"] = roundf(motionWindow.confidence * 100.0f) / 100.0f;
  behavior["posture"] = motionWindow.posture;
  behavior["postureConfidence"] =
      roundf(motionWindow.postureConfidence * 100.0f) / 100.0f;
  behavior["model"] = cattle_behavior_model::kVersion;
  behavior["postureModel"] = cattle_posture_model::kVersion;
  behavior["fusion"] = "three_adxl+body_tilt+leg_activity";
  behavior["scope"] = "behavior_screening_only";
  behavior["windowSamples"] = motionWindow.classifiedSamples;
  behavior["postureModelSamples"] = motionWindow.postureClassifiedSamples;
  behavior["neckModelState"] = motionWindow.neckModelBehavior;
  behavior["neckModelConfidence"] =
      roundf(motionWindow.neckModelConfidence * 100.0f) / 100.0f;
  JsonObject temporal = behavior["temporalResearch"].to<JsonObject>();
  const MotionTemporalPrediction &temporalPrediction = motionTemporalResearch.prediction();
  temporal["modelVersion"] = MOTION_TEMPORAL_MODEL_VERSION;
  temporal["status"] = motionTemporalResearch.status();
  temporal["scope"] = "neck_temporal_behavior_research";
  temporal["sensorLocation"] = "neck";
  temporal["sampleRateHz"] = MOTION_TEMPORAL_SAMPLE_RATE_HZ;
  temporal["windowSamples"] = MOTION_TEMPORAL_WINDOW_SAMPLES;
  temporal["observedSamples"] = motionTemporalResearch.samples();
  temporal["observedWindowSpanMs"] = motionTemporalResearch.spanMs();
  temporal["hopSamples"] = MOTION_TEMPORAL_HOP_SAMPLES;
  temporal["diagnosisAvailable"] = false;
  temporal["screeningEligible"] = false;
  temporal["label"] = temporalPrediction.rejected ? "unknown" : motion_temporal_class_names[temporalPrediction.label];
  if (temporalPrediction.rejected) {
    temporal["score"] = nullptr;
  } else {
    temporal["score"] = temporalPrediction.confidence;
    JsonArray temporalScores = temporal["probabilities"].to<JsonArray>();
    for (uint8_t index = 0; index < MOTION_TEMPORAL_CLASS_COUNT; ++index) {
      temporalScores.add(temporalPrediction.probabilities[index]);
    }
  }
  if (isfinite(motionWindow.bodyTiltDeg)) {
    behavior["bodyTiltDeg"] = roundf(motionWindow.bodyTiltDeg * 10.0f) / 10.0f;
    behavior["neckActivity"] = roundf(motionWindow.neckActivity * 100.0f) / 100.0f;
    behavior["bodyActivity"] = roundf(motionWindow.bodyActivity * 100.0f) / 100.0f;
    behavior["legActivity"] = roundf(motionWindow.legActivity * 100.0f) / 100.0f;
  } else {
    behavior["bodyTiltDeg"] = nullptr;
    behavior["neckActivity"] = nullptr;
    behavior["bodyActivity"] = nullptr;
    behavior["legActivity"] = nullptr;
  }
  JsonObject lameness = doc["lamenessScreen"].to<JsonObject>();
  lameness["modelStatus"] = lamenessReading.status;
  lameness["modelVersion"] = lamenessReading.modelVersion;
  lameness["windowSamples"] = lamenessReading.windowSamples;
  lameness["candidate"] = lamenessReading.candidate;
  lameness["rejected"] = lamenessReading.rejected;
  lameness["target"] = "lameness_suspect";
  lameness["screeningOnly"] = true;
  lameness["requiresClinicalReview"] = true;
  lameness["diagnosisAvailable"] = false;
  if (isfinite(lamenessReading.score)) {
    lameness["score"] = roundf(lamenessReading.score * 100.0f) / 100.0f;
  } else {
    lameness["score"] = nullptr;
  }

  // Disease labels are intentionally unavailable until clinically verified
  // animal-grouped captures have passed the release gate.
  JsonObject disease = doc["diseaseScreen"].to<JsonObject>();
  disease["modelStatus"] = "not_trained";
  disease["modelVersion"] = "none";
  disease["candidate"] = false;
  disease["diagnosisAvailable"] = false;
  disease["screeningOnly"] = true;
  disease["requiresVeterinarian"] = true;
  disease["reason"] = "no_clinically_verified_disease_dataset";

  JsonObject microphone = doc["microphone"].to<JsonObject>();
  microphone["initialized"] = microphoneOk;
  microphone["samples"] = audioReading.samples;
  microphone["readErrors"] = microphoneReadErrors;
  microphone["status"] = audioReading.status;
  microphone["channel"] = audioReading.channel;
  microphone["modelVersion"] = audioReading.modelVersion;
  microphone["modelStatus"] = audioReading.modelStatus;
  if (microphoneOk && isfinite(audioReading.rms)) {
    microphone["rawMin"] = audioReading.rawMin;
    microphone["rawMax"] = audioReading.rawMax;
    microphone["rawMean"] = roundf(audioReading.rawMean * 10.0f) / 10.0f;
    microphone["rms"] = roundf(audioReading.rms * 100000.0f) / 100000.0f;
    microphone["peak"] = roundf(audioReading.peak * 100000.0f) / 100000.0f;
    microphone["dbfs"] = roundf(audioReading.dbfs * 10.0f) / 10.0f;
  } else {
    microphone["rms"] = nullptr;
    microphone["peak"] = nullptr;
    microphone["dbfs"] = nullptr;
  }
  if (isfinite(audioReading.saturationRatio)) {
    microphone["saturationRatio"] = roundf(audioReading.saturationRatio * 100000.0f) / 100000.0f;
  } else {
    microphone["saturationRatio"] = nullptr;
  }
  if (isfinite(audioReading.zeroCrossingRate)) {
    microphone["zeroCrossingRate"] = roundf(audioReading.zeroCrossingRate * 100000.0f) / 100000.0f;
  } else {
    microphone["zeroCrossingRate"] = nullptr;
  }
  if (isfinite(audioReading.lowBandRatio)) {
    microphone["lowBandRatio"] = roundf(audioReading.lowBandRatio * 100000.0f) / 100000.0f;
    microphone["midBandRatio"] = roundf(audioReading.midBandRatio * 100000.0f) / 100000.0f;
    microphone["highBandRatio"] = roundf(audioReading.highBandRatio * 100000.0f) / 100000.0f;
  } else {
    microphone["lowBandRatio"] = nullptr;
    microphone["midBandRatio"] = nullptr;
    microphone["highBandRatio"] = nullptr;
  }
  if (isfinite(audioReading.snrDb)) {
    microphone["snrDb"] = roundf(audioReading.snrDb * 10.0f) / 10.0f;
  } else {
    microphone["snrDb"] = nullptr;
  }
  microphone["soundActive"] = audioReading.soundActive;
  microphone["vocalizationCandidate"] = audioReading.vocalizationCandidate;
  microphone["respiratoryCandidate"] = audioReading.respiratoryCandidate;
  microphone["abnormalVocalizationCandidate"] = audioReading.abnormalVocalizationCandidate;
  microphone["eventId"] = audioReading.eventId;
  microphone["eventLabel"] = audioReading.eventLabel;
  microphone["eventScore"] = roundf(audioReading.eventScore * 10000.0f) / 10000.0f;
  microphone["captureInProgress"] = audioReading.captureInProgress;
  microphone["captureAvailable"] = audioReading.captureAvailable;

  JsonObject b1 = doc["b1Infrared"].to<JsonObject>();
  b1["uart"] = true;
  b1["transport"] = "uart";
  b1["baud"] = B1_UART_BAUD;
  b1["rxLevel"] = digitalRead(PIN_B1_UART_RX);
  b1["receiving"] = b1Reading.receiving;
  b1["bytes"] = b1Reading.bytes;
  b1["status"] = b1Reading.status;
  b1["rawHex"] = b1Reading.rawHex;
  b1["validFrames"] = b1Reading.validFrames;
  b1["invalidFrames"] = b1Reading.invalidFrames;
  b1["lastCommand"] = b1Reading.lastCommand;
  b1["uartConfigured"] = b1Reading.uartConfigured;
  b1["bodyModeSent"] = b1BodyModeSent;
  b1["debugShell"] = b1Reading.debugShell;
  b1["debugAscii"] = b1Reading.debugAscii;
  b1["temperatureValid"] = b1Reading.temperatureValid;
  if (b1Reading.temperatureValid && isfinite(b1Reading.surfaceTemperature)) {
    b1["surfaceTemperature"] =
        roundf(b1Reading.surfaceTemperature * 10.0f) / 10.0f;
    b1["ambientTemperature"] =
        roundf(b1Reading.ambientTemperature * 10.0f) / 10.0f;
    b1["measurementType"] = b1Reading.measurementType;
    b1["ageMs"] = millis() - b1Reading.lastMeasurementMs;
  } else {
    b1["surfaceTemperature"] = nullptr;
    b1["ambientTemperature"] = nullptr;
    b1["measurementType"] = nullptr;
    b1["ageMs"] = nullptr;
  }
  doc["fan"] = fanOn;
  doc["fanMode"] = fanModeName();
  JsonObject control = doc["control"].to<JsonObject>();
  control["fanAvailable"] = ENABLE_ENV_SENSORS && PIN_FAN_CONTROL >= 0;
  control["alarmAvailable"] = true;
  control["atomizerAvailable"] = false;
  control["snapshotAvailable"] = false;
  control["fan"] = fanOn;
  control["fanMode"] = fanModeName();
  control["manualAlarm"] = manualAlarmOn;
  control["lastCommandId"] = lastHostCommandId;
  control["lastCommandAction"] = lastHostCommandAction;
  control["lastCommandStatus"] = lastHostCommandStatus;
  doc["level"] = latest.level;
  emitTelemetry(doc);
}

void i2cScan() {
  Serial.println("I2C scan:");
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("  found 0x%02X\n", addr);
    }
  }
}

void setupAddedI2cSensors() {
  sht31Ok = i2cDevicePresent(SHT31_I2C_ADDR);

  if (i2cDevicePresent(BH1750_I2C_ADDR)) {
    bh1750Address = BH1750_I2C_ADDR;
    bh1750Ok = true;
  } else if (i2cDevicePresent(BH1750_I2C_ALT_ADDR)) {
    bh1750Address = BH1750_I2C_ALT_ADDR;
    bh1750Ok = true;
  } else {
    bh1750Ok = false;
  }
  if (bh1750Ok) {
    const uint8_t powerOn = 0x01;
    const uint8_t continuousHighResolution = 0x10;
    bh1750Ok = i2cWrite(bh1750Address, &powerOn, 1) &&
                i2cWrite(bh1750Address, &continuousHighResolution, 1);
  }

  oledOk = i2cDevicePresent(OLED_I2C_ADDR);
  if (oledOk) {
    oled.setI2CAddress(OLED_I2C_ADDR << 1);
    oled.begin();
  }

  Serial.printf("SHT31=%s BH1750=%s@0x%02X OLED=%s\n",
                sht31Ok ? "ok" : "missing",
                bh1750Ok ? "ok" : "missing",
                bh1750Address,
                oledOk ? "ok" : "missing");
}

void recoverI2cDevices(uint32_t now) {
#if ENABLE_ENV_SENSORS
  bool criticalDeviceMissing = !sht31Ok || !maxOk;
#else
  bool criticalDeviceMissing = !maxOk;
#endif
  if (!criticalDeviceMissing ||
      now - lastI2cRecoveryMs < I2C_RECOVERY_INTERVAL_MS) {
    return;
  }
  lastI2cRecoveryMs = now;
  Serial.println("Retrying I2C bus and sensors...");

  Wire.end();
  pinMode(PIN_I2C_SDA, INPUT_PULLUP);
  pinMode(PIN_I2C_SCL, OUTPUT_OPEN_DRAIN);
  digitalWrite(PIN_I2C_SCL, HIGH);
  delayMicroseconds(5);
  for (uint8_t pulse = 0; pulse < 9; pulse++) {
    digitalWrite(PIN_I2C_SCL, LOW);
    delayMicroseconds(5);
    digitalWrite(PIN_I2C_SCL, HIGH);
    delayMicroseconds(5);
  }
  pinMode(PIN_I2C_SDA, OUTPUT_OPEN_DRAIN);
  digitalWrite(PIN_I2C_SDA, LOW);
  delayMicroseconds(5);
  digitalWrite(PIN_I2C_SCL, HIGH);
  delayMicroseconds(5);
  digitalWrite(PIN_I2C_SDA, HIGH);
  delayMicroseconds(5);

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(100000);
  setupAddedI2cSensors();
  maxOk = max30102.begin(Wire, I2C_SPEED_STANDARD);
  if (maxOk) {
    max30102.setup(0x24, 4, 2, 100, 411, 4096);
  }
  latest.maxStatus = maxOk ? "no_finger" : "missing";
  latest.fingerDetected = false;
  latest.heartRateValid = false;
  latest.spo2Valid = false;
  latest.heartRateEstimated = false;
  latest.spo2Estimated = false;
  latest.heartRate = NAN;
  latest.spo2 = -1;
  // Only a real I2C restart invalidates the MAX30102 accumulation window.
  bufferIndex = 0;
  bufferFilled = false;
  fingerSinceMs = 0;
  maxIrSeen = 0;
  minIrSeen = UINT32_MAX;
  for (uint8_t &rate : rates) {
    rate = 0;
  }
  rateSpot = 0;
  lastBeat = 0;
  Serial.printf("I2C retry MAX30102=%s\n", maxOk ? "ok" : "missing");
}

void recoverSpiMotionDevices(uint32_t now) {
  if ((mpu0Ok && adxl345Ok && mpu1Ok) ||
      now - lastSpiRecoveryMs < SPI_RECOVERY_INTERVAL_MS) {
    return;
  }
  lastSpiRecoveryMs = now;
  bool recovered = false;
  if (!mpu0Ok) {
    mpu0Ok = setupAdxl345Spi(PIN_ADXL_NECK_CS);
    recovered = recovered || mpu0Ok;
  }
  if (!adxl345Ok) {
    adxl345Ok = setupAdxl345Spi(PIN_ADXL_BODY_CS);
    recovered = recovered || adxl345Ok;
  }
  if (!mpu1Ok) {
    mpu1Ok = setupAdxl345Spi(PIN_ADXL_LEG_CS);
    recovered = recovered || mpu1Ok;
  }
  if (recovered) {
    resetMotionContinuity();
  }
}

void setup() {
  Serial.begin(115200);
  deviceBootId = esp_random();
  delay(500);
  Serial.println();
  Serial.println("Smart Cattle ESP32-S3 cow wearable node boot");
  loadNetworkConfig();

#if ENABLE_ENV_SENSORS
  pinMode(PIN_FLAME_DO, INPUT_PULLUP);
#endif
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
#if ENABLE_ENV_SENSORS
  if (PIN_FAN_CONTROL >= 0) {
    pinMode(PIN_FAN_CONTROL, OUTPUT);
  }
#endif
  if (ENCODER_ENABLED) {
    pinMode(PIN_ENCODER_CLK, INPUT_PULLUP);
    pinMode(PIN_ENCODER_DT, INPUT_PULLUP);
    pinMode(PIN_ENCODER_SW, INPUT_PULLUP);
  }
#if ENABLE_ENV_SENSORS
  if (PIN_FAN_CONTROL >= 0) {
    digitalWrite(PIN_FAN_CONTROL, FAN_ACTIVE_HIGH ? LOW : HIGH);
  }
#endif
  if (ENCODER_ENABLED) {
    lastEncoderClk = digitalRead(PIN_ENCODER_CLK);
    lastEncoderButton = digitalRead(PIN_ENCODER_SW);
  }
  if (BUZZER_ACTIVE_MODULE) {
    digitalWrite(PIN_BUZZER, BUZZER_ACTIVE_HIGH ? LOW : HIGH);
  } else {
    ledcSetup(BUZZER_LEDC_CHANNEL, BUZZER_FREQUENCY_HZ, BUZZER_LEDC_RESOLUTION);
    ledcAttachPin(PIN_BUZZER, BUZZER_LEDC_CHANNEL);
  }
  analogReadResolution(12);
#if defined(ADC_11db)
#if ENABLE_ENV_SENSORS
  analogSetPinAttenuation(PIN_MQ_AO, ADC_11db);
#endif
#endif
  setLed(false, false, false);
  if (BUZZER_ACTIVE_MODULE) {
    digitalWrite(PIN_BUZZER, BUZZER_ACTIVE_HIGH ? LOW : HIGH);
  } else {
    ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
  }

#if ENABLE_ENV_SENSORS
  dht.begin();
#endif
  microphoneOk = setupInmp441();
  pinMode(PIN_B1_UART_RX, INPUT);
  b1Serial.begin(B1_UART_BAUD, SERIAL_8N1, PIN_B1_UART_RX, PIN_B1_UART_TX);
  b1StartedMs = millis();
  requestB1Temperature();
  adxlSpi.begin(PIN_ADXL_SCK, PIN_ADXL_MISO, PIN_ADXL_MOSI, -1);
  pinMode(PIN_ADXL_NECK_CS, OUTPUT);
  pinMode(PIN_ADXL_BODY_CS, OUTPUT);
  pinMode(PIN_ADXL_LEG_CS, OUTPUT);
  digitalWrite(PIN_ADXL_NECK_CS, HIGH);
  digitalWrite(PIN_ADXL_BODY_CS, HIGH);
  digitalWrite(PIN_ADXL_LEG_CS, HIGH);
  mpu0Ok = setupAdxl345Spi(PIN_ADXL_NECK_CS);
  adxl345Ok = setupAdxl345Spi(PIN_ADXL_BODY_CS);
  mpu1Ok = setupAdxl345Spi(PIN_ADXL_LEG_CS);
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(100000);
  i2cScan();
  setupAddedI2cSensors();

  maxOk = max30102.begin(Wire, I2C_SPEED_STANDARD);
  if (maxOk) {
    // Moderate LED current avoids ADC saturation on close fingertip contact.
    max30102.setup(0x24, 4, 2, 100, 411, 4096);
  }
  latest.maxStatus = maxOk ? "no_finger" : "missing";
  latest.fingerDetected = false;
  latest.heartRateValid = false;
  latest.spo2Valid = false;
  latest.heartRateEstimated = false;
  latest.spo2Estimated = false;
  latest.heartRate = NAN;
  latest.spo2 = -1;
  Serial.printf("DHT11 pin=%d Flame pin=%d MQ AO pin=%d MAX30102=%s\n",
                PIN_DHT11, PIN_FLAME_DO, PIN_MQ_AO, maxOk ? "ok" : "missing");
  Serial.printf("LED: green=normal yellow=warning red=alarm, buzzer pin=%d\n", PIN_BUZZER);
  Serial.printf("Fan control=%d Encoder CLK/DT/SW=%d/%d/%d\n",
                PIN_FAN_CONTROL, PIN_ENCODER_CLK, PIN_ENCODER_DT, PIN_ENCODER_SW);
  Serial.printf("INMP441=%s SCK/WS/SD=%d/%d/%d, L/R must be GND\n",
                microphoneOk ? "ok" : "init_failed",
                PIN_INMP441_SCK, PIN_INMP441_WS, PIN_INMP441_SD);
  Serial.printf("B-1 UART%d baud=%d RX/TX=%d/%d (active query mode)\n",
                2, B1_UART_BAUD, PIN_B1_UART_RX, PIN_B1_UART_TX);
  Serial.printf("ADXL345 SPI SCK/MOSI/MISO=%d/%d/%d CS neck/body/leg=%d/%d/%d\n",
                PIN_ADXL_SCK, PIN_ADXL_MOSI, PIN_ADXL_MISO,
                PIN_ADXL_NECK_CS, PIN_ADXL_BODY_CS, PIN_ADXL_LEG_CS);
  Serial.printf("Behavior model=%s trees=%u, fusion=three ADXL345 + body tilt + leg activity\n",
                cattle_behavior_model::kVersion,
                cattle_behavior_model::kTreeCount);
}

void loop() {
  uint32_t now = millis();
  readHostCommands();
  ensureWifi();
  recoverI2cDevices(now);
  recoverSpiMotionDevices(now);
  handleEncoder();
  sampleInmp441();
  readB1Uart();
  updateB1Protocol(now);
  if (now - lastMaxSampleMs >= MAX30102_SAMPLE_INTERVAL_MS) {
    lastMaxSampleMs = now;
    updateMax30102();
  }

  if (now - lastMotionSampleMs >= MOTION_SAMPLE_INTERVAL_MS) {
    lastMotionSampleMs = now;
    sampleMotionSensors();
    emitMotionCaptureSample(now);
  }

  if (now - lastSampleMs >= SAMPLE_INTERVAL_MS) {
    lastSampleMs = now;
    classifyBehavior();
    finalizeAudioWindow();
    finalizeB1Window();
    readSensors();
    printReading();
  }

  if (manualAlarmOn) {
    setLed(false, false, true);
  }
  updateBuzzer(manualAlarmOn || latest.level == "alarm");
  updateDisplay();
  flushPendingAudioEvent();
}
