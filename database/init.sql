CREATE DATABASE IF NOT EXISTS smart_cattle DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smart_cattle;

CREATE TABLE IF NOT EXISTS device (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  device_id VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  type VARCHAR(64) NOT NULL,
  barn_id VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  battery INT,
  signal_strength INT,
  last_seen DATETIME(6)
);

CREATE TABLE IF NOT EXISTS environment_reading (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  barn_id VARCHAR(64) NOT NULL,
  device_id VARCHAR(64) NOT NULL,
  temperature DOUBLE,
  humidity DOUBLE,
  ammonia DOUBLE,
  nh3_raw INT,
  light_lux DOUBLE,
  smoke DOUBLE,
  smoke_raw INT,
  flame BOOLEAN,
  fan_on BOOLEAN,
  fan_mode VARCHAR(32),
  atomizer_on BOOLEAN,
  atomizer_mode VARCHAR(32),
  alarm_mode VARCHAR(32),
  rssi INT,
  recorded_at DATETIME(6)
);

CREATE TABLE IF NOT EXISTS vision_event (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  camera_id VARCHAR(64) NOT NULL,
  barn_id VARCHAR(64) NOT NULL,
  event_type VARCHAR(96) NOT NULL,
  severity VARCHAR(32) NOT NULL,
  score DOUBLE,
  target_id VARCHAR(64),
  source_key VARCHAR(190),
  source_snapshot_path VARCHAR(255),
  snapshot_path VARCHAR(255),
  snapshot_sha256 VARCHAR(64),
  snapshot_available BOOLEAN,
  snapshot_content_type VARCHAR(64),
  snapshot_bytes BIGINT,
  evidence VARCHAR(1000),
  model_name VARCHAR(120),
  model_version VARCHAR(120),
  model_status VARCHAR(40),
  model_approved_by_server BOOLEAN,
  screening_eligible BOOLEAN,
  recorded_at DATETIME(6)
);

CREATE TABLE IF NOT EXISTS vision_event_review (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  vision_event_id BIGINT NOT NULL,
  status VARCHAR(20),
  label VARCHAR(96),
  reviewer VARCHAR(80),
  animal_id VARCHAR(120),
  veterinarian VARCHAR(80),
  clinical_evidence_reference VARCHAR(1200),
  note VARCHAR(1200),
  clinically_verified_at DATETIME(6),
  reviewed_at DATETIME(6),
  UNIQUE KEY uk_vision_event_review_event (vision_event_id)
);

CREATE TABLE IF NOT EXISTS audio_event (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  device_id VARCHAR(64) NOT NULL,
  barn_id VARCHAR(64) NOT NULL,
  event_type VARCHAR(96) NOT NULL,
  score DOUBLE,
  duration_ms INT,
  snr DOUBLE,
  audio_clip_path VARCHAR(255),
  recorded_at DATETIME(6)
);

CREATE TABLE IF NOT EXISTS audio_event_metadata (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  audio_event_id BIGINT NOT NULL,
  source_key VARCHAR(190),
  cattle_id VARCHAR(120),
  model_version VARCHAR(120),
  model_status VARCHAR(80),
  approved_by_server BOOLEAN,
  screening_eligible BOOLEAN,
  approval_reason VARCHAR(80),
  predicted_label VARCHAR(80),
  clip_available BOOLEAN,
  clip_sha256 VARCHAR(64),
  rms DOUBLE,
  dbfs DOUBLE,
  zero_crossing_rate DOUBLE,
  low_band_ratio DOUBLE,
  mid_band_ratio DOUBLE,
  high_band_ratio DOUBLE,
  saturation_ratio DOUBLE,
  features_json LONGTEXT,
  UNIQUE KEY uk_audio_event_metadata_event (audio_event_id),
  UNIQUE KEY uk_audio_event_metadata_source (source_key)
);

CREATE TABLE IF NOT EXISTS audio_event_review (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  audio_event_id BIGINT NOT NULL,
  status VARCHAR(20),
  label VARCHAR(80),
  reviewer VARCHAR(80),
  animal_id VARCHAR(120),
  recording_session_id VARCHAR(120),
  veterinarian VARCHAR(80),
  clinical_evidence_reference VARCHAR(1200),
  clinically_verified_at DATETIME(6),
  note LONGTEXT,
  reviewed_at DATETIME(6),
  UNIQUE KEY uk_audio_event_review_event (audio_event_id)
);

