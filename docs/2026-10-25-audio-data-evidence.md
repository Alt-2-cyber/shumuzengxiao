# 牛声音数据证据与分组训练实验

核查日期：2026-10-25。工作目录：`D:\table\shumuzengxiao`。

## 结论

本次实际取得 INRAE/ENVT 研究公开的 **20 段犊牛咳嗽事件与 20 段非咳嗽事件 WAV**，合计 3,475,780 字节、39.38798 秒。下载均为 HTTP 200，40 个文件均通过仓库 MD5 和本地 SHA256 核验。真实犊牛来源与人工事件标注有仓库、论文摘要和公开预印本相互支持；这不等于每段都有可审计的兽医确诊标签。

缺少短片段对应的原录音、牛只、栏位、时间和逐段临床记录，所以新数据保留为研究事件样本，`clinicalVerified=false`、`allowForDiseaseLabels=false`，没有训练疾病模型，也没有生成部署固件。

另外完成了 **非疾病声音事件** 的嵌套分组训练：从现有数据选出可映射 ESC-50 上游原录音 ID 的 120 段、86 个原录音组、240 个 2 秒窗口。按原录音隔离后，改进 SVM 的组级准确率为 **94.19%**、宏 F1 为 **0.93318**；同条件原 softmax 基线为 93.02%、0.92057。改进只少错 1 个组，不能宣称统计显著，也不能外推到牛疾病或新牧场。

## 已读现有材料

- [现有来源配置](D:/table/shumuzengxiao/硬件代码/现有硬件演示节点/tools/audio_dataset_sources.json)：仅允许 `Cow -> cow_vocalization`、`Dog/Frog -> non_cattle_audio`；`public_species_label`，禁止疾病标签。
- [现有训练脚本](D:/table/shumuzengxiao/硬件代码/现有硬件演示节点/tools/train_audio_model.py)：8 kHz、2 秒、128 样本特征帧、10 维特征；六个 Goertzel bin 为 2、4、8、16、32、48。
- [v1 数据报告](D:/table/shumuzengxiao/audio-training-data/prepared/kaggle-asc24-v1/dataset_report.json)：352 段，111 牛叫、241 非牛音频。
- [v2 数据报告](D:/table/shumuzengxiao/audio-training-data/prepared/kaggle-asc24-v2/dataset_report.json)：去重后 322 段，100 牛叫、222 非牛音频，288 个原有命名组。
- [v2 模型报告](D:/table/shumuzengxiao/audio-training-data/artifacts/kaggle-asc24-v2/audio_model_metadata.json)：临床核验样本为 0。旧报告有在同一验证集上选择置信度/距离拒识阈值的步骤，本次不沿用该计分方式。
- [论文索引](D:/table/shumuzengxiao/疾病识别生产落地/论文资料/论文索引.json)、[此前检索记录](D:/table/shumuzengxiao/疾病识别生产落地/论文资料/公共音频数据检索记录.md)，以及只读检查当前节点音频实现与配置。

按用户要求读取并应用 `dispatching-parallel-agents` 技能。当前会话未提供子代理派发工具，实际按独立工作项分别核查数据与训练，没有声称运行了不存在的子代理。

## 新增真实咳嗽事件数据

数据集：**AI-Powered Acoustic Surveillance for Early Detection of Calf Respiratory Disease**。

