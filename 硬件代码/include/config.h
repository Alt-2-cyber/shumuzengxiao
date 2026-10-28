#pragma once

// Edit these defaults before flashing, or set them later from Serial:
//   set wifi_ssid your_ssid
//   set wifi_pass your_password
//   set mqtt_host 192.168.1.10
//   set backend_url http://192.168.1.10:8080

#define DEFAULT_BARN_ID "barn_01"
#define DEFAULT_DEVICE_ID "env_01"

#define DEFAULT_WIFI_SSID ""
#define DEFAULT_WIFI_PASS ""

#define DEFAULT_MQTT_HOST ""
#define DEFAULT_MQTT_PORT 1883
#define DEFAULT_MQTT_USER ""
#define DEFAULT_MQTT_PASS ""

// Example: http://192.168.1.100:8080
#define DEFAULT_BACKEND_URL ""

#define SENSOR_INTERVAL_MS 2000UL
#define TELEMETRY_INTERVAL_MS 10000UL
#define STATUS_INTERVAL_MS 30000UL
#define COMMAND_POLL_INTERVAL_MS 5000UL
#define MAIX_CAPTURE_COOLDOWN_MS 60000UL

// MQ modules stay disabled by default. Use the dedicated PlatformIO
// ``esp32s3_mq`` environment only after AO voltage has been verified below
// 3.3 V with a divider and the sensors have been preheated/calibrated.
#ifndef ENABLE_MQ_SENSORS
#define ENABLE_MQ_SENSORS false
#endif

#define SHT31_I2C_ADDR 0x44
#define BH1750_I2C_ADDR 0x23
#define OLED_I2C_ADDR 0x3C

// MQ sensors in prototype mode are trend sensors. Calibrate these two values
// with clean air and a known high reading before field use.
#define NH3_RAW_ZERO 450
#define NH3_RAW_FULL 2600
#define NH3_PPM_FULL 50.0f

#define TEMP_FAN_ON_C 32.0f
#define TEMP_ALARM_C 38.0f
#define HUMIDITY_HIGH_PERCENT 85.0f
#define ATOMIZER_TEMP_ON_C 30.0f
#define ATOMIZER_MAX_HUMIDITY_PERCENT 75.0f
#define NH3_FAN_ON_PPM 20.0f
#define NH3_ALARM_PPM 30.0f
#define SMOKE_ALARM_PERCENT 60.0f

#define RELAY_ACTIVE_LOW true
#define BUZZER_ACTIVE_HIGH true
#define BUZZER_ACTIVE_MODULE false
#define BUZZER_FREQUENCY_HZ 2200
#define BUZZER_LEDC_CHANNEL 0
#define BUZZER_LEDC_RESOLUTION 8
#define FLAME_ACTIVE_LOW true

// Default pins for common ESP32-S3 DevKit boards.
#if defined(CONFIG_IDF_TARGET_ESP32S3)
#define PIN_I2C_SDA 8
#define PIN_I2C_SCL 9
#define PIN_NH3_ADC 1
#define PIN_SMOKE_ADC 2
#define PIN_FLAME_DIGITAL 10
#define PIN_FAN_RELAY 14
#define PIN_ATOMIZER_RELAY 15
#define PIN_ALARM_LIGHT 16
#define PIN_BUZZER 21
#define PIN_STATUS_LED 48
#define PIN_MAIX_RX 18
#define PIN_MAIX_TX 17
#else
// Fallback pins for classic ESP32 DevKit boards.
#define PIN_I2C_SDA 21
#define PIN_I2C_SCL 22
#define PIN_NH3_ADC 34
#define PIN_SMOKE_ADC 35
#define PIN_FLAME_DIGITAL 32
#define PIN_FAN_RELAY 25
#define PIN_ATOMIZER_RELAY 26
#define PIN_ALARM_LIGHT 27
#define PIN_BUZZER 33
#define PIN_STATUS_LED 2
#define PIN_MAIX_RX 16
#define PIN_MAIX_TX 17
#endif
