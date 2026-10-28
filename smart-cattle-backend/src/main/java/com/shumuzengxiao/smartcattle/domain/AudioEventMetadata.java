package com.shumuzengxiao.smartcattle.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Lob;

@Entity
public class AudioEventMetadata {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private Long audioEventId;

    @Column(length = 190, unique = true)
    private String sourceKey;

    @Column(length = 120)
    private String cattleId;
    @Column(length = 120)
    private String modelVersion;
    @Column(length = 80)
    private String modelStatus;
    private Boolean approvedByServer;
    private Boolean screeningEligible;
    @Column(length = 80)
    private String approvalReason;
    @Column(length = 80)
    private String predictedLabel;
    private Boolean clipAvailable;
    @Column(length = 64)
    private String clipSha256;
    private Double rms;
    private Double dbfs;
    private Double zeroCrossingRate;
    private Double lowBandRatio;
    private Double midBandRatio;
    private Double highBandRatio;
    private Double saturationRatio;

    @Lob
    @Column(columnDefinition = "LONGTEXT")
    private String featuresJson;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getAudioEventId() { return audioEventId; }
    public void setAudioEventId(Long audioEventId) { this.audioEventId = audioEventId; }
    public String getSourceKey() { return sourceKey; }
    public void setSourceKey(String sourceKey) { this.sourceKey = sourceKey; }
    public String getCattleId() { return cattleId; }
    public void setCattleId(String cattleId) { this.cattleId = cattleId; }
    public String getModelVersion() { return modelVersion; }
    public void setModelVersion(String modelVersion) { this.modelVersion = modelVersion; }
    public String getModelStatus() { return modelStatus; }
    public void setModelStatus(String modelStatus) { this.modelStatus = modelStatus; }
    public Boolean getApprovedByServer() { return approvedByServer; }
    public void setApprovedByServer(Boolean approvedByServer) { this.approvedByServer = approvedByServer; }
    public Boolean getScreeningEligible() { return screeningEligible; }
    public void setScreeningEligible(Boolean screeningEligible) { this.screeningEligible = screeningEligible; }
    public String getApprovalReason() { return approvalReason; }
    public void setApprovalReason(String approvalReason) { this.approvalReason = approvalReason; }
    public String getPredictedLabel() { return predictedLabel; }
    public void setPredictedLabel(String predictedLabel) { this.predictedLabel = predictedLabel; }
    public Boolean getClipAvailable() { return clipAvailable; }
    public void setClipAvailable(Boolean clipAvailable) { this.clipAvailable = clipAvailable; }
    public String getClipSha256() { return clipSha256; }
    public void setClipSha256(String clipSha256) { this.clipSha256 = clipSha256; }
    public Double getRms() { return rms; }
    public void setRms(Double rms) { this.rms = rms; }
    public Double getDbfs() { return dbfs; }
    public void setDbfs(Double dbfs) { this.dbfs = dbfs; }
    public Double getZeroCrossingRate() { return zeroCrossingRate; }
    public void setZeroCrossingRate(Double zeroCrossingRate) { this.zeroCrossingRate = zeroCrossingRate; }
    public Double getLowBandRatio() { return lowBandRatio; }
    public void setLowBandRatio(Double lowBandRatio) { this.lowBandRatio = lowBandRatio; }
    public Double getMidBandRatio() { return midBandRatio; }
    public void setMidBandRatio(Double midBandRatio) { this.midBandRatio = midBandRatio; }
    public Double getHighBandRatio() { return highBandRatio; }
    public void setHighBandRatio(Double highBandRatio) { this.highBandRatio = highBandRatio; }
    public Double getSaturationRatio() { return saturationRatio; }
    public void setSaturationRatio(Double saturationRatio) { this.saturationRatio = saturationRatio; }
    public String getFeaturesJson() { return featuresJson; }
    public void setFeaturesJson(String featuresJson) { this.featuresJson = featuresJson; }
}
