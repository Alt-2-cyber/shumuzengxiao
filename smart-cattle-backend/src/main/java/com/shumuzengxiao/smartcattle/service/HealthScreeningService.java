package com.shumuzengxiao.smartcattle.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.shumuzengxiao.smartcattle.domain.HealthScreeningObservation;
import com.shumuzengxiao.smartcattle.domain.Severity;
import com.shumuzengxiao.smartcattle.repository.HealthScreeningObservationRepository;
import jakarta.annotation.PostConstruct;
import jakarta.transaction.Transactional;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Deque;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.NavigableMap;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.TreeMap;

/**
 * Converts live behavior telemetry into individualized health-screening evidence.
 * This is deliberately a conservative screening layer, not a disease diagnosis.
 */
@Service
public class HealthScreeningService {
    private static final String VERSION = "disease-screen-v1";
    private static final long BASELINE_BUCKET_MINUTES = 5;
    private static final int MIN_MOTION_SAMPLES_PER_BASELINE_BUCKET = 30;
    private static final double MIN_CURRENT_MOTION_COVERAGE = 0.75;
    private static final double EPSILON = 1e-6;

    private final ConcurrentMap<String, HealthProfile> profiles = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, Map<String, Object>> latestScreens = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, VisionEvidence> visionEvidence = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, AudioEvidence> audioEvidence = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, ClinicalEvidence> clinicalEvidence = new ConcurrentHashMap<>();
    private final HealthScreeningObservationRepository observationRepository;

    public HealthScreeningService() {
        this(null);
    }

    @Autowired
    public HealthScreeningService(HealthScreeningObservationRepository observationRepository) {
        this.observationRepository = observationRepository;
    }

    @Value("${health.screening.current-window-minutes:30}")
    private int currentWindowMinutes = 30;

    @Value("${health.screening.baseline-retention-days:7}")
    private int baselineRetentionDays = 7;

    @Value("${health.screening.minimum-baseline-minutes:60}")
    private int minimumBaselineMinutes = 60;

    @Value("${health.screening.minimum-current-window-minutes:10}")
    private int minimumCurrentWindowMinutes = 10;

    @Value("${health.screening.vision-evidence-max-minutes:30}")
    private int visionEvidenceMaxMinutes = 30;

    @Value("${health.screening.audio-evidence-max-minutes:30}")
    private int audioEvidenceMaxMinutes = 30;

    @Value("${health.screening.clinical-evidence-max-hours:24}")
    private int clinicalEvidenceMaxHours = 24;

    @PostConstruct
    void restorePersistedBaseline() {
        if (observationRepository == null) {
            return;
        }
        Instant cutoff = Instant.now().minus(Duration.ofDays(Math.max(1, baselineRetentionDays)));
        ScreeningConfig config = config();
        for (HealthScreeningObservation observation : observationRepository
                .findByReceivedAtAfterOrderByReceivedAtAsc(cutoff)) {
            Sample sample = sampleFromObservation(observation);
            if (!isCattleObservation(sample)) {
                continue;
            }
            profiles.computeIfAbsent(sample.targetId(), ignored -> new HealthProfile())
                    .restore(sample, config);
        }
    }

    @Scheduled(fixedDelayString = "${health.screening.observation-cleanup-ms:3600000}")
    @Transactional
    void purgeExpiredObservations() {
        if (observationRepository == null) {
            return;
        }
        observationRepository.deleteByReceivedAtBefore(
                Instant.now().minus(Duration.ofDays(Math.max(1, baselineRetentionDays))));
    }

    /**
     * Vision evidence can strengthen a screening candidate but cannot establish
     * a diagnosis. Events expire so stale detections cannot raise new alerts.
     */
    public void recordVisionEvidence(String targetId, String eventType, Double score, Instant recordedAt) {
        if (targetId == null || targetId.isBlank() || eventType == null || eventType.isBlank()) {
            return;
        }
        visionEvidence.compute(targetId.trim(), (ignored, current) -> {
            VisionEvidence next = current == null ? new VisionEvidence() : current;
            next.record(eventType.trim(), score == null ? 0.0 : score, recordedAt == null ? Instant.now() : recordedAt);
            return next;
        });
    }

    /**
     * Stores a deduplicated edge audio event. The event is visible as evidence
     * immediately, but only an approved respiratory or abnormal-vocalization
     * label can affect individual screening. A missing cattle ID is
     * intentionally ignored for individual fusion while the raw event remains
     * archived by AudioEventService.
     */
    public void recordAudioEvidence(
            String targetId,
            String label,
            Double score,
            boolean diseaseEligible,
            Instant recordedAt,
            String evidenceId
    ) {
        if (targetId == null || targetId.isBlank() || label == null || label.isBlank()) {
            return;
        }
        String normalizedTarget = targetId.trim();
        Instant timestamp = recordedAt == null ? Instant.now() : recordedAt;
        audioEvidence.compute(normalizedTarget, (ignored, current) -> {
            AudioEvidence next = current == null ? new AudioEvidence() : current;
            next.record(label.trim(), score == null ? 0.0 : score, diseaseEligible, timestamp, evidenceId);
            return next;
        });

        // The next telemetry frame recomputes risks. This lightweight update
        // keeps the live source matrix truthful between frames as well.
        Map<String, Object> latest = latestScreens.get(normalizedTarget);
        if (latest != null) {
            latest.put("audio", audioEvidence.get(normalizedTarget)
                    .snapshot(timestamp, Math.max(5, audioEvidenceMaxMinutes)).metrics());
            latest.put("fusionPendingRefresh", true);
        }
    }

    /** Records a human-performed check without injecting a fake telemetry frame. */
    public void recordClinicalCheck(
            String targetId,
            String checkType,
            boolean verified,
            boolean alert,
            Double value,
            String evidenceType,
            Instant recordedAt
    ) {
        if (targetId == null || targetId.isBlank() || checkType == null || checkType.isBlank()) {
            return;
        }
        clinicalEvidence.compute(targetId.trim(), (ignored, current) -> {
            ClinicalEvidence next = current == null ? new ClinicalEvidence() : current;
            next.record(checkType.trim(), verified, alert, value, evidenceType,
                    recordedAt == null ? Instant.now() : recordedAt);
            return next;
        });
    }

    public Map<String, Object> evaluate(ObjectNode telemetry, Instant receivedAt) {
        Sample sample = Sample.from(telemetry, receivedAt);
        HealthProfile profile = profiles.computeIfAbsent(sample.targetId(), ignored -> new HealthProfile());
        ScreeningConfig config = config();
        Map<String, Object> screen;
        synchronized (profile) {
            VisionEvidence evidence = visionEvidence.get(sample.targetId());
            AudioEvidence audio = audioEvidence.get(sample.targetId());
            ClinicalEvidence clinical = clinicalEvidence.get(sample.targetId());
            screen = profile.record(
                    sample,
                    config,
                    evidence == null ? VisionSnapshot.empty() : evidence.snapshot(receivedAt, config.visionEvidenceMaxMinutes()),
                    audio == null ? AudioSnapshot.empty() : audio.snapshot(receivedAt, config.audioEvidenceMaxMinutes()),
                    clinical == null ? ClinicalSnapshot.empty(config.clinicalEvidenceMaxHours())
                            : clinical.snapshot(receivedAt, config.clinicalEvidenceMaxHours()));
        }
        latestScreens.put(sample.targetId(), screen);
        persistObservation(sample);
        return screen;
    }

