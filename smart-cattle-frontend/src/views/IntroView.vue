<template>
  <div class="intro-page">
    <section class="intro-hero">
      <img class="intro-hero-image" :src="barnWide" alt="肉牛养殖现场" data-depth="0.22" />
      <div class="intro-hero-shade"></div>
      <div class="intro-hero-content">
        <div class="intro-release" data-depth="-0.08">Smart Cattle OS · Field Edition 2026</div>
        <h1 data-depth="-0.16">数牧增效</h1>
        <p>把 ESP32-S3 环境节点、MaixCam 视觉 AI、I2S 声音识别和 Spring Boot 平台汇成一套农户用得起、现场跑得动的肉牛健康监测系统。</p>
        <div class="intro-actions">
          <RouterLink to="/dashboard" class="intro-primary">进入驾驶舱</RouterLink>
          <RouterLink to="/models" class="intro-secondary">查看 AI 方案</RouterLink>
        </div>
      </div>
      <div class="intro-hero-metrics" data-depth="-0.1">
        <div>
          <span>边缘推理</span>
          <strong>9.8 FPS</strong>
        </div>
        <div>
          <span>融合数据</span>
          <strong>4 模态</strong>
        </div>
        <div>
          <span>部署成本</span>
          <strong>农户级</strong>
        </div>
      </div>
    </section>

    <section class="edition-band">
      <div>
        <p class="intro-kicker">System Architecture</p>
        <h2>现场端先判断，平台端再融合。</h2>
      </div>
      <p>环境异常不等云端回复，ESP32-S3 本地规则直接联动风扇、雾化和报警；视觉与声音事件再进入后端形成证据链，减少误报和漏报。</p>
    </section>

    <section class="edition-scroll">
      <div class="edition-scroll-heading">
        <p class="intro-kicker">Field Editions</p>
        <h2>牛舍能力一层层接入。</h2>
      </div>

      <div class="edition-story">
        <div class="edition-copy-stack">
          <article
            v-for="(item, index) in editionItems"
            :key="item.title"
            class="edition-step"
            :data-edition-step="index"
          >
            <div class="edition-step-index">0{{ index + 1 }}</div>
            <span>{{ item.label }}</span>
            <h3>{{ item.title }}</h3>
            <p>{{ item.text }}</p>
            <dl class="edition-step-metrics">
              <div v-for="metric in item.metrics" :key="metric.name">
                <dt>{{ metric.name }}</dt>
                <dd>{{ metric.value }}</dd>
              </div>
            </dl>
          </article>
        </div>

        <aside class="edition-visual-stage">
          <div class="edition-orbit" aria-hidden="true"></div>
          <figure
            v-for="(item, index) in editionItems"
            :key="item.title"
            class="edition-visual"
            :data-edition-visual="index"
          >
            <img :src="item.image" :alt="item.alt" :data-depth="item.depth" />
            <figcaption>
              <span>{{ item.caption }}</span>
              <strong>{{ item.signal }}</strong>
            </figcaption>
          </figure>
          <div class="edition-progress-list">
            <button
              v-for="(item, index) in editionItems"
              :key="item.label"
              type="button"
              class="edition-progress-dot"
              :data-edition-dot="index"
              :aria-label="item.label"
            ></button>
          </div>
        </aside>
      </div>
    </section>

    <section class="feature-mosaic">
      <article class="feature-card feature-large">
        <img :src="barnResting" alt="牛舍内休息的牛群" data-depth="0.14" />
        <div>
          <span>Vision AI</span>
          <h3>识别姿态、皮肤、眼睛鼻子异常。</h3>
          <p>MaixCam 在牛舍端执行 YOLO 轻量推理，输出目标跟踪、姿态事件、局部异常截图和置信度。</p>
        </div>
      </article>
      <article class="feature-card feature-dark">
        <span>Audio AI</span>
        <h3>听见咳嗽和喘鸣。</h3>
        <p>I2S 麦克风采集牛舍声音，VAD 过滤噪声后提取 Log-Mel/MFCC，识别咳嗽、喘鸣和异常叫声。</p>
      </article>
      <article class="feature-card">
        <span>Edge Control</span>
        <h3>ESP32-S3 替代 STM32，通信更直接。</h3>
        <p>WiFi、MQTT、UART JSON、I2S 能力集成在一个主控上，硬件链路更少，调试成本更低。</p>
      </article>
      <article class="feature-card feature-image">
        <img :src="closeup" alt="牛只局部特写" data-depth="0.12" />
      </article>
    </section>

    <section class="release-grid">
      <article v-for="item in releaseItems" :key="item.title" class="release-card">
        <span>{{ item.label }}</span>
        <h3>{{ item.title }}</h3>
        <p>{{ item.text }}</p>
      </article>
    </section>
  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import barnWide from '../assets/images/cattle-barn-wide.jpg'
