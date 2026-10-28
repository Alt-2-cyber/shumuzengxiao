#pragma once

#define DEVICE_ID "demo_esp32_01"
#define BARN_ID "barn_01"
// Set this to the ear-tag or management identifier of the cow before deployment.
// The default keeps current telemetry compatible during bench testing.
#define CATTLE_ID DEVICE_ID

#define PIN_DHT11 4
#define PIN_FLAME_DO 32
#define PIN_MQ_AO 34

#define PIN_I2C_SDA 21
#define PIN_I2C_SCL 22

// INMP441 uses the ESP32 I2S0 receiver. L/R should be connected to GND.
// The firmware reads both I2S slots at boot and selects the valid one, so a
// wrong L/R level can be diagnosed instead of being silently treated as audio.
#define PIN_INMP441_SCK 5
#define PIN_INMP441_WS 16
#define PIN_INMP441_SD 17

// B-1 shares these wires between UART (TX/RX) and I2C (SDA/SCL).
#define PIN_B1_UART_RX 23
#define PIN_B1_UART_TX 19

#define PIN_LED_GREEN 25
#define PIN_LED_YELLOW 26
#define PIN_LED_RED 27
#define PIN_BUZZER 33

// Added hardware. All I2C modules share GPIO21/GPIO22.
#define PIN_FAN_CONTROL 14
#define PIN_ENCODER_CLK 35
#define PIN_ENCODER_DT 13
#define PIN_ENCODER_SW 18
#define ENCODER_ENABLED false

#define SHT31_I2C_ADDR 0x44
#define BH1750_I2C_ADDR 0x23
#define BH1750_I2C_ALT_ADDR 0x5C
#define OLED_I2C_ADDR 0x3C
#define ADXL345_I2C_ADDR 0x53
#define MPU0_I2C_ADDR 0x68
#define MPU1_I2C_ADDR 0x69

#define DHT_TYPE DHT11
#define FLAME_ACTIVE_LOW true

#define SAMPLE_INTERVAL_MS 2000UL
#define MAX30102_SAMPLE_INTERVAL_MS 20UL
#define MOTION_SAMPLE_INTERVAL_MS 50UL
#define I2C_RECOVERY_INTERVAL_MS 5000UL

// Raw three-position IMU data is emitted only during an explicitly started,
// time-limited clinical collection session. The 20 Hz rows are intended for
// synchronized video/gait-score annotation, not ordinary live telemetry.
#define MOTION_CAPTURE_DEFAULT_DURATION_MS 60000UL
#define MOTION_CAPTURE_MAX_DURATION_MS 300000UL

#define LAMENESS_WINDOW_SAMPLES 200U

#define INMP441_SAMPLE_RATE_HZ 16000
#define INMP441_DMA_SAMPLES 256
#define INMP441_SAMPLE_SHIFT 8
#define INMP441_SLOT_CALIBRATION_FRAMES 4096UL
// -1 selects the healthier I2S slot automatically. Use 0 or 1 only when a
// logic analyser or a known-good wiring test has identified the data slot.
#define INMP441_FORCE_SLOT -1
#define INMP441_FEATURE_SAMPLE_RATE_HZ 8000
#define INMP441_FEATURE_FRAME_SAMPLES 128
// Keep the reviewed WAV duration equal to the two-second inference window.
#define INMP441_CAPTURE_DURATION_MS 2000UL
#define INMP441_CAPTURE_SAMPLES ((INMP441_FEATURE_SAMPLE_RATE_HZ * INMP441_CAPTURE_DURATION_MS) / 1000UL)
#define INMP441_CAPTURE_GAIN 8.0f
#define AUDIO_ACTIVE_RMS 0.010f
#define AUDIO_VOCALIZATION_RMS 0.020f
#define AUDIO_VOCALIZATION_PEAK 0.080f
#define AUDIO_INVALID_RMS 0.250f
#define AUDIO_INVALID_SATURATION_RATIO 0.08f
#define AUDIO_DISEASE_CANDIDATE_SCORE 0.72f
#define AUDIO_EVENT_MIN_INTERVAL_MS 30000UL
#define AUDIO_AUTO_CAPTURE_ENABLED true
#define AUDIO_AUTO_CAPTURE_MIN_INTERVAL_MS 60000UL

// AFUIOT B-1 UART protocol: 38400 baud, 8 data bits, 1 stop bit, no parity.
#define B1_UART_BAUD 38400
#define B1_RAW_BUFFER_SIZE 128
#define B1_FRAME_BUFFER_SIZE 32
#define B1_REQUEST_INTERVAL_MS 1000UL
#define B1_BODY_MODE_DELAY_MS 1200UL
#define B1_READING_STALE_MS 5000UL

// Physical fusion thresholds around the public neck-IMU model. Recalibrate
// after collecting synchronized neck/body/leg data from mounted sensors.
#define BODY_LIE_TILT_DEG 55.0f
#define WALK_LEG_ACTIVITY 1.20f
#define VIGOROUS_LEG_ACTIVITY 3.00f
#define ACTIVE_NECK_ACTIVITY 0.65f

#define FINGER_IR_THRESHOLD 10000UL
#define BUZZER_FREQUENCY_HZ 2200
#define BUZZER_LEDC_CHANNEL 0
#define BUZZER_LEDC_RESOLUTION 8
#define BUZZER_ACTIVE_MODULE false
#define BUZZER_ACTIVE_HIGH true
#define FAN_ACTIVE_HIGH true

#define TEMP_FAN_ON_C 30.0f
#define HUMIDITY_FAN_ON_PERCENT 80.0f

// MQ module is a trend sensor here. Thresholds are raw ADC 0-4095.
#define MQ_WARN_RAW 1800
#define MQ_ALARM_RAW 2600
