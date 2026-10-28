# YOLOv8n-cls source-label image-group heldout research

Completed UTC: 2026-10-26T02:50:51.891172+00:00. Status: `research_only`.

This is **source-label image-group heldout**, not independent farm disease
accuracy, external clinical validation, or a veterinary diagnostic model.
The three outputs rank appearance associated with public source-directory
labels, including `foot-and-mouth`; that label is not proof of FMD. Scores
are not calibrated clinical disease probabilities. No animal ID, farm ID,
veterinarian, laboratory result, or clinical reference standard was supplied.

## Existing Project Restrictions

Read the local source dataset card, both existing vision baseline model cards,
the model release manual, the hardware integration plan, and MaixCAM README.
The existing deployed YOLO model is a COCO cow detector. Its cow detections
cannot establish lesions, behavior, or diseases. Existing baseline metrics
were image-level source-label results and cannot establish independent farm
accuracy. This classifier is a separate research artifact. No hardware or
backend files were edited, no serial port was opened, and no MaixCAM files
were converted, installed, or registered for production by this script.

## Source and Deduplication

- Source: https://www.kaggle.com/datasets/devang03mgr/cattle-diseases-datasets
- Local source: `D:\table\shumuzengxiao\疾病识别生产落地\外部视觉数据\Kaggle_CattleDiseases_2025\raw\Cows datasets`.
- Original images: 3244; counts: `{'foot-and-mouth': 746, 'healthy': 1291, 'lumpy': 1207}`.
- Decodable images: 3244; invalid images: 0.
- Connected image groups: 2755; eligible groups: 2752.
- Cross-class groups quarantined: 3, containing
  7 source images. Entire components were copied
  to `quarantine/` and excluded. Raw source files were not modified.
- Same-class redundant variants excluded: 485.

Every file has SHA-256 of original bytes and EXIF-transposed decoded RGB pixels
(with width/height header), plus 64-bit DCT pHash and dHash for original and
mirrored images. Connected components merge exact file/pixel matches,
Roboflow names stripped of `.rf.*` and `_jpg`/`_png` variants, and near matches
with pHash Hamming distance <=6 AND dHash <=10, aspect ratio within 10%.
Descriptive Roboflow names are global; ambiguous numeric stems are namespaced
by source folder because numeric equality alone does not establish provenance.
Content matching remains global across all labels. Every mixed-label component
is quarantined. Edge reasons and members are recorded in `duplicate_edges.json`
and `groups.json`; no clinical relabeling was attempted.

One representative per eligible component is chosen by largest pixel area,
then file SHA-256 and path. All other members remain inventoried but are
excluded from model inputs. The heuristic cannot detect all crops, rotations,
montages, or repeated views of the same animal; it is not animal/farm grouping.

## Fixed Group Split

Seed 20261026; stratified at group level, approximately 70/15/15. Split assignment
was frozen before training. Test representatives are in `heldout_test/`, outside
the `dataset/` root read by Ultralytics. Test was not used for early stopping,
hyperparameter selection, threshold selection, or checkpoint selection.

| Split | foot-and-mouth | healthy | lumpy | Total |
|---|---:|---:|---:|---:|
| train | 460 | 828 | 638 | 1926 |
| val | 98 | 178 | 137 | 413 |
| test | 98 | 178 | 137 | 413 |

All retained inputs are EXIF-corrected, lossless RGB PNGs. `manifest.jsonl`
preserves every original source path, label origin, hashes, group, split and
role. `split.csv`/`split.json` enumerate the representative inputs. Final
integrity checks rehashed all original files, materialized inputs and
quarantine copies and confirmed no exact/pixel/source-name group overlap.

## Actual Training

- Architecture: official pretrained YOLOv8n-cls, adapted to three classes.
- Weights: https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n-cls.pt
- Downloaded weight SHA-256: `11fa19f2aea79bc960d680a13f82f22105982b325eb9e17a4a5e1a9f8245980a`.
- GPU: NVIDIA GeForce RTX 3050 6GB Laptop GPU.
- Input 224, batch 16, workers 0, FP32, AdamW lr0=0.001/lrf=0.01,
  weight decay 0.0005, warmup 3, dropout 0.1.
- 30 epoch cap, patience 8; actual epochs: 13.
- Wall training time: 756.17 seconds.
- Peak allocated CUDA memory: 0.353 GiB.
- Maximum validation top-1: 0.888620, first reached
  at epoch 5 (CSV is 1-based).
- Selected checkpoint epoch: 12; equal-fitness
  checkpoints use the trainer's latest tie. Native fitness is (top1+top5)/2;
  top5=1 for three classes, so its ranking equals validation top1.
- Selection: a single prespecified run, validation top-1 fitness only. Best
  checkpoint copied to `best.pt` and SHA-locked before heldout inference.
- Augmentation: random resized crop with area range [0.7,1.0] (scale=0.3 argument), horizontal
  flip 0.5, HSV h/s/v=0.015/0.3/0.2; no auto augment or erasing.