import barnResting from '../assets/images/cattle-barn-resting.jpg'
import closeup from '../assets/images/cattle-closeup.jpg'
import editionBarnFlow from '../assets/images/edition-barn-flow.jpg'
import editionCattleField from '../assets/images/edition-cattle-field.jpg'
import editionEdgeBoard from '../assets/images/edition-edge-board.jpg'
import editionCamera from '../assets/images/edition-camera.jpg'
import editionFarmHand from '../assets/images/edition-farm-hand.jpg'

const editionItems = [
  {
    label: 'Barn OS',
    title: '每一间牛舍都有自己的实时层。',
    text: '温湿度、氨气、烟雾和风扇状态先汇入边缘规则，平台从“现场发生了什么”开始组织整套方案。',
    caption: 'Barn telemetry',
    signal: '16.2 ppm NH3',
    alt: '牛舍环境流动监测画面',
    image: editionBarnFlow,
    depth: '0.18',
    metrics: [
      { name: '本地刷新', value: '15s' },
      { name: '执行链路', value: '规则直连' }
    ]
  },
  {
    label: 'Vision Layer',
    title: '摄像头不是看热闹，而是产生证据。',
    text: 'MaixCam 对姿态、皮肤、眼鼻局部和活动量做轻量推理，异常截图直接成为后端风险评分的证据。',
    caption: 'Vision events',
    signal: 'YOLO edge',
    alt: '牛群视觉识别场景',
    image: editionCattleField,
    depth: '0.12',
    metrics: [
      { name: '推理帧率', value: '9.8 FPS' },
      { name: '截图证据', value: '自动归档' }
    ]
  },
  {
    label: 'Edge Board',
    title: 'ESP32-S3 把传感、通信和控制压到一块板上。',
    text: 'WiFi、MQTT、UART JSON、I2S 与继电器控制集中在边缘端，减少农户现场布线和维护复杂度。',
    caption: 'Control bus',
    signal: 'MQTT stable',
    alt: '边缘计算电路板',
    image: editionEdgeBoard,
    depth: '0.2',
    metrics: [
      { name: '主控', value: 'ESP32-S3' },
      { name: '供电', value: '12V/24V' }
    ]
  },
  {
    label: 'Risk Chain',
    title: '声音、图像、环境一起给出复核优先级。',
    text: '咳嗽、喘鸣、卧地时长、氨气偏高会被合并成风险队列，先推最值得复核的牛只和区域。',
    caption: 'Risk fusion',
    signal: '4 modalities',
    alt: '摄像头监控设备',
    image: editionCamera,
    depth: '0.16',
    metrics: [
      { name: '风险等级', value: '4 档' },
      { name: '人工复核', value: '优先队列' }
    ]
  },
  {
    label: 'Farmer Ready',
    title: '最后落到普通牛舍也能维护。',
    text: '硬件、模型、平台和训练样本回流都围绕低成本部署设计，让系统不是演示品，而是能长期跑的农户工具。',
    caption: 'Deployment',
    signal: 'Field ready',
    alt: '农场现场维护',
    image: editionFarmHand,
    depth: '0.1',
    metrics: [
      { name: '安装路径', value: '清晰' },
      { name: '样本回流', value: '持续优化' }
    ]
  }
]

const releaseItems = [
  {
    label: 'Data Flow',
    title: '设备到平台的闭环链路',
    text: 'ESP32-S3 和 MaixCam 通过 MQTT/HTTP 上传遥测、事件和截图，Spring Boot 入库 MySQL，Vue 看板实时刷新。'
  },
  {
    label: 'Health Risk',
    title: '多模态疾病筛查',
    text: '环境、声音、姿态、皮肤、眼鼻局部和历史趋势一起评分，输出正常、关注、告警、需复核等级。'
  },
  {
    label: 'Deployment',
    title: '可在普通牛舍落地',
    text: '12V/24V 供电、5V/3.3V 降压、继电器控制、WiFi/4G 路由器回传，现场安装和维护路径清晰。'
  },
  {
    label: 'Training',
    title: '开源模型二次优化',
    text: '以 YOLO、MobileNet、轻量 CNN 为基线，使用本地采集样本持续回流训练，降低牛舍场景误报。'
  }
]
</script>
