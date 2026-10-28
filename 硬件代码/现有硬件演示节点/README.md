# 现有硬件综合演示节点

适配普通 ESP32 DevKit（ESP32-D0WD-V3）。这块板当前由后端连接为 `COM19`（早期曾为 `COM13`/`COM17`/`COM18`）；若端口号变化，以设备管理器或 `pio device list` 的结果为准。

## 牛只标识

在每块绑在牛身上的节点的 `include/config.h` 中设置真实耳标或管理编号：

```cpp
#define CATTLE_ID "cow_001"
```

该字段会随每帧遥测上传，健康筛查按 `cattleId` 分别建立 7 天内的个体基线。未改动时会回退到 `DEVICE_ID`，适合台架联调但不适合多头牛同时使用。

## 照片中的新增硬件

- 1.3 寸 I2C OLED（常见 SH1106，地址 `0x3C`）
- ADXL345 三轴加速度模块（地址 `0x53`）
- 两块 MPU-9250/6500 六轴/九轴模块（地址 `0x68` 和 `0x69`）
- GY-302 / BH1750 光照模块（地址 `0x23`）
- SHT3X-DIS / SHT31 温湿度模块（地址 `0x44`）
- HW-040 / KY-040 旋转编码器
- 带驱动板的小风扇模块
- 六针 INMP441 I2S 数字麦克风
- 安服优 B-1 UART/IIC 红外测温模块

照片第三、第四张是同一个旋转编码器的正反面，不是 RGB 灯。

## 电源总线

先在面包板建立两组电源：

```text
ESP32 3V3 -> 面包板 3.3V 正极轨
ESP32 GND -> 面包板公共 GND 负极轨
ESP32 VIN/5V -> 面包板 5V 正极轨（只供风扇、MQ 等 5V 模块）
```

所有设备必须共地。I2C 传感器只使用 `3.3V`，不要接 `5V`。

## 三个牛身运动传感器接法（按板上 Dxx 丝印）

这块 ESP32 板上的 `D21` 就是程序中的 `GPIO21`，`D22` 就是 `GPIO22`。三个运动传感器并联共用这两根线：

```text
ESP32 D21 -> 两块 MPU 的 SDA + ADXL345 的 SDA
ESP32 D22 -> 两块 MPU 的 SCL + ADXL345 的 SCL
ESP32 3V3 -> 三块模块的 VCC
ESP32 GND -> 三块模块的 GND
```

建议固定位置：

| 身体位置 | 模块 | 地址 | 地址脚接法 |
|---|---|---:|---|
| 颈部/项圈 | 第 1 块 MPU-9250/6500 | `0x68` | `NCS -> 3V3`，`AD0 -> GND` |
| 躯干/背部 | ADXL345 | `0x53` | `CS -> 3V3`，`SDO -> GND` |
| 前腿或后腿 | 第 2 块 MPU-9250/6500 | `0x69` | `NCS -> 3V3`，`AD0 -> 3V3` |

两块 MPU 的 `EDA`、`ECL`、`INT`、`FSYNC` 不接；ADXL345 的 `INT1`、`INT2` 不接。三块板的 X/Y/Z 朝向要固定并记录，不能每次绑缚时随意旋转。

桌面样机可以用面包板并联。实际绑牛时，ESP32 建议固定在背部中央，I2C 线尽量短于 30-50 cm，并使用柔软线束、应力释放和绝缘外壳；若必须跨颈部到腿部拉长线，应改用多个本地节点或 I2C 差分延长方案。

## 其他 I2C 模块

OLED、SHT31、BH1750、MAX30102 也可以共用 `D21/D22`：

| 模块 | 额外接线 | 预期地址 |
|---|---|---:|
| OLED | 只接 VCC、GND、SCL、SDA | `0x3C` |
| SHT3X-DIS | 只接 VCC、GND、SCL、SDA | `0x44` |
| GY-302/BH1750 | `ADDR -> GND` 为 `0x23`，接 3V3 为 `0x5C` | `0x23`/`0x5C` |
| MAX30102 | INT 不接 | `0x57` |

两块 MPU 的 `AD0` 必须一低一高，否则都在 `0x68`，ESP32 无法区分。

GY-302 建议固定为默认地址接法：

```text
GY-302 VCC  -> ESP32 3V3
GY-302 GND  -> ESP32 GND
GY-302 SDA  -> ESP32 D21
GY-302 SCL  -> ESP32 D22
GY-302 ADDR -> ESP32 GND
```

固件会自动兼容 `0x23` 和 `0x5C`。若启动扫描中两个地址都没有出现，说明不是地址配置问题，应检查模块供电、SDA/SCL 是否接反或杜邦线是否断路。

## 六针 INMP441 麦克风

照片中的圆形模块共有六个引脚：`SD`、`VDD`、`GND`、`L/R`、`WS`、`SCK`。六个引脚按下表处理：

