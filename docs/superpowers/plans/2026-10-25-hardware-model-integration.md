# Cattle Hardware and Disease Screening Implementation Plan

**Goal:** Integrate the connected MaixCAM, COM5 environment node and COM9 wearable node with the platform; train and validate vision, acoustic and three-position motion models and deploy compatible artifacts to the devices.

**Architecture:** Keep environment acquisition and actuation on the environment ESP32-S3, motion and microphone acquisition on the wearable, and vision inference on MaixCAM. The backend stores evidence, model scope and device acknowledgements; disease labels require appropriate clinical data and independent validation.

**Tech Stack:** PlatformIO Arduino ESP32-S3, MaixPy, YOLO, PyTorch, scikit-learn, Spring Boot, Vue and MySQL.

## Current evidence

- COM5 is also assigned to a Bluetooth serial port. Opening the USB interface path directly with DTR asserted reaches the environment firmware; ordinary COM5 resolves to Bluetooth.
- Environment USB device serial is `28:84:85:9D:78:F0`; wearable USB device serial is `14:C1:9F:2D:6A:24` on COM9.
- Environment reports actual SHT31/BH1750 data. Its saved backend address belongs to an earlier network.
- Wearable reports neck and leg ADXL345, microphone and valid B-1 temperature. Back ADXL345 is missing. Full three-position behavior and lameness windows are unavailable.
- MaixCAM USB interfaces enumerate as VID359F PID2120, but the network media link is disconnected. System WiFi and camera applications black out even after independent power cycling. Logs have not been read yet.
- Existing vision research uses unverified image folder labels; the deployed camera artifact is only a COCO cow detector.
- A public calf cough corpus is being independently verified. Public UCD motion data contains farm grouping but clinical outcome labels must be verified before training.

## Tasks and verification

- [x] Read existing architecture, firmware, training gates and actual device data.
- [ ] Restore camera maintenance access over USB; collect last application log, boot log, free disk space, memory and running project processes. Back up relevant files before repair. Stop only the identified project process and verify the system WiFi and camera apps launch afterward.
- [ ] Resolve Windows USB/Bluetooth name collision with an explicit USB interface, preserve logical environment/wearable routing, and verify two distinct device IDs and fresh telemetry at the backend.
- [ ] Verify SPI device IDs and register configuration for all three ADXL345s, add actionable diagnostics and conservative bus recovery, flash the wearable and verify live neck/back/leg windows. If a module remains electrically absent, record its exact pin and register evidence for wiring correction.
- [ ] Prepare a reproducible vision dataset with duplicate grouping and untouched test data. Train a YOLO architecture, export ONNX, convert using the MaixCAM toolchain, compare reference and converted inference, then install with an automatic rollback if loading fails. Report image-level versus animal/farm validation honestly.
- [ ] Acquire and verify bovine cough/respiratory data, train and evaluate an appropriate acoustic event model without relabeling ordinary vocalization as disease, verify 8kHz streaming feature parity and device inference. Disease-level deployment remains incomplete until clinical labels and validation support it.
- [ ] Train a three-position motion model on compatible synchronized clinical data; retain real grouping, sampling rate and sensor positions. A single rear-leg Z-axis dataset cannot be substituted for the installed neck/back/leg XYZ stream.
- [ ] Run end-to-end sensor, audio capture, vision frame/event, command acknowledgement and UI checks. Preserve real raw samples and inference/version reports in `.run/hardware-integration-20261025`.

## Completion evidence

Require logs from all three physical nodes, server data timestamps, sensor health, captured audio and images, group-separated validation results for each enabled model, runtime compatibility and actual inference on the intended hardware. Keep unavailable modalities visible and do not fill them with synthetic readings. The full user objective remains open when any of these requirements lack direct evidence.
