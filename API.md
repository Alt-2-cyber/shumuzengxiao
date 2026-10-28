# 后端接口清单

默认地址：`http://localhost:8080`

## 总览

- `GET /api/dashboard?barnId=barn_01`
  - 返回最新环境、48 小时趋势、设备、健康风险、告警和统计指标。
  - 不返回原始视觉或声音事件；这些可识别健康证据只向临床角色开放。

## 环境

- `GET /api/environment/latest?barnId=barn_01`
  - 返回指定牛舍最新环境数据。
- `GET /api/environment/trend?barnId=barn_01`
  - 返回最近 48 条环境数据。
- `POST /api/environment`
  - 写入环境数据，适合 ESP32-S3/MQTT 网关转换后调用。

示例：

```json
{
  "barnId": "barn_01",
  "deviceId": "env_01",
  "temperature": 27.4,
  "humidity": 70.2,
  "ammonia": 18.6,
  "lightLux": 230,
  "smoke": 0.1,
  "fanOn": false,
  "atomizerOn": false
}
```

## 设备

- `GET /api/devices?barnId=barn_01`
  - 返回设备清单。
- `POST /api/devices/command`
  - 写入命令记录，并通过当前 ESP32 串口立即下发。
- `GET /api/devices/commands`
  - 返回最近 20 条控制命令历史。

控制命令示例：

```json
{
  "deviceId": "relay_01",
  "action": "fan",
  "enabled": true
}
```

当前可执行动作：

- `fan + enabled=true/false`：风扇强制开/关。
- `fan_auto + enabled=true`：恢复风扇自动联动。
- `alarm + enabled=true/false`：触发/解除红灯与蜂鸣器。
- `motion_capture`：仅由下方的采集会话接口创建，携带会话 ID 与时长；不作为普通控制入口开放。

接口状态包括 `sent`、`failed` 和 `unsupported`。ESP32 执行后通过
WebSocket 推送 `command_ack`，后续遥测的 `control` 字段也会持续报告实际状态。
雾化器和 MaixCam 抓拍尚未建立硬件控制链路，前端保持禁用。

## 事件

- `GET /api/events/vision`（`clinical` / `admin`）
- `POST /api/events/vision`
  - MaixCam 直接 HTTP 上报入口。`targetId` 必须是经耳标、RFID 或人工复核关联的真实牛只编号；
    视觉跟踪编号不可作为 `targetId`。`gait_abnormal_suspect`、`hoof_lesion_suspect`、
    `oral_lesion_suspect` 只形成筛查证据。
- `GET /api/events/audio`（`clinical` / `admin`）
- `GET /api/events/audio/{eventId}/training-lineage`（`clinical` / `admin`）
  - 仅用于疾病声音模型训练和发布门禁。服务器读取并重新计算受保护归档 WAV 的 SHA-256，返回
    归档哈希、当前审核状态、兽医签核、真实耳标、录音会话和临床证据。它不创建或修改声音事件。
- `GET /api/events/health-risks`
- `GET /api/events/alerts`

声音事件只能从 ESP32 串口遥测的 `audio_event` 帧归档；健康风险只能由后端的
`HealthRiskLedgerService` 在证据门禁通过后写入。生产环境不提供通用 REST 接口来伪造声音事件
或疾病风险记录。

声音筛查标签包括 `cough_suspect`、`wheeze_suspect` 和
`abnormal_vocalization_suspect`。最后一项只表示异常发声候选，不能作为疼痛、应激或疾病确诊；
三项标签均必须经过服务端批准的模型版本和真实牛只编号才能进入个体健康融合。

声音疾病模型必须使用 `tools/train_audio_model.py --release --clinical-api ... --clinical-api-key ...`。
发布训练与 `tools/register_model_release.py --family audio` 都会逐条调用上述血缘接口；服务器登记事务
会再根据源事件清单重建指纹，重新核对 WAV 哈希、审核标签和完整临床签核。公开数据只能用于禁用的声学基线，不能登记为疾病模型。

## 临床复测与步态采集

- `POST /api/clinical-checks`
  - 保存人工完成的 `core_temperature`、`gait_exam`、`lesion_exam`，与设备遥测分开持久化。
  - `core_temperature` 必须给出 30-45 C 的实测值和检查人员；B-1 体表温度不能写入此接口。
- `GET /api/clinical-checks?cattleId=cow_001`
- `POST /api/motion-captures`
  - 下发限时三位置 IMU 原始采集，ESP32 以 20 Hz 保存颈部 MPU、背部 ADXL345、腿部 MPU
    同步 NDJSON。请求必须提供真实牛只、节点、操作人员和同步视频引用。
- `GET /api/motion-captures?cattleId=cow_001`
- `GET /api/motion-captures/{sessionId}/raw`
- `PUT /api/motion-captures/{sessionId}/clinical-review`（`clinical` / `admin`）
  - 对一个已验收、哈希正确且带同步视频的会话保存最终步态评分、蹄部检查人、兽医、蹄部发现和临床证据编号。
    请求必须显式确认临床签核；每次写入都进入审计链。
