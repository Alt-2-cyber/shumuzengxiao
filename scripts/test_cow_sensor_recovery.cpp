// Run with: python scripts/test_cow_sensor_recovery.py
#include <array>
#include <cmath>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <functional>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

using String = std::string;
using std::isfinite;
#include "config.h"
#include "cattle_behavior_model.h"
#include "cattle_posture_model.h"
#include "cattle_lameness_model.h"
#include "motion_temporal_stream.h"
#include "cow_sensor_types.h"

constexpr int LOW = 0;
constexpr int HIGH = 1;
constexpr int OUTPUT = 1;
constexpr int INPUT_PULLUP = 2;
constexpr int OUTPUT_OPEN_DRAIN = 3;
constexpr int I2C_SPEED_STANDARD = 100000;

struct FakeDevice {
  std::array<uint8_t, 64> registers{};
  bool connected = true;
  bool discardWrites = false;
  unsigned writes = 0;

  FakeDevice() {
    registers[0] = 0xE5;
    registers[0x2C] = 0x0A;
    registers[0x2D] = 0x08;
    registers[0x31] = 0x0B;
    registers[0x36] = 0x00;
    registers[0x37] = 0x01;
  }
};

std::map<int, FakeDevice> devices;
int selectedPin = -1;
bool commandPending = false;
bool spiRead = false;
bool spiIncrement = false;
uint8_t spiRegister = 0;

void pinMode(int, int) {}
void delayMicroseconds(int) {}
void digitalWrite(int pin, int value) {
  if (devices.count(pin)) {
    selectedPin = value == LOW ? pin : -1;
    commandPending = value == LOW;
  }
}

struct FakeSpi {
  void beginTransaction(int) {}
  void endTransaction() {}
  uint8_t transfer(uint8_t value) {
    if (selectedPin < 0) {
      throw std::runtime_error("SPI transfer without a selected device");
    }
    FakeDevice &device = devices.at(selectedPin);
    if (commandPending) {
      commandPending = false;
      spiRead = (value & 0x80) != 0;
      spiIncrement = (value & 0x40) != 0;
      spiRegister = value & 0x3F;
      return 0;
    }
    uint8_t result = 0xFF;
    if (device.connected) {
      if (spiRead) {
        result = device.registers.at(spiRegister);
      } else {
        device.writes++;
        if (!device.discardWrites) {
          device.registers.at(spiRegister) = value;
        }
      }
    }
    if (spiIncrement) {
      spiRegister++;
    }
    return result;
  }
} adxlSpi;
int adxlSpiSettings = 0;

struct FakeWire {
  unsigned ends = 0;
  unsigned begins = 0;
  unsigned transactions = 0;
  void end() { ends++; }
  void begin(int, int) { begins++; }
  void setClock(int) {}
} Wire;

struct FakeMax {
  unsigned begins = 0;
  unsigned setups = 0;
  bool begin(FakeWire &, int) { begins++; return true; }
  void setup(int, int, int, int, int, int) { setups++; }
} max30102;

struct FakeOled {
  void setI2CAddress(int) {}
  void begin() {}
} oled;

struct FakeSerial {
  String output;
  void println(const char *value) { output += value; output += '\n'; }
  void printf(const char *format, ...) {
    char buffer[512];
    va_list arguments;
    va_start(arguments, format);
    std::vsnprintf(buffer, sizeof(buffer), format, arguments);
    va_end(arguments);
    output += buffer;
  }
} Serial;

bool maxOk, sht31Ok, bh1750Ok, oledOk, adxl345Ok, mpu0Ok, mpu1Ok;
uint8_t bh1750Address = BH1750_I2C_ADDR;
uint32_t lastI2cRecoveryMs = 0;
#if HAS_SPI_RECOVERY
uint32_t lastSpiRecoveryMs = 0;
#endif
uint32_t fingerSinceMs = 0, maxIrSeen = 0, minIrSeen = UINT32_MAX;
int bufferIndex = 0;
bool bufferFilled = false;
uint8_t rates[6] = {};
uint8_t rateSpot = 0;
long lastBeat = 0;
Reading latest;
MotionReading adxlReading, mpu0Reading, mpu1Reading;
MotionReading previousAdxlReading, previousMpu0Reading, previousMpu1Reading;
MotionWindow motionWindow;
MotionTemporalStream motionTemporalResearch;
uint32_t testClockMs = 0;
uint32_t millis() { return testClockMs; }
LamenessFeatureWindow lamenessWindow;
LamenessReading lamenessReading;
MotionCaptureSession motionCapture;
#if HAS_SPI_DIAGNOSTICS
Adxl345SpiDiagnostics neckSpiDiagnostics, bodySpiDiagnostics, legSpiDiagnostics;
#endif
String captureStatus;
unsigned captureStateEvents = 0;

