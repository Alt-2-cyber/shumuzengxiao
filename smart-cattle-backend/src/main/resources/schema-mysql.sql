CREATE TABLE IF NOT EXISTS cattle_article (
    id VARCHAR(64) NOT NULL PRIMARY KEY,
    kind VARCHAR(16) NOT NULL,
    category VARCHAR(24) NOT NULL,
    title VARCHAR(240) NOT NULL,
    summary VARCHAR(400) NOT NULL,
    content LONGTEXT NOT NULL,
    source_name VARCHAR(120) NOT NULL,
    source_url VARCHAR(600) NOT NULL,
    published_at DATETIME(6) NOT NULL,
    collected_at DATETIME(6) NOT NULL,
    KEY idx_cattle_article_date (published_at)
) CHARACTER SET utf8mb4;

CREATE TABLE IF NOT EXISTS cattle_news_source (
    id VARCHAR(32) NOT NULL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    url VARCHAR(600) NOT NULL,
    status VARCHAR(20) NOT NULL,
    last_attempt_at DATETIME(6),
    last_success_at DATETIME(6),
    article_count INT NOT NULL
) CHARACTER SET utf8mb4;

CREATE TABLE IF NOT EXISTS mobile_consultation (
    id VARCHAR(64) NOT NULL,
    owner_hash VARCHAR(64) NOT NULL,
    category VARCHAR(20) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    subject VARCHAR(80) NOT NULL,
    description VARCHAR(2000) NOT NULL,
    cattle_id VARCHAR(80),
    contact VARCHAR(80),
    status VARCHAR(20) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    KEY idx_mobile_consultation_owner (owner_hash, created_at)
) CHARACTER SET utf8mb4;

CREATE TABLE IF NOT EXISTS audio_event_metadata (
    id BIGINT NOT NULL AUTO_INCREMENT,
    audio_event_id BIGINT NOT NULL,
    source_key VARCHAR(190),
    cattle_id VARCHAR(120),
    model_version VARCHAR(120),
    model_status VARCHAR(80),
    approved_by_server BIT,
    screening_eligible BIT,
    approval_reason VARCHAR(80),
    predicted_label VARCHAR(80),
    clip_available BIT,
    clip_sha256 VARCHAR(64),
    rms DOUBLE,
    dbfs DOUBLE,
    zero_crossing_rate DOUBLE,
    low_band_ratio DOUBLE,
    mid_band_ratio DOUBLE,
    high_band_ratio DOUBLE,
    saturation_ratio DOUBLE,
    features_json LONGTEXT,
    PRIMARY KEY (id),
    UNIQUE KEY uk_audio_event_metadata_event (audio_event_id),
    UNIQUE KEY uk_audio_event_metadata_source (source_key)
);

CREATE TABLE IF NOT EXISTS vision_event_review (
    id BIGINT NOT NULL AUTO_INCREMENT,
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
    PRIMARY KEY (id),
    UNIQUE KEY uk_vision_event_review_event (vision_event_id)
);

CREATE TABLE IF NOT EXISTS audio_event_review (
    id BIGINT NOT NULL AUTO_INCREMENT,
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
    PRIMARY KEY (id),
    UNIQUE KEY uk_audio_event_review_event (audio_event_id)
);

CREATE TABLE IF NOT EXISTS health_screening_observation (
    id BIGINT NOT NULL AUTO_INCREMENT,
    target_id VARCHAR(120) NOT NULL,
    received_at DATETIME(6) NOT NULL,
    motion_available BIT,
    behavior VARCHAR(64),
    behavior_confidence DOUBLE,
    activity DOUBLE,
    surface_temperature DOUBLE,
    lameness_model_deployed BIT,
    lameness_candidate BIT,
    lameness_rejected BIT,
    lameness_score DOUBLE,
    microphone_available BIT,
    vocalization_candidate BIT,
    audio_model_deployed BIT,
    respiratory_candidate BIT,
    abnormal_vocalization_candidate BIT,
    PRIMARY KEY (id),
    KEY idx_health_screen_observation_target_time (target_id, received_at),
    KEY idx_health_screen_observation_time (received_at)
);

