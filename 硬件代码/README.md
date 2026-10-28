# 数牧增效 ESP32 硬件节点

这是项目计划书第一阶段的 ESP32-S3 环境控制节点固件，放在
`D:\table\shumuzengxiao\硬件代码`。当前实物端口是 `COM5`，两块板实测 Flash
均为 16MB。

## 已实现功能

- SHT31 温湿度、BH1750 光照、MQ-137 氨气趋势、MQ-135/烟雾模拟量、火焰数字量采集。
- 风扇、雾化器、声光报警三路执行器联动控制。
- 本地阈值规则：高温、氨气偏高、烟雾/火情触发风扇、报警，并通过 UART 通知 MaixCam 抓拍。
- MQTT 上报 `telemetry`、`status`、`alert`，订阅云端命令。
- HTTP 写入后端 `POST /api/environment`，并轮询 `GET /api/devices/commands`。
- MaixCam 串口 JSON 联动：接收 `vision_event` 后触发本地报警。
- 串口配置 WiFi、MQTT、后端地址，不需要反复改代码。
- OLED 显示联网、传感器、执行器状态。没有接 OLED 时固件会自动跳过。

当前台架未接 MQ 模块，`include/config.h` 中 `ENABLE_MQ_SENSORS=false`，因此氨气和
烟雾输出为空值且不参与自动控制。接好 MQ、完成 5V 模拟输出分压和预热标定后，再改为
`true` 并重新烧录。

推荐使用专用构建环境开启 MQ，默认环境仍保持禁用：

```powershell
cd D:\table\shumuzengxiao\硬件代码
& 'C:\Users\q4984\AppData\Local\Programs\Python\Python311\python.exe' -m platformio run -e esp32s3_mq -t upload
```

只有确认 MQ AO 经 20k/10k 分压、ESP32 ADC 脚实测不超过 3.3V，并完成预热后才执行该命令。

## 默认接线

ESP32-S3 DevKit 默认引脚：

| 功能 | GPIO |
|---|---:|
| I2C SDA | 8 |
| I2C SCL | 9 |
| MQ-137 模拟量 | 1 |
| MQ-135/烟雾模拟量 | 2 |
| 火焰传感器 DO | 10 |
| 风扇继电器 | 14 |
| 雾化器继电器 | 15 |
| 警示灯继电器 | 16 |
| 蜂鸣器 | 21 |
| 板载状态灯 | 48 |
| MaixCam RX <- ESP32 TX | 17 |
| MaixCam TX -> ESP32 RX | 18 |

普通 ESP32 DevKit 备用环境会使用 21/22 I2C、34/35 ADC、25/26/27/33 执行器、16/17 串口。

继电器默认按低电平触发处理，火焰传感器默认低电平为检测到火焰。不同模块相反时，改 `include/config.h` 里的 `RELAY_ACTIVE_LOW`、`FLAME_ACTIVE_LOW`。

## 串口配置

打开 115200 波特率串口监视器，输入：

```text
set wifi_ssid 你的WiFi
set wifi_pass 你的密码
set mqtt_host 192.168.1.10
set mqtt_port 1883
set backend_url http://192.168.1.10:8080
show
reboot
```

本地手动控制：

```text
fan on
fan off
fan auto
atomizer on
atomizer auto
alarm on
alarm auto
capture nh3_high
```

## MQTT Topic

```text
cattle/{barnId}/{deviceId}/telemetry
cattle/{barnId}/{deviceId}/status
cattle/{barnId}/{deviceId}/alert
cattle/{barnId}/{deviceId}/cmd
cattle/{barnId}/relay_01/cmd
cattle/{barnId}/cam_01/vision/event
```

命令示例：

```json
{"action":"fan","enabled":true}
```

MaixCam 发给 ESP32 的串口事件示例：

```json
{"type":"vision_event","event":"fall_suspect","level":"warning","score":0.86,"trackId":3}
```

ESP32 发给 MaixCam 的抓拍请求示例：

```json
{"type":"capture_request","reason":"nh3_high","durationMs":3000}
```

## 构建和烧录

推荐使用 PlatformIO：

```powershell
py -m pip install platformio
cd D:\table\shumuzengxiao\硬件代码
py -m platformio run -e esp32s3
py -m platformio run -e esp32s3 -t upload --upload-port COM5
py -m platformio device monitor -p COM5 -b 115200
```

如果 COM13 上是普通 ESP32，不是 ESP32-S3：

```powershell
pio run -e esp32dev -t upload --upload-port COM13
```

## 后端联调

后端接口来自项目的 `API.md`：

- 环境数据写入：`POST /api/environment`
- 控制命令队列：`GET /api/devices/commands`

ESP32 不能访问电脑上的 `localhost`，`backend_url` 要写电脑在同一热点下的局域网 IP。
电脑通过 WLAN 获取的地址可能变化；热点重新开启后以系统实际分配的 WLAN 地址为准。
`Get-NetIPAddress` 显示的 Remote NDIS 网卡地址为准。

## 现场注意

- MaixCam、继电器、风扇不要从 ESP32 板载 5V 直接取电。
- ESP32 与 MaixCam 独立供电时必须共地。
- MQ-137/MQ-135 需要预热和标定，当前固件按趋势告警处理，不作为精确 ppm 计量。
- 强电负载要使用隔离继电器/接触器、保险丝和浪涌保护。
