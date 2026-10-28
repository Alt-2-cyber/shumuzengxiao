# 2026-10-25 牛跛行与三位置 IMU 数据实证

## 结论

已验证 UCD 公开数据的加速度特征完整，牧场分组存在；没有取得可核验的逐牛临床标签 `CombConorAll$High`。因此本次没有训练跛行模型，没有生成模型权重、固件头文件或本地验证性能。研究状态是 `blocked_missing_clinical_labels`，不是训练成功。

已实际产出 383 头牛的序列质量表、11 折留一牧场分区、完整压缩包校验、官方仓库全部历史清单、论文补充指标表和带哈希的公开来源快照。所有产物位于：

`D:\table\shumuzengxiao\疾病识别生产落地\研究模型\ucd-lameness-20261025\`

没有访问 COM 口，没有启动或停止服务，没有修改固件、现有训练程序或审批门禁。只新增研究脚本、本文档和研究目录产物。

## 原始来源与追溯

- 论文：[Riaz et al., PLOS ONE 2025, DOI 10.1371/journal.pone.0325927](https://doi.org/10.1371/journal.pone.0325927)。全文 Data Availability 指向下述 GitHub，声明支持复现与复用。
- 官方仓库：[june18usman/UCD](https://github.com/june18usman/UCD)，本次镜像 HEAD 为 `30d505f38f46d4bdb2c9f0528f82a2101d9818c1`。
- Git 镜像取回唯一公开分支 `main` 的全部 7 次提交，时间跨度为 2025-02-14 至 2026-01-07。`repository_history.json` 记录所有历史路径及压缩包成员；`git_commands.json` 保存命令与输出。
- 全部历史中没有 `CombConorAll` 文件，没有 `.xlsx` / RData 标签文件；唯一历史数据 ZIP 只含 `AllCowsDataX.csv`。原始 CSV、PCA/FPCA 文件和 R 代码均未包含独立临床标签表。
- 官方 `CombConorAll.csv` 与 `CombConorAll.xlsx` 直接 URL 均实测返回 HTTP 404；响应体、时间和 SHA-256 保存在 `retrieval_log.json` 与 `public_sources/`。
- 仓库 [Forks 页面](https://github.com/june18usman/UCD/forks) 实测显示 `No one has forked this repository yet`，HTML 已保存；作者仓库列表 API 则受限流影响，不能据此排除作者其他非公开或未索引资料。
- 论文只提供一个补充文件：[S1 Table](https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0325927.s001)。已下载 32,551 字节 DOCX 并解析 XML：只有 1 个表、176 行汇总指标，没有逐牛标签。SHA-256 为 `43d15e8fc8a6aa5a6386d792d457c2b56161d00f38d45598b1ea89f41dd0a119`。
- 同源临床研究为 Logan et al. 2024，[DOI 10.3168/jds.2023-23928](https://doi.org/10.3168/jds.2023-23928)。本次没有从该论文获得能与 UCD 行顺序核对的标签表。

证据范围是本次成功读取的官方仓库、全部公开 Git 历史、论文及其唯一补充文件。部分 GitHub API 请求限流，其他公开数据端点有 TLS / 超时失败，均原样记入日志；这些网络失败不构成“全网不存在标签”的证明。没有联系作者、提交申请或发送外部消息。

Git 最初直连失败，随后在该子进程中继承 Windows 当前代理成功。脚本不修改全局 Git / 代理配置。仓库未提供独立 LICENSE；论文为 CC BY，作者的数据可复用声明保存在全文中，数据的具体授权边界仍应在后续获取标签时确认。

## 本地文件实测

| 文件 | 实测结果 |
|---|---|
| `UCD_Riaz_2025\AllCowsDataX.zip` | 40,960 字节，`BadZipFile`，下载不完整 |
| `UCD_Riaz_2025\UCD-main.zip` | 6,424,808 字节，全部成员 CRC 通过 |
| `UCD-main\AllCowsDataX.zip` | 5,773,151 字节，CRC 通过，仅 1 个 CSV 成员 |
| `source\AllCowsDataX.csv` | 64,158,736 字节，383 行，20,001 列 |
| `AfterPCA_AllCowsX.csv` | 383 行，76 个分量，另有隐式行名 |
| `AfterFPCA_AllCowsX.csv` | 383 行，91 个分量，另有隐式行名 |

完整 ZIP 解压内容和现存 `source` CSV 的 SHA-256 完全一致：

`8a8f92b123ac17d73bd3fb26b3b2e805298a302109fcacaad7f1c43456af7b22`

该 ZIP 与远端 Git 数据 blob 的 SHA-256 也一致：

`053e731fc6a68603e1eed909514703bb3b360d7c7e55155fa786fb266065f808`

因此无需重下或覆盖原有损坏 ZIP，就能确认现有研究特征完整。没有对原文件做修复或替换。

CSV 第一列确为 `farmer`，其余列为 `V3` 到 `V20002`，每头牛 20,000 个 Z 轴观测值。没有 `High`、步态评分、原始牛号、时间戳、颈部/背部数据或 X/Y 轴。

| 牧场 | 牛数 | 牧场 | 牛数 |
|---|---:|---|---:|
| Farmer_1 | 43 | Farmer_7 | 24 |
| Farmer_2 | 12 | Farmer_8 | 24 |
| Farmer_3 | 45 | Farmer_9 | 43 |
| Farmer_4 | 44 | Farmer_10 | 44 |
| Farmer_5 | 12 | Farmer_11 | 46 |
| Farmer_6 | 46 | 合计 | 383 |

实测 7,660,000 个数值全部有限，数值序列完全重复的行数为 0。范围为 `[-8.0, 7.984375]`，全部落在 `1/64` 的量化格点，119 个值等于上述量程端点。端点值只作为质量统计，没有推断疾病标签或擅自删除牛。

全体均值 `0.4702988740`、标准差 `0.5734496086`；逐特征均值范围 `0.02158..0.87243`，标准差范围 `0.32623..0.81340`。因此公开 CSV 不符合论文“逐特征均值 0、标准差 1”的描述。文件中没有充分的标定、单位和抽样时间元数据，不能直接假定为已标准化输入。

PCA/FPCA CSV 数据行分别比表头多 1 列，首列是 `1..383` 的 R 隐式行名，不是额外分量或临床牛号。论文正文写 77/105 个分量，公开文件实为 76/91；不能声称无差异复现论文。21 个现有 R 脚本均已逐文件读取并记录依赖；README 提到的 `A3_FPCA_SVM_FS21.R` 不在公开文件中。

## 标签含义与现有程序

论文参考标准是第二次农场访问时，兽医检查四足后确定的 **case definition 3：严重蹄部病变**。第一次访问没有评估跛行。该目标不能直接改名为本项目 `lamenessScore >= 2`，也不能把行为 `walking`、低活动量或极端加速度当作阳性。

现有 `train_export_model.py` 处理单传感器的六类行为，默认只使用 XYZ 加速度；其分区基于连续行为段，没有临床蹄病标签，现有姿态分数不能作为跛行指标。

现有 `train_lameness_model.py` 则需要带临床审核和原始文件哈希的清单，读取 20 Hz 的 `motion_capture_sample` NDJSON。每个 10 秒窗口，分别从 neck/body/leg 的三轴模长计算均值、标准差、绝对相邻差均值和标准差，共 12 个特征。默认步长为 5 秒，并保留牛只独立外部测试及发布审批。

研究脚本仅静态读取上述接口并记录 SHA-256，没有调用其训练入口、发布入口或临床 API。现有采集目录的示例 `lameness_annotations.csv` 包含 `YYYY-MM-DD` 等模板内容，不是可用的真实临床病例。

## 三位置部署兼容性

| 项目 | UCD 公开数据 | 现有目标硬件/训练输入 | 判断 |
|---|---|---|---|
| 部位 | 单个后肢 AX3 | 颈、背、腿各一 ADXL345 | 缺 2 个部位 |
| 通道 | 仅 Z | 每部位 XYZ，共 9 通道 | 缺 X/Y，无法求真实三轴模长 |
| 时间尺度 | 最后 7 天，1500 点抽取 1 点，约 30 秒 1 点 | 20 Hz，10 秒 200 点窗口 | 有效采样率相差约 600 倍 |
| 样本单位 | 每牛一条 20,000 点序列 | 每牛多次同步会话和窗口 | 数据契约不同 |
| 临床目标 | 严重蹄部病变 | 临床审核的步态筛查 | 定义需重新对应与验证 |
| 身份/质控 | 匿名牧场，缺原始牛号与时间戳 | 牛号、会话、哈希、完整度、视频与审核 | 无法直接进入现有门禁 |

论文原文不是“30 秒内 20,000 点”，而是约“每 30 秒保留一个点”。抽稀丢失的高频步态无法靠插值恢复；复制 Z 轴到 X/Y 或其他部位也不能生成真实三位置输入。即使今后补齐 UCD 标签并训练出研究模型，也不能直接烧录到本项目硬件。

## 训练实现与真实验证结果

新增脚本：`D:\table\shumuzengxiao\scripts\train_ucd_lameness_20261025.py`。

当前实测结果为：`model_created=false`，`production_eligible=false`。**本次 Accuracy、AUC、敏感度、特异度、PPV 均不可计算**，没有被写成 0，也没有借用论文值冒充实测值。缺标签时脚本预期返回退出码 2；证据和质量表仍完整保存。

已实际运行 `--verify`：9 项实证检查全部通过，包括完整 CSV、源文件哈希、ZIP CRC 和解压内容一致、11 折分组互斥与覆盖、每个牛行仅一次测试、无模型/固件产物、无伪造验证指标、受保护现有程序哈希不变、全部官方 Git 历史读取成功。CLI 实测返回 2，标准错误为空；仅提供 `--labels` 而缺 `--provenance` 时也返回 2 并报参数错误。镜像 `git fsck --full` 返回 0，无错误。检查通过表示证据链和拒训行为正确，不表示模型已获得验证。

`unlabeled_leave_one_farm_out_partitions.csv` 提供真实 11 牧场的分区计划：每折 383 条角色记录，共 4,213 条；每行在其中一折作为测试。行标识明确写作 `source_row_1based`，没有冒充临床牛号。这只是特征分区，不是模型验证结果。

脚本预留真实标签训练入口，需要完整的 `source_row_1based,cow_id,High,farmer` 映射，以及来源 URL、授权、临床定义、行对应依据和两份文件 SHA-256。取得作者标签后必须人工核对来源及对应关系，不能仅凭 JSON 声明认定真实。

有真实标签时，训练实现固定的多数类先验基线、原始 Z 序列 RF、训练折内标准化/PCA/逻辑回归；按牛分组 5 折及留一牧场 11 折验证，固定阈值 0.5，输出逐折/汇总指标和逐牛 out-of-fold 预测。牧场名和牛号不进入特征，PCA 不复用公开的全量变换。当前正向训练路径因没有真实标签未运行，不能声称已经验证其预测性能。

下载的 `paper_reported_metrics.csv` 仅为论文 S1 表的原样结构化提取。例如论文原始 Z RF 的 farm-fold AUC 为 62.32%，敏感度 3.33%，特异度 86.43%；PCA+LR 的 farm-fold AUC 为 66.66%，敏感度 37.58%，特异度 80.96%。这些均为**论文报告值**，不是本次训练或部署效果。

## 其他公开数据检索

已保存 DataCite `cattle AND accelerometer` 的全部 98 条元数据（包含同一数据集的不同版本、论文与代码，不等于 98 个独立临床数据集），并保存其他查询及失败日志。没有下载大型数据集、安装新运行环境或把其他疾病/行为标签改作跛行。

| 公开来源 | 读取到的结构 | 当前是否可替代 |
|---|---|---|
| [Japanese Black Beef Cow Behavior, 10.5281/zenodo.5849025](https://doi.org/10.5281/zenodo.5849025) | 6 牛，单颈部 XYZ，25 Hz，13 类行为；BY-NC-ND | 没有临床跛行、没有背/腿，授权也需单独确认 |
| [Precision Beef, 10.5281/zenodo.4064801](https://doi.org/10.5281/zenodo.4064801) | 18 牛，10 Hz 项圈加速度 + 下颌压力，三类行为；CC BY | 不是三位置加速度，也没有临床跛行 |
| [The Cow Pedogram, 10.7892/boris.95040](https://doi.org/10.7892/boris.95040) | 有临床跛行/病变研究，两个 400 Hz 加速度计 | 获取的是论文元数据，没有获得可训练原始数据；部位也不匹配 |
| [German Six-Farm Study, 10.3390/ani13233681](https://doi.org/10.3390/ani13233681) | 4860 牛、6 场、临床跛行与活动量研究 | 本次未获得逐牛可下载数据，不能用论文性能替代数据 |
| [SARA collar study, 10.15129/6be31987-3086-4753-b97b-70696ff70a4a](https://doi.org/10.15129/6be31987-3086-4753-b97b-70696ff70a4a) | 项圈加速度与瘤胃 pH | 病种和部位不同，不能当跛行标签 |

在本次成功获取的来源中，未核实到可直接使用的“真实临床跛行 + 颈/背/腿同步 XYZ + 原始时间序列 + 牛/场分组”的公开数据。网络失败的来源仍列为未核实，不宣称不存在。本研究目录保存了有限的真实公开样例：论文补充 DOCX、176 行汇总表、仓库镜像与元数据快照；没有把元数据伪装成原始临床样例。

## 复现与剩余缺口

本机实际运行环境为 Python 3.13.14、NumPy 2.4.3、SciPy 1.17.1、scikit-learn 1.8.0。`py -3.13` 未被旧 launcher 注册，使用已存在的 `python` 即可，不需要安装。

```powershell
Set-Location D:\table\shumuzengxiao
python scripts/train_ucd_lameness_20261025.py --verify
# 缺标签时预期退出 2；重新计算本地实证，不请求网络。

python scripts/train_ucd_lameness_20261025.py --online --discover --verify
# 有界读取公开来源，成功快照按 SHA-256 复用；失败状态原样记录。
```

主要产物：`local_data_audit.json`、`cow_series_qc.csv`、`unlabeled_leave_one_farm_out_partitions.csv`、`repository_history.json`、`git_commands.json`、`paper_evidence.json`、`supplement_audit.json`、`paper_reported_metrics.csv`、`retrieval_log.json`、`alternative_dataset_search.json`、`alternative_dataset_inventory.csv`、`training_status.json`、`verification_results.json`、`verification_cli_results.json`、`artifact_manifest.json`。

UCD 研究训练剩余缺口是：作者真实的 383 牛严重病变 `High` 标签及其与当前 CSV 的精确行对应；原始牛号和具体数据授权也应取得或说明。若只能取得无对应关系的其他牛标签，仍不得训练。

三位置部署剩余缺口是：本机同型号/同安装方式的同步 20 Hz 颈背腿数据、真实牛号与牧场分组、步态视频、评分、蹄部检查、兽医审核、时间同步和原始数据质量记录，以及独立牛/独立场测试。现有审批门禁继续由原程序执行，本研究输出不授予上线资格。