CREATE TABLE IF NOT EXISTS clinical_check (
    id BIGINT NOT NULL AUTO_INCREMENT,
    cattle_id VARCHAR(120) NOT NULL,
    check_type VARCHAR(32) NOT NULL,
    verified BIT,
    alert BIT,
    measured_value DOUBLE,
    examiner VARCHAR(80),
    evidence_reference VARCHAR(1200),
    findings VARCHAR(1200),
    evidence_type VARCHAR(96),
    recorded_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    KEY idx_clinical_cattle_time (cattle_id, recorded_at)
);

CREATE TABLE IF NOT EXISTS motion_capture_session (
    id BIGINT NOT NULL AUTO_INCREMENT,
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
    PRIMARY KEY (id),
    UNIQUE KEY uk_motion_capture_session_id (session_id),
    KEY idx_motion_capture_cattle_time (cattle_id, requested_at)
);

CREATE TABLE IF NOT EXISTS motion_capture_clinical_review (
    id BIGINT NOT NULL AUTO_INCREMENT,
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
    PRIMARY KEY (id),
    UNIQUE KEY uk_motion_capture_clinical_review_session (session_id),
    KEY idx_motion_capture_clinical_review_cattle_time (cattle_id, clinically_verified_at)
);

CREATE TABLE IF NOT EXISTS audit_record (
    id BIGINT NOT NULL AUTO_INCREMENT,
    event_type VARCHAR(80) NOT NULL,
    actor VARCHAR(120) NOT NULL,
    target_type VARCHAR(80) NOT NULL,
    target_id VARCHAR(120) NOT NULL,
    payload_json LONGTEXT,
    recorded_at DATETIME(6) NOT NULL,
    previous_hash VARCHAR(64),
    entry_hash VARCHAR(64) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_audit_record_entry_hash (entry_hash),
    KEY idx_audit_target_time (target_type, target_id, recorded_at)
);

CREATE TABLE IF NOT EXISTS fmd_triage_case (
    id BIGINT NOT NULL AUTO_INCREMENT,
    health_risk_id BIGINT NOT NULL,
    cattle_id VARCHAR(120) NOT NULL,
    barn_id VARCHAR(80) NOT NULL,
    status VARCHAR(48) NOT NULL,
    opened_by VARCHAR(120) NOT NULL,
    veterinarian VARCHAR(80) NOT NULL,
    evidence_reference VARCHAR(1200) NOT NULL,
    opened_at DATETIME(6),
    closed_at DATETIME(6),
    PRIMARY KEY (id),
    UNIQUE KEY uk_fmd_triage_case_risk (health_risk_id),
    KEY idx_fmd_triage_cattle_time (cattle_id, opened_at)
);

CREATE TABLE IF NOT EXISTS model_release (
    id BIGINT NOT NULL AUTO_INCREMENT,
    model_family VARCHAR(32) NOT NULL,
    model_version VARCHAR(120) NOT NULL,
    approval_state VARCHAR(24) NOT NULL,
    dataset_manifest_sha256 VARCHAR(64) NOT NULL,
    model_card_sha256 VARCHAR(64) NOT NULL,
    firmware_sha256 VARCHAR(64) NOT NULL,
    source_lineage_sha256 VARCHAR(64) NOT NULL,
    source_lineage_json LONGTEXT,
    evidence_reference VARCHAR(1200) NOT NULL,
    approved_by VARCHAR(120) NOT NULL,
    approved_at DATETIME(6),
    revoked_by VARCHAR(120),
    revoked_at DATETIME(6),
    revocation_evidence_reference VARCHAR(1200),
    revocation_notes VARCHAR(1200),
    validation_summary LONGTEXT,
    notes VARCHAR(1200),
    PRIMARY KEY (id),
    UNIQUE KEY uk_model_release_family_version (model_family, model_version),
    KEY idx_model_release_state_time (approval_state, approved_at)
);
