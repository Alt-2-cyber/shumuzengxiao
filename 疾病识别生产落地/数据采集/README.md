# 临床数据采集包

此目录用于生成可发布疾病筛查模型所需的现场数据。它不含真实病例数据；真实数据必须由
试点牛场、兽医和项目数据负责人依照授权与隐私要求采集。

## 声音 BRD 数据

1. ESP32 以 `audio_capture` 留存两秒 WAV，平台审核后导出清单。
2. 兽医填写 `audio_clinical_annotations.csv`，每个事件必须有动物、会话和临床证据。
3. `verify_clinical_audio_manifest.py` 生成临床清单。
4. 运行 `train_audio_model.py --release --clinical-api ... --clinical-api-key ...`。训练器逐条向平台回查
   归档 WAV 哈希和兽医签核；所有类别都必须来自受保护平台归档。未通过所有门禁时，头文件必须保持
   `kEnabled=false`。

## 跛行数据

每次记录应收集：颈部/背部/腿部同步 IMU、至少一段侧视或后视步态视频、安装方向、
栏位、地面、日期、行为阶段、步态评分员和兽医/蹄部检查结果。

`lameness_annotations.csv` 中的 `lamenessScore` 应采用项目统一、经培训评分员实施的
标准步态评分体系。它不能由模型预填。每个训练和验证分区必须按 `animalId` 隔离。评分、蹄部检查人、
兽医、检查结果、证据编号和 `verifiedAt` 必须先通过临床页面写入同一个 `recordingSessionId` 的会话签核；
CSV 只作为可复现训练清单，不能替代平台签核。

训练发布时不信任本地清单本身：`train_lameness_model.py --release --clinical-api ... --clinical-api-key ...`
以及 `register_model_release.py --family lameness` 会逐条回查受保护的
`GET /api/motion-captures/{sessionId}/training-lineage`。原始 NDJSON 哈希、20 Hz 连续性和完整度、
会话/耳标、同步视频、步态评分、蹄部检查和临床证据任一不一致即拒绝发布。

## 视觉筛查数据

MaixCam 先保存原始截图并通过平台归档；每条样本必须保留 `eventId`、`recordingId`、
`cameraId`、`barnId`、真实 `animalId`、采集时间和服务器生成的 `snapshotSha256`。
视觉标签只允许 `normal`、`gait_abnormal_suspect`、`hoof_lesion_suspect`、
`oral_lesion_suspect` 和 `nasal_discharge_suspect`。风险标签必须有兽医和临床证据编号；
不得填写 FMD 阳性/阴性、腐蹄或其他具体疾病确诊标签。

`vision_annotations.example.jsonl` 只展示字段结构，里面的图片路径和全零哈希不能直接训练。
替换为真实归档图片和 SHA-256 后，先完成平台逐条临床复核，再运行：

```powershell
cd D:\table\shumuzengxiao\硬件代码\现有硬件演示节点
python tools\train_vision_model.py `
  --manifest D:\table\shumuzengxiao\疾病识别生产落地\数据采集\vision_annotations.jsonl `
  --images-root D:\table\shumuzengxiao\疾病识别生产落地\数据采集 `
  --output tools\vision_model_baseline.npz `
  --metadata tools\vision_model_metadata.json `
  --model-card tools\vision_model_card.md
```

该脚本生成的 NumPy 文件只是数据管线基线，不是 MaixCam `.mud`。只有真实视觉数据按牛只隔离、
外部测试和临床签核全部通过，并提供独立转换的 `.mud`，才能尝试 `--release`。发布登记使用
`register_model_release.py --family vision`，服务器会重新核验每条截图的哈希、相机、栏舍、
标签、兽医签核和临床证据。视觉输出仍是病灶/步态候选；口蹄疫只能进入 `fmd_suspect_triage` 分诊。

## FMD 疑似分诊

仅登记人工/兽医发现的口鼻或蹄部病灶、经接触式体温计确认的核心体温异常和监管报告信息。
不要把传感器或摄像头输出写成 FMD 阳性或阴性。

## 乳房炎数据：暂不采集为现有模型训练标签

现有设备没有乳检输入，因此不要将 B-1、声音、IMU 或视频标签伪装为乳房炎标签。未来接入乳汁
电导率、SCC、挤奶量和乳房/乳样检查后，才可建立独立的 `mastitis_attention` 采集包与发布门禁。