CREATE TABLE IF NOT EXISTS health_screening_observation (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  target_id VARCHAR(120) NOT NULL,
  received_at DATETIME(6) NOT NULL,
  motion_available BOOLEAN,
  behavior VARCHAR(64),
  behavior_confidence DOUBLE,
  activity DOUBLE,
  surface_temperature DOUBLE,
  lameness_model_deployed BOOLEAN,
  lameness_candidate BOOLEAN,
  lameness_rejected BOOLEAN,
  lameness_score DOUBLE,
  microphone_available BOOLEAN,
  vocalization_candidate BOOLEAN,
  audio_model_deployed BOOLEAN,
  respiratory_candidate BOOLEAN,
  abnormal_vocalization_candidate BOOLEAN,
  KEY idx_health_screen_observation_target_time (target_id, received_at),
  KEY idx_health_screen_observation_time (received_at)
);

CREATE TABLE IF NOT EXISTS health_risk (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  barn_id VARCHAR(64) NOT NULL,
  target_id VARCHAR(64),
  risk_type VARCHAR(96) NOT NULL,
  risk_level VARCHAR(32) NOT NULL,
  score DOUBLE,
  evidence VARCHAR(1200),
  suggestion VARCHAR(500),
  status VARCHAR(32),
  recorded_at DATETIME(6)
);

CREATE TABLE IF NOT EXISTS clinical_check (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  cattle_id VARCHAR(120) NOT NULL,
  check_type VARCHAR(32) NOT NULL,
  verified BOOLEAN,
  alert BOOLEAN,
  measured_value DOUBLE,
  examiner VARCHAR(80),
  evidence_reference VARCHAR(1200),
  findings VARCHAR(1200),
  evidence_type VARCHAR(96),
  recorded_at DATETIME(6) NOT NULL
);

CREATE TABLE IF NOT EXISTS motion_capture_session (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  session_id VARCHAR(120) NOT NULL,
  cattle_id VARCHAR(120) NOT NULL,
  device_id VARCHAR(80) NOT NULL,
  barn_id VARCHAR(80) NOT NULL,
  duration_ms INT,
  sample_rate_hz INT,
  received_samples BIGINT,
  status VARCHAR(32),
  raw_data_path VARCHAR(255),
  raw_data_sha256 VARCHAR(128),
  video_reference VARCHAR(1200),
  notes VARCHAR(1200),
  operator_name VARCHAR(80),
  requested_at DATETIME(6),
  started_at DATETIME(6),
  completed_at DATETIME(6),
  UNIQUE KEY uk_motion_capture_session_id (session_id)
);

CREATE TABLE IF NOT EXISTS alert_record (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  barn_id VARCHAR(64) NOT NULL,
  title VARCHAR(128) NOT NULL,
  severity VARCHAR(32) NOT NULL,
  message VARCHAR(800),
  source VARCHAR(64),
  status VARCHAR(32),
  created_at DATETIME(6)
);

CREATE TABLE IF NOT EXISTS control_command_record (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  device_id VARCHAR(64) NOT NULL,
  action VARCHAR(64) NOT NULL,
  enabled BOOLEAN,
  status VARCHAR(32),
  queued_at DATETIME(6)
);

CREATE INDEX idx_environment_barn_time ON environment_reading (barn_id, recorded_at);
CREATE INDEX idx_vision_time ON vision_event (recorded_at);
CREATE INDEX idx_vision_barn_time ON vision_event (barn_id, recorded_at);
CREATE UNIQUE INDEX uk_vision_source_key ON vision_event (source_key);
CREATE INDEX idx_audio_time ON audio_event (recorded_at);
CREATE INDEX idx_health_time ON health_risk (recorded_at);
CREATE INDEX idx_clinical_cattle_time ON clinical_check (cattle_id, recorded_at);
CREATE INDEX idx_motion_capture_cattle_time ON motion_capture_session (cattle_id, requested_at);
CREATE INDEX idx_alert_time ON alert_record (created_at);
CREATE INDEX idx_command_time ON control_command_record (queued_at);
