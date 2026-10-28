# MaixCam 边缘视觉节点

这是 MaixCam 端代码，负责摄像头采集、YOLO 推理、事件判断、截图留证、MQTT 上报，以及通过 UART 通知 ESP32 本地报警。

## 2026-10-28 系统菜单应用

摄像头已安装前台应用 **杨文昊-数牧增效**，应用 ID 为 `shumu_ywh`，
安装位置为 `/maixapp/apps/shumu_ywh`。源程序位于本目录 `launcher_app`。

- 当前版本1.1.0默认进入“牛只定位后外观研究”：先检测 `cow`，再裁剪牛只区域，
  使用2026-10-28继续训练的 `cattle_research.mud` / `cattle_research_int8.cvimodel`。
- 无牛时不调用分类器；目标太小、画质或置信度不足时拒识。不会沿用上一帧结果。
- 右上角“切换”：进入仅牛只检测模式，显示牛只框和数量。
- 外观分类的来源标签为 `foot-and-mouth`、`healthy`、`lumpy`；界面显示
  “研究 / 非诊断”和样本类名称，不能据此确诊或触发疾病告警。
- 左上角返回按钮退出到系统菜单；切换/退出会释放相机和模型资源。

本次前台应用使用独立配置，提供摄像头本地预览与推理。网络上报配置默认为空；
原有 `/root/cattle-vision` 节点及其配置保留。不要同时启动多个占用相机的程序。

在本机重新安装时，使用 `scripts/install_maixcam_launcher.py --host 设备IP --output 新的证据目录`。
密码通过交互输入或临时环境变量 `SHUMU_MAIX_PASSWORD` 提供，不写入源码。
安装器核对原卡 UUID、模型哈希和全部上传文件，备份菜单注册表后注册应用。
当前升级前的设备安装备份位于 `/root/shumu-ywh-install-backup-20261028-131326`。

两种模式均已由系统启动器实际运行并完成三帧摄像头推理，截图和 JSON 记录位于
`D:\table\shumuzengxiao\.run\maixcam-app-install-20261028`。
它们证明模型可在设备上执行，不代表疾病识别的临床性能。

当前升级的实机证据位于 `.run/maixcam-cascade-deploy-20261028` 和
`.run/cascade-device-qa-20261028`，详细数据、训练和量化成绩见
`docs/2026-10-28-cow-cascade-training-deployment.md`。
重新安装新版时，为安装器增加 `--research-model-dir vision-training-data/maixcam-cascade-20261028`。

## 文件

- `main.py`：MaixCam 主程序。
- `config.json`：设备编号、MQTT、模型路径、UART 引脚和阈值配置。
- `models/cattle_yolov8.mud`：MaixCAM 模型描述文件。
- `models/cattle_yolov8.cvimodel`：对应的量化推理模型。

## 放到 MaixCam

把整个 `MaixCam节点` 目录复制到 MaixCam，例如：

```text
/root/MaixCam节点/main.py
/root/MaixCam节点/config.json
```

MaixCAM 通过 USB 虚拟网卡连接电脑，不会出现在 Windows 的 COM 口列表中。当前设备可用地址为
`10.139.183.1`；Windows 主机端通常会看到 `UsbNcm Host Device` 或 RNDIS 网卡。出厂系统的
SSH 默认账号为 `root`、密码为 `root`，生产部署后应立即修改默认密码。也可以在 MaixVision
中手动连接该 IP。

模型文件放到 `config.json` 里的路径。当前项目部署的是设备上可直接运行的
`cattle_yolov8.mud`，它基于 MaixCAM 自带的量化 YOLOv8n COCO 模型，包含 `cow`
类别，能先完成牛只目标检测和画框：

```text
/root/models/cattle_yolov8.mud
```

模型部署时必须同时存在以下两个文件，`.mud` 中的 `model` 字段会引用同目录下的
`.cvimodel`：

```text
/root/models/cattle_yolov8.mud
/root/models/cattle_yolov8.cvimodel
```

本项目目录的 `models` 子目录已保存这两个文件的部署副本。复制方式：

```sh
mkdir -p /root/models
cp models/cattle_yolov8.mud models/cattle_yolov8.cvimodel /root/models/
```

这个模型只识别“画面中有牛及其位置”，不等于已经训练了站立、卧倒、跛行或具体疾病。
这些行为/疾病类别需要用现场摄像头采集并标注后重新训练、验证，再转换为 MaixCAM 的
`.mud` 模型；程序不会把普通 `cow` 检测结果伪装成疾病诊断。

当前配置使用 `320x240` 采集分辨率，适配这台设备的摄像头缓冲区；YOLOv8 模型内部仍按
自身的 `320x224` 输入推理。状态上报中的 `cattleDetected` 和 `cattleScores` 表示当前
画面中检测到的 `cow` 数量和置信度。

