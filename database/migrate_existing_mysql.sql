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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS environment_reading (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  barn_id VARCHAR(64) NOT NULL,
  device_id VARCHAR(64) NOT NULL,
  temperature DOUBLE,
  humidity DOUBLE,
  ammonia DOUBLE,
  light_lux DOUBLE,
  smoke DOUBLE,
  flame BOOLEAN,
  fan_on BOOLEAN,
  atomizer_on BOOLEAN,
  recorded_at DATETIME(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS vision_event (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  camera_id VARCHAR(64) NOT NULL,
  barn_id VARCHAR(64) NOT NULL,
  event_type VARCHAR(96) NOT NULL,
  severity VARCHAR(32) NOT NULL,
  score DOUBLE,
  target_id VARCHAR(64),
  source_key VARCHAR(190),
  snapshot_path VARCHAR(255),
  evidence VARCHAR(1000),
  recorded_at DATETIME(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audio_event_metadata (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  audio_event_id BIGINT NOT NULL,
  source_key VARCHAR(190),
  cattle_id VARCHAR(120),
  model_version VARCHAR(120),
  model_status VARCHAR(80),
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS motion_capture_session (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  session_id VARCHAR(120) NOT NULL,
  cattle_id VARCHAR(120) NOT NULL,
  device_id VARCHAR(80) NOT NULL,
  barn_id VARCHAR(80) NOT NULL,
  duration_ms INT,
  sample_rate_hz INT,
  received_samples BIGINT,
  expected_samples BIGINT,
  attempted_samples BIGINT,
  dropped_backpressure_samples BIGINT,
  dropped_sensor_samples BIGINT,
  completeness_ratio DOUBLE,
  quality_status VARCHAR(32),
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS motion_capture_clinical_review (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  session_id VARCHAR(120) NOT NULL,
  cattle_id VARCHAR(120) NOT NULL,
  lameness_score INT,
  gait_reviewer VARCHAR(80),
  hoof_examiner VARCHAR(80),
  veterinarian VARCHAR(80),
  hoof_finding VARCHAR(1200),
  clinical_evidence_reference VARCHAR(1200),
  clinically_verified_at DATETIME(6),
  reviewed_at DATETIME(6),
  UNIQUE KEY uk_motion_capture_clinical_review_session (session_id),
  KEY idx_motion_capture_clinical_review_cattle_time (cattle_id, clinically_verified_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_record (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  event_type VARCHAR(80) NOT NULL,
  actor VARCHAR(120) NOT NULL,
  target_type VARCHAR(80) NOT NULL,
  target_id VARCHAR(120) NOT NULL,
  payload_json LONGTEXT,
  recorded_at DATETIME(6) NOT NULL,
  previous_hash VARCHAR(64),
  entry_hash VARCHAR(64) NOT NULL,
  UNIQUE KEY uk_audit_record_entry_hash (entry_hash),
  KEY idx_audit_target_time (target_type, target_id, recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fmd_triage_case (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  health_risk_id BIGINT NOT NULL,
  cattle_id VARCHAR(120) NOT NULL,
  barn_id VARCHAR(80) NOT NULL,
  status VARCHAR(48) NOT NULL,
  opened_by VARCHAR(120) NOT NULL,
  veterinarian VARCHAR(80) NOT NULL,
  evidence_reference VARCHAR(1200) NOT NULL,
  opened_at DATETIME(6),
  closed_at DATETIME(6),
  UNIQUE KEY uk_fmd_triage_case_risk (health_risk_id),
  KEY idx_fmd_triage_cattle_time (cattle_id, opened_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS model_release (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  model_family VARCHAR(32) NOT NULL,
  model_version VARCHAR(120) NOT NULL,
  approval_state VARCHAR(24) NOT NULL,
  dataset_manifest_sha256 VARCHAR(64) NOT NULL,
  model_card_sha256 VARCHAR(64) NOT NULL,
  firmware_sha256 VARCHAR(64) NOT NULL,
  evidence_reference VARCHAR(1200) NOT NULL,
  approved_by VARCHAR(120) NOT NULL,
  approved_at DATETIME(6),
  revoked_by VARCHAR(120),
  revoked_at DATETIME(6),
  validation_summary LONGTEXT,
  notes VARCHAR(1200),
  UNIQUE KEY uk_model_release_family_version (model_family, model_version),
  KEY idx_model_release_state_time (approval_state, approved_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS alert_record (
  id BIGINT PRIMARY KEY AUTO_INCREMENT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS control_command_record (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  device_id VARCHAR(64) NOT NULL,
  action VARCHAR(64) NOT NULL,
  enabled BOOLEAN,
  status VARCHAR(32),
  queued_at DATETIME(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @db = DATABASE();

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='environment_reading' AND COLUMN_NAME='flame') = 0,
  'ALTER TABLE environment_reading ADD COLUMN flame BOOLEAN NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='environment_reading' AND COLUMN_NAME='nh3_raw') = 0,
  'ALTER TABLE environment_reading ADD COLUMN nh3_raw INT NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='environment_reading' AND COLUMN_NAME='smoke_raw') = 0,
  'ALTER TABLE environment_reading ADD COLUMN smoke_raw INT NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='environment_reading' AND COLUMN_NAME='fan_mode') = 0,
  'ALTER TABLE environment_reading ADD COLUMN fan_mode VARCHAR(32) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='environment_reading' AND COLUMN_NAME='atomizer_mode') = 0,
  'ALTER TABLE environment_reading ADD COLUMN atomizer_mode VARCHAR(32) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='environment_reading' AND COLUMN_NAME='alarm_mode') = 0,
  'ALTER TABLE environment_reading ADD COLUMN alarm_mode VARCHAR(32) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='environment_reading' AND COLUMN_NAME='rssi') = 0,
  'ALTER TABLE environment_reading ADD COLUMN rssi INT NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='alert_record' AND COLUMN_NAME='barn_id') = 0,
  'ALTER TABLE alert_record ADD COLUMN barn_id VARCHAR(64) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='alert_record' AND COLUMN_NAME='title') = 0,
  'ALTER TABLE alert_record ADD COLUMN title VARCHAR(128) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='alert_record' AND COLUMN_NAME='severity') = 0,
  'ALTER TABLE alert_record ADD COLUMN severity VARCHAR(32) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='alert_record' AND COLUMN_NAME='message') = 0,
  'ALTER TABLE alert_record ADD COLUMN message VARCHAR(800) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='alert_record' AND COLUMN_NAME='source') = 0,
  'ALTER TABLE alert_record ADD COLUMN source VARCHAR(64) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='alert_record' AND COLUMN_NAME='created_at') = 0,
  'ALTER TABLE alert_record ADD COLUMN created_at DATETIME(6) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='vision_event' AND COLUMN_NAME='source_key') = 0,
  'ALTER TABLE vision_event ADD COLUMN source_key VARCHAR(190) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='vision_event' AND COLUMN_NAME='source_snapshot_path') = 0,
  'ALTER TABLE vision_event ADD COLUMN source_snapshot_path VARCHAR(255) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='vision_event' AND COLUMN_NAME='snapshot_sha256') = 0,
  'ALTER TABLE vision_event ADD COLUMN snapshot_sha256 VARCHAR(64) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='vision_event' AND COLUMN_NAME='snapshot_available') = 0,
  'ALTER TABLE vision_event ADD COLUMN snapshot_available BOOLEAN NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='vision_event' AND COLUMN_NAME='snapshot_content_type') = 0,
  'ALTER TABLE vision_event ADD COLUMN snapshot_content_type VARCHAR(64) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='vision_event' AND COLUMN_NAME='snapshot_bytes') = 0,
  'ALTER TABLE vision_event ADD COLUMN snapshot_bytes BIGINT NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='vision_event' AND COLUMN_NAME='model_name') = 0,
  'ALTER TABLE vision_event ADD COLUMN model_name VARCHAR(120) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='vision_event' AND COLUMN_NAME='model_version') = 0,
  'ALTER TABLE vision_event ADD COLUMN model_version VARCHAR(120) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='vision_event' AND COLUMN_NAME='model_status') = 0,
  'ALTER TABLE vision_event ADD COLUMN model_status VARCHAR(40) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='vision_event' AND COLUMN_NAME='model_approved_by_server') = 0,
  'ALTER TABLE vision_event ADD COLUMN model_approved_by_server BOOLEAN NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='vision_event' AND COLUMN_NAME='screening_eligible') = 0,
  'ALTER TABLE vision_event ADD COLUMN screening_eligible BOOLEAN NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='audio_event_metadata' AND COLUMN_NAME='approved_by_server') = 0,
  'ALTER TABLE audio_event_metadata ADD COLUMN approved_by_server BOOLEAN NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='audio_event_metadata' AND COLUMN_NAME='screening_eligible') = 0,
  'ALTER TABLE audio_event_metadata ADD COLUMN screening_eligible BOOLEAN NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='audio_event_metadata' AND COLUMN_NAME='approval_reason') = 0,
  'ALTER TABLE audio_event_metadata ADD COLUMN approval_reason VARCHAR(80) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='clinical_check' AND COLUMN_NAME='measured_value') = 0,
  'ALTER TABLE clinical_check ADD COLUMN measured_value DOUBLE NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='clinical_check' AND COLUMN_NAME='evidence_type') = 0,
  'ALTER TABLE clinical_check ADD COLUMN evidence_type VARCHAR(96) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='motion_capture_session' AND COLUMN_NAME='expected_samples') = 0,
  'ALTER TABLE motion_capture_session ADD COLUMN expected_samples BIGINT NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='motion_capture_session' AND COLUMN_NAME='attempted_samples') = 0,
  'ALTER TABLE motion_capture_session ADD COLUMN attempted_samples BIGINT NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='motion_capture_session' AND COLUMN_NAME='dropped_backpressure_samples') = 0,
  'ALTER TABLE motion_capture_session ADD COLUMN dropped_backpressure_samples BIGINT NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='motion_capture_session' AND COLUMN_NAME='dropped_sensor_samples') = 0,
  'ALTER TABLE motion_capture_session ADD COLUMN dropped_sensor_samples BIGINT NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='motion_capture_session' AND COLUMN_NAME='completeness_ratio') = 0,
  'ALTER TABLE motion_capture_session ADD COLUMN completeness_ratio DOUBLE NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='motion_capture_session' AND COLUMN_NAME='quality_status') = 0,
  'ALTER TABLE motion_capture_session ADD COLUMN quality_status VARCHAR(32) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='audio_event_review' AND COLUMN_NAME='animal_id') = 0,
  'ALTER TABLE audio_event_review ADD COLUMN animal_id VARCHAR(120) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='audio_event_metadata' AND COLUMN_NAME='clip_sha256') = 0,
  'ALTER TABLE audio_event_metadata ADD COLUMN clip_sha256 VARCHAR(64) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='audio_event_review' AND COLUMN_NAME='recording_session_id') = 0,
  'ALTER TABLE audio_event_review ADD COLUMN recording_session_id VARCHAR(120) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='audio_event_review' AND COLUMN_NAME='veterinarian') = 0,
  'ALTER TABLE audio_event_review ADD COLUMN veterinarian VARCHAR(80) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='audio_event_review' AND COLUMN_NAME='clinical_evidence_reference') = 0,
  'ALTER TABLE audio_event_review ADD COLUMN clinical_evidence_reference VARCHAR(1200) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='audio_event_review' AND COLUMN_NAME='clinically_verified_at') = 0,
  'ALTER TABLE audio_event_review ADD COLUMN clinically_verified_at DATETIME(6) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='model_release' AND COLUMN_NAME='source_lineage_sha256') = 0,
  'ALTER TABLE model_release ADD COLUMN source_lineage_sha256 VARCHAR(64) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='model_release' AND COLUMN_NAME='source_lineage_json') = 0,
  'ALTER TABLE model_release ADD COLUMN source_lineage_json LONGTEXT NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='model_release' AND COLUMN_NAME='revocation_evidence_reference') = 0,
  'ALTER TABLE model_release ADD COLUMN revocation_evidence_reference VARCHAR(1200) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='model_release' AND COLUMN_NAME='revocation_notes') = 0,
  'ALTER TABLE model_release ADD COLUMN revocation_notes VARCHAR(1200) NULL',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='audit_record' AND INDEX_NAME='idx_audit_target_time') = 0,
  'CREATE INDEX idx_audit_target_time ON audit_record (target_type, target_id, recorded_at)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='fmd_triage_case' AND INDEX_NAME='idx_fmd_triage_cattle_time') = 0,
  'CREATE INDEX idx_fmd_triage_cattle_time ON fmd_triage_case (cattle_id, opened_at)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='model_release' AND INDEX_NAME='idx_model_release_state_time') = 0,
  'CREATE INDEX idx_model_release_state_time ON model_release (approval_state, approved_at)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='environment_reading' AND INDEX_NAME='idx_environment_barn_time') = 0,
  'CREATE INDEX idx_environment_barn_time ON environment_reading (barn_id, recorded_at)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='vision_event' AND INDEX_NAME='idx_vision_time') = 0,
  'CREATE INDEX idx_vision_time ON vision_event (recorded_at)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='vision_event' AND INDEX_NAME='idx_vision_barn_time') = 0,
  'CREATE INDEX idx_vision_barn_time ON vision_event (barn_id(64), recorded_at)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='vision_event' AND INDEX_NAME='uk_vision_source_key') = 0,
  'CREATE UNIQUE INDEX uk_vision_source_key ON vision_event (source_key)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='audio_event' AND INDEX_NAME='idx_audio_time') = 0,
  'CREATE INDEX idx_audio_time ON audio_event (recorded_at)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='health_risk' AND INDEX_NAME='idx_health_time') = 0,
  'CREATE INDEX idx_health_time ON health_risk (recorded_at)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='clinical_check' AND INDEX_NAME='idx_clinical_cattle_time') = 0,
  'CREATE INDEX idx_clinical_cattle_time ON clinical_check (cattle_id, recorded_at)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='motion_capture_session' AND INDEX_NAME='idx_motion_capture_cattle_time') = 0,
  'CREATE INDEX idx_motion_capture_cattle_time ON motion_capture_session (cattle_id, requested_at)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='alert_record' AND INDEX_NAME='idx_alert_time') = 0,
  'CREATE INDEX idx_alert_time ON alert_record (created_at)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF((SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='control_command_record' AND INDEX_NAME='idx_command_time') = 0,
  'CREATE INDEX idx_command_time ON control_command_record (queued_at)',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