Full arguments, epoch history, environment/package versions, and timing are
in `training_protocol.json`, `training_history.csv`, `environment.json`, and
`training_summary.json`. A reproducible script snapshot is included.

## Heldout Results

Each evaluated image is the single representative of a distinct heldout image
group. There are 413 images/groups and 380 correct source-label
predictions. Accuracy: **0.920097**; balanced accuracy:
**0.919960**; macro-F1: **0.921027**;
weighted-F1: 0.920139; log loss: 0.354711.
Accuracy Wilson 95% interval: [0.889910,
0.942541], an image-group binomial approximation,
not uncertainty across independent farms or animals.

| Public source label | Precision | Recall | F1 | Groups/images |
|---|---:|---:|---:|---:|
| foot-and-mouth | 0.946809 | 0.908163 | 0.927083 | 98 |
| healthy | 0.925714 | 0.910112 | 0.917847 | 178 |
| lumpy | 0.895833 | 0.941606 | 0.918149 | 137 |

Confusion matrix: rows are source labels and columns predicted labels, both
in order `foot-and-mouth`, `healthy`, `lumpy`.

```text
  89    5    4
   5  162   11
   0    8  129
```

`heldout_predictions.csv` includes source/group paths, all PyTorch logits,
PyTorch/ONNX probabilities, correctness, and per-image numerical differences.
Confusion matrices are supplied as CSV and PNG. No test-driven retraining or
claim of independent external validation was performed.

## ONNX and MaixCAM Handoff

`best.onnx` is float32, opset 13, fixed batch 1, static input `[1,3,224,224]`
and output `[1,3]`; ONNX checker and ONNX Runtime CPU execution passed.
All 413 heldout inputs were compared with PyTorch CUDA:
maximum absolute probability difference 4.231929779e-06,
argmax agreement 1.000000; tolerance atol=1e-5, rtol=1e-4.
Strict reference inference disables CUDA/cuDNN TF32. The first parity check
with the default cuDNN TF32 setting differed by 0.000796318 on one input;
CPU and strict FP32 CUDA isolated the issue to numerical precision, not the
checkpoint or graph. The unchanged tolerance passed after disabling TF32.
The initial failure and diagnostic values are retained in the artifacts.
No weights, data splits, or training hyperparameters changed during this fix.

The later `nn.Classifier` conversion needs this contract:

- RGB, NCHW, 224x224, float32. EXIF transpose, bilinear resize shorter edge to
  224 while preserving aspect ratio, then center crop 224x224. Directly
  stretching a non-square image is not the evaluated preprocessing.
- For raw RGB 0..255, `mean=[0,0,0]`,
  `scale=[0.00392156862745098,0.00392156862745098,0.00392156862745098]`.
  Formula: `(pixel - mean) * scale`. Do not divide by 255 twice. Torchvision
  mean/std after ToTensor are `[0,0,0]` and `[1,1,1]`.
- Labels in exact index order: `0=foot-and-mouth`, `1=healthy`, `2=lumpy`.
- Exported ONNX output is **softmax probabilities**, with Softmax already in
  the graph. Do not apply softmax again. Native PyTorch evaluation returns
  `(probabilities, logits)`; training consumes logits. A converter that removes
  Softmax would need to declare a different output contract and revalidate it.
- MaixPy's documented default is `classifier.classify(img, softmax=True)`.
  With this exported graph preserved, explicitly use
  `classifier.classify(preprocessed_rgb_image, softmax=False)`. Reference:
  [official MaixPy classification documentation](https://github.com/sipeed/maixpy/blob/main/docs/doc/en/vision/classify.md).
- `input_output_contract.json`, `labels.txt`, and three float32 reference
  tensors (`reference_inputs_nchw_float32.npy`) accompany per-image reference
  logits/probabilities. Feed each reference tensor individually for batch 1.
- The main agent must convert with the correct MaixCAM toolchain, preserve
  geometry/normalization, and verify `nn.Classifier` decoding and converted
  numeric outputs. No `.mud`/`.cvimodel` or hardware execution is claimed here.

## Limitations and Reproduction

Source-label bias can include breed, background, image framing, web source,
watermarks and augmentation style. Healthy folder membership does not prove
clinical health. Image grouping reduces known duplication leakage but does
not establish animal, farm or date independence. Pretrained data overlap is
unknown. There are no clinical calibration, prospective, multi-farm, lesion
localization or diagnostic performance claims. Full images were used; this
run did not train or evaluate cow-detector crops or a cascade.

Original source data rights are reported by the existing card as
`Database: Open Database, Contents: Database Contents`; individual image
rights were not independently audited. Ultralytics code/weights licensing
must be reviewed before redistribution or commercial use.

```powershell
& .\.run\cattle-ml-venv\Scripts\python.exe scripts/train_vision_yolo_research_20261026.py --stage all
```

Preparation is immutable and will refuse an existing manifest. To inspect
or regenerate export/metrics from the frozen run, use `--stage finalize`.
`SHA256SUMS.txt` and `artifact_hashes.json` cover the run artifacts (excluding
the hashes index itself and the actively written console log). The Python
script does not access a serial port, SSH, camera, backend, or deployment API.