| INMP441 | ESP32 | 作用 |
|---|---:|---|
| `VDD` | `3V3` | 只能使用 3.3V |
| `GND` | `GND` | 公共地 |
| `SCK` | `D5` | I2S 位时钟/BCLK |
| `WS` | `D16` | I2S 左右声道时钟/LRCL |
| `SD` | `D17` | 麦克风数据输出到 ESP32 |
| `L/R` | `GND` | 选择左声道，与固件设置一致 |

不要把 `SD` 当作模拟 AO，也不要把模块接到 5V。固件以 16 kHz 采样，并在启动后同时检查两个 I2S 数据槽位；`microphone.channel` 会显示选中的 `slot0` 或 `slot1`。每 2 秒上报 `rms`、`peak`、`dbfs`、饱和率、过零率和低/中/高频能量比例。

- `status=calibrating`：刚启动，正在判断 I2S 数据槽位；等待约 1 秒。
- `status=ok`：声音链路可用于采样和特征筛查。
- `status=signal_invalid`：数据线、`L/R`、SCK、WS、供电或公共地存在问题。当前实机旧固件的 `rawMin=-8388608`、`rawMax=0` 就属于这一类，不能拿来做声音分析。

网站“声音筛查”页可以发送一次 1 秒采样请求；ESP32 以 8 kHz PCM 通过串口上传，后端保存为 WAV，并可在网页试听和标注。当前固件可运行公开数据的 `cow_vocalization`/`non_cattle_audio` 事件基线，但该基线只用于声音证据采集，不进入疾病风险。咳嗽、喘鸣和异常鸣叫疾病标签仍必须使用真实牛只录音、兽医签核和独立验证后，再运行 `tools/train_audio_model.py` 生成新的发布头文件。任何声音候选都不能作为疾病确诊。

## 临床复核与三位置跛行采集

网页 `http://localhost:5173/clinical` 可保存接触式核心体温、步态评分与病灶检查，并下发
`motion_capture` 会话。会话期间 ESP32 只通过串口输出限时 20 Hz 原始 NDJSON：颈部 MPU、背部
ADXL345、腿部 MPU 的三轴数据（MPU 同时含陀螺仪）。后端按会话写入 `motion-captures/`，结束时
计算 SHA-256，并要求关联真实 `cattleId`、同步侧视视频和操作人员。

固件内置的 `cattle_lameness_model.h` 初始为 `kEnabled=false`。不要使用公开颈部行为数据集训练
跛行模型。先在临床页面的“步态与蹄部签核”中选择已验收会话，由评分员、蹄部检查人和兽医完成
同一会话的签核；再把该平台签核中的字段写入完整 `lameness_annotations.csv`，最后执行：

```powershell
cd D:\table\shumuzengxiao\硬件代码\现有硬件演示节点
$python = 'C:\Users\q4984\AppData\Local\Programs\Python\Python311\python.exe'

& $python tools\verify_lameness_manifest.py `
  --annotations D:\table\shumuzengxiao\疾病识别生产落地\数据采集\lameness_annotations.csv `
  --api http://localhost:8080 `
  --api-key $env:CLINICAL_API_KEY `
  --output D:\table\shumuzengxiao\疾病识别生产落地\数据采集\lameness_manifest.json

& $python tools\train_lameness_model.py `
  --manifest D:\table\shumuzengxiao\疾病识别生产落地\数据采集\lameness_manifest.json `
  --data-root D:\table\shumuzengxiao\motion-captures `
  --output include\cattle_lameness_model.h `
  --metadata tools\lameness_model_metadata.json `
  --model-card tools\lameness_model_card.md `
  --release `
  --clinical-api http://localhost:8080 `
  --clinical-api-key $env:CLINICAL_API_KEY
