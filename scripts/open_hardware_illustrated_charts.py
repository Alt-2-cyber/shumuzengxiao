# -*- coding: utf-8 -*-
"""Research figures from saved experiment records, without retraining models."""
from __future__ import annotations

import csv
import hashlib
import json
import wave
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "outputs/open_hardware_submission_illustrated_20261026/work/assets"
VISION = ROOT / "vision-training-data/yolov8-disease-research-20261026"
AUDIO = ROOT / "audio-training-data/artifacts/calf-cough-research-20261026"


def style():
    font_manager.fontManager.addfont("C:/Windows/Fonts/msyh.ttc")
    family = font_manager.FontProperties(fname="C:/Windows/Fonts/msyh.ttc").get_name()
    plt.rcParams.update({"font.family": family, "font.size": 16, "axes.titlesize": 18, "axes.labelsize": 16, "xtick.labelsize": 14, "ytick.labelsize": 14, "axes.spines.top": False, "axes.spines.right": False, "axes.unicode_minus": False, "figure.facecolor": "white", "savefig.facecolor": "white"})


def export(fig, name, note):
    fig.text(.04, .025, note, fontsize=12, color="#4B6257")
    fig.savefig(ASSETS / (name + ".png"), dpi=190, bbox_inches="tight", pad_inches=.20)
    plt.close(fig)