`display_enabled` 默认关闭。MaixCam 设备上的显示通道会占用视频缓冲区，在模型推理和摄像头
同时运行时可能触发 `No buffer space available`；需要本地预览时再改为 `true`，生产采集优先保持关闭。
如果设备系统服务暂时占用摄像头，节点会按 `camera_retry_seconds` 自动重试并在日志中保留原因。

### 视觉模型训练数据采集

生产训练不能直接使用当前 COCO 牛只检测模型的输出作为疾病标签。每条截图应与平台事件绑定，
保留 `eventId`、`recordingId`、`cameraId`、`barnId`、真实耳标、时间和服务器归档哈希；由兽医
复核为 `normal`、`gait_abnormal_suspect`、`hoof_lesion_suspect`、`oral_lesion_suspect` 或
`nasal_discharge_suspect`。风险标签需填写临床证据编号。训练脚本和字段样例位于：

```text
D:\table\shumuzengxiao\疾病识别生产落地\数据采集\vision_annotations.example.jsonl
D:\table\shumuzengxiao\硬件代码\现有硬件演示节点\tools\train_vision_model.py
```

样例中的路径和哈希是占位值，不能直接训练。训练得到的 NumPy 基线不能改名为 `.mud`；需要
独立训练、验证并转换后的 MaixCAM `.mud`，通过发布门禁后才可替换设备模型。视觉节点不能
确诊口蹄疫，相关结果只能进入兽医分诊。

事件和状态包会同时上报 `modelName`、`modelVersion`、`modelStatus` 和 `modelScope`。
事件通过 HTTP 上报时还会携带受 `snapshot_upload_max_bytes`（默认 900 KB）限制的 JPEG Base64，后端会写入
`vision-snapshots` 并重新计算 SHA-256；MQTT 只发送元数据，避免图片撑大消息。这样网站视觉证据页
只有服务器归档成功后才显示真实缩略图。
当前版本是 `cattle-yolov8-coco-v1`，范围为 `cow_detection_only`；如果模型文件加载失败，
运行时状态会自动改为 `unavailable`，避免把配置中的“已部署”误当成实际加载成功。

如果替换为其他 YOLOv8 模型，把配置改成：

```json
"model_type": "yolov8",
"model_path": "/root/models/cattle_yolov8.mud"
```