bool i2cDevicePresent(uint8_t) { Wire.transactions++; return false; }
bool i2cWrite(uint8_t, const uint8_t *, size_t) { Wire.transactions++; return true; }
void sendMotionCaptureState(const char *status) { captureStatus = status; captureStateEvents++; }

#include "cow_sensor_functions.h"

#define CHECK(condition) do { if (!(condition)) { \
  throw std::runtime_error(String("line ") + std::to_string(__LINE__) + ": " #condition); \
} } while (false)

const int pins[] = {PIN_ADXL_NECK_CS, PIN_ADXL_BODY_CS, PIN_ADXL_LEG_CS};

void fixture() {
  motionTemporalResearch = MotionTemporalStream();
  testClockMs = 0;
  devices.clear();
  for (int pin : pins) {
    devices.emplace(pin, FakeDevice());
  }
  selectedPin = -1;
  Wire = FakeWire();
  max30102 = FakeMax();
  Serial.output.clear();
  maxOk = mpu0Ok = adxl345Ok = mpu1Ok = true;
  sht31Ok = bh1750Ok = oledOk = false;
  lastI2cRecoveryMs = 0;
#if HAS_SPI_RECOVERY
  lastSpiRecoveryMs = 0;
#endif
  latest = Reading();
  latest.heartRate = 72.0f;
  latest.heartRateValid = true;
  latest.spo2 = 98;
  latest.spo2Valid = true;
  latest.maxStatus = "valid";
  bufferIndex = 73;
  bufferFilled = true;
  fingerSinceMs = 100;
  rates[0] = 72;
  mpu0Reading = adxlReading = mpu1Reading = MotionReading();
  previousMpu0Reading = previousAdxlReading = previousMpu1Reading = MotionReading();
  motionWindow = MotionWindow();
  lamenessWindow = LamenessFeatureWindow();
  lamenessReading = LamenessReading();
  motionCapture = MotionCaptureSession();
  captureStatus.clear();
  captureStateEvents = 0;
}

void seedInterruptedWindow() {
  motionWindow.samples = 17;
  motionWindow.modelSamples = 17;
  motionWindow.postureModelSamples = 17;
  motionWindow.classVotes[4] = 17;
  motionWindow.postureClassVotes[1] = 17;
  motionWindow.classifiedSamples = 40;
  motionWindow.postureClassifiedSamples = 40;
  motionWindow.neckActivitySum = motionWindow.bodyActivitySum = motionWindow.legActivitySum = 250.0f;
  motionWindow.neckActivity = motionWindow.bodyActivity = motionWindow.legActivity = 6.0f;
  motionWindow.bodyTiltDeg = 80.0f;
  motionWindow.behavior = "walking";
  motionWindow.neckModelBehavior = "walking";
  motionWindow.confidence = motionWindow.neckModelConfidence = 0.9f;
  for (unsigned i = 0; i < 199; i++) {
    lamenessWindow.neckAcceleration.add(300.0f + i);
    lamenessWindow.bodyAcceleration.add(300.0f + i);
    lamenessWindow.legAcceleration.add(300.0f + i);
    lamenessWindow.samples++;
  }
  lamenessReading.windowSamples = 200;
  lamenessReading.candidate = true;
  lamenessReading.score = 0.9f;
  previousMpu0Reading.ax = previousAdxlReading.ax = previousMpu1Reading.ax = 900.0f;
  previousMpu0Reading.ay = previousAdxlReading.ay = previousMpu1Reading.ay = 0.0f;
  previousMpu0Reading.az = previousAdxlReading.az = previousMpu1Reading.az = 0.0f;
}

void checkMaxUntouched() {
  CHECK(Wire.ends == 0 && Wire.begins == 0 && Wire.transactions == 0);
  CHECK(max30102.begins == 0 && max30102.setups == 0);
  CHECK(latest.heartRateValid && latest.heartRate == 72.0f);
  CHECK(latest.spo2Valid && latest.spo2 == 98 && latest.maxStatus == "valid");
  CHECK(bufferIndex == 73 && bufferFilled && fingerSinceMs == 100 && rates[0] == 72);
}