    private void persistObservation(Sample sample) {
        if (observationRepository == null || !isCattleObservation(sample)) {
            return;
        }
        HealthScreeningObservation observation = new HealthScreeningObservation();
        observation.setTargetId(sample.targetId());
        observation.setReceivedAt(sample.receivedAt());
        observation.setMotionAvailable(sample.motionAvailable());
        observation.setBehavior(sample.behavior());
        observation.setBehaviorConfidence(sample.behaviorConfidence());
        observation.setActivity(sample.activity());
        observation.setSurfaceTemperature(sample.surfaceTemperature());
        observation.setLamenessModelDeployed(sample.lamenessModelDeployed());
        observation.setLamenessCandidate(sample.lamenessCandidate());
        observation.setLamenessRejected(sample.lamenessRejected());
        observation.setLamenessScore(sample.lamenessScore());
        observation.setMicrophoneAvailable(sample.microphoneAvailable());
        observation.setVocalizationCandidate(sample.vocalizationCandidate());
        observation.setAudioModelDeployed(sample.audioModelDeployed());
        observation.setRespiratoryCandidate(sample.respiratoryCandidate());
        observation.setAbnormalVocalizationCandidate(sample.abnormalVocalizationCandidate());
        try {
            observationRepository.save(observation);
        } catch (RuntimeException ignored) {
            // A database write must not drop the live screening frame.
        }
    }

    private static boolean isCattleObservation(Sample sample) {
        return sample.motionAvailable() || sample.microphoneAvailable()
                || sample.lamenessModelDeployed() || sample.audioModelDeployed();
    }

    private static Sample sampleFromObservation(HealthScreeningObservation observation) {
        return new Sample(
                observation.getTargetId(),
                observation.getReceivedAt(),
                Boolean.TRUE.equals(observation.getMotionAvailable()),
                observation.getBehavior() == null ? "sensors_missing" : observation.getBehavior(),
                observation.getBehaviorConfidence() == null ? 0.0 : observation.getBehaviorConfidence(),
                observation.getActivity(),
                observation.getSurfaceTemperature(),
                Boolean.TRUE.equals(observation.getLamenessModelDeployed()),
                Boolean.TRUE.equals(observation.getLamenessCandidate()),
                Boolean.TRUE.equals(observation.getLamenessRejected()),
                observation.getLamenessScore(),
                Boolean.TRUE.equals(observation.getMicrophoneAvailable()),
                Boolean.TRUE.equals(observation.getVocalizationCandidate()),
                Boolean.TRUE.equals(observation.getAudioModelDeployed()),
                Boolean.TRUE.equals(observation.getRespiratoryCandidate()),
                Boolean.TRUE.equals(observation.getAbnormalVocalizationCandidate()));
    }

    public Map<String, Object> snapshot(String targetId) {
        if (targetId != null && !targetId.isBlank()) {
            return latestScreens.getOrDefault(targetId, waitingSnapshot(targetId));
        }
        return latestScreens.entrySet().stream()
                .max(Comparator.comparing(entry -> String.valueOf(entry.getValue().get("updatedAt"))))
                .map(Map.Entry::getValue)
                .orElseGet(() -> waitingSnapshot("-"));
    }

    private ScreeningConfig config() {
        return new ScreeningConfig(
                Math.max(10, currentWindowMinutes),
                Math.max(1, baselineRetentionDays),
                Math.max(30, minimumBaselineMinutes),
                Math.max(1, minimumCurrentWindowMinutes),
                Math.max(5, visionEvidenceMaxMinutes),
                Math.max(5, audioEvidenceMaxMinutes),
                Math.max(1, clinicalEvidenceMaxHours));
    }

