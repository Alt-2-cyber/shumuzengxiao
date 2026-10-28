# 数牧增效智能牛舍监测平台

本项目是“农户普惠型肉牛养殖监测专家”的网站与后端原型，已按 Spring Boot + Vue 3 + Three.js + MySQL 的技术路线落地为可运行系统。

## 功能范围

- 总览驾驶舱：存栏、在线设备、未闭环告警、边缘推理 FPS、3D 牛舍态势。
- 环境监测：温湿度、氨气、光照、烟雾趋势，风扇和雾化器联动状态。
- 健康风险：融合声音 AI、视觉 AI、环境数据生成疾病风险证据链。
- 牛体行为：实时显示颈部、背部、腿部运动节点、六分类结果、置信度和活动趋势。
- 临床复核：记录接触式核心体温、步态/病灶检查，并下发带视频引用的三位置 20 Hz 原始 IMU 采集会话。
- 设备控制：风扇、雾化、声光报警、抓拍等控制命令下发，并记录命令历史。
- AI 模型：展示 YOLO、声音分类、多模态融合模型和训练部署流程。

## 目录

```text
smart-cattle-backend/    Spring Boot REST API
smart-cattle-frontend/   Vue3 + Vite + Three.js 前端
hm/                      HarmonyOS ArkTS 应用
wx/                      微信小程序
硬件代码/                 ESP32-S3 固件与 MaixCAM 应用
scripts/                 调试、训练、转换及部署工具
docs/                    硬件联调与模型验证记录
database/init.sql        MySQL 初始化脚本
API.md                   后端接口清单
```

仓库包含运行源码、依赖锁文件、固件模型头文件、声音研究模型及 MaixCAM 部署模型。
原始训练数据、录音、现场截图、TF 卡镜像、本机依赖、生成文档和运行日志保留在本地，
不随源码上传；公开数据来源和训练过程记录在 `docs/` 及各模型元数据中。
模型产物沿用其来源的许可和研究用途边界，本仓库未额外授予第三方代码或模型的使用许可。

开发环境需要 Java 17、Maven、Node.js/npm；硬件开发使用 PlatformIO，
鸿蒙应用使用对应 SDK 的 DevEco Studio，小程序使用微信开发者工具。
配置变量见 `.env.example`，应设置到启动进程或服务环境中；程序不会自动加载 `.env`。

最新 MaixCAM 应用为“杨文昊-数牧增效”V1.1，执行牛只检测后再进行牛体区域外观研究分类。
部署入口为 `scripts/install_maixcam_launcher.py`，详细结果见
`docs/2026-10-28-cow-cascade-training-deployment.md`。研究结果不用于疾病确诊。

## 本地演示

一键启动前后端：

```powershell
D:\table\shumuzengxiao\start-all.bat
```

当前硬件架构下，启动脚本会自动启用 `COM5` 环境节点和 `COM9` 牛身节点的
`115200` 串口监听；如果改用 WiFi，可设置 `ESP32_SERIAL_ENABLED=false` 后再启动。

停止前后端：

```powershell
D:\table\shumuzengxiao\stop-all.bat
```

后端默认使用 H2 内存数据库，会自动写入演示数据：

```powershell
cd D:\table\shumuzengxiao\smart-cattle-backend
mvn spring-boot:run
```

前端启动：

```powershell
cd D:\table\shumuzengxiao\smart-cattle-frontend
npm install
npm run dev
```

访问地址：

- 项目介绍页：http://localhost:5173
- 前端看板：http://localhost:5173/dashboard
- 牛体行为实时页：http://localhost:5173/behavior
- 后端接口：http://localhost:8080/api/dashboard
- H2 控制台：http://localhost:8080/h2-console

## MySQL 部署

先执行：

```powershell
mysql -uroot -p < D:\table\shumuzengxiao\database\init.sql
```

如果本机已经存在旧版 `smart_cattle` 库，执行兼容迁移脚本补齐字段和索引：

```powershell
mysql -uroot -p < D:\table\shumuzengxiao\database\migrate_existing_mysql.sql
```

通过 `start-all.bat` 或 `start-backend.bat` 以 `mysql` profile 启动时，脚本会先自动执行这份幂等迁移。
默认使用本机 `127.0.0.1:3306` 和 `smart_cattle`；用户名和密码通过环境变量提供，可用
`SMART_CATTLE_MYSQL_CLIENT`、`SMART_CATTLE_MYSQL_HOST`、`SMART_CATTLE_MYSQL_PORT`、
`SMART_CATTLE_MYSQL_DATABASE`、`SMART_CATTLE_MYSQL_USER`、`SMART_CATTLE_MYSQL_PASSWORD` 覆盖。
MySQL 客户端不存在时，脚本会在启动前报出明确提示。

再用 MySQL profile 启动后端：

