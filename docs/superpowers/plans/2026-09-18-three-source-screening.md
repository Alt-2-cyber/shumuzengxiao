# Three-Source Disease Screening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an auditable cattle health screening platform that combines vision, audio, and three-position motion evidence while keeping disease outputs gated as screening or triage until clinical validation exists.

**Architecture:** ESP32-S3 and MaixCam emit timestamped evidence frames; Spring Boot verifies model release status, persists raw evidence and screening observations in MySQL, and produces per-animal risk summaries; Vue displays source freshness, evidence, model status, and clinical next actions. Disease claims remain `_suspect` or `_triage`, never a diagnosis.

**Tech Stack:** ESP32-S3 Arduino/PlatformIO, MaixPy, Spring Boot, JPA/MySQL, Vue 3/Vite, Python/NumPy training utilities, JUnit 5.

**Spec:** `D:\table\shumuzengxiao\疾病识别生产落地\疾病路径与生产发布规范.md` and `D:\table\shumuzengxiao\疾病识别生产落地\疾病实体与证据字典.md`.

## Global Constraints

- Screening outputs are not veterinary diagnoses; FMD is triage-only and requires official laboratory confirmation.
- Audio and lameness models remain disabled until animal-grouped, clinically signed, independently tested releases pass the server approval gate.
- Public datasets may support research baselines but cannot be treated as local veterinary sign-off data.
- Raw evidence hashes, model versions, source lineage, and clinical reviewers must remain auditable.
- ESP32 ADC inputs must stay below 3.3 V; motor loads require an external driver and independent 5 V supply.

---

### Task 1: Preserve Hardware Diagnostic Telemetry

**Files:**
- Modify: `smart-cattle-backend/src/main/java/com/shumuzengxiao/smartcattle/domain/EnvironmentReading.java`
- Modify: `smart-cattle-backend/src/main/java/com/shumuzengxiao/smartcattle/service/TelemetryService.java`
- Modify: `database/init.sql`
- Modify: `database/migrate_existing_mysql.sql`
- Modify: `smart-cattle-frontend/src/views/EnvironmentView.vue`
- Test: `smart-cattle-backend/src/test/java/com/shumuzengxiao/smartcattle/service/TelemetryServiceTest.java`

**Interfaces:**
- Consumes: ESP32 environment fields `nh3Raw`, `smokeRaw`, `rssi`, `fanMode`, and `alarmMode`.
- Produces: persisted nullable diagnostic fields and a visible environment diagnostics table.

- [x] Write a failing persistence test that captures `EnvironmentReading` from a telemetry frame and asserts all raw/control fields.
- [x] Run the focused JUnit test and observe failure because the entity has no diagnostic fields.
- [x] Add nullable JPA fields, MySQL columns, and telemetry mapping.
- [x] Render raw values and control mode in the environment view without replacing the normal user-facing values.
- [x] Run the focused test, full backend tests, MySQL migration, and frontend build.

### Task 2: Strengthen Three-Source Evidence Summary

**Files:**
- Modify: `smart-cattle-backend/src/main/java/com/shumuzengxiao/smartcattle/service/HealthScreeningService.java`
- Modify: `smart-cattle-backend/src/test/java/com/shumuzengxiao/smartcattle/service/HealthScreeningServiceTest.java`
- Modify: `smart-cattle-frontend/src/views/HealthView.vue`

**Interfaces:**
- Consumes: approved vision events, approved audio events, three-position motion frames, surface/core temperature checks, and freshness timestamps.
- Produces: source-specific participation, data quality, evidence counts, and disease-path next actions.

- [x] Add failing tests for stale source exclusion and explicit three-source evidence counts.
- [x] Implement only the smallest aggregation changes needed to keep unapproved audio out of disease fusion.
- [x] Display source freshness and missing-evidence reasons in the health page.
- [x] Run focused and full tests.

### Task 3: Complete Clinically Gated Training and Edge Artifacts

**Files:**
- Modify: `硬件代码/现有硬件演示节点/tools/train_lameness_model.py`
- Modify: `硬件代码/现有硬件演示节点/tools/train_audio_model.py`
- Modify: `硬件代码/MaixCam节点/config.json`
- Create: `疾病识别生产落地/模型发布/` model cards and lineage manifests only from verified data.

**Interfaces:**
- Consumes: animal-grouped IMU sessions, archived audio, reviewed vision snapshots, and clinical lineage APIs.
- Produces: disabled research artifacts until release thresholds pass; approved artifacts carry immutable hashes and model cards.

- [ ] Add tests for insufficient clinical labels and mismatched source hashes.
- [x] Install the public `cow_vocalization`/`non_cattle_audio` baseline as a non-diagnostic feature-only event model; keep server approval disabled.
- [x] Add a strict cross-family disease-data audit that rejects placeholder annotations and missing clinical archives.
- [x] Allow the same audit to gate one model family at a time without weakening that family's clinical thresholds.
- [x] Add a reviewed MaixCam snapshot exporter that re-downloads and verifies image hashes before writing a training manifest.
- [x] Train and register a clearly marked `research_only` lumpy-skin image baseline without edge deployment or disease-fusion approval.
- [x] Record SHA-256 hashes for research artifacts and their external source archives.
- [ ] Run the trainers against current manifests and record the expected disabled result.
- [ ] Do not enable a disease model without real local clinical labels and external validation.

### Task 4: End-to-End Hardware and Production Verification

**Files:**
- Modify: `scripts/audit_system.ps1`
- Modify: `README.md`
- Test: `scripts` audit output, PlatformIO builds, API snapshot, and browser smoke tests.

- [x] Verify COM5/COM9 freshness and three-position sensor coverage.
- [x] Verify COM9 MQ raw ADC diagnostics and fan command acknowledgement.
- [ ] Verify MaixCam model file hash and camera/UART status.
- [x] Run full backend, frontend, firmware, and audit checks; report any external hardware blockers separately.