def confusion(ax, matrix, labels, title):
    matrix = np.array(matrix)
    ax.imshow(matrix, cmap="YlGnBu", vmin=0, vmax=max(1, matrix.max()))
    ax.set_xticks(range(len(labels)), labels, rotation=0)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("预测来源标签" if len(labels) == 3 else "预测事件标签")
    ax.set_ylabel("原始来源标签" if len(labels) == 3 else "原始事件标签")
    ax.set_title(title, pad=15)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, str(matrix[i, j]), ha="center", va="center", fontsize=24, color="white" if matrix[i, j] > matrix.max() * .52 else "#172820")


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    style()
    metrics = json.loads((VISION / "heldout_metrics.json").read_text(encoding="utf-8"))
    fig, axs = plt.subplots(1, 2, figsize=(13.5, 5.7), gridspec_kw={"width_ratios": [1.15, 1]})
    fig.subplots_adjust(left=.11, right=.98, bottom=.25, top=.86, wspace=.55)
    labels = ["foot-and-\nmouth", "healthy", "lumpy"]
    confusion(axs[0], metrics["confusion_matrix_rows_true_columns_predicted"], labels, "413 个图像组的留出结果")
    scores = [metrics["classification_report"][name]["f1-score"] for name in metrics["label_order"]]
    axs[1].barh(range(3), scores, color=["#1D7054", "#166F83", "#A97820"], height=.58)
    axs[1].set_yticks(range(3), ["foot-and-mouth", "healthy", "lumpy"])
    axs[1].set_xlim(0, 1.06)
    axs[1].set_xlabel("F1 分数")
    axs[1].set_title("三个公开标签的分类表现", pad=15)
    axs[1].grid(axis="x", color="#DDE5DF", alpha=.7)
    axs[1].set_axisbelow(True)
    for i, value in enumerate(scores):
        axs[1].text(value + .015, i, f"{value:.3f}", va="center", fontsize=15)
    export(fig, "vision_results", "来源  heldout_metrics.json  |  标签是公开图片目录标签  不是独立牧场疾病诊断结果")

    with (VISION / "training_history.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    epochs = np.array([int(r["epoch"]) for r in rows])
    fig, axs = plt.subplots(1, 2, figsize=(13.5, 4.8))
    fig.subplots_adjust(left=.075, right=.98, bottom=.23, top=.86, wspace=.30)
    axs[0].plot(epochs, [float(r["train/loss"]) for r in rows], "o-", color="#1D7054", label="训练 loss", markersize=4)
    axs[0].plot(epochs, [float(r["val/loss"]) for r in rows], "s-", color="#A97820", label="验证 loss", markersize=4)
    axs[0].set(title="实际 13 个 epoch 的损失", xlabel="Epoch", ylabel="Loss")
    axs[0].legend(fontsize=13)
    axs[1].plot(epochs, [float(r["metrics/accuracy_top1"]) * 100 for r in rows], "o-", color="#166F83", markersize=4)
    axs[1].axvline(12, color="#A97820", linestyle="--", linewidth=1.6)
    axs[1].set(title="验证集 top-1 与选定检查点", xlabel="Epoch", ylabel="验证 top-1  %", ylim=(0, 100))
    axs[1].text(12, 11, "第 12 epoch\n选定检查点", ha="right", fontsize=12, color="#805812")
    for ax in axs:
        ax.grid(color="#E0E7E2", alpha=.8)
        ax.set_xticks([1, 3, 5, 7, 9, 11, 13])
    export(fig, "vision_training", "来源  training_history.csv  |  仅验证集参与选模  留出测试不用于调参")

    report = json.loads((AUDIO / "training_report.json").read_text(encoding="utf-8"))
    pooled = report["exploratory_file_oof_metrics"]
    folds = report["fold_metrics"]
    if isinstance(folds, dict):
        folds = list(folds.values())
    fig, axs = plt.subplots(1, 2, figsize=(13.5, 5.6))
    fig.subplots_adjust(left=.10, right=.98, bottom=.25, top=.86, wspace=.32)
    confusion(axs[0], pooled["confusion_matrix_true_rows_predicted_columns"], ["non_cough", "cough"], "40 个原始文件的合并留出预测")
    fold_values = [f["accuracy"] for f in folds]
    axs[1].bar(range(1, 6), np.array(fold_values) * 100, color="#166F83", width=.60)
    axs[1].set(title="五折文件留出的正确数", xlabel="折编号", ylabel="准确率  %", ylim=(0, 105), xticks=range(1, 6))
    for i, value in enumerate(fold_values, 1):
        axs[1].text(i, value * 100 + 2, f"{round(value*8)}/8", ha="center", fontsize=15)
    axs[1].grid(axis="y", color="#E0E7E2")
    axs[1].set_axisbelow(True)
    export(fig, "audio_results", "来源  training_report.json  |  每折 8 个文件  动物与会话未知  结果限于探索性事件实验")

    raw = ROOT / "audio-training-data/external/20261025/raw/rdg-FP5LA9/cough_001.wav"
    with wave.open(str(raw), "rb") as f:
        rate = f.getframerate()
        assert f.getsampwidth() == 2 and f.getnchannels() == 1
        samples = np.frombuffer(f.readframes(f.getnframes()), dtype="<i2").astype(float) / 32768.0
    fig, axs = plt.subplots(1, 2, figsize=(13.5, 4.8))
    fig.subplots_adjust(left=.09, right=.96, bottom=.24, top=.86, wspace=.32)
    axs[0].plot(np.arange(len(samples)) / rate, samples, color="#166F83", linewidth=.7)
    axs[0].set(title="公开 cough_001 原始片段", xlabel="时间  秒", ylabel="PCM 满幅归一化振幅")
    axs[0].grid(color="#E0E7E2")
    spectrum = axs[1].specgram(samples, NFFT=512, Fs=rate, noverlap=384, cmap="viridis", vmin=-100, vmax=-40)
    colorbar = fig.colorbar(spectrum[3], ax=axs[1], fraction=.048, pad=.025)
    colorbar.set_label("功率谱密度  dBFS/Hz", fontsize=11)
    colorbar.ax.tick_params(labelsize=10)
    axs[1].set(title="同一片段的短时频谱", xlabel="时间  秒", ylabel="频率  Hz", ylim=(0, 8000))
    axs[1].axhline(4000, color="white", linestyle="--", linewidth=1.3)
    axs[1].text(.03, 4200, "8 kHz 重采样的 Nyquist 上限", color="white", fontsize=10)
    export(fig, "audio_signal", "来源  INRAE/ENVT  DOI 10.57745/FP5LA9  |  原始样本的研究配图  不表示疾病诊断")
    sources = [VISION / "heldout_metrics.json", VISION / "training_history.csv", AUDIO / "training_report.json", raw]
    (ASSETS.parent / "chart-sources.json").write_text(json.dumps([{"path": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources], ensure_ascii=False, indent=2), encoding="utf-8")
    print("4 research figures created from saved results and one original audio file")


if __name__ == "__main__":
    main()
