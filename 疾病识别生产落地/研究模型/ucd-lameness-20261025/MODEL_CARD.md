# UCD foot-lesion research evidence, 2026-10-25

Status: **blocked_missing_clinical_labels**. No fitted model or firmware header exists.

- Verified input: 383 cow rows, 20,000 sparse hind-limb Z observations per cow, 11 real farm groups.
- Missing input: observed clinical `CombConorAll$High` labels and exact cow-to-row linkage.
- Target described by the paper: severe foot lesions (case definition 3), assessed at the second farm visit.
- Local accuracy, AUC, sensitivity, specificity and PPV: unavailable, because no supervised validation was possible.
- `paper_reported_metrics.csv` contains published aggregate values, not results of this run.
- `unlabeled_leave_one_farm_out_partitions.csv` is a partition plan only.
- Deployment compatibility: false. Sparse single-position Z data cannot provide synchronized neck/body/leg XYZ at 20 Hz.
- Production approval: false. Existing firmware, trainers, clinical checks and release gates are unchanged.

Reproduce with the installed Python 3.13:

```powershell
python D:\table\shumuzengxiao\scripts\train_ucd_lameness_20261025.py
```

Expected exit status without labels: 2. The script still writes the evidence artifacts.

The complete Chinese evidence report is `D:\table\shumuzengxiao\docs\2026-10-25-imu-data-evidence.md`.