```powershell
cd D:\table\shumuzengxiao\smart-cattle-backend
mvn spring-boot:run "-Dspring-boot.run.profiles=mysql,production"
```

默认连接参数在 `smart-cattle-backend/src/main/resources/application-mysql.yml`，上线前请设置实际账号和密码。`production` profile 会禁用 H2/演示数据，并要求五个不同的角色密钥；缺一个即拒绝启动。环境变量示例见 `.env.example`，不要把真实值提交到仓库。

## 疾病风险生产边界

实现与论文资料在 `D:\table\shumuzengxiao\疾病识别生产落地`。跛行、BRD 和口蹄疫仅输出
`_suspect` / `_triage` 筛查结果：临床和实验室确认仍由兽医、主管部门及有资质实验室完成。
声音和三位置 IMU 固件默认均为 `feature_only`，必须通过数据、外部验证和发布门禁才会启用。
乳房炎目前仅有文献与采集规范，因现有硬件没有乳汁电导率、SCC 和乳样输入，平台不会生成
`mastitis_attention`。具体疾病、证据和确认方式见 `疾病识别生产落地/疾病实体与证据字典.md`。

健康筛查观测摘要写入 MySQL 的 `health_screening_observation` 表，后端启动时恢复最近 7 天的
个体行为/声音/体表温度摘要，用于避免重启后丢失个体基线。该表不存储未经授权的疾病结论；
声音、跛行、FMD 仍受模型审批和临床证据门禁约束。

生产启用 API 鉴权时，请分别配置 `API_KEY_VIEWER`、`API_KEY_INGEST`、`API_KEY_OPERATOR`、
`API_KEY_CLINICAL` 和 `API_KEY_ADMIN`，且它们不得重复。MaixCam 只能拿 `API_KEY_INGEST`；
临床数据、原始音频、IMU 归档、FMD 人工交接和审计记录仅向 `clinical` / `admin` 开放。完整角色表见
`API.md` 与 `疾病识别生产落地/生产部署与审计清单.md`。

声音疾病模型发布会对每条训练 WAV 的平台归档哈希、审核标签、真实耳标、录音会话、兽医与临床证据
做三次在线复核：训练时一次、登记工具一次、服务器登记事务一次。公开声音数据当前只用于已明确标注为
“非疾病”的牛声事件基线，不能登记为咳嗽、喘鸣或异常鸣叫疾病模型。

跛行疾病模型也执行同样的三重在线复核：训练、登记工具和服务器登记事务逐条重新核对受保护 IMU 归档的
SHA-256、20 Hz 连续性和完整度、会话/耳标、同步视频、步态评分、蹄部检查及临床证据。
真实多场、跨季节数据与外部验证达标前，`cattle_lameness_model.h` 必须保持 `kEnabled=false`。

## 验证

```powershell
cd D:\table\shumuzengxiao\smart-cattle-backend
mvn package -DskipTests

cd D:\table\shumuzengxiao\smart-cattle-frontend
npm run build
npm run smoke
```

`npm run smoke` 需要前后端服务已启动，会检查总览页、Three.js 画布、ESP32
WebSocket 实时序号、行为趋势画布和手机端横向溢出，并生成测试截图。

疾病模型发布前运行数据就绪审计：

```powershell
cd D:\table\shumuzengxiao
& 'C:\Users\q4984\AppData\Local\Programs\Python\Python311\python.exe' .\scripts\audit_disease_data.py --strict
```

该命令检查视觉病灶图片、兽医签核音频、三位置 IMU、动物分组和占位符；任一路径未满足门禁都会以退出码 `2` 拒绝发布。公开牛声基线不计入疾病模型就绪状态。
也可以用 `--family vision`、`--family audio` 或 `--family lameness` 单独检查某一条发布路径。

视觉事件导出为训练清单（仅临床角色）：

```powershell
& 'C:\Users\q4984\AppData\Local\Programs\Python\Python311\python.exe' .\scripts\export_reviewed_vision_dataset.py `
  --api http://localhost:8080 `
  --api-key $env:CLINICAL_API_KEY `
  --output D:\table\shumuzengxiao\vision-training-data\reviewed `
  --manifest D:\table\shumuzengxiao\vision-training-data\reviewed\reviewed_manifest.jsonl
```

导出器会重新下载图片并核对 SHA-256；只有带真实牛只编号、兽医、临床证据和签核时间的事件才会写入 `allowForDiseaseLabels=true`。

现场硬件验收使用统一审计脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File D:\table\shumuzengxiao\scripts\audit_system.ps1
```

脚本会检查 MySQL、前后端接口、COM5/COM9、固件构建产物和模型状态。`dataFresh=true`
才表示最近 7 秒确实收到 ESP32 数据；端口存在但没有帧时会显示
`connected_waiting_data`。加 `-FailOnStaleHardware` 可让硬件无实时数据时以退出码 `2` 失败。
