# Audio Dataset And Release Workflow

This directory contains only versioned source definitions and examples. Large
audio archives, normalized clips, and trained artifacts belong under
`D:\table\shumuzengxiao\audio-training-data` and are ignored by Git.

## Source policy

The source registry is [audio_dataset_sources.json](../tools/audio_dataset_sources.json).

- `kaggle-asc24-v1` is a CC0 public dataset with Cow, Dog, and Frog clips. It
  is approved only for the `cow_vocalization` / `non_cattle_audio` baseline.
  It is never an `abnormal_vocalization_suspect`, cough, wheeze,
  respiratory-disease, or diagnosis dataset.
- `sinc-grazing-jaw-movements` is deliberately blocked. Its public repository
  has no declared license, so it must not be trained on or redistributed until
  permission is verified.

## Reproducible public baseline

The following command converts every source clip to 8 kHz, mono, 16-bit PCM,
checks the registered archive SHA-256, rejects invalid clips, and writes a
group-safe manifest. `AUDIO_FFMPEG` can be set instead of passing `--ffmpeg`.

```powershell
cd D:\table\shumuzengxiao\硬件代码\现有硬件演示节点
$python = 'C:\Users\q4984\AppData\Local\Programs\Python\Python311\python.exe'
& $python tools\prepare_audio_dataset.py `
  --source-id kaggle-asc24-v1 `
  --archive D:\table\shumuzengxiao\audio-training-data\raw\kaggle-asc24-sounds-of-animals-v1.zip `
  --output D:\table\shumuzengxiao\audio-training-data\prepared\kaggle-asc24-v2 `
  --ffmpeg C:\path\to\ffmpeg.exe
```

Train the baseline into the external artifact directory. It remains disabled
even when its validation score is good because it has no clinical labels.

```powershell
& $python tools\train_audio_model.py `
  --manifest D:\table\shumuzengxiao\audio-training-data\prepared\kaggle-asc24-v2\manifest.jsonl `
  --output D:\table\shumuzengxiao\audio-training-data\artifacts\kaggle-asc24-v2\cattle_vocalization_baseline.h `
  --metadata D:\table\shumuzengxiao\audio-training-data\artifacts\kaggle-asc24-v2\audio_model_metadata.json `
  --model-card D:\table\shumuzengxiao\audio-training-data\artifacts\kaggle-asc24-v2\audio_model_card.md
```

## Clinical training data

Export platform-reviewed clips and a source manifest:

```powershell
& $python tools\export_reviewed_audio_dataset.py `
  --api http://localhost:8080 `
  --output D:\table\shumuzengxiao\audio-training-data\reviewed\batch-001
```

Ordinary platform review is intentionally not clinical verification. A
veterinarian must complete one row per audio event using
[clinical_annotations.example.csv](clinical_annotations.example.csv), then the
verified manifest is generated as follows:

```powershell
& $python tools\verify_clinical_audio_manifest.py `
  --manifest D:\table\shumuzengxiao\audio-training-data\reviewed\batch-001\reviewed_manifest.jsonl `
  --annotations D:\table\shumuzengxiao\audio-training-data\reviewed\batch-001\clinical_annotations.csv `
  --output D:\table\shumuzengxiao\audio-training-data\reviewed\batch-001\clinical_manifest.jsonl
```

The final risk-model command must explicitly request release. It only enables
the generated header if clinical provenance, independent animal groups,
validation samples, precision, recall, and macro-F1 all meet the configured
thresholds.

```powershell
& $python tools\train_audio_model.py `
  --manifest D:\table\shumuzengxiao\audio-training-data\reviewed\batch-001\clinical_manifest.jsonl `
  --output include\cattle_audio_model.h `
  --metadata tools\audio_model_metadata.json `
  --model-card tools\audio_model_card.md `
  --release `
  --required-clinical-labels cough_suspect,wheeze_suspect,abnormal_vocalization_suspect
```

The firmware consumes two-second feature windows. Each generated header has a
confidence threshold and a class-distance reject gate; a rejected window is
reported as `unknown` and cannot generate a health-screening candidate. The
clinical label `abnormal_vocalization_suspect` is only an abnormal-sound
candidate; it cannot identify pain, stress, or a disease by itself.
