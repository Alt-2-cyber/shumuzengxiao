# Expanded cattle appearance YOLO research, 2026-10-26

Status: research_only. Public source-directory/annotation appearance labels are not clinical diagnoses.

## Actual Data

Global components use file/pixel hashes, original prior groups, normalized descriptive source names,
64-bit pHash <=6 AND dHash <=10, aspect ratio within 10%, including horizontal mirrors.
Numeric/generic names are source-and-label namespaced. Transitive components are kept intact.

- Inventoried images: 11826; new public downloaded images: 7433.
- Global groups: 3904; novel groups with no prior-original overlap: 1158.
- Genuinely new retained training groups: 274; of these connected to new downloads: 242.
- Actual input counts: {'train': 1976, 'test': 413, 'val': 412, 'source_holdout': 621}.

| Split | foot-and-mouth | healthy | lumpy |
|---|---:|---:|---:|
| train | 396 | 880 | 700 |
| val | 98 | 178 | 136 |
| test | 98 | 178 | 137 |
| source_holdout | 7 | 487 | 127 |

## Public Sources And Overlap

| Source | Raw Images | Groups | Overlap Prior | Overlap Prior Test | Retained Train | Source Holdout |
|---|---:|---:|---:|---:|---:|---:|
| devang03mgr/cattle-diseases-datasets | 3244 | 2746 | 2746 | 413 | 1702 | 0 |
| drtawfikrrahman/cowhealth-6k-cow-disease-detection | 4367 | 3115 | 2746 | 413 | 93 | 0 |
| magantirajasri/cattle-diseases-dataset | 1038 | 930 | 307 | 47 | 0 | 621 |
| shivamagarwal29/cow-lumpy-disease-dataset | 936 | 932 | 747 | 112 | 90 | 0 |
| tanushtambea/calf-lumpy-skin-disease | 1012 | 820 | 281 | 37 | 0 | 0 |
| warcoder/lumpy-skin-images-dataset | 1024 | 903 | 208 | 29 | 79 | 0 |
| wasimfaraz/cattle-foot-and-mouth-disease-fmd | 125 | 69 | 0 | 0 | 0 | 0 |
| wasimfaraz/fmd-cattle-dataset | 80 | 40 | 28 | 4 | 12 | 0 |

Exact official URLs, version metadata, uploader licenses and archive SHA-256 are preserved in
each new external-data source folder ending expanded-20261026. Search receipts are in
PublicSearch_expanded-20261026. GitHub/Zenodo search results were catalogued; HF public API TLS failed.
Search was bounded to first pages and five Kaggle acquisitions, with bounded/resumable transfers.

The old 125-image FMD package has only cow/source annotation categories and supplied no FMD labels.
The new 80-image FMD package explicitly annotates the source spelling "foot and mougth".
Calf "unhealthy" is deliberately left unmapped; no disease label is synthesized.
Mastitis and filename-identified non-bovine subjects are not added to the three classifier labels.

## Frozen Selection And Training

All prior 413 test representatives are copied byte-for-byte and retained, outside the trainer root.
Any global component touching any prior test member is excluded from training, even through new-source bridges.
Original validation representatives are fixed, with components that become protected or label-conflicting removed.
Source holdout chosen before model inference: magantirajasri/cattle-diseases-dataset. Selection evidence is in source_holdout_selection.json.
The entire source is excluded from training; evaluated source groups have no overlap with any prior original.

One fixed run initialized from original official YOLOv8n-cls ImageNet weights, without inheriting prior disease-fit weights.
AdamW, 224, batch16, workers0, FP32, lr0=.001/lrf=.01, weight_decay=.0005, dropout=.1, seed20261026,
30 epoch cap, patience8; crop area .7-1, horizontal flip .5, HSV .015/.3/.2, no auto augment/erasing.
Actual GPU: NVIDIA GeForce RTX 3050 6GB Laptop GPU; epochs 19; elapsed 940.94s;
maximum fixed-validation top1 0.898060; selected epoch 12.
Checkpoint fitness uses validation only; latest equal-fitness tie, then SHA-locked before heldout inference.

Global cross-source bridges exposed 3 original training representatives connected to frozen test components.
They are excluded here. The prior model may inherit that historical duplication; it is a historical baseline,
and the current candidate deliberately starts from the original official pretrained weights instead.

## Comparable Results

| Evaluation | Images | Prior Accuracy | Candidate Accuracy | Prior Macro-F1 | Candidate Macro-F1 |
|---|---:|---:|---:|---:|---:|
| frozen_test | 413 | 0.920097 | 0.912833 | 0.921027 | 0.915331 |
| independent_source_holdout | 621 | 0.867955 | 0.900161 | 0.803507 | 0.819986 |

Per-class metrics, confusion matrices, probabilities/logits, paired correctness and Wilson intervals are
in the corresponding metrics JSON and predictions CSV files. Tests were evaluated only after weights were fixed.
A lower candidate score is reported as such; no additional test-driven run or automatic production promotion occurs.

## ONNX And Conversion Handoff

