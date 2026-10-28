#pragma once

// ESP32-S3 cow-wearable node. Set CATTLE_ID to the real ear-tag or management
// identifier before putting the node on an animal.
#define DEVICE_ID "cow_node_01"
#define BARN_ID "barn_01"
#define CATTLE_ID "cow_001"

// WiFi/HTTP transport. Credentials are normally written at runtime with the
// serial commands `set wifi_ssid`, `set wifi_pass`, and `set backend_url`.
#define DEFAULT_WIFI_SSID ""
#define DEFAULT_WIFI_PASS ""
#define DEFAULT_BACKEND_URL ""
#define WIFI_RETRY_INTERVAL_MS 10000UL
#define WIFI_POST_INTERVAL_MS 10000UL
#define WIFI_HTTP_TIMEOUT_MS 2000UL

// This node owns three ADXL345 accelerometers, microphone, MAX30102 and B-1.
// Environment sensors and the fan remain on the separate COM9 node.
#define ENABLE_ENV_SENSORS false

// ESP32-S3 DevKitC-1 pin map. This board prints bare GPIO numbers (not Dxx).
// GPIO13 is not broken out on the N16R8 board, so the buzzer uses GPIO3.
#define PIN_I2C_SDA 8
#define PIN_I2C_SCL 9

// Three ADXL345 modules use one shared SPI bus and one chip-select per position.
// The module pin labelled SDA is MOSI/SDI in 4-wire SPI mode; SDO is MISO.
#define PIN_ADXL_SCK 40
#define PIN_ADXL_MOSI 41
#define PIN_ADXL_MISO 42
#define PIN_ADXL_NECK_CS 38
#define PIN_ADXL_BODY_CS 39
#define PIN_ADXL_LEG_CS 47
// Conservative clock for shared SPI over short Dupont jumper wires.
#define ADXL345_SPI_FREQUENCY_HZ 500000UL

// INMP441: VDD=3V3, GND=GND, L/R=GND.
#define PIN_INMP441_SCK 5
#define PIN_INMP441_WS 6
#define PIN_INMP441_SD 7

// B-1 UART, crossed: B-1 TX -> ESP32 RX, B-1 RX <- ESP32 TX.
#define PIN_B1_UART_RX 18
#define PIN_B1_UART_TX 17

// External common-cathode LEDs through resistors and an active buzzer/driver.
#define PIN_LED_GREEN 10
#define PIN_LED_YELLOW 11
#define PIN_LED_RED 12
#define PIN_BUZZER 3

// No fan or rotary encoder is connected to the wearable node.
#define PIN_FAN_CONTROL -1
#define PIN_ENCODER_CLK 35
#define PIN_ENCODER_DT 36
#define PIN_ENCODER_SW 37
#define ENCODER_ENABLED false

// Kept as optional diagnostic inputs; they are ignored while
// ENABLE_ENV_SENSORS is false.
#define PIN_DHT11 4
#define PIN_FLAME_DO 10
#define PIN_MQ_AO 1

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
#define MOTION_TEMPORAL_RESEARCH_ENABLED true
#define I2C_RECOVERY_INTERVAL_MS 5000UL
#define SPI_RECOVERY_INTERVAL_MS 5000UL

#define MOTION_CAPTURE_DEFAULT_DURATION_MS 60000UL
#define MOTION_CAPTURE_MAX_DURATION_MS 300000UL
#define LAMENESS_WINDOW_SAMPLES 200U

#define INMP441_SAMPLE_RATE_HZ 16000
#define INMP441_DMA_SAMPLES 256
#define INMP441_SAMPLE_SHIFT 8
#define INMP441_SLOT_CALIBRATION_FRAMES 4096UL
#define INMP441_FORCE_SLOT -1
#define INMP441_FEATURE_SAMPLE_RATE_HZ 8000
#define INMP441_FEATURE_FRAME_SAMPLES 128
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

// Used only if ENABLE_ENV_SENSORS is enabled for a bench variant.
#define MQ_WARN_RAW 1800
#define MQ_ALARM_RAW 2600