Windows 主机可使用项目脚本部署当前节点（SSH 会交互询问 MaixCam 密码）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File D:\table\shumuzengxiao\scripts\deploy_maixcam.ps1
```

该脚本只部署当前已验证的牛只检测模型；它不会把普通 `cow` 检测升级为疾病、跛行或口蹄疫模型。

2026-10-26 更新：部署脚本固定使用本目录，不再从项目副本中模糊查找源程序。
上传会保留设备上已有的访问凭证并备份配置，只管理该项目自己的进程。
默认安装后不启动后台摄像头；检查系统相机已退出后可加 `-StartNode`。
程序响应 `app.need_exit()`，退出或推理异常时释放相机、显示和串口。
脚本不再修改系统启动项或批量终止 Python / MaixVision 服务。

```powershell
./scripts/deploy_maixcam.ps1 -HostName 设备实际IP -BackendUrl http://电脑实际IP:8080 -StartNode
```

USB 默认地址可能是 `10.131.167.1`，历史配置中的 `10.139.183.1` 不应作为设备当前可达的证明。
若系统相机和 WiFi 应用都黑屏，先读取 `/maixapp/tmp/last_run.log`、磁盘空间及进程信息再修复。

## 2026-10-26 图像分类研究模型

节点现在支持 `nn.Classifier`。分类模型与 YOLO 画框检测器是不同接口，不能把分类 `.mud`
配置为 `yolov8` 检测器。使用已转换的分类候选时，配置以下字段，并保留原有网络配置：

```json
{
  "model_type": "classifier",
  "model_path": "/root/models/cattle_research.mud",
  "model_name": "cattle-appearance-research",
  "model_version": "与转换记录对应的实际版本",
  "classifier_image_size": 224,
  "classifier_softmax": true,
  "classifier_interval_seconds": 1,
  "model_status": "research_only",
  "model_scope": "public_source_appearance_research"
}
```

`classifier_softmax=true` 对应本项目转换时移除了 Softmax 的 logits 输出；如果另外转换的模型
已经输出概率，应设为 `false`。`.mud` 与它引用的 `.cvimodel` 必须位于同一目录。

程序以双线性插值缩放短边，再居中裁剪为 224x224；使用单缓冲推理，使结果对应当前截图。
分类结果不会生成检测框或牛只数量，也不进入站卧、病灶和疾病告警。状态中的
`appearanceResearch` 保留来源标签及得分，HTTP 以 `snapshot_event` 和研究说明归档。
无论配置如何填写，当前公开目录分类候选均上报 `research_only`。

Windows 端先准备训练集校准图片，再在 WSL 的转换环境中转换。两个脚本现在支持新输出目录，
会拒绝覆盖已完成的输入或转换记录；校准图片逐文件校验，只允许训练分区。
设备系统应用黑屏和 USB 网络不通仍需单独修复，主机转换成功不等于设备已经运行。
独立 USB 转 TTL 使用 UART0：模块 RXD 接 A16(TX)，TXD 接 A17(RX)，共地，3.3V 信号，VCC 不接。
COM5 是环境板、COM9 是牛身板；两者均不自动作为 MaixCAM 控制台。

## 接 ESP32 串口

默认配置：

| MaixCam | ESP32 环境控制箱 |
|---|---|
| TX（按 MaixCam 实物 TX 丝印） | ESP32-S3 环境节点 RX GPIO18/D18 |
| RX（按 MaixCam 实物 RX 丝印） | ESP32-S3 环境节点 TX GPIO17/D17 |
| GND | GND |

注意：MaixCam 和 ESP32 必须共地。两块板建议独立供电，MaixCam 用稳定 5V/2A。

这块 MaixCAM 的 UART1 映射为 `A18=UART1_RX`、`A19=UART1_TX`，当前 `config.json` 已按此配置：

```json
"uart_tx_pin": "A19",
"uart_rx_pin": "A18",
"uart_device": "/dev/ttyS1"
```

## MQTT Topic

```text
cattle/{barn_id}/{camera_id}/vision/status
cattle/{barn_id}/{camera_id}/vision/event
```

事件示例：

```json
{
  "cameraId": "cam_01",
  "barnId": "barn_01",
  "ts": 1715500800,
  "eventType": "fall_suspect",
  "level": "warning",
  "score": 0.86,
  "bbox": [120, 80, 260, 210],
  "durationSec": 180,
  "snapshotPath": "/root/snapshots/fall_suspect_20260708_190000.jpg"
}
```

## 和 ESP32 的 UART JSON

MaixCam 发给 ESP32：

```json
{"type":"vision_event","cameraId":"cam_01","event":"fall_suspect","level":"warning","score":0.86,"durationSec":180}
```

ESP32 发给 MaixCam：

```json
{"type":"capture_request","reason":"nh3_high","durationMs":3000}
```

## 配置 WiFi/MQTT

MaixCam 自己需要先连上 WiFi。然后改 `config.json`：

```json
"mqtt_host": "192.168.1.10",
"mqtt_port": 1883
```

## 直接上报后端

后端当前提供 HTTP 事件入口，不依赖 MQTT 订阅器。请将 `backend_url` 改为当前电脑在局域网中的实际地址；地址变化后同步修改 `config.json`。再填写
**真实耳标/管理编号**：

```json
"backend_url": "http://192.168.1.20:8080",
"cattle_id": "cow_001",
"source_boot_id": "cam01-20260719"
```

`cattle_id` 为空时，事件仍可保存为摄像头事件，但不会参与某一头牛的跛行、BRD
或口蹄疫风险筛查。不得把视觉追踪 ID 当成 `cattle_id`。应由固定栏位、RFID/耳标
或人工复核把画面对象关联到真实牛只。

生产部署若启用了后端 `API_KEY_ENABLED=true`，在 MaixCam 的 `config.json` 写入**仅用于
视觉事件上报的** `API_KEY_INGEST`，程序会发送 `Authorization: Bearer ...`。它只能调用
`POST /api/events/vision`，不能用于临床复核、设备控制或模型发布。不要把真实密钥提交到项目
或截图中：

```json
"backend_api_key": "通过设备安全配置注入的密钥"
```

## 运行

在 MaixCam 上执行：

```sh
cd /root/MaixCam节点
python main.py
```

如果没有模型，程序会提示 `Model missing`，仍会启动摄像头、显示画面、响应 ESP32 抓拍请求，但不会产生 YOLO 检测事件。

## 类别名称

代码默认识别这些模型类别名：

```json
"stand": ["cattle_stand", "stand", "cow_stand"],
"lie": ["cattle_lie", "lie", "cow_lie"],
"person": ["person"]
```

如果你训练的类别名不同，改 `config.json` 的 `classes` 即可。

### 跛行、蹄病和口蹄疫的边界

可在经过本地临床验证的模型中配置以下可选类别：

```json
"gait_abnormal": ["gait_abnormal"],
"hoof_lesion": ["hoof_lesion"],
"oral_lesion": ["oral_lesion"],
"nasal_discharge": ["nasal_discharge"]
```

它们只会上报 `gait_abnormal_suspect`、`hoof_lesion_suspect`、
`oral_lesion_suspect`、`nasal_discharge_suspect` 作为人工复核证据。没有部署和验证该类模型时，
应保持这些列表为空。鼻部分泌物事件可作为 BRD 风险的视觉独立证据，但不能单独诊断 BRD。
视觉节点不能确诊跛行、蹄病或口蹄疫；口蹄疫疑似必须由兽医和法定实验室流程处理。