void retryMotion(uint32_t now) {
#if HAS_SPI_RECOVERY
  recoverSpiMotionDevices(now);
#else
  // Exercise the pre-fix route as well, to prove the regression test fails.
  recoverI2cDevices(now);
#endif
}

void missingSpiCannotRestartMax() {
  for (unsigned mask = 1; mask < 8; mask++) {
    fixture();
    mpu0Ok = !(mask & 1);
    adxl345Ok = !(mask & 2);
    mpu1Ok = !(mask & 4);
    for (uint32_t now : {5000U, 10000U, 15000U, 20000U}) {
      recoverI2cDevices(now);
    }
    checkMaxUntouched();
    for (int pin : pins) {
      CHECK(devices.at(pin).writes == 0);
    }
  }
}

void i2cRecoveryCannotTouchMotion() {
  fixture();
  maxOk = false;
  adxl345Ok = false;
  seedInterruptedWindow();
  recoverI2cDevices(4999);
  CHECK(Wire.ends == 0);
  recoverI2cDevices(5000);
  CHECK(Wire.ends == 1 && Wire.begins == 1);
  CHECK(max30102.begins == 1 && max30102.setups == 1 && maxOk);
  for (int pin : pins) {
    CHECK(devices.at(pin).writes == 0);
  }
  CHECK(mpu0Ok && !adxl345Ok && mpu1Ok);
  CHECK(motionWindow.samples == 17 && lamenessWindow.samples == 199);
  CHECK(previousAdxlReading.ax == 900.0f);
}

void retriesOnlyMissingSpi() {
  for (int missingPin : pins) {
    fixture();
    seedInterruptedWindow();
    mpu0Ok = missingPin != PIN_ADXL_NECK_CS;
    adxl345Ok = missingPin != PIN_ADXL_BODY_CS;
    mpu1Ok = missingPin != PIN_ADXL_LEG_CS;
    devices.at(missingPin).connected = false;
    retryMotion(4999);
    CHECK(Serial.output.empty());
    retryMotion(5000);
    CHECK(mpu0Ok == (missingPin != PIN_ADXL_NECK_CS));
    CHECK(adxl345Ok == (missingPin != PIN_ADXL_BODY_CS));
    CHECK(mpu1Ok == (missingPin != PIN_ADXL_LEG_CS));
    for (int pin : pins) {
      CHECK(devices.at(pin).writes == 0);
    }
    checkMaxUntouched();
    devices.at(missingPin).connected = true;
    retryMotion(9999);
    CHECK(devices.at(missingPin).writes == 0);
    retryMotion(10000);
    CHECK(adxl345Ok && mpu0Ok && mpu1Ok);
    for (int pin : pins) {
      CHECK((devices.at(pin).writes > 0) == (pin == missingPin));
    }
    CHECK(motionWindow.samples == 0 && lamenessWindow.samples == 0);
    CHECK(!isfinite(previousAdxlReading.ax));
    const unsigned writes = devices.at(missingPin).writes;
    retryMotion(15000);
    CHECK(devices.at(missingPin).writes == writes);
    checkMaxUntouched();
  }
}

void badIdInterruptsAllFeatureWindows() {
  for (int pin : pins) {
    for (uint8_t badId : {0x00, 0xFF, 0xE4}) {
      fixture();
      seedInterruptedWindow();
      motionCapture.active = true;
      motionCapture.samples = 11;
      devices.at(pin).registers[0] = badId;
      sampleMotionSensors();
      CHECK(mpu0Ok == (pin != PIN_ADXL_NECK_CS));
      CHECK(adxl345Ok == (pin != PIN_ADXL_BODY_CS));
      CHECK(mpu1Ok == (pin != PIN_ADXL_LEG_CS));
      CHECK(motionWindow.samples == 0 && motionWindow.modelSamples == 0);
      CHECK(motionWindow.classVotes[4] == 0 && motionWindow.postureClassVotes[1] == 0);
      CHECK(motionWindow.classifiedSamples == 0 && motionWindow.postureClassifiedSamples == 0);
      CHECK(motionWindow.behavior == "sensors_missing" && motionWindow.confidence == 0.0f);
      CHECK(!isfinite(motionWindow.bodyTiltDeg) && !isfinite(motionWindow.neckActivity));
      CHECK(lamenessWindow.samples == 0 && lamenessWindow.neckAcceleration.deltaSamples == 0);
      CHECK(lamenessReading.windowSamples == 0 && !lamenessReading.candidate && !isfinite(lamenessReading.score));
      CHECK(!isfinite(previousMpu0Reading.ax) && !isfinite(previousAdxlReading.ax) && !isfinite(previousMpu1Reading.ax));
      CHECK(!motionCapture.active && motionCapture.samples == 11);
      CHECK(motionCapture.droppedSensorSamples == 1 && captureStatus == "sensor_failure");
      sampleMotionSensors();
      CHECK(captureStateEvents == 1 && motionCapture.droppedSensorSamples == 1);
      checkMaxUntouched();
    }
  }
}