- `GET /api/motion-captures/{sessionId}/training-lineage`（`clinical` / `admin`）
  - 仅用于跛行筛查模型的训练与登记发布门禁。服务器在每次请求时重新计算原始 NDJSON 的
    SHA-256，并重新检查连续 20 Hz 索引、完整度、丢样、会话状态、真实耳标、视频引用和会话级临床签核。
    它不创建或修改采集会话。

采集结束后后端保存 SHA-256。只有经标准步态评分、蹄部检查和独立动物分组验证的数据才允许训练
`lameness_suspect` 筛查模型。

跛行疾病模型必须使用 `tools/train_lameness_model.py --release --clinical-api ... --clinical-api-key ...`。
训练与 `tools/register_model_release.py --family lameness` 都会逐条调用上述血缘接口；服务器登记事务会
根据源会话清单再次重建指纹，重新核对原始 NDJSON 哈希、会话/耳标、采样完整性、视频引用、步态评分员、蹄部检查人、检查结果和临床证据；任何一项变更都会拒绝发布。

## 生产访问角色

启用 `API_KEY_ENABLED=true` 后，所有 `/api/**` 与 `/ws/telemetry` 均要求角色密钥。

- `viewer`：总览、环境、健康风险和设备状态等运行态势读取，以及实时 WebSocket 订阅；不读取原始视觉/音频事件。
- `ingest`：仅允许 MaixCam 写入 `POST /api/events/vision`。
- `operator`：包含 `viewer`，并可下发 `POST /api/devices/command`。
- `clinical`：包含 `operator`，可读取和写入临床记录、声音复核、音频原件、IMU 原始数据、FMD 人工交接和审计记录。
- `admin`：包含所有角色权限，并是唯一可访问 `POST/GET /api/model-releases` 的角色。

`API_KEY_VIEWER`、`API_KEY_INGEST`、`API_KEY_OPERATOR`、`API_KEY_CLINICAL`、`API_KEY_ADMIN`
必须是不同的部署机密。`API_KEY` 仅保留为旧版管理员密钥兼容项。浏览器 WebSocket 由于平台限制通过
`?apiKey=` 携带密钥；仅在受 TLS 保护的内网或身份代理后使用，互联网部署应由反向代理处理用户身份。

## 模型

- `GET /api/models`
  - 返回视觉、声音、行为识别和多模态融合模型的版本、任务和指标。

## 模型发布登记

- `GET /api/model-releases`（仅 `admin`）
- `POST /api/model-releases`（仅 `admin`）
  - 仅登记已经通过训练门禁的声音或三位置跛行筛查模型；不改变环境变量白名单。
  - 除数据清单、模型卡、固件 SHA-256 和验证摘要外，请求必须携带训练元数据中的
    `sourceLineageSha256` 以及 `sourceLineage`。声音条目的 `sourceId` 是音频事件 ID；
    跛行条目的 `sourceId` 是 IMU 会话 ID，并带原训练清单的 `recordingId`。
  - 后端在提交事务内再次读取每一条受保护档案：音频会重新校验 WAV SHA-256、审核状态和兽医签核；
    跛行会重新校验 NDJSON SHA-256、20 Hz 完整性、丢样、视频和步态/蹄部签核。重建的规范指纹
    与 `sourceLineageSha256` 不一致即返回 `409`，不会创建批准记录。
  - 同一 `modelFamily + modelVersion` 的批准记录不可覆盖。完全相同的重试为幂等；任何哈希、血缘、
    验证摘要或批准证据不同都必须使用新版本号。
- `POST /api/model-releases/{releaseId}/revoke`（仅 `admin`）
  - 撤回记录独立保存撤回人、撤回时间、证据编号和备注，不覆盖原始批准证据；已撤回版本不能再次批准。

建议仅通过 `硬件代码/现有硬件演示节点/tools/register_model_release.py --confirm-production-release`
登记版本。该工具在本地复核后会把同一批源档案交给后端再次复核。

## ESP32 实时遥测

- `POST /api/telemetry/ingest`
  - LAN/WiFi 设备上报一帧 JSON 遥测；请求会复用 USB 串口的校验、健康筛查和 WebSocket 推送流程。
  - 默认本地调试模式无需密钥；生产启用 API key 后使用 `ingest` 角色密钥。
- `GET /api/telemetry/snapshot?limit=60`
  - 返回串口连接状态、最新一帧和最近遥测历史。
- `WS /ws/telemetry`
  - 推送 `telemetry` 数据帧和 `status` 串口状态事件。

后端默认同时读取 `COM5`（牛身节点）和 `COM9`（环境节点），波特率均为 `115200`。
串口不存在时对应读线程会等待并自动重连。旧版单串口部署可通过环境变量覆盖：

```powershell
$env:ESP32_SERIAL_PORTS='COM19'
$env:ESP32_SERIAL_BAUD='115200'
$env:ESP32_SERIAL_ENABLED='true'
```
