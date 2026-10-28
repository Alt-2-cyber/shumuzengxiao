package com.shumuzengxiao.smartcattle.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/models")
public class ModelController {
    @GetMapping
    public List<Map<String, Object>> models() {
        return List.of(
                model(
                        "name", "cattle-appearance-yolov8-research",
                        "version", "appearance-expanded-20261026-v1",
                        "task", "三类牛体外观分类研究（YOLOv8n-cls）",
                        "device", "MaixCAM candidate",
                        "status", "research_only",
                        "statusLabel", "已转换，待实机验证",
                        "scope", "公开外观标签分类；无病灶定位或疾病确诊能力",
                        "metricsAvailable", true,
                        "primaryMetricLabel", "新来源 Accuracy",
                        "primaryMetric", 0.9001610306,
                        "secondaryMetricLabel", "新来源 Macro-F1",
                        "secondaryMetric", 0.8199855589,
                        "metricsNote", "新来源621图：旧版86.80%、新版90.02%；原413图测试新版91.28%。新增下载7433图，跨库去重后274个新图像组进入训练。已生成 .mud/.cvimodel，尚无设备运行验证。",
                        "releaseState", "research_only",
                        "releaseReasons", List.of("无独立牛只/牧场临床验证", "新来源口蹄疫标签仅7图", "待摄像头实机验收")),
                model(
                        "name", "calf-cough-event-research",
                        "version", "audio-calf-cough-expanded-20261026-v1",
                        "task", "犊牛咳嗽/非咳嗽声学事件研究",
                        "device", "Backend / 8kHz WAV",
                        "status", "research_only",
                        "statusLabel", "已接入录音分析（研究）",
                        "scope", "独立于设备原标签的研究输出；非咳嗽不表示健康",
                        "metricsAvailable", true,
                        "primaryMetricLabel", "保留集 Accuracy",
                        "primaryMetric", 0.8793103448,
                        "secondaryMetricLabel", "保留集 Macro-F1",
                        "secondaryMetric", 0.8611016079,
                        "metricsNote", "新增725段原始录音，清理后共552段；378开发、174保留，咳嗽召回率83.72%。文件名推断组不等于独立牛只，连续一秒切窗尚未现场验证。",
                        "releaseState", "research_only",
                        "releaseReasons", List.of("牛只/录音会话身份未知", "需连续牛舍音频和实际麦克风验证", "不进入疾病融合")),
                model(
                        "name", "cattle-motion-temporal-research",
                        "version", "motion-temporal-20261026-v1",
                        "task", "颈部四类行为时间窗口研究",
                        "device", "ESP32-S3 candidate",
                        "status", "research_only",
                        "statusLabel", "固件已编译，待设备验证",
                        "scope", "4秒颈部XYZ窗口、24维特征；保留原有站卧和六类行为输出",
                        "metricsAvailable", true,
                        "primaryMetricLabel", "分牛 Accuracy",
                        "primaryMetric", 0.8579481398,
                        "secondaryMetricLabel", "分牛 Macro-F1",
                        "secondaryMetric", 0.8386286691,
                        "metricsNote", "6牛共1391224个原始点；4牛训练、2牛887窗测试。同条件旧点分类55.47%、时序85.79%。已导出ESP32代码，非三位置联合或临床跛行模型。",
                        "releaseState", "research_only",
                        "releaseReasons", List.of("仅单场单日6牛", "需本地安装方向与采样带宽验证", "缺少三位置同步临床标签")),
                model(
                        "name", "maixcam-cattle-detector",
                        "version", "cattle-yolov8-coco-v1",
                        "task", "MaixCAM 牛只目标检测与框选",
                        "device", "MaixCAM",
                        "status", "deployed",
                        "statusLabel", "已部署（仅牛只检测）",
                        "scope", "仅 cow 目标检测，不输出姿态或疾病结论",
                        "metricsAvailable", false,
                        "metricsStatus", "目标检测已部署",
                        "metricsNote", "当前 .mud/.cvimodel 来自 MaixCAM COCO YOLOv8n，支持 cow 类别；不支持站立、卧倒、跛行、蹄部病灶或口蹄疫识别"),
                model(
                        "name", "cattle-audio-screening",
                        "version", "cattle-vocalization-baseline-v2-bedc334739f4",
                        "task", "牛声/非牛声事件筛查；咳嗽、喘鸣和异常鸣叫疾病标签仍禁用",
                        "device", "ESP32/Backend",
                        "status", "feature_only",
                        "statusLabel", "事件筛查（非疾病）",
                        "scope", "仅生成 cow_vocalization 事件和可回放证据，不进入疾病风险",
                        "metricsAvailable", true,
                        "primaryMetricLabel", "公开 Accuracy",
                        "primaryMetric", 0.824,
                        "secondaryMetricLabel", "公开 Macro-F1",
                        "secondaryMetric", 0.8179363,
                        "metricsNote", "公开牛声/非牛声基线；无兽医咳嗽、喘鸣签核数据，服务端不会批准疾病标签",
                        "releaseState", "not_ready",
                        "releaseReasons", List.of("缺少兽医签核的咳嗽/喘鸣录音", "缺少按牛只、栏舍、日期隔离的外部测试")),
                model(
                        "name", "cattle-posture-rf",
                        "version", "posture-binary-rf-v2",
                        "task", "站立/卧倒二分类姿态筛查；背部倾角与腿部活动用于物理交叉检查",
                        "device", "ESP32-S3",
                        "status", "deployed",
                        "statusLabel", "已部署（行为筛查）",
                        "scope", "姿态/行为筛查，不用于跛行或疾病诊断",
                        "metricsAvailable", true,
                        "primaryMetricLabel", "Accuracy",
                        "primaryMetric", 0.8691,
                        "secondaryMetricLabel", "Macro-F1",
                        "secondaryMetric", 0.8555,
                        "metricsNote", "连续行为段隔离测试指标；公开数据只有一个加速度计，固件应用于颈部传感器，不能代表本地牛群或疾病识别性能"),
                model(
                        "name", "lameness-multimodal-screening",
                        "version", "untrained-three-position-accel-lameness-v1",
                        "task", "三位置 IMU 异常 + 经验证的步态/蹄部视觉证据，生成跛行筛查候选",
                        "device", "ESP32/MaixCam/Backend",
                        "status", "not_trained",
                        "statusLabel", "未训练（临床数据采集中）",
                        "scope", "仅保留运动异常关注，尚不能输出跛行疑似",
                        "metricsAvailable", false,
                        "metricsStatus", "未训练",
                        "metricsNote", "仅 IMU 异常保持活动关注；只有有效视觉证据和本地临床验证后才可输出 lameness_suspect",
                        "releaseState", "not_ready",
                        "releaseReasons", List.of("没有合格的三位置 20 Hz IMU 会话", "缺少同步步态视频和蹄部检查", "缺少外部动物测试")),
                model(
                        "name", "fmd-emergency-triage",
                        "version", "rule-gated-v1",
                        "task", "口蹄疫疑似事件分诊：蹄/口鼻病灶视觉证据 + 跛行候选 + 人工复测核心体温",
                        "device", "MaixCam/Backend",
                        "status", "triage_only",
                        "statusLabel", "仅分诊",
                        "scope", "生成疑似分诊，不输出阳性或阴性诊断",
                        "metricsAvailable", false,
                        "metricsStatus", "仅分诊",
                        "metricsNote", "不输出 FMD 阳性或阴性；必须由兽医、主管部门和法定实验室检测确认",
                        "releaseState", "triage_only",
                        "releaseReasons", List.of("必须由兽医检查和法定实验室确认", "不能自动解除隔离或输出阴性结论")) ,
                model(
                        "name", "cattle-skin-lesion-research",
                        "version", "lumpy-skin-research-dd36286fdeb3",
                        "task", "牛结节性皮肤病图像研究基线",
                        "device", "Training only",
                        "status", "research_only",
                        "statusLabel", "研究基线（禁止部署）",
                        "scope", "仅用于图像训练链路验证，不是 FMD 或临床诊断模型",
                        "metricsAvailable", true,
                        "primaryMetricLabel", "外部 Accuracy",
                        "primaryMetric", 0.6282,
                        "secondaryMetricLabel", "外部 Macro-F1",
                        "secondaryMetric", 0.6048,
                        "metricsNote", "公开文件夹数据无动物/牧场分组和兽医签核，未生成 .mud，不进入三源疾病融合",
                        "releaseState", "research_only",
                        "releaseReasons", List.of("缺少动物/牧场分组", "缺少兽医签核", "没有 MaixCAM .mud 产物")),
                model(
                        "name", "cattle-disease-multiclass-research",
                        "version", "cattle-disease-research-797d5d9b4cbc",
                        "task", "FMD/健康/结节性皮肤病图像研究基线",
                        "device", "Training only",
                        "status", "research_only",
                        "statusLabel", "研究基线（禁止部署）",
                        "scope", "公开文件夹标签的研究分类，不输出 FMD 阳性/阴性",
                        "metricsAvailable", true,
                        "primaryMetricLabel", "外部 Accuracy",
                        "primaryMetric", 0.6857,
                        "secondaryMetricLabel", "外部 Macro-F1",
                        "secondaryMetric", 0.6915,
                        "metricsNote", "无动物/牧场/日期分组和临床签核，未生成 .mud，不进入三源疾病融合",
                        "releaseState", "research_only",
                        "releaseReasons", List.of("公开目录标签不等于临床确诊", "缺少动物/牧场/日期分组", "没有 MaixCAM .mud 产物")),
                model(
                        "name", "disease-screening-rule",
                        "version", "disease-screen-v1",
                        "task", "多模态个体化健康风险筛查（非诊断）",
                        "device", "Backend",
                        "status", "screening_only",
                        "statusLabel", "风险筛查",
                        "scope", "基于个体基线的证据融合和复核建议",
                        "metricsAvailable", false,
                        "metricsStatus", "未标定",
                        "metricsNote", "需使用疾病/兽医结局标注数据完成独立验证后，才能报告性能指标")
        );
    }

    private static Map<String, Object> model(Object... entries) {
        if (entries.length % 2 != 0) {
            throw new IllegalArgumentException("model metadata must contain key/value pairs");
        }
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index < entries.length; index += 2) {
            result.put(String.valueOf(entries[index]), entries[index + 1]);
        }
        return result;
    }
}
