# 牛身佩戴 ESP32 节点

这是牛身/项圈节点固件，和上一级目录的牛舍环境控制箱固件分开。当前按
ESP32-S3 编译，烧录到 `COM9`。它使用三块 SPI ADXL345 运动传感器、INMP441、MAX30102
和安服优 B-1；环境传感器和风扇在上一级目录的 `COM5` 固件中。

## 功能

- 颈部、背部、腿部三块 ADXL345：通过 SPI 输出三位置轴数据、行为特征和跛行筛查特征。
- 行为模型同时输出六类细行为和二分类姿态：`lying`、`standing`。
- INMP441：I2S 声音特征、声音证据采集和已审核模型的候选筛查。
- MAX30102：输出 IR/RED；只有稳定贴合且算法通过质量检查时才输出有效心率/血氧，不生成演示假数据。
- 安服优 B-1：38400 8N1 UART 帧校验后输出表面温度趋势。
- OLED、三色灯、蜂鸣器均为可选本地调试设备。
- WiFi/HTTP：按 10 秒频率上报最新遥测到后端，USB 串口继续保留为调试和高频原始采集链路。

## 当前模型版本

COM9 固件内置两个由公开加速度数据训练的紧凑随机森林：

- `cattle_behavior_model.h`：六类细行为，版本 `posture-behavior-rf-v2`。
- `cattle_posture_model.h`：`lying/standing` 二分类姿态，版本 `posture-binary-rf-v2`。

二分类姿态模型在按连续行为段隔离的测试集上准确率为 0.8691，宏平均 F1 为
0.8555（lying F1=0.8111，standing F1=0.8999）。数据来自公开的单加速度计数据，
固件将它应用于颈部 ADXL345，并用背部倾角和腿部活动量做物理交叉检查；这个指标只代表
姿态筛查性能，不能替代本地牛群验证，也不能直接诊断跛行或疾病。

`lamenessScreen.modelStatus` 当前为 `feature_only`，`diseaseScreen.modelStatus`
当前为 `not_trained`。项目没有把公开行为数据伪装成跛行或疾病诊断数据；要启用
`lameness_suspect`，必须先采集三位置同步 IMU、视频、步态评分、蹄部检查和兽医签核，
再运行 `硬件代码/现有硬件演示节点/tools/verify_lameness_manifest.py` 和
`硬件代码/现有硬件演示节点/tools/train_lameness_model.py` 的发布门槛。

## 接线

先断电，把 ESP32-S3 的 `3V3` 和 `GND` 分配到公共电源轨。所有模块必须共地，
传感器只能使用 3.3V。

| 模块/位置 | 模块引脚 | ESP32-S3 |
|---|---|---|
| 三块 ADXL345 | VCC/GND | 3V3/GND |
| 三块 ADXL345 | SCK | 数字 40 |
| 三块 ADXL345 | SDA/SDI/MOSI | 数字 41 |
| 三块 ADXL345 | SDO/MISO | 数字 42 |
| 颈部 ADXL345 | CS | 数字 38 |
| 背部 ADXL345 | CS | 数字 39 |
| 腿部 ADXL345 | CS | 数字 47 |
| 三块 ADXL345 | INT1/INT2 | 不接 |
| MAX30102 | VCC/GND/SDA/SCL | 3V3/GND/D8/D9 |
| INMP441 六针 | VDD/GND | 3V3/GND |
| INMP441 六针 | SCK/WS/SD | D5/D6/D7 |
| INMP441 六针 | L/R | GND |
| B-1 UART | TX/RX | ESP32 D18/D17（交叉） |
| B-1 UART | VDD/GND | 3V3/GND |
| 绿/黄/红 LED | 信号 | D10/D11/D12，串联限流电阻 |
| 蜂鸣器 | 信号/驱动输入 | GPIO3（板上数字 3） |

ADXL345 的 `CS` 必须分别接数字 `38/39/47`，`CS` 不要接 3V3；SPI 模式下模块的
`SDA` 是 `SDI/MOSI`，`SDO` 是 `MISO`。B-1 是表面温度模块，不要把它接到
I2C 的 D8/D9。三个运动模块的 X/Y/Z 方向要固定，否则后续行为模型和跛行筛查特征
会失去可比性。

## SPI / I2C 故障隔离与诊断

三块 ADXL345 使用 `SPI_MODE3`，`config.h` 中
`ADXL345_SPI_FREQUENCY_HZ` 默认是 **500000 Hz**，适合短杜邦线联调。
`SPI_RECOVERY_INTERVAL_MS` 和 `I2C_RECOVERY_INTERVAL_MS` 各为 5000 ms，分别计时：

- SPI 重试只重新配置健康状态为 false 的位置，不重启共享 SPI 总线，不重新配置正常位置。
- SPI 缺件、错误 ID 或配置回读失败不会触发 `Wire.end()`、MAX30102 初始化或心率/血氧窗口清空。
- I2C 恢复只处理 MAX30102，以及启用环境传感器时的必要 I2C 设备，不重配 SPI 或重置运动窗口。
- 启动时先将三个 CS 全部置高，再依次初始化运动模块；I2C 初始化单独执行。

启动、SPI 重试及运行期首次读取故障时，日志包含 `neck/body/leg` 的
`csPin`、`deviceId`、`DATA_FORMAT`、`BW_RATE`、`POWER_CTL` 和 `configVerified`。
普通遥测始终保留 `motionSpiDiagnostics.neck/body/leg`，缺件位置也有诊断：

| 字段 | 期望值 |
|---|---|
| `csPin` | neck=38、body=39、leg=47 |
| `deviceId` / `expectedDeviceId` | 229，即 `0xE5` |
| `dataFormat` | 11，即 `0x0B`，全分辨率 ±16 g、四线 SPI |
| `bwRate` | 10，即 `0x0A`，100 Hz |
| `powerCtl` | 8，即 `0x08`，测量模式 |
| `healthy` / `configVerified` | ID、配置回读及采样成功后才为 true |