    private Map<String, Object> waitingSnapshot(String targetId) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("version", VERSION);
        result.put("targetId", targetId);
        result.put("mode", "WAITING_FOR_TELEMETRY");
        result.put("riskLevel", Severity.NORMAL.name());
        result.put("score", 0.0);
        result.put("dataQuality", "INVALID");
        result.put("message", "等待 ESP32 行为与健康遥测数据");
        result.put("risks", List.of());
        result.put("vision", Map.of("activeEvents", Map.of(), "maximumAgeMinutes", 0));
        result.put("audio", Map.of(
                "activeEvents", Map.of(),
                "respiratoryCandidate", false,
                "vocalizationCandidate", false,
                "maximumAgeMinutes", 0));
        result.put("sources", Map.of());
        result.put("fusion", Map.of("decisionScope", "screening_only", "participatingSources", List.of()));
        result.put("clinicalRequirements", List.of("需要兽医或授权人员复核"));
        result.put("decisionScope", "screening_only");
        result.put("updatedAt", null);
        return result;
    }

    private static final class HealthProfile {
        private final Deque<Sample> recent = new ArrayDeque<>();
        private final NavigableMap<Long, Aggregate> buckets = new TreeMap<>();

        Map<String, Object> record(
                Sample sample,
                ScreeningConfig config,
                VisionSnapshot vision,
                AudioSnapshot audio,
                ClinicalSnapshot clinical
        ) {
            recent.addLast(sample);
            pruneRecent(sample.receivedAt().minus(Duration.ofMinutes(config.currentWindowMinutes())));

            long bucketKey = bucketKey(sample.receivedAt());
            buckets.computeIfAbsent(bucketKey, ignored -> new Aggregate()).add(sample);
            pruneBuckets(bucketKey - config.baselineRetentionDays() * 24L * 60L / BASELINE_BUCKET_MINUTES);

            Aggregate current = Aggregate.from(recent);
            Aggregate baseline = new Aggregate();
            Instant currentWindowStart = sample.receivedAt().minus(Duration.ofMinutes(config.currentWindowMinutes()));
            int baselineBucketCount = 0;
            for (Aggregate bucket : buckets.values()) {
                if (!bucket.endsBefore(currentWindowStart)
                        || !bucket.hasSufficientMotionCoverage(MIN_MOTION_SAMPLES_PER_BASELINE_BUCKET)) {
                    continue;
                }
                baseline.merge(bucket);
                baselineBucketCount++;
            }

            long currentMinutes = current.windowMinutes();
            long baselineMinutes = baselineBucketCount * BASELINE_BUCKET_MINUTES;
            boolean motionAvailable = current.motionSamples > 0;
            boolean currentMotionCoverageReady = current.hasSufficientMotionCoverage(MIN_CURRENT_MOTION_COVERAGE);
            boolean baselineReady = baselineMinutes >= config.minimumBaselineMinutes()
                    && baseline.behaviorSamples >= 12;
            boolean currentReady = currentMinutes >= config.minimumCurrentWindowMinutes()
                    && current.behaviorSamples >= 6
                    && currentMotionCoverageReady;

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("version", VERSION);
            result.put("targetId", sample.targetId());
            result.put("updatedAt", sample.receivedAt().toString());
            result.put("windowMinutes", config.currentWindowMinutes());
            result.put("currentWindowMinutes", currentMinutes);
            result.put("windowSamples", current.observations);
            result.put("baselineMinutes", baselineMinutes);
            result.put("baselineRetentionDays", config.baselineRetentionDays());
            result.put("minimumBaselineMinutes", config.minimumBaselineMinutes());
            result.put("minimumCurrentWindowMinutes", config.minimumCurrentWindowMinutes());
            result.put("minimumObservationMinutes",
                    config.minimumBaselineMinutes() + config.currentWindowMinutes());
            result.put("current", current.metrics());
            result.put("baseline", baseline.metrics());
            result.put("vision", vision.metrics());
            result.put("audio", audio.metrics());
            result.put("clinical", clinical.metrics());
            result.put("sources", sourceMetrics(sample, current, vision, audio, clinical));
            result.put("fusion", fusionMetrics(sample, current, vision, audio, clinical));
            result.put("clinicalRequirements", List.of(
                    "风险结果仅用于筛查和分诊，不构成疾病确诊",
                    "B-1 体表温度异常必须用标准核心体温复测",
                    "跛行和口蹄疫疑似必须由兽医检查；口蹄疫还需法定实验室确认"));
            result.put("decisionScope", "screening_only");
            String audioLimitation = sample.audioModelDeployed()
                    ? "声音分类结果仅作为咳嗽、喘鸣或异常鸣叫候选，仍需结合录音、临床症状和兽医复核。"
                    : "当前麦克风处于特征采集模式，尚未部署经验证的咳嗽、喘鸣或异常鸣叫分类器。";
            result.put("limitations", List.of(
                    "本结果用于健康风险筛查，不构成疾病确诊。",
                    "B-1 为非接触体表温度，需用标准临床体温复核。",
                    audioLimitation,
                    "口蹄疫仅能生成疑似分诊；法定报告、兽医检查和实验室检测才能确认或排除。"));

            if (!motionAvailable || !currentMotionCoverageReady) {
                result.put("mode", "DATA_UNAVAILABLE");
                result.put("riskLevel", Severity.NORMAL.name());
                result.put("score", 0.0);
                result.put("dataQuality", "INVALID");
                result.put("message", "三位置运动数据覆盖不足，暂不计算健康风险");
                result.put("risks", List.of());
                return result;
            }

            String dataQuality = quality(current, baselineReady, currentReady);
            result.put("dataQuality", dataQuality);

            if (!baselineReady || !currentReady) {
                result.put("mode", "BASELINE_LEARNING");
                result.put("riskLevel", Severity.NORMAL.name());
                result.put("score", 0.0);
                result.put("message", learningMessage(current, baselineMinutes, config));
                result.put("risks", List.of());
                return result;
            }

            List<Map<String, Object>> risks = evaluateRisks(current, baseline, vision, audio, clinical);
            double score = risks.stream()
                    .mapToDouble(risk -> ((Number) risk.get("score")).doubleValue())
                    .max()
                    .orElse(0.0);
            if (risks.size() >= 2) {
                score = Math.min(1.0, score + Math.min(0.15, (risks.size() - 1) * 0.05));
            }

            Severity level = overallSeverity(score, risks.size());
            result.put("mode", "SCREENING");
            result.put("riskLevel", level.name());
            result.put("score", round(score));
            result.put("message", risks.isEmpty()
                    ? "当前窗口未发现相对个体基线的持续异常"
                    : "发现 " + risks.size() + " 项需要人工复核的健康风险证据");
            result.put("risks", risks);
            return result;
        }

        void restore(Sample sample, ScreeningConfig config) {
            recent.addLast(sample);
            pruneRecent(sample.receivedAt().minus(Duration.ofMinutes(config.currentWindowMinutes())));
            long bucketKey = bucketKey(sample.receivedAt());
            buckets.computeIfAbsent(bucketKey, ignored -> new Aggregate()).add(sample);
            pruneBuckets(bucketKey - config.baselineRetentionDays() * 24L * 60L / BASELINE_BUCKET_MINUTES);
        }

        private List<Map<String, Object>> evaluateRisks(
                Aggregate current,
                Aggregate baseline,
                VisionSnapshot vision,
                AudioSnapshot audio,
                ClinicalSnapshot clinical) {
            List<Map<String, Object>> risks = new ArrayList<>();

            Double grazingDrop = relativeDrop(baseline.grazingRatio(), current.grazingRatio());
            Double ruminationDrop = relativeDrop(baseline.ruminationRatio(), current.ruminationRatio());
            Double activityDrop = relativeDrop(baseline.averageActivity(), current.averageActivity());
            Double lyingIncrease = difference(current.lyingRatio(), baseline.lyingRatio());
            Double lamenessCandidateIncrease = difference(
                    current.lamenessCandidateRate(), baseline.lamenessCandidateRate());
            Double temperatureDelta = difference(current.averageSurfaceTemperature(), baseline.averageSurfaceTemperature());
            Double vocalizationIncrease = difference(current.vocalizationRate(), baseline.vocalizationRate());
            Double respiratoryCandidateIncrease = difference(
                    current.respiratoryCandidateRate(), baseline.respiratoryCandidateRate());
            Double abnormalVocalizationCandidateIncrease = difference(
                    current.abnormalVocalizationCandidateRate(), baseline.abnormalVocalizationCandidateRate());

            double feedingEvidence = Math.max(orZero(grazingDrop), orZero(ruminationDrop));
            if (feedingEvidence >= 0.35) {
                double score = clamp(0.22 + feedingEvidence * 0.55 + orZero(ruminationDrop) * 0.18);
                List<String> evidence = new ArrayList<>();
                if (grazingDrop != null) {
                    evidence.add("采食行为较个体基线下降 " + percent(grazingDrop));
                }
                if (ruminationDrop != null) {
                    evidence.add("反刍行为较个体基线下降 " + percent(ruminationDrop));
                }
                evidence.add("当前窗口为 " + current.windowMinutes() + " 分钟");
                risks.add(risk(
                        "feeding_rumination_attention",
                        "采食/反刍下降关注",
                        score,
                        evidence,
                        "复核饲喂、饮水、粪便和反刍情况；持续异常时请兽医检查消化与代谢状态。"));
            }

            boolean mobilityAnomaly = activityDrop != null && activityDrop >= 0.40
                    && lyingIncrease != null && lyingIncrease >= 0.10;
            boolean deployedLamenessCandidate = current.lamenessModelSamples >= 2
                    && current.lamenessCandidateSamples >= 2
                    && (lamenessCandidateIncrease == null || lamenessCandidateIncrease >= 0.10);
            boolean mobilityEvidence = mobilityAnomaly || deployedLamenessCandidate;
            if (mobilityEvidence) {
                double score = mobilityAnomaly
                        ? clamp(0.18 + activityDrop * 0.58 + lyingIncrease * 0.38)
                        : 0.0;
                boolean gaitEvidence = vision.has("gait_abnormal_suspect") || vision.has("hoof_lesion_suspect")
                        || clinical.has("gait_abnormal_suspect") || clinical.has("hoof_lesion_suspect");
                List<String> evidence = new ArrayList<>();
                if (mobilityAnomaly) {
                    evidence.add("运动活动较个体基线下降 " + percent(activityDrop));
                    evidence.add("卧姿比例较个体基线增加 " + percent(lyingIncrease));
                }
                if (deployedLamenessCandidate) {
                    score = clamp(Math.max(score, 0.48 + orZero(lamenessCandidateIncrease) * 0.32));
                    evidence.add("已批准三位置 IMU 模型在当前窗口输出 "
                            + current.lamenessCandidateSamples + " 次跛行筛查候选");
                    if (current.averageLamenessScore() != null) {
                        evidence.add("当前 IMU 候选平均分数 " + percent(current.averageLamenessScore()));
                    }
                }
                if (gaitEvidence) {
                    evidence.add("有效步态/蹄部证据："
                            + evidenceDescription(vision, clinical, "gait_abnormal_suspect", "hoof_lesion_suspect"));
                    if (deployedLamenessCandidate) {
                        evidence.add("跛行筛查候选不能确定病灶或跛行侧别");
                    } else {
                        evidence.add("尚未有经批准的三位置 IMU 候选，只能保留为运动异常关注");
                    }
                } else {
                    evidence.add("缺少新鲜步态或蹄部视觉证据，不能升级为跛行疑似");
                }
                boolean confirmedLamenessScreeningEvidence = deployedLamenessCandidate && gaitEvidence;
                risks.add(risk(
                        confirmedLamenessScreeningEvidence ? "lameness_suspect" : "mobility_activity_attention",
                        confirmedLamenessScreeningEvidence ? "跛行/蹄病疑似" : "活动/运动异常关注",
                        score,
                        evidence,
                        "检查起立、步态、蹄部和绑带松动情况；必要时补拍侧视视频。"));
            }

            if (temperatureDelta != null && temperatureDelta >= 0.8
                    && (feedingEvidence >= 0.20 || orZero(activityDrop) >= 0.20)) {
                double score = clamp(0.30 + Math.min(temperatureDelta / 2.0, 1.0) * 0.34
                        + Math.max(feedingEvidence, orZero(activityDrop)) * 0.22);
                List<String> evidence = new ArrayList<>();
                evidence.add("B-1 体表温度较个体基线升高 " + signedTemperature(temperatureDelta));
                if (feedingEvidence >= 0.20) {
                    evidence.add("同时存在采食/反刍下降趋势");
                }
                if (orZero(activityDrop) >= 0.20) {
                    evidence.add("同时存在活动下降趋势");
                }
                evidence.add("体表温度不是核心体温");
                risks.add(risk(
                        "temperature_inflammation_attention",
                        "体温/炎症关注",
                        score,
                        evidence,
                        "使用经过校准的体温计复测；若持续升高或伴随精神、采食异常，请联系兽医。"));
            }

            if (vocalizationIncrease != null && vocalizationIncrease >= 0.15 && current.vocalizationSamples >= 3) {
                double score = clamp(0.18 + Math.min(vocalizationIncrease / 0.50, 1.0) * 0.42);
                risks.add(risk(
                        "vocalization_attention",
                        "异常发声关注",
                        score,
                        List.of(
                                "声音活动候选比例较个体基线增加 " + percent(vocalizationIncrease),
                                "当前窗口检测到 " + current.vocalizationSamples + " 次候选",
                                "这是信号级候选，不是异常鸣叫或疾病分类结果"),
                        "保留音频片段并人工复核；只有经批准的声音分类器才能进入疾病风险筛查。"));
            }

            if (abnormalVocalizationCandidateIncrease != null
                    && abnormalVocalizationCandidateIncrease >= 0.10
                    && current.abnormalVocalizationCandidateSamples >= 2
                    && current.audioModelSamples >= 3) {
                double score = clamp(0.24 + Math.min(abnormalVocalizationCandidateIncrease / 0.40, 1.0) * 0.44);
                risks.add(risk(
                        "abnormal_vocalization_attention",
                        "异常鸣叫/发声关注",
                        score,
                        List.of(
                                "已批准声音模型的异常鸣叫候选比例较个体基线增加 "
                                        + percent(abnormalVocalizationCandidateIncrease),
                                "当前窗口检测到 " + current.abnormalVocalizationCandidateSamples + " 次异常鸣叫候选",
                                "该结果不能确定疼痛、应激或具体疾病"),
                        "回放原始音频并核对发情、分群、运输、疼痛和呼吸症状；持续异常时请兽医复核。"));
            }

            if (respiratoryCandidateIncrease != null && respiratoryCandidateIncrease >= 0.10
                    && current.respiratoryCandidateSamples >= 2 && current.audioModelSamples >= 3) {
                double score = clamp(0.25 + Math.min(respiratoryCandidateIncrease / 0.40, 1.0) * 0.46);
                risks.add(risk(
                        "respiratory_sound_attention",
                        "呼吸异常声音关注",
                        score,
                        List.of(
                                "已部署声音模型的呼吸声候选比例较个体基线增加 "
                                        + percent(respiratoryCandidateIncrease),
                                "当前窗口检测到 " + current.respiratoryCandidateSamples + " 次咳嗽或喘鸣候选",
                                "声音候选不是呼吸道疾病确诊"),
                        "回放对应音频片段并检查呼吸频率、鼻液、精神和体温；存在持续症状时联系兽医复核。"));

                boolean respiratoryContext = (temperatureDelta != null && temperatureDelta >= 0.8)
                        || feedingEvidence >= 0.20
                        || mobilityAnomaly
                        || vision.has("nasal_discharge_suspect");
                if (respiratoryContext) {
                    List<String> brdEvidence = new ArrayList<>();
                    brdEvidence.add("已部署模型连续检出 " + current.respiratoryCandidateSamples + " 次呼吸异常声音候选");
                    if (temperatureDelta != null && temperatureDelta >= 0.8) {
                        brdEvidence.add("体表温度较个体基线升高 " + signedTemperature(temperatureDelta));
                    }
                    if (feedingEvidence >= 0.20) {
                        brdEvidence.add("采食或反刍存在下降趋势");
                    }
                    if (vision.has("nasal_discharge_suspect")) {
                        brdEvidence.add("视觉端存在鼻部分泌物疑似证据");
                    }
                    brdEvidence.add("BRD 疑似需要临床呼吸评分、听诊或肺部超声复核");
                    risks.add(risk(
                            "brd_suspect",
                            "牛呼吸道疾病疑似（BRD）",
                            clamp(score + 0.12),
                            brdEvidence,
                            "立即回放音频并复测体温；检查呼吸频率、鼻液和精神状态，安排兽医进行临床评分与必要的肺部超声/检测。"));
                }
            }

            // Independent audio events arrive between telemetry frames. They
            // are counted only when the server approved the exact respiratory
            // model version; raw or unapproved labels remain archive-only.
            if (audio.respiratoryCandidate()) {
                double audioScore = clamp(0.34 + audio.maximumRespiratoryScore() * 0.42);
                List<String> audioEvidence = new ArrayList<>();
                audioEvidence.add("服务端批准的声音模型检出 " + audio.respiratoryEventCount()
                        + " 次咳嗽/喘鸣候选");
                audioEvidence.add("候选标签：" + String.join("、", audio.respiratoryLabels()));
                audioEvidence.add("声音候选不是呼吸道疾病确诊");
                boolean existingRespiratoryRisk = risks.stream().anyMatch(risk ->
                        "respiratory_sound_attention".equals(risk.get("type")));
                if (!existingRespiratoryRisk) {
                    risks.add(risk(
                            "respiratory_sound_attention",
                            "呼吸异常声音关注",
                            audioScore,
                            audioEvidence,
                            "回放音频并检查呼吸频率、鼻液、精神和核心体温；持续异常时联系兽医复核。"));
                }

                boolean respiratoryContext = (temperatureDelta != null && temperatureDelta >= 0.8)
                        || feedingEvidence >= 0.20
                        || mobilityAnomaly
                        || vision.has("nasal_discharge_suspect");
                boolean existingBrdRisk = risks.stream().anyMatch(risk -> "brd_suspect".equals(risk.get("type")));
                if (respiratoryContext && !existingBrdRisk) {
                    List<String> brdEvidence = new ArrayList<>(audioEvidence);
                    if (temperatureDelta != null && temperatureDelta >= 0.8) {
                        brdEvidence.add("体表温度较个体基线升高 " + signedTemperature(temperatureDelta));
                    }
                    if (feedingEvidence >= 0.20) {
                        brdEvidence.add("采食或反刍存在下降趋势");
                    }
                    if (vision.has("nasal_discharge_suspect")) {
                        brdEvidence.add("视觉端存在鼻部分泌物疑似证据");
                    }
                    brdEvidence.add("BRD 疑似需要临床呼吸评分、听诊或肺部超声复核");
                    risks.add(risk(
                            "brd_suspect",
                            "牛呼吸道疾病疑似（BRD）",
                            clamp(audioScore + 0.12),
                            brdEvidence,
                            "立即回放音频并复测核心体温；检查呼吸频率、鼻液和精神状态，安排兽医进行临床评分与必要的肺部超声/检测。"));
                }
            }

            if (audio.vocalizationCandidate()) {
                double audioScore = clamp(0.30 + audio.maximumVocalizationScore() * 0.40);
                List<String> audioEvidence = new ArrayList<>();
                audioEvidence.add("服务端批准的声音模型检出 " + audio.vocalizationEventCount()
                        + " 次异常鸣叫候选");
                audioEvidence.add("候选标签：" + String.join("、", audio.vocalizationLabels()));
                audioEvidence.add("异常鸣叫候选不能确定疼痛、应激或具体疾病");
                boolean existingVocalizationRisk = risks.stream().anyMatch(risk ->
                        "abnormal_vocalization_attention".equals(risk.get("type")));
                if (!existingVocalizationRisk) {
                    risks.add(risk(
                            "abnormal_vocalization_attention",
                            "异常鸣叫/发声关注",
                            audioScore,
                            audioEvidence,
                            "回放音频并核对发情、分群、运输、疼痛和呼吸症状；持续异常时请兽医复核。"));
                }
            }

            boolean fmdVisionEvidence = vision.has("oral_lesion_suspect") || vision.has("hoof_lesion_suspect")
                    || clinical.has("oral_lesion_suspect") || clinical.has("hoof_lesion_suspect");
            boolean feverConfirmed = clinical.coreTemperatureAlert();
            boolean fmdMobilityEvidence = risks.stream().anyMatch(risk -> "lameness_suspect".equals(risk.get("type")));
            if (fmdVisionEvidence && feverConfirmed && fmdMobilityEvidence) {
                risks.add(risk(
                        "fmd_suspect_triage",
                        "口蹄疫疑似事件分诊",
                        0.95,
                        List.of(
                                "有效口鼻/蹄部病灶证据："
                                        + evidenceDescription(vision, clinical, "oral_lesion_suspect", "hoof_lesion_suspect"),
                                "24 小时内存在人工复测核心体温异常",
                                "同时满足跛行/蹄病筛查候选",
                                "传感器不能确认或排除口蹄疫"),
                        "按当地动物防疫法规立即启动兽医和主管部门报告流程；隔离、采样和实验室检测仅由有资质人员决定和执行。"));
            }

            return risks;
        }

        private static String evidenceDescription(
                VisionSnapshot vision,
                ClinicalSnapshot clinical,
                String... types
        ) {
            List<String> present = new ArrayList<>();
            for (String type : types) {
                if (vision.has(type)) {
                    present.add("视觉 " + type);
                }
                if (clinical.has(type)) {
                    present.add("人工检查 " + type);
                }
            }
            return present.isEmpty() ? "无" : String.join("、", present);
        }

        private void pruneRecent(Instant cutoff) {
            while (!recent.isEmpty() && recent.peekFirst().receivedAt().isBefore(cutoff)) {
                recent.removeFirst();
            }
        }

        private void pruneBuckets(long earliestBucket) {
            while (!buckets.isEmpty() && buckets.firstKey() < earliestBucket) {
                buckets.pollFirstEntry();
            }
        }
    }

    private static Map<String, Object> risk(
            String type,
            String label,
            double score,
            List<String> evidence,
            String suggestion) {
        Map<String, Object> risk = new LinkedHashMap<>();
        risk.put("type", type);
        risk.put("label", label);
        risk.put("level", riskSeverity(score).name());
        risk.put("score", round(score));
        risk.put("evidence", evidence);
        risk.put("suggestion", suggestion);
        return risk;
    }

    private static Severity riskSeverity(double score) {
        return score >= 0.72 ? Severity.WARNING : Severity.OBSERVE;
    }

    private static Severity overallSeverity(double score, int riskCount) {
        if (riskCount == 0) {
            return Severity.NORMAL;
        }
        if (score >= 0.72 || (riskCount >= 2 && score >= 0.58)) {
            return Severity.WARNING;
        }
        return Severity.OBSERVE;
    }

    private static String quality(Aggregate current, boolean baselineReady, boolean currentReady) {
        if (current.motionSamples == 0) {
            return "INVALID";
        }
        if (!baselineReady || !currentReady || current.temperatureSamples == 0 || current.microphoneSamples == 0) {
            return "LIMITED";
        }
        return "GOOD";
    }

    private static String learningMessage(Aggregate current, long baselineMinutes, ScreeningConfig config) {
        if (current.windowMinutes() < config.minimumCurrentWindowMinutes()) {
            return "正在积累当前观察窗口，至少需要 " + config.minimumCurrentWindowMinutes() + " 分钟连续行为数据";
        }
        if (baselineMinutes < config.minimumBaselineMinutes()) {
            return "正在建立个体基线，当前窗口之外已积累 " + baselineMinutes
                    + " 分钟有效历史；需要 " + config.minimumBaselineMinutes()
                    + " 分钟基线，累计观察约 "
                    + (config.minimumBaselineMinutes() + config.currentWindowMinutes()) + " 分钟";
        }
        return "正在校验行为和健康信号质量";
    }

    private static Map<String, Object> sourceMetrics(
            Sample sample,
            Aggregate current,
            VisionSnapshot vision,
            AudioSnapshot audio,
            ClinicalSnapshot clinical
    ) {
        Map<String, Object> sources = new LinkedHashMap<>();
        sources.put("motion", source(
                sample.motionAvailable(),
                sample.motionAvailable(),
                false,
                false,
                sample.motionAvailable(),
                sample.motionAvailable(),
                "三位置 ADXL345/行为模型；用于姿态和活动筛查，不是疾病确诊模型"));
        sources.put("vision", source(
                !vision.activeEvents().isEmpty(),
                !vision.activeEvents().isEmpty(),
                !vision.activeEvents().isEmpty(),
                true,
                !vision.activeEvents().isEmpty(),
                !vision.activeEvents().isEmpty(),
                "只有服务端批准的视觉病灶/步态事件才能进入融合"));
        boolean audioObserved = sample.microphoneAvailable() || audio.activeEventCount() > 0;
        boolean audioParticipating = audio.screeningEligibleCount() > 0;
        sources.put("audio", source(
                audioObserved,
                audioObserved,
                audioParticipating,
                true,
                audioParticipating,
                audioObserved,
                "未批准的声音标签仅保存音频和特征，不进入疾病风险"));
        sources.put("surfaceTemperature", source(
                sample.surfaceTemperature() != null,
                sample.surfaceTemperature() != null,
                false,
                false,
                sample.surfaceTemperature() != null,
                sample.surfaceTemperature() != null,
                "B-1 是体表温度，只能作为炎症关注，不能替代核心体温"));
        sources.put("clinical", source(
                clinical.coreTemperatureRecordedAt() != null || !clinical.activeEvidence().isEmpty(),
                clinical.coreTemperatureRecordedAt() != null || !clinical.activeEvidence().isEmpty(),
                false,
                false,
                clinical.coreTemperatureVerified() || !clinical.activeEvidence().isEmpty(),
                clinical.coreTemperatureRecordedAt() != null || !clinical.activeEvidence().isEmpty(),
                "兽医/授权人员复核是口蹄疫和疾病分诊的必要证据"));
        return sources;
    }

    private static Map<String, Object> fusionMetrics(
            Sample sample,
            Aggregate current,
            VisionSnapshot vision,
            AudioSnapshot audio,
            ClinicalSnapshot clinical
    ) {
        List<String> participating = new ArrayList<>();
        List<String> observed = new ArrayList<>();
        if (sample.motionAvailable()) {
            observed.add("motion");
            participating.add("motion");
        }
        if (!vision.activeEvents().isEmpty()) {
            observed.add("vision");
            participating.add("vision");
        }
        if (current.microphoneSamples > 0 || audio.activeEventCount() > 0) {
            observed.add("audio");
        }
        if (audio.screeningEligibleCount() > 0) {
            participating.add("audio");
        }
        if (sample.surfaceTemperature() != null) {
            observed.add("surfaceTemperature");
            participating.add("surfaceTemperature");
        }
        if (clinical.coreTemperatureVerified() || !clinical.activeEvidence().isEmpty()) {
            observed.add("clinical");
            participating.add("clinical");
        }
        Map<String, Object> fusion = new LinkedHashMap<>();
        fusion.put("observedSources", observed);
        fusion.put("observedEvidenceCount", observed.size());
        fusion.put("participatingSources", participating);
        fusion.put("evidenceCount", participating.size());
        fusion.put("decisionScope", "screening_only");
        fusion.put("requiresClinicalConfirmation", true);
        return fusion;
    }

    private static Map<String, Object> source(
            boolean online,
            boolean fresh,
            boolean modelApproved,
            boolean modelApprovalRequired,
            boolean participating,
            boolean observed,
            String note
    ) {
        Map<String, Object> source = new LinkedHashMap<>();
        source.put("online", online);
        source.put("fresh", fresh);
        source.put("modelApproved", modelApproved);
        source.put("modelApprovalRequired", modelApprovalRequired);
        source.put("observed", observed);
        source.put("participating", participating);
        source.put("note", note);
        return source;
    }

    private static Double relativeDrop(Double baseline, Double current) {
        if (baseline == null || current == null || baseline < 0.03) {
            return null;
        }
        return Math.max(0.0, (baseline - current) / Math.max(baseline, EPSILON));
    }

    private static Double difference(Double current, Double baseline) {
        if (baseline == null || current == null) {
            return null;
        }
        return current - baseline;
    }

    private static double orZero(Double value) {
        return value == null ? 0.0 : value;
    }

    private static double clamp(double value) {
        return Math.max(0.0, Math.min(1.0, value));
    }

    private static double round(double value) {
        return Math.round(value * 1000.0) / 1000.0;
    }

    private static String percent(double value) {
        return Math.round(value * 100.0) + "%";
    }

    private static String signedTemperature(double delta) {
        return String.format("%+.1f°C", delta);
    }

    private static long bucketKey(Instant instant) {
        return instant.toEpochMilli() / Duration.ofMinutes(BASELINE_BUCKET_MINUTES).toMillis();
    }

    private record ScreeningConfig(
            int currentWindowMinutes,
            int baselineRetentionDays,
            int minimumBaselineMinutes,
            int minimumCurrentWindowMinutes,
            int visionEvidenceMaxMinutes,
            int audioEvidenceMaxMinutes,
            int clinicalEvidenceMaxHours) {
    }

    private record Sample(
            String targetId,
            Instant receivedAt,
            boolean motionAvailable,
            String behavior,
            double behaviorConfidence,
            Double activity,
            Double surfaceTemperature,
            boolean lamenessModelDeployed,
            boolean lamenessCandidate,
            boolean lamenessRejected,
            Double lamenessScore,
            boolean microphoneAvailable,
            boolean vocalizationCandidate,
            boolean audioModelDeployed,
            boolean respiratoryCandidate,
            boolean abnormalVocalizationCandidate) {

        static Sample from(ObjectNode telemetry, Instant receivedAt) {
            String targetId = text(telemetry, "cattleId", text(telemetry, "deviceId", "unknown-cattle"));
            JsonNode behavior = telemetry.path("behavior");
            String state = behavior.path("state").asText("sensors_missing");
            double confidence = behavior.path("confidence").asDouble(0.0);
            boolean motionAvailable = telemetry.path("mpu0").asBoolean(false)
                    && telemetry.path("adxl345").asBoolean(false)
                    && telemetry.path("mpu1").asBoolean(false)
                    && !"sensors_missing".equals(state);

            Double bodyActivity = number(behavior.path("bodyActivity"));
            Double legActivity = number(behavior.path("legActivity"));
            Double activity = null;
            if (bodyActivity != null && legActivity != null) {
                activity = bodyActivity * 0.35 + legActivity * 0.65;
            } else if (legActivity != null) {
                activity = legActivity;
            } else if (bodyActivity != null) {
                activity = bodyActivity;
            }

            JsonNode b1 = telemetry.path("b1Infrared");
            Double surfaceTemperature = b1.path("temperatureValid").asBoolean(false)
                    ? number(b1.path("surfaceTemperature"))
                    : null;

            JsonNode lameness = telemetry.path("lamenessScreen");
            boolean lamenessModelDeployed = "deployed".equals(lameness.path("modelStatus").asText());
            boolean lamenessRejected = lamenessModelDeployed && lameness.path("rejected").asBoolean(false);
            boolean lamenessCandidate = lamenessModelDeployed && !lamenessRejected
                    && lameness.path("candidate").asBoolean(false);
            Double lamenessScore = lamenessModelDeployed ? number(lameness.path("score")) : null;

            JsonNode microphone = telemetry.path("microphone");
            boolean microphoneAvailable = microphone.path("initialized").asBoolean(false)
                    && "ok".equals(microphone.path("status").asText());
            boolean vocalizationCandidate = microphoneAvailable
                    && microphone.path("vocalizationCandidate").asBoolean(false);
            boolean audioModelDeployed = microphoneAvailable
                    && "deployed".equals(microphone.path("modelStatus").asText());
            boolean respiratoryCandidate = audioModelDeployed
                    && microphone.path("respiratoryCandidate").asBoolean(false);
            boolean abnormalVocalizationCandidate = audioModelDeployed
                    && microphone.path("abnormalVocalizationCandidate").asBoolean(false);
            return new Sample(
                    targetId,
                    receivedAt,
                    motionAvailable,
                    state,
                    confidence,
                    activity,
                    surfaceTemperature,
                    lamenessModelDeployed,
                    lamenessCandidate,
                    lamenessRejected,
                    lamenessScore,
                    microphoneAvailable,
                    vocalizationCandidate,
                    audioModelDeployed,
                    respiratoryCandidate,
                    abnormalVocalizationCandidate);
        }

        private static String text(JsonNode node, String field, String fallback) {
            String value = node.path(field).asText("").trim();
            return value.isEmpty() ? fallback : value;
        }

        private static Double number(JsonNode node) {
            if (node == null || node.isNull() || !node.isNumber()) {
                return null;
            }
            double value = node.asDouble();
            return Double.isFinite(value) ? value : null;
        }
    }

    private static final class Aggregate {
        private int observations;
        private int motionSamples;
        private int behaviorSamples;
        private int grazingSamples;
        private int ruminationSamples;
        private int lyingSamples;
        private int walkingSamples;
        private int activitySamples;
        private double activitySum;
        private int temperatureSamples;
        private double temperatureSum;
        private int lamenessModelSamples;
        private int lamenessCandidateSamples;
        private int lamenessRejectedSamples;
        private double lamenessScoreSum;
        private int lamenessScoreSamples;
        private int microphoneSamples;
        private int vocalizationSamples;
        private int audioModelSamples;
        private int respiratoryCandidateSamples;
        private int abnormalVocalizationCandidateSamples;
        private Instant firstReceivedAt;
        private Instant lastReceivedAt;

        static Aggregate from(Iterable<Sample> samples) {
            Aggregate aggregate = new Aggregate();
            for (Sample sample : samples) {
                aggregate.add(sample);
            }
            return aggregate;
        }

        void add(Sample sample) {
            observations++;
            if (firstReceivedAt == null || sample.receivedAt().isBefore(firstReceivedAt)) {
                firstReceivedAt = sample.receivedAt();
            }
            if (lastReceivedAt == null || sample.receivedAt().isAfter(lastReceivedAt)) {
                lastReceivedAt = sample.receivedAt();
            }

            if (sample.motionAvailable()) {
                motionSamples++;
                if (sample.behaviorConfidence() >= 0.35 && isKnownBehavior(sample.behavior())) {
                    behaviorSamples++;
                    switch (sample.behavior()) {
                        case "grazing" -> grazingSamples++;
                        case "lying_ruminating", "standing_ruminating" -> ruminationSamples++;
                        default -> {
                        }
                    }
                    if ("lying_ruminating".equals(sample.behavior()) || "lying_resting".equals(sample.behavior())) {
                        lyingSamples++;
                    }
                    if ("walking".equals(sample.behavior())) {
                        walkingSamples++;
                    }
                }
                if (sample.activity() != null) {
                    activitySamples++;
                    activitySum += sample.activity();
                }
            }
            if (sample.surfaceTemperature() != null) {
                temperatureSamples++;
                temperatureSum += sample.surfaceTemperature();
            }
            if (sample.lamenessModelDeployed()) {
                lamenessModelSamples++;
                if (sample.lamenessCandidate()) {
                    lamenessCandidateSamples++;
                }
                if (sample.lamenessRejected()) {
                    lamenessRejectedSamples++;
                }
                if (sample.lamenessScore() != null) {
                    lamenessScoreSum += sample.lamenessScore();
                    lamenessScoreSamples++;
                }
            }
            if (sample.microphoneAvailable()) {
                microphoneSamples++;
                if (sample.vocalizationCandidate()) {
                    vocalizationSamples++;
                }
                if (sample.audioModelDeployed()) {
                    audioModelSamples++;
                    if (sample.respiratoryCandidate()) {
                        respiratoryCandidateSamples++;
                    }
                    if (sample.abnormalVocalizationCandidate()) {
                        abnormalVocalizationCandidateSamples++;
                    }
                }
            }
        }

        void merge(Aggregate other) {
            observations += other.observations;
            motionSamples += other.motionSamples;
            behaviorSamples += other.behaviorSamples;
            grazingSamples += other.grazingSamples;
            ruminationSamples += other.ruminationSamples;
            lyingSamples += other.lyingSamples;
            walkingSamples += other.walkingSamples;
            activitySamples += other.activitySamples;
            activitySum += other.activitySum;
            temperatureSamples += other.temperatureSamples;
            temperatureSum += other.temperatureSum;
            lamenessModelSamples += other.lamenessModelSamples;
            lamenessCandidateSamples += other.lamenessCandidateSamples;
            lamenessRejectedSamples += other.lamenessRejectedSamples;
            lamenessScoreSum += other.lamenessScoreSum;
            lamenessScoreSamples += other.lamenessScoreSamples;
            microphoneSamples += other.microphoneSamples;
            vocalizationSamples += other.vocalizationSamples;
            audioModelSamples += other.audioModelSamples;
            respiratoryCandidateSamples += other.respiratoryCandidateSamples;
            abnormalVocalizationCandidateSamples += other.abnormalVocalizationCandidateSamples;
            if (firstReceivedAt == null || (other.firstReceivedAt != null && other.firstReceivedAt.isBefore(firstReceivedAt))) {
                firstReceivedAt = other.firstReceivedAt;
            }
            if (lastReceivedAt == null || (other.lastReceivedAt != null && other.lastReceivedAt.isAfter(lastReceivedAt))) {
                lastReceivedAt = other.lastReceivedAt;
            }
        }

        long windowMinutes() {
            if (firstReceivedAt == null || lastReceivedAt == null) {
                return 0;
            }
            return Math.max(0, Duration.between(firstReceivedAt, lastReceivedAt).toMinutes());
        }

        boolean endsBefore(Instant instant) {
            return lastReceivedAt != null && lastReceivedAt.isBefore(instant);
        }

        boolean hasSufficientMotionCoverage(int minimumSamples) {
            return motionSamples >= minimumSamples;
        }

        boolean hasSufficientMotionCoverage(double minimumRatio) {
            return observations > 0 && (double) motionSamples / observations >= minimumRatio;
        }

        Double grazingRatio() {
            return ratio(grazingSamples, behaviorSamples);
        }

        Double ruminationRatio() {
            return ratio(ruminationSamples, behaviorSamples);
        }

        Double lyingRatio() {
            return ratio(lyingSamples, behaviorSamples);
        }

        Double walkingRatio() {
            return ratio(walkingSamples, behaviorSamples);
        }

        Double averageActivity() {
            return ratio(activitySum, activitySamples);
        }

        Double averageSurfaceTemperature() {
            return ratio(temperatureSum, temperatureSamples);
        }

        Double lamenessCandidateRate() {
            return ratio(lamenessCandidateSamples, lamenessModelSamples);
        }

        Double lamenessRejectionRate() {
            return ratio(lamenessRejectedSamples, lamenessModelSamples);
        }

        Double averageLamenessScore() {
            return ratio(lamenessScoreSum, lamenessScoreSamples);
        }

        Double vocalizationRate() {
            return ratio(vocalizationSamples, microphoneSamples);
        }

        Double respiratoryCandidateRate() {
            return ratio(respiratoryCandidateSamples, audioModelSamples);
        }

        Double abnormalVocalizationCandidateRate() {
            return ratio(abnormalVocalizationCandidateSamples, audioModelSamples);
        }

        Map<String, Object> metrics() {
            Map<String, Object> metrics = new LinkedHashMap<>();
            metrics.put("behaviorSamples", behaviorSamples);
            metrics.put("motionCoverage", percentage(motionSamples, observations));
            metrics.put("grazingRatio", rounded(grazingRatio()));
            metrics.put("ruminationRatio", rounded(ruminationRatio()));
            metrics.put("lyingRatio", rounded(lyingRatio()));
            metrics.put("walkingRatio", rounded(walkingRatio()));
            metrics.put("activity", rounded(averageActivity()));
            metrics.put("surfaceTemperature", rounded(averageSurfaceTemperature()));
            metrics.put("lamenessModelSamples", lamenessModelSamples);
            metrics.put("lamenessCandidateRate", rounded(lamenessCandidateRate()));
            metrics.put("lamenessRejectionRate", rounded(lamenessRejectionRate()));
            metrics.put("lamenessScore", rounded(averageLamenessScore()));
            metrics.put("vocalizationRate", rounded(vocalizationRate()));
            metrics.put("respiratoryCandidateRate", rounded(respiratoryCandidateRate()));
            metrics.put("temperatureSamples", temperatureSamples);
            metrics.put("microphoneSamples", microphoneSamples);
            metrics.put("audioModelSamples", audioModelSamples);
            metrics.put("respiratoryCandidateSamples", respiratoryCandidateSamples);
            metrics.put("abnormalVocalizationCandidateRate", rounded(abnormalVocalizationCandidateRate()));
            metrics.put("abnormalVocalizationCandidateSamples", abnormalVocalizationCandidateSamples);
            return metrics;
        }

        private static boolean isKnownBehavior(String value) {
            return switch (value) {
                case "grazing", "lying_ruminating", "lying_resting", "standing_resting", "walking", "standing_ruminating" -> true;
                default -> false;
            };
        }

        private static Double ratio(int numerator, int denominator) {
            return denominator > 0 ? (double) numerator / denominator : null;
        }

        private static Double ratio(double numerator, int denominator) {
            return denominator > 0 ? numerator / denominator : null;
        }

        private static Double rounded(Double value) {
            return value == null ? null : round(value);
        }

        private static Double percentage(int numerator, int denominator) {
            return denominator > 0 ? round((double) numerator / denominator) : null;
        }
    }

    private static final class VisionEvidence {
        private final Map<String, Instant> latestByType = new HashMap<>();
        private final Map<String, Double> scoreByType = new HashMap<>();

        void record(String eventType, double score, Instant recordedAt) {
            latestByType.put(eventType, recordedAt);
            scoreByType.put(eventType, clamp(score));
        }

        VisionSnapshot snapshot(Instant now, int maximumAgeMinutes) {
            Map<String, Double> active = new LinkedHashMap<>();
            Instant cutoff = now.minus(Duration.ofMinutes(maximumAgeMinutes));
            latestByType.forEach((eventType, recordedAt) -> {
                if (recordedAt != null && !recordedAt.isBefore(cutoff)) {
                    active.put(eventType, scoreByType.getOrDefault(eventType, 0.0));
                }
            });
            return new VisionSnapshot(active, maximumAgeMinutes);
        }
    }

    private static final class AudioEvidence {
        private static final Set<String> RESPIRATORY_LABELS = Set.of("cough_suspect", "wheeze_suspect");
        private static final Set<String> VOCALIZATION_LABELS = Set.of("abnormal_vocalization_suspect");
        private final Map<String, AudioRecord> records = new LinkedHashMap<>();

        synchronized void record(
                String label,
                double score,
                boolean diseaseEligible,
                Instant recordedAt,
                String evidenceId
        ) {
            String key = evidenceId == null || evidenceId.isBlank()
                    ? label + "@" + recordedAt.toEpochMilli()
                    : evidenceId.trim();
            if (records.containsKey(key)) {
                return;
            }
            records.put(key, new AudioRecord(label.toLowerCase(), clamp(score), diseaseEligible, recordedAt));
            while (records.size() > 256) {
                records.remove(records.keySet().iterator().next());
            }
        }

        synchronized AudioSnapshot snapshot(Instant now, int maximumAgeMinutes) {
            Instant cutoff = now.minus(Duration.ofMinutes(maximumAgeMinutes));
            Map<String, Double> active = new LinkedHashMap<>();
            List<String> labels = new ArrayList<>();
            List<String> vocalizationLabels = new ArrayList<>();
            Instant latest = null;
            int eligibleCount = 0;
            int respiratoryCount = 0;
            int vocalizationCount = 0;
            double maximumRespiratoryScore = 0.0;
            double maximumVocalizationScore = 0.0;
            for (AudioRecord record : records.values()) {
                if (record.recordedAt().isBefore(cutoff)) {
                    continue;
                }
                active.merge(record.label(), record.score(), Math::max);
                if (latest == null || record.recordedAt().isAfter(latest)) {
                    latest = record.recordedAt();
                }
                if (record.diseaseEligible()) {
                    eligibleCount++;
                }
                if (record.diseaseEligible() && RESPIRATORY_LABELS.contains(record.label())) {
                    respiratoryCount++;
                    maximumRespiratoryScore = Math.max(maximumRespiratoryScore, record.score());
                    if (!labels.contains(record.label())) {
                        labels.add(record.label());
                    }
                }
                if (record.diseaseEligible() && VOCALIZATION_LABELS.contains(record.label())) {
                    vocalizationCount++;
                    maximumVocalizationScore = Math.max(maximumVocalizationScore, record.score());
                    if (!vocalizationLabels.contains(record.label())) {
                        vocalizationLabels.add(record.label());
                    }
                }
            }
            return new AudioSnapshot(
                    active,
                    active.size(),
                    eligibleCount,
                    respiratoryCount > 0,
                    respiratoryCount,
                    List.copyOf(labels),
                    maximumRespiratoryScore,
                    vocalizationCount > 0,
                    vocalizationCount,
                    List.copyOf(vocalizationLabels),
                    maximumVocalizationScore,
                    maximumAgeMinutes,
                    latest);
        }
    }

    private record AudioRecord(
            String label,
            double score,
            boolean diseaseEligible,
            Instant recordedAt
    ) {
    }

    private static final class ClinicalEvidence {
        private Instant coreTemperatureRecordedAt;
        private boolean coreTemperatureVerified;
        private boolean coreTemperatureAlert;
        private Double coreTemperatureC;
        private final Map<String, Instant> clinicalVisionRecordedAt = new HashMap<>();

        void record(String checkType, boolean verified, boolean alert, Double value, String evidenceType, Instant recordedAt) {
            if (evidenceType != null && !evidenceType.isBlank() && verified && alert) {
                Instant previous = clinicalVisionRecordedAt.get(evidenceType);
                if (previous == null || !recordedAt.isBefore(previous)) {
                    clinicalVisionRecordedAt.put(evidenceType, recordedAt);
                }
            }
            if (!"core_temperature".equals(checkType)) {
                return;
            }
            if (coreTemperatureRecordedAt != null && recordedAt.isBefore(coreTemperatureRecordedAt)) {
                return;
            }
            coreTemperatureRecordedAt = recordedAt;
            coreTemperatureVerified = verified;
            coreTemperatureAlert = alert;
            coreTemperatureC = value;
        }

        ClinicalSnapshot snapshot(Instant now, int maximumAgeHours) {
            if (coreTemperatureRecordedAt == null ||
                    coreTemperatureRecordedAt.isBefore(now.minus(Duration.ofHours(maximumAgeHours)))) {
                return new ClinicalSnapshot(
                        null, false, false, null,
                        activeClinicalEvidence(now, maximumAgeHours), maximumAgeHours);
            }
            return new ClinicalSnapshot(
                    coreTemperatureRecordedAt,
                    coreTemperatureVerified,
                    coreTemperatureAlert,
                    coreTemperatureC,
                    activeClinicalEvidence(now, maximumAgeHours),
                    maximumAgeHours);
        }

        private Map<String, Double> activeClinicalEvidence(Instant now, int maximumAgeHours) {
            Instant cutoff = now.minus(Duration.ofHours(maximumAgeHours));
            Map<String, Double> active = new LinkedHashMap<>();
            clinicalVisionRecordedAt.forEach((type, recordedAt) -> {
                if (recordedAt != null && !recordedAt.isBefore(cutoff)) {
                    active.put(type, 1.0);
                }
            });
            return active;
        }
    }

    private record ClinicalSnapshot(
            Instant coreTemperatureRecordedAt,
            boolean coreTemperatureVerified,
            boolean coreTemperatureAlert,
            Double coreTemperatureC,
            Map<String, Double> activeEvidence,
            int maximumAgeHours
    ) {
        static ClinicalSnapshot empty(int maximumAgeHours) {
            return new ClinicalSnapshot(null, false, false, null, Map.of(), maximumAgeHours);
        }

        boolean has(String evidenceType) {
            return activeEvidence.containsKey(evidenceType);
        }

        Map<String, Object> metrics() {
            Map<String, Object> metrics = new LinkedHashMap<>();
            metrics.put("coreTemperatureRecordedAt", coreTemperatureRecordedAt == null ? null : coreTemperatureRecordedAt.toString());
            metrics.put("coreTemperatureVerified", coreTemperatureVerified);
            metrics.put("coreTemperatureAlert", coreTemperatureAlert);
            metrics.put("coreTemperatureC", coreTemperatureC);
            metrics.put("activeEvidence", activeEvidence);
            metrics.put("maximumAgeHours", maximumAgeHours);
            return metrics;
        }
    }

    private record AudioSnapshot(
            Map<String, Double> activeEvents,
            int activeEventCount,
            int screeningEligibleCount,
            boolean respiratoryCandidate,
            int respiratoryEventCount,
            List<String> respiratoryLabels,
            double maximumRespiratoryScore,
            boolean vocalizationCandidate,
            int vocalizationEventCount,
            List<String> vocalizationLabels,
            double maximumVocalizationScore,
            int maximumAgeMinutes,
            Instant latestAt
    ) {
        static AudioSnapshot empty() {
            return new AudioSnapshot(Map.of(), 0, 0, false, 0, List.of(), 0.0,
                    false, 0, List.of(), 0.0, 0, null);
        }

        Map<String, Object> metrics() {
            Map<String, Object> metrics = new LinkedHashMap<>();
            metrics.put("activeEvents", activeEvents);
            metrics.put("activeEventCount", activeEventCount);
            metrics.put("screeningEligibleCount", screeningEligibleCount);
            metrics.put("respiratoryCandidate", respiratoryCandidate);
            metrics.put("respiratoryEventCount", respiratoryEventCount);
            metrics.put("respiratoryLabels", respiratoryLabels);
            metrics.put("maximumRespiratoryScore", round(maximumRespiratoryScore));
            metrics.put("vocalizationCandidate", vocalizationCandidate);
            metrics.put("vocalizationEventCount", vocalizationEventCount);
            metrics.put("vocalizationLabels", vocalizationLabels);
            metrics.put("maximumVocalizationScore", round(maximumVocalizationScore));
            metrics.put("maximumAgeMinutes", maximumAgeMinutes);
            metrics.put("latestAt", latestAt == null ? null : latestAt.toString());
            metrics.put("approvedByServer", screeningEligibleCount > 0);
            return metrics;
        }
    }

    private record VisionSnapshot(Map<String, Double> activeEvents, int maximumAgeMinutes) {
        static VisionSnapshot empty() {
            return new VisionSnapshot(Map.of(), 0);
        }

        boolean has(String eventType) {
            return activeEvents.containsKey(eventType);
        }

        String describe(String... types) {
            List<String> present = new ArrayList<>();
            for (String type : types) {
                if (has(type)) {
                    present.add(type + "(" + Math.round(activeEvents.get(type) * 100) + "%)");
                }
            }
            return present.isEmpty() ? "无有效视觉证据" : String.join("、", present);
        }

        Map<String, Object> metrics() {
            Map<String, Object> metrics = new LinkedHashMap<>();
            metrics.put("activeEvents", activeEvents);
            metrics.put("maximumAgeMinutes", maximumAgeMinutes);
            return metrics;
        }
    }
}
