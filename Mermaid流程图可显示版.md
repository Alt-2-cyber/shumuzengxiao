# Mermaid 流程图可显示版

说明：下面每个图都必须放在 ` ```mermaid ` 代码块中。普通 Word、普通文本框和部分 Markdown 编辑器不会自动渲染 Mermaid。

## 1. 系统总体架构

```mermaid
flowchart TB
    subgraph Barn["牛舍现场端"]
        subgraph EnvNode["ESP32-S3 环境控制节点"]
            Sensors["温湿度/氨气/光照/火情/烟雾传感器"]
            ESP32["ESP32-S3 主控<br/>采集/控制/MQTT/本地规则"]
            Actuators["风扇/雾化器/声光报警/继电器"]
            LCD["本地屏幕/按键"]
            Sensors --> ESP32
            ESP32 --> Actuators
            ESP32 --> LCD
        end

        subgraph VisionNode["MaixCam 视觉 AI 节点"]
            Camera["摄像头"]
            Maix["MaixCam<br/>YOLO 推理/跟踪/事件判定"]
            SD["本地 SD 卡<br/>截图/日志/模型"]
            Camera --> Maix
            Maix --> SD
        end

        ESP32 <-->|UART JSON| Maix
        Router["WiFi/4G 路由器"]
        ESP32 --> Router
        Maix --> Router
    end

    Router --> Broker["MQTT Broker/EMQX"]
    Broker --> Backend["Spring Boot 后端"]
    Backend --> DB["MySQL 数据库"]
    Backend --> WS["WebSocket"]
    WS --> Frontend["Vue 前端看板"]
    Backend --> Alert["短信/微信/邮件/站内告警"]
```

## 2. 全链路数据流

```mermaid
flowchart TD
    A["环境传感器采集"] --> B["ESP32-S3 数据滤波"]
    B --> C["本地阈值判断"]
    C --> D{"是否异常"}
    D -- 否 --> E["周期 MQTT 上报 telemetry"]
    D -- 是 --> F["本地执行器联动<br/>风扇/雾化/声光报警"]
    F --> G["MQTT 上报告警 alert"]
    F --> H["UART 通知 MaixCam 抓拍"]

    I["MaixCam 摄像头采集"] --> J["图像预处理"]
    J --> K["YOLO 开源模型推理"]
    K --> L["目标跟踪 + 行为状态机"]
    L --> M{"是否产生视觉事件"}
    M -- 否 --> N["仅更新本地状态"]
    M -- 是 --> O["保存截图/事件 JSON"]
    O --> P["MQTT 上报 vision/event"]
    O --> Q["UART 通知 ESP32-S3 本地报警"]

    E --> R["MQTT Broker"]
    G --> R
    P --> R
    R --> S["Spring Boot 后端"]
    S --> T["MySQL 入库"]
    S --> U["WebSocket 推送"]
    U --> V["Vue 前端看板/告警中心"]
```

## 3. 供电流程

```mermaid
flowchart LR
    IN["12V/24V 输入"] --> Protect["保险丝/反接保护/TVS"]
    Protect --> Buck5["5V 3A DC-DC"]
    Protect --> Buck33["3.3V 1A DC-DC"]
    Protect --> Load12["12V 执行器/补光"]
    Buck5 --> MaixCam["MaixCam"]
    Buck5 --> Relay["继电器模块/部分传感器"]
    Buck33 --> ESP32["ESP32-S3"]
    Buck33 --> I2C["I2C 数字传感器"]
```

## 4. 断网缓存流程

```mermaid
flowchart TD
    A["ESP32-S3/MaixCam 产生数据"] --> B{"MQTT 是否在线"}
    B -- 在线 --> C["立即上报"]
    B -- 离线 --> D["本地缓存关键数据"]
    D --> E["定时重连 MQTT"]
    E --> F{"网络恢复"}
    F -- 否 --> D
    F -- 是 --> G["补传事件摘要和关键截图"]
    G --> H["清理已确认缓存"]
```

## 5. 声音与疾病风险数据流

```mermaid
flowchart TD
    A["I2S 麦克风采集牛舍声音"] --> B["ESP32-S3 音频分帧"]
    B --> C["降噪/能量检测/VAD"]
    C --> D{"是否疑似有效声音"}
    D -- 否 --> E["丢弃或只记录噪声水平"]
    D -- 是 --> F["提取 MFCC/Log-Mel 特征"]
    F --> G["轻量声音分类模型<br/>咳嗽/喘鸣/异常叫声/背景噪声"]
    G --> H["生成 audio_event"]
    H --> I["MQTT 上报声音事件"]
    H --> J["触发 MaixCam 抓拍对应时间窗口"]
    J --> K["视觉疾病风险筛查"]
    I --> L["后端多模态融合"]
    K --> L
    L --> M["健康风险等级<br/>正常/关注/告警/需人工复核"]
```

## 6. 多模态疾病风险判断

```mermaid
flowchart TD
    A["环境数据<br/>温湿度/氨气/烟雾"] --> F["多模态融合评分"]
    B["声音数据<br/>咳嗽/喘鸣/异常叫声"] --> F
    C["姿态行为<br/>卧倒/跛行/活动减少"] --> F
    D["局部视觉<br/>皮肤/眼睛/鼻部异常"] --> F
    E["历史数据<br/>同一牛只/同一栏位趋势"] --> F
    F --> G{"健康风险等级"}
    G -- 低 --> H["记录趋势"]
    G -- 中 --> I["前端提示观察"]
    G -- 高 --> J["告警 + 截图/音频证据"]
    G -- 严重 --> K["建议人工/兽医复核"]
```