每次 20 Hz 读取都会核验 ID 和配置。错误 ID（包括浮空常见的 `0x00/0xFF`）
或配置不符会使对应健康字段变为 false，不输出该位置的加速度。
任何位置中断都会清空运动投票、已发布运动结果、前一帧和跛行统计，避免把中断前后
的数据拼成连续特征；恢复后的第一帧不与旧帧求差，跛行窗口重新累计完整的 200 点。
正在进行的临床 raw 采集仍以 `sensor_failure` 终止，不会随模块恢复自动续接。
缺件不会被软件重试掩盖，疾病和临床发布门槛不变。

### 无硬件验证

在项目主目录运行：

```powershell
& 'C:\Users\q4984\AppData\Local\Programs\Python\Python311\python.exe' scripts/test_cow_sensor_recovery.py
& 'C:\Users\q4984\AppData\Local\Programs\Python\Python311\python.exe' -m platformio run --project-dir 硬件代码/牛身节点 -e esp32s3_collar
```

host 测试要求 `g++`，从 `src/main.cpp` 提取真实恢复、SPI 读取及窗口函数编译，
仅替换总线与串口边界；验证总线隔离、错误 ID、配置写入失效、限频重试、窗口中断和
临床采集终止。它不能验证杜邦线信号质量或 MAX30102 的实际贴合与算法质量。

本次修改只做 host 测试和编译，USB 设备断开期间不打开串口、不烧录。待重连并另行
安排硬件验证时，需要检查三位置 ID/配置；在已观测 `neck=true/body=false/leg=true`
的缺件条件下确认只出现 body 的 SPI 重试，MAX30102 不因 SPI 重试而周期性重新初始化；
补齐 body 后确认健康状态恢复、特征窗口重新开始，旧 raw 会话维持终止状态。

## 烧录

```powershell
cd D:\table\shumuzengxiao\硬件代码\牛身节点
py -m platformio run -e esp32s3_collar
py -m platformio run -e esp32s3_collar -t upload --upload-port COM9
```

打开串口：

```powershell
py -m platformio device monitor -p COM9 -b 115200
```

## 串口数据与控制

```json
{
  "barnId": "barn_01",
  "cowId": "cow_001",
  "deviceId": "cow_node_01",
  "cattleId": "cow_001",
  "behavior": {"state": "walking", "posture": "standing", "confidence": 0.82},
  "mpu0": true,
  "mpu1": true,
  "adxl345": true,
  "microphone": {"status": "ok"},
  "b1Infrared": {"status": "valid", "surfaceTemperature": 35.8},
  "maxStatus": "no_finger"
}
```

临床步态采集由后端通过串口下发一行 JSON，例如：

```json
{"type":"command","commandId":1,"action":"motion_capture","enabled":true,"sessionId":"session-001","durationMs":60000}
```

普通控制命令使用 `audio_capture` 或 `alarm`。疾病模型头文件当前是禁用的
`feature_only` 占位模型，必须完成真实牛只数据采集和临床签核后才能替换。

### WiFi 配置

固件烧录后，在 COM9 的 115200 串口输入：

```text
set wifi_ssid 你的WiFi
set wifi_pass 你的密码
set backend_url http://电脑在同一WiFi下的IP:8080
show
reboot
```

连接成功后，串口 JSON 会带有 `wifiConnected`、`wifiRssi` 和
`transport=usb_serial+wifi_http`。普通遥测通过 `POST /api/telemetry/ingest` 上报；20 Hz
运动采集仍走 USB 串口，保证原始数据连续性。

## 注意

- MAX30102 在牛身上要贴合少毛、稳定的位置；当前输出只用于趋势筛查，不做医疗判断。
- B-1 是表面温度，不等于核心体温；距离、毛发、角度和环境会明显影响读数。
- 佩戴节点需要外壳固定和防水，避免模块被牛甩动或咬坏。
- 蜂鸣器默认按被动蜂鸣器输出 2.2kHz PWM；如果实物是三针有源蜂鸣器，把
  `BUZZER_ACTIVE_MODULE` 改为 `true` 后重新编译烧录。
# 2026-10-26 颈部时间窗口研究模型

新增 `motion-temporal-20261026-v1`，与原有六类行为及站卧输出并行运行。
输入为颈部 ADXL345 的连续 20Hz 三轴加速度，单位 g；4秒窗口、2秒步长，提取24维时序特征。
类别为采食/放牧、站立反刍、站立休息和移动；`moving` 不表示跛行。
本轮另做站卧重训，固定原测试集后候选为86.06%，低于原86.91%，因此保留原站卧模型。

`include/config.h` 的 `MOTION_TEMPORAL_RESEARCH_ENABLED` 控制研究输出。
数据位于遥测 `behavior.temporalResearch`，包含版本、窗口完整度、标签、得分、四类分数及状态。
采样间隔超出35-75ms、累计时长偏差超过50ms、非有限值或三位置传感器断流都会丢弃未完成窗口并重新积累80个真实样本。
研究结果不会替换原有行为状态，不进入疾病或跛行判定。

公开6牛数据按整牛隔离后，新时序模型在887个测试窗口的 Accuracy 为85.79%、Macro-F1为0.8386；
在同一测试窗口上重训的旧点分类算法为55.47%、0.5986。它不是旧六分类的直接替代，
本地安装方向、采样带宽、更多牛只和牧场仍需验证。训练产物和数据来源见
`牛行为识别数据集/esp32_motion_temporal_20261026` 与
`docs/2026-10-26-motion-temporal-training.md`。