void recoveryStartsANewContinuousWindow() {
  fixture();
  for (unsigned i = 0; i < 199; i++) {
    sampleMotionSensors();
  }
  CHECK(lamenessWindow.samples == 199 && lamenessReading.windowSamples == 0);
  motionCapture.active = true;
  devices.at(PIN_ADXL_BODY_CS).registers[0] = 0xFF;
  sampleMotionSensors();
  CHECK(lamenessWindow.samples == 0 && !adxl345Ok);
  devices.at(PIN_ADXL_BODY_CS).registers[0] = 0xE5;
  retryMotion(5000);
  CHECK(!motionCapture.active && captureStatus == "sensor_failure");
  sampleMotionSensors();
  CHECK(motionWindow.samples == 1 && motionWindow.bodyActivitySum == 0.0f);
  CHECK(lamenessWindow.samples == 1 && lamenessWindow.bodyAcceleration.deltaSamples == 0);
  CHECK(lamenessReading.windowSamples == 0);
  for (unsigned i = 1; i < 199; i++) {
    sampleMotionSensors();
  }
  CHECK(lamenessWindow.samples == 199 && lamenessReading.windowSamples == 0);
  sampleMotionSensors();
  CHECK(lamenessWindow.samples == 0 && lamenessReading.windowSamples == 200);
  CHECK(!lamenessReading.candidate && !isfinite(lamenessReading.score));
  checkMaxUntouched();
}

void configurationMustReadBack() {
  for (int pin : pins) {
    for (uint8_t reg : {0x31, 0x2C, 0x2D}) {
      fixture();
      devices.at(pin).registers[reg] = 0;
      devices.at(pin).discardWrites = true;
      CHECK(!setupAdxl345Spi(pin));
      devices.at(pin).discardWrites = false;
      CHECK(setupAdxl345Spi(pin));
      CHECK(devices.at(pin).registers[0x31] == 0x0B);
      CHECK(devices.at(pin).registers[0x2C] == 0x0A);
      CHECK(devices.at(pin).registers[0x2D] == 0x08);
      devices.at(pin).connected = false;
      MotionReading reading;
      reading.ax = 123.0f;
      CHECK(!readAdxl345Spi(pin, reading));
      CHECK(!isfinite(reading.ax));
    }
  }
}

void temporalCandidateRequiresFreshContinuousSamples() {
  fixture();
  for (unsigned i = 0; i < 80; ++i) {
    testClockMs = i * 50;
    sampleMotionSensors();
  }
  CHECK(motionTemporalResearch.samples() == 80);
  CHECK(!motionTemporalResearch.prediction().rejected);
  devices.at(PIN_ADXL_BODY_CS).connected = false;
  testClockMs += 50;
  sampleMotionSensors();
  CHECK(motionTemporalResearch.samples() == 0);
  CHECK(motionTemporalResearch.prediction().rejected);
}

int main() {
  const std::vector<std::pair<const char *, std::function<void()>>> tests = {
      {"all missing-SPI combinations leave I2C/MAX windows intact", missingSpiCannotRestartMax},
      {"real I2C recovery leaves SPI and motion windows intact", i2cRecoveryCannotTouchMotion},
      {"SPI retries are throttled and initialize only the missing module", retriesOnlyMissingSpi},
      {"bad runtime IDs invalidate health, windows and clinical raw capture", badIdInterruptsAllFeatureWindows},
      {"recovery requires a fresh 200-sample lameness window", recoveryStartsANewContinuousWindow},
      {"configuration readback and unplugged reads fail honestly", configurationMustReadBack},
      {"temporal research requires fresh samples and resets after sensor failure", temporalCandidateRequiresFreshContinuousSamples},
  };
  unsigned failures = 0;
  for (const auto &test : tests) {
    try {
      test.second();
      std::cout << "PASS " << test.first << '\n';
    } catch (const std::exception &error) {
      failures++;
      std::cout << "FAIL " << test.first << ": " << error.what() << '\n';
    }
  }
  std::cout << tests.size() - failures << '/' << tests.size() << " host scenarios passed\n";
  return failures ? 1 : 0;
}