```

训练器要求动物分组的训练/验证/外部测试，并检查灵敏度、特异度、PPV、拒识率和每头牛每天误报量。
`--release` 与模型登记工具会逐条调用受保护的 `GET /api/motion-captures/{sessionId}/training-lineage`；
服务器在登记事务中还会根据同一份源会话清单第三次重新核对归档哈希、会话/耳标、20 Hz 完整性、视频引用、步态评分员、蹄部检查与临床证据。
未满足门禁时会写出 `kEnabled=false` 的头文件。即使已部署，端侧候选仍需 MaixCam 的新鲜步态/蹄部
证据才能升级为 `lameness_suspect`，并须人工步态评分和蹄部检查确认。

## 安服优 B-1 UART/IIC 红外测温

这块 B-1 的接口丝印是 `TX RX VDD GND`。模块在 UART 与 IIC 模式下复用同一组信号线，不接主传感器总线的 `D21/D22`。UART 必须交叉连接：

| B-1 丝印 | ESP32 | 说明 |
|---|---:|---|
| `TX` | `D23` | UART 时为 B-1 TX；IIC 时为 SDA |
| `RX` | `D19` | UART 时为 B-1 RX；IIC 时为 SCL |
| `VDD` | `3V3` | 官方明确要求 3.3V，禁止接 5V |
| `GND` | `GND` | 公共地 |

插头线色不符合常见红正黑负习惯，**不得按线色接电源**，必须逐根按 PCB 丝印确认。接线和改线都应先断电。官方 V2.1 规格书明确写明 B-1 只能接 `3.3V`，不能接 `5V`。

已根据 AFUIOT B-1 V2.1 协议和 STM32 主机示例确认：串口为 `38400 8N1`。模块上电默认 UART，但 5 秒内没有收到 UART 命令会自动切换成 IIC。固件启动串口后立即发送测温帧 `AA A5 03 01 04 55`，1.2 秒后设置体温模式 `AA A5 04 02 02 08 55`，之后每秒测温。

返回帧必须通过包头、包长、累加校验和及 `0x55` 包尾验证后才会解析。程序不会发送通信方式配置命令，也不会在运行中自动切换 IIC，避免反复改写模块 NVM 或在同次上电中造成协议状态不确定。

`C51_host_test.zip` 是主机侧 IIC 测试工程，其实际链接文件不包含压缩包里残留的 `protocol` 和测温算法对象，不能把这些列表当作 B-1 生产固件。程序会记录模块输出的 `dbg>` 启动文本但继续测温；禁止发送低温或高温标定命令。

B-1 测到的是目标表面温度趋势，不等同于牛的核心体温。毛发、距离、角度、风速和环境温度都会影响结果，安装后需要用可靠温度计做同位置标定。

## 风扇模块

照片左侧风扇已经接在驱动板上，驱动板三针按丝印连接：

| 风扇驱动板 | ESP32/电源 |
|---|---|
| GPIO | GPIO14 |
| GND | 公共 GND |
| VCC | 5V |

不要把风扇红线或电机直接接到 ESP32 GPIO。小风扇短时桌面测试可用 ESP32 的 `VIN/5V`，长期运行建议使用独立 5V 电源，并与 ESP32 共地。

## 旋转编码器

旋转编码器是带旋钮、支持左右旋转和按压的可选模块。当前实物节点未安装，固件中 `ENCODER_ENABLED` 默认为 `false`；没有该模块时下面三根信号线全部不接。

按 HW-040 板上的丝印接，不要按照片左右位置猜：

| 编码器 | ESP32 |
|---|---:|
| `+` | 3V3 |
| GND | GND |
| CLK | GPIO35 |
| DT | GPIO13 |
| SW | GPIO18 |

旋转编码器切换 OLED 的四个页面；按下编码器依次切换风扇 `AUTO -> ON -> OFF`。

## 原有模块接线

| 模块 | 模块引脚 | ESP32 |
|---|---|---:|
| DHT11 | OUT | GPIO4 |
| 火焰传感器 | DO | GPIO32 |
| MQ 模块 | AO | GPIO34（必须分压） |
| 绿灯 | 电阻后接长脚 | GPIO25 |
| 黄灯 | 电阻后接长脚 | GPIO26 |
| 红灯 | 电阻后接长脚 | GPIO27 |
| 蜂鸣器 | 正极/信号 | GPIO33 |

MQ 模块若用 5V 供电，AO 需要分压：

```text
MQ AO -- 10k -- GPIO34 -- 20k -- GND
```

## 固件行为

- SHT31 正常时优先使用 SHT31；缺失时自动回退到 DHT11。
- 风扇自动模式在温度达到 30 C、湿度达到 80%，或 MQ 原始值达到 1800 时开启。
- 检测到火焰时风扇无条件关闭，避免通风助燃，同时红灯和蜂鸣器报警。
- OLED 四页显示温湿度、光照、MQ、风扇、MAX30102、运动传感器、麦克风和 B-1 接收状态。
- 三个运动传感器以 20 Hz 采样，每 2 秒输出颈部、躯干、腿部运动特征。
- 初步行为标签包括 `standing_quiet`、`standing_active`、`walking`、`lying`、`transition`、`vigorous`。
- `confidence` 只是阈值规则可信度；吃草、饮水、反刍等细分类必须用真实牛只数据标注和训练后再判断。
- 缺失的 I2C 模块显示为 `missing`，不会阻塞其他模块运行。
- INMP441 以 16 kHz 通过 I2S DMA 非阻塞采样，自动校验两个 I2S 槽位，并以 8 kHz 提取可部署的声学特征；手动采样时上传 1 秒 WAV 证据。
- B-1 先以 UART 原始帧采集模式运行，确认协议前不输出虚假温度。
- 串口每 2 秒输出完整 JSON，包括 `lightLux`、运动数据、`microphone`、`b1Infrared`、`fan` 和 `fanMode`。

## 启动扫描预期

所有模块按上表接好后，串口应看到：

```text
I2C scan:
  found 0x23
  found 0x3C
  found 0x44
  found 0x53
  found 0x57
  found 0x68
  found 0x69
```

若少一个地址，优先检查该模块的 VCC/GND、SDA/SCL 和地址选择脚。

## 编译、烧录和串口

```powershell
cd D:\table\shumuzengxiao\硬件代码\现有硬件演示节点
py -3.11 -m platformio run
py -3.11 -m platformio run -t upload --upload-port COM19
py -3.11 -m platformio device monitor -p COM19 -b 115200
```

若没有 `COM19`，先执行：

```powershell
py -3.11 -m platformio device list
```

然后把烧录和监视命令中的端口替换成实际出现的 `COMx`。