- best.onnx SHA-256: `3e49e2451993e6e45e452253dd94a456c58ecdee634dfe1ffeb276053aa6cbfb`.
- best.pt SHA-256: `bc0ed384f8904a5cddad49d4b53942d29e3d43159fbdac6a5e421c76a6702b44`.
- Static float32 input images [1,3,224,224], RGB NCHW, pixels /255.
- EXIF transpose, bilinear resize shorter edge to224 with aspect preserved, center crop224.
- Output [1,3], labels 0 foot-and-mouth, 1 healthy, 2 lumpy; Softmax is already in graph.
- nn.Classifier must use softmax=False for best.onnx. A separately extracted logits graph must use True and revalidate.
- mean=[0,0,0], scale=[1/255,1/255,1/255], formula (pixel-mean)*scale; avoid double normalization.
- split.json images and training_calibration_manifest.json are converter-compatible; calibration uses train only.
- Three train-only float32 reference tensors and exact input records accompany input_output_contract.json.
- PT CUDA/ONNX CPU parity: {'passed': True, 'tested_images': 1034, 'maximum_absolute_difference': 2.771615982055664e-06, 'mean_image_maximum_absolute_difference': 1.666365640203045e-07, 'argmax_agreement': 1.0, 'atol': 1e-05, 'rtol': 0.0001, 'pytorch_device': 'cuda:0 strict FP32, TF32 disabled', 'onnx_provider': 'CPUExecutionProvider', 'onnx_checker_passed': True, 'input_shape': [1, 3, 224, 224], 'output_shape': [1, 3], 'softmax_in_graph': True}.

No cvimodel/mud conversion, device execution, hardware/backend changes or production registration was performed here.

## Limits

All sources lack verified animal IDs, farm IDs, recording dates, veterinarian labels and clinical reference standards.
Uploader licenses/collection claims do not establish individual image rights or clinical correctness.
Image components reduce known duplicate leakage but cannot prove distinct animals/farms or detect every crop, montage,
rotation, repeated animal view, web repost or pretraining overlap. Source holdout is a public-source stress test.
Directory labels can encode background/breed/watermark/source bias; healthy is not verified clinical health.
No clinical diagnosis, calibration, sensitivity in farms, lesion localization or risk-fusion claim is made.
Ultralytics code/weights licensing remains applicable.

Before training, a preparation attempt was rejected because ancestor-directory parsing could map "unhealthy"
from an LSD dataset root and a highly overlapping whole-source holdout discarded nearly all old training data.
That attempt, which has no model checkpoint or epoch results, is retained under rejected_preparation_01.
The corrected run uses only direct class-directory labels and source-overlap criteria; no test predictions
were used for these corrections. split_exclusion_audit.json documents every removed prior validation image.
source_acquisition_receipts.json and source_pair_global_group_overlap.csv preserve hashes/licenses and source intersections.

## Commands

```powershell
& .run/cattle-ml-venv/Scripts/python.exe -m unittest discover -s scripts -p test_vision_expand_retrain_20261026.py
& .run/cattle-ml-venv/Scripts/python.exe scripts/vision_expand_retrain_20261026.py --stage acquire
& .run/cattle-ml-venv/Scripts/python.exe scripts/vision_expand_retrain_20261026.py --stage inventory
& .run/cattle-ml-venv/Scripts/python.exe scripts/vision_expand_retrain_20261026.py --stage prepare
& .run/cattle-ml-venv/Scripts/python.exe scripts/vision_expand_retrain_20261026.py --stage train
& .run/cattle-ml-venv/Scripts/python.exe scripts/vision_expand_retrain_20261026.py --stage finalize
```

Inventory, split preparation and training refuse an existing completed stage. No old run is overwritten.
SHA256SUMS.txt/artifact_hashes.json cover artifacts except their own indexes and active console.log.

## Host Conversion Handoff Verification

The main agent prepared classifier_logits.onnx and 120 calibration files in maixcam-expanded-yolo-20261026.
Extracted logits SHA-256: `2774d857d2d9cff0526e665d61d899c96eb6619fb9b550f30de97589c6a7d23d`.
All 120 files have verified hashes, pixel-exact bilinear resize/center crop, and distinct train-only groups (40 per class).
No validation, frozen-test or source-holdout group was used for calibration.
On three train-only reference tensors, softmax(logits) matches the original probability graph; max absolute difference 2.910383046e-11.
The logits graph requires classifier_softmax=True; best.onnx retains Softmax and requires False.
This verification did not rerun training or heldout inference and did not change model weights.
The main agent owns the separate WSL conversion process; this check does not execute or deploy the camera.
Physical deployment/device inference remain unverified because the camera USB/network is unavailable.
UI checks were static: research snapshots remain unapproved, with a generic feature/archive badge.
The existing vision screenshot predates this work and is not evidence of the new classifier path.
Run the host check with --stage verify-handoff. Detailed evidence: handoff_final_verification.json.

The main agent's converted CVIMODEL SHA-256 is `ca9900d75e8b0b0dca0f15d7b425077de031fb5c3da676ed4cef44736492da09`.
The CVIMODEL hash, MUD same-directory model reference, RGB input, normalization and label order passed read-only checks.
The host deployment log records a successful TPU simulator comparison. This is not physical camera execution.
The reported 413/621-image metrics apply to the FP32 research model; INT8 heldout accuracy was not evaluated here.
Run converted-file checks with --stage verify-conversion-files.