| 项目 | 本次实际核验 |
| --- | --- |
| DOI | [10.57745/FP5LA9](https://doi.org/10.57745/FP5LA9) |
| 公共元数据 API | [Dataverse dataset API](https://entrepot.recherche.data.gouv.fr/api/datasets/:persistentId/?persistentId=doi:10.57745/FP5LA9)，HTTP 200 |
| 版本 | 1.0，RELEASED，发布于 2026-05-30 |
| 提供方 | Mach 等，INRAE、ENVT 等研究机构 |
| 仓库总文件数 | 45：40 个小 WAV、4 个长 WAV、1 个模型检查点 |
| 本次下载 | `cough_001.wav` 至 `cough_020.wav`，`non_cough_001.wav` 至 `non_cough_020.wav` |
| 直链示例 | [cough_001 下载 API](https://entrepot.recherche.data.gouv.fr/api/access/datafile/665257)，HTTP 200；其余 39 条见下载日志 |
| 实际采样格式 | 全部 44,100 Hz、单声道、16-bit PCM |
| 实际时长 | 39 段为 1 秒；`cough_012.wav` 为 0.3879818594 秒 |
| 实际规模 | 40 段、40 个不同 SHA256，合计 3,475,780 字节 |
| 校验 | 40/40 仓库 MD5 匹配，40/40 原始 SHA256、40/40 派生 SHA256 匹配 |
| 仓库许可 | [Etalab Open License 2.0](https://spdx.org/licenses/etalab-2.0.html)，许可页 HTTP 200；保留来源署名与修改说明 |
| 许可范围待确认 | 公开预印本又写明 “research and educational purposes only”，与仓库开放许可表述存在范围差异；本次作为研究证据保存，未确认商业使用权 |
| 标签来源 | 仓库目录、文件名及描述，并由论文 Data Availability 明确确认“20 人工标注咳嗽、20 非咳嗽” |
| 临床级标签 | 未取得逐段临床评分、确诊、兽医签核或原录音对应表；不把 `non_cough` 解释为健康 |
| 录音组 | 每个文件有唯一 `fileUnitId`，但原录音/牛只/会话未知；全部保守放入同一个 `groupId`，不随机拆作独立验证 |

对应论文为 Mach et al. (2026)，*Animal* 20(10):101928，[DOI 10.1016/j.animal.2026.101928](https://doi.org/10.1016/j.animal.2026.101928)。[Europe PMC API](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:42700709&resultType=core&format=json) 返回 HTTP 200，确认作者、标题和摘要；正式出版全文标为订阅访问。

[公开预印本全文](https://www.biorxiv.org/content/10.64898/2026.01.20.700576v1.full) 返回 HTTP 200，Data Availability 明确说明公开仓库仅提供 40 段短音频和四段长录音。论文所述 **1,045 段、308 咳嗽/737 非咳嗽、92% 准确率为作者实验结果**，不是本次下载数量或本次训练结果。论文层面的兽医监测背景不能替代短片段级临床标签映射。

没有下载四个合计约 8.29 GB 的长录音，也没有下载或加载 `.pth` 检查点。没有使用人类咳嗽、合成疾病样本或自行编造兽医信息。

## 其他候选与负结果

| 来源 | 许可/规模证据 | 实际访问与决定 |
| --- | --- | --- |
| [Zenodo 17764250](https://zenodo.org/records/17764250)，既有论文索引中的 569 段/48 类牛生物声学数据 | 元数据含 CC BY 4.0，但明确要求非商业研究 Data Access Agreement；有 cough/respiratory 行为类的论文描述 | API HTTP 200，`access_right=restricted`，公共 `files=[]`；没有取得音频，也没有绕过访问限制 |
| [Figshare 31979640](https://doi.org/10.6084/m9.figshare.31979640)，畜禽咳嗽识别数据 | DataCite DOI 元数据 HTTP 200，描述明确为 calf dataset，CC BY 4.0，133,087,841 字节 | 网页、article API、版本 API 均 HTTP 403；样本数、实际采样率、分组和临床标签未知，未下载归档 |
| [calf-cough-array GitHub](https://github.com/Goosefeatherr/calf-cough-array) | 没有声明许可 | 仓库检索/文件树 HTTP 200，只有空占位文件和短 README，没有音频 |
| Kaggle `cattle cough` | 无可核查候选 | API HTTP 200，结果为空数组 |
| Hugging Face `cattle` | 本次无法核查 | 连接超时；不能把网络失败当作“没有数据” |
| DataCite 牛/犊牛 + wheeze/wheezing | 返回五条相关性弱的 DOI | 未发现可核验的牛喘鸣音频，不下载无关内容 |

其他公开检索包括 GitHub `cattle cough audio`、`calf cough`，DataCite `bovine cough` 与 `(cattle OR bovine OR calf) AND cough AND (audio OR sound)`。所有请求时间、HTTP 状态、响应文件与哈希在 [HTTP 检查日志](D:/table/shumuzengxiao/audio-training-data/external/20261025/evidence/http_checks.jsonl)。这是有边界的检索，不证明其他数据绝不存在。

## 已完成的非疾病训练

任务仅为 `cow_vocalization` 与 `non_cattle_audio`，后者在本实验中只有 dog/frog，不代表全面的牛舍背景噪声。

从已有 v2 322 段中保留文件名与物种标签均可映射到 [ESC-50 官方 metadata](https://api.github.com/repos/karoldvl/ESC-50/contents/meta/esc50.csv) 的 120 段，其余 202 段因本次没有可靠上游录音映射而排除。官方 CSV、README 和 LICENSE 均经 GitHub contents API 实际下载，保存了响应与解码版本。映射依据是来源文件名和官方 `src_file`，本次未重新下载全部 Freesound 原录音逐字节核对。

- 120 文件：40 牛叫、40 狗声、40 蛙声；240 个窗口。
- 86 个官方原录音组：牛叫 27 组、非牛 59 组。
- 外层官方五折，每个原录音只作一次验证；训练/验证组交集为 0。同一录音所有 take、切片和窗口保持在同一折。
- 内层三折 `StratifiedGroupKFold`，只在外层训练组中选择 `C` 和 `gamma`；SVM 固定决策阈值 0，基线 softmax 固定概率阈值 0.5。
- 两种方法使用相同的现有 10 维特征；改进方案为标准化 RBF SVC、类别平衡及每组总样本权重相等。没有基于最终验证标签调拒识阈值。
- 组级结果将一个原录音的所有验证窗口得分取均值，每个原录音计一票；同时另报实际 2 秒窗口结果。

| 模型 | 86 组准确率 | 86 组宏 F1 | 240 窗口准确率 | 240 窗口宏 F1 |
| --- | ---: | ---: | ---: | ---: |
| 原 softmax 基线，重新按严格分组运行 | 0.93023 | 0.92057 | 0.93750 | 0.93074 |
| RBF SVC 改进实验 | 0.94186 | 0.93318 | 0.94167 | 0.93478 |

组级混淆矩阵行是真实标签、列是预测，顺序均为 `[cow_vocalization, non_cattle_audio]`：基线 `[[25,2],[4,55]]`，改进 `[[25,2],[3,56]]`。改进模型牛叫精确率 0.89286、召回率 0.92593、F1 0.90909。

2,000 次按原录音组配对 bootstrap 得到宏 F1 差值的条件 95% 区间 `[0.00000, 0.04210]`。区间含 0，且没有重新抽取牧场/动物，不代表跨牧场泛化或显著进步。不要与旧 322 段验证集的分数直接比较。

许可核查还发现：这 120 段中的 dog 属于 ESC-10，40 段按 CC BY 3.0；cow/frog 共 80 段属于 ESC-50 的 CC BY-NC 3.0 范围。上游逐片段来源署名见 input manifest 的 `upstreamAttribution` 和 `evidence/esc50-LICENSE.txt`。Kaggle CC0 声明不能自动覆盖上游限制；本实验属于非商业研究验证，未确认商业部署授权。

运行环境：Python 3.13.14、NumPy 2.4.3、SciPy 1.17.1、scikit-learn 1.8.0。训练报告保存了输入 manifest、特征提取脚本的 SHA256、全部内层候选分数、各外层折参数、逐窗口和逐组预测。保存的是可数值还原的 `.npz` 参数，没有生成固件头文件。

## 与 INMP441 的兼容性

40 段新数据均已通过带抗混叠滤波的 `scipy.signal.resample_poly` 转为 **8 kHz、单声道、16-bit、16,000 样本的 2 秒容器**，派生与原始各自保存，manifest 记录了填零量。1 秒片段补 8,000 个零样本；约 0.388 秒片段补 12,896 个零样本。补零不会产生新的 2 秒现场录音，也不会增加独立样本数。

现有 INMP441 输入为 16 kHz I2S，固件做 2:1 抽取后以 8 kHz 累计 128 样本帧，2 秒窗口；本次非疾病训练复用了现有 10 维提取器。这证明数据格式/窗口可用，不证明现场分布相同。

8 kHz 的 Nyquist 上限为 4 kHz。实测新数据全片去均值后 FFT 能量中，4 kHz 以上比例的中位数为 **3.94%**，范围 **0.30% 至 55.29%**；降采样可能丢失重要信息。作者 HuBERT 路径采用 16 kHz 输入，作者的 92% 结果不能直接套到当前 8 kHz/10 维模型。

固件上传片段还有 `INMP441_CAPTURE_GAIN=8` 的放大和有符号 8-bit 量化，特征路径则使用量化前样本；软件逐窗去均值也与硬件流式 DC 校正存在差异。公开短片段到 INMP441 的麦克风频响、增益、量化、牛舍噪声与切窗方式尚未做现场校准。本次没有验证或修改这些硬件行为。

## 产物与复现

全部新增数据与实验在 [external/20261025](D:/table/shumuzengxiao/audio-training-data/external/20261025/)：

- `raw/rdg-FP5LA9/`：40 个原始 WAV。
- `derived/rdg-FP5LA9-8khz-2s/`：40 个派生 WAV。
- `manifest.jsonl`：40 行，包含 source、group、作者事件标签、临床缺失字段、许可、原始与派生哈希。
- `source-records.json`：本次各来源的可达性、许可与准入决定。
- `evidence/`：原始 API/网页响应、下载检查、论文证据摘录、上游录音 metadata 与许可。
- `experiment/`：严格分组输入 manifest、特征、五折模型参数、窗口/组预测和 `training-report.json`。
- `verification.json`：40 原始/40 派生格式与哈希核验、120 现有输入哈希核验、240 个保存模型预测复算、两套组指标复算均通过。
- `SHA256SUMS.txt`：该 external 目录内除清单自身外的逐文件 SHA256；后续重新生成结果时需同步更新。

主 manifest SHA256：`12eef566e91552e380536581c930be7bcbd5f427bc0c832d12297bdc22dc73e6`。

脚本为 [audio_dataset_research_20261025.py](D:/table/shumuzengxiao/scripts/audio_dataset_research_20261025.py)。已实际执行的主要命令如下；首次重建时先执行 `query` 获取用到的 API 响应，现有响应均已留档：

```powershell
python -X utf8 D:\table\shumuzengxiao\scripts\audio_dataset_research_20261025.py collect-dataverse
python -X utf8 D:\table\shumuzengxiao\scripts\audio_dataset_research_20261025.py train-events
python -X utf8 D:\table\shumuzengxiao\scripts\audio_dataset_research_20261025.py audit
python -X utf8 D:\table\shumuzengxiao\scripts\audio_dataset_research_20261025.py checksums
```

脚本不使用登录凭据，HTTP 会话禁用 `.netrc`，不会输出已有密钥；重定向 URL 中敏感查询字段会被遮蔽。训练依赖只读取既有脚本函数，不运行其命令行主流程。

写入范围仅限本脚本、本报告和 external 新目录。没有打开串口，没有启动/停止后端，没有修改业务文件或硬件/固件头文件。

## 尚缺的疾病证据

需要取得短片段到原录音时间戳、录音会话、匿名牛只、栏位和日期的对应表；人工事件标注者/复核方式；与片段对应的兽医签核、临床参考标准及证据编号。`cough` 是事件，不能自行升级成 BRD、病原或疾病严重程度；`non_cough` 也不能作为健康诊断。

还缺牛喘鸣/其他异常呼吸音的明确真实样本与可靠正常呼吸/牛舍背景对照，以及独立牛只、日期、栏舍、牧场上的保留验证。当前新数据缺少可审计分组，因此没有给出新咳嗽数据的伪独立验证准确率。

未来疾病模型还需要解决许可表述冲突、8 kHz 信息损失和实际 INMP441 采集分布，最后经过现有临床 lineage/release gate；本次未满足疾病部署条件。
