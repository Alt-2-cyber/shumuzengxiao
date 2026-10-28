# Expanded calf cough event experiment (2026-10-26)

Status: downloaded, audited, actually trained and revalidated on CPU. Research
acoustic events only; `clinical_diagnosis=false`. Final counts supersede the
intermediate 553-file count before decoded-PCM deduplication.

## Actual results

Figshare contributed **725 additional original WAV files**, including **266
author-labeled calf coughs**. After explicit exclusions it contributes **512
distinct included PCM recordings**. Together with the previous 40 INRAE files,
the experiment contains **552 included original recordings** (286 cough,
266 non_cough), totaling 643.585941 observed seconds. There are no augmented
training samples, human/pig substitutes or fabricated veterinary records.

| Paired evaluation, identical files and folds | Fixed baseline accuracy | Spectral accuracy | Fixed baseline macro F1 | Spectral macro F1 |
| --- | ---: | ---: | ---: | ---: |
| Original 40, exact previous five file folds | 0.725000 | 0.900000 | 0.724828 | 0.899749 |
| Expanded development, 378 files, five group folds | 0.854497 | 0.910053 | 0.847852 | 0.907566 |
| Reserved final holdout, 174 files, two filename groups | 0.827586 | 0.879310 | 0.809211 | 0.861102 |

The original comparison improves from 29/40 to 36/40 correct. The final
holdout improves from 144/174 to 153/174 correct. Final holdout balanced
accuracy is 0.883721 versus 0.918605; cough recall is 0.767442 versus
0.837209, and cough F1 is 0.868421 versus 0.911392. Both models have cough
precision 1.0 on this limited holdout. ROC AUC is 0.957278 versus 0.989492.
These selected-source, whole-clip metrics do not establish animal/session
independence, continuous-barn false-alarm rates, clinical performance or a
statistically significant improvement.

Final holdout confusion matrices use true rows and predicted columns in
`[non_cough, cough]` order:

```text
fixed baseline: [[45, 0], [30,  99]]
spectral model: [[45, 0], [21, 108]]
```

The runtime model trains only on **378 development recordings**, comprising
the original 40 plus **338 additional Figshare recordings**. They contain
157 cough and 221 non_cough events. The **174 reserved Figshare recordings**
(129 cough, 39 metal, six excretion) remain outside the runtime model.
Development has 13 effective heuristic groups; the holdout consists of the
`lyyn` and `y` filename families. Group/hash overlap is zero, but verified
animal and session group counts are both zero.

Final model: balanced RBF SVC, C=1, gamma=0.007518796992481203, 133 features,
216 support vectors, fixed threshold 0.5. Numeric JSON is **619,719 bytes**;
no pickle, torch or GPU is used. Its SHA256 is
`9851f50d3ef6cd858a2effe4bcfefa5018e16b0f12982ffb5866ee422ab9268e`.

## Fixed implementation and evaluation plan

The authorized scope is public bovine/calf cough acquisition and a CPU audio
experiment. Existing scripts, runs, hardware and backend remain read-only.
New writes are limited to this report, `scripts/audio_expand_retrain_20261026.py`,
`tests/test_audio_expand_retrain_20261026.py`,
`audio-training-data/external/calf-cough-expanded-20261026/`, and
`audio-training-data/artifacts/calf-cough-expanded-20261026/`.

- [x] Retrieve bounded public metadata and files, starting with Figshare
  DOI 10.6084/m9.figshare.31979640. Record HTTP failures as well as successes,
  original responses, SHA256, repository checksums, attribution and licenses.
- [x] Audit actual audio labels and parent/animal/session grouping. Unknown
  mappings stay unknown. Long unannotated INRAE files are not labeled.
- [x] Write and run failing tests for download bounds, spectral extraction,
  coverage, grouping, train-only preprocessing and portable prediction.
- [x] Train a fixed legacy baseline and nested spectral model comparison on
  identical outer folds, with all choices made using training data only.
- [x] Export JSON parameters, a runtime contract, memberships and predictions;
  revalidate input hashes, fitted scalers, all held-out scores and CLI output.
- [x] Report actual source counts, comparable metrics, limitations and commands.

Protocol fixed before expanded model training: 8 kHz, nonoverlapping 1 s
windows, no zero trimming, explicit optional native-rate valid-prefix count.
The legacy 14-feature C=0.1 logistic model is fixed. The spectral family uses
40 log-mel bands and 13 MFCCs with temporal summary statistics, train-only
StandardScaler, and a small predeclared regularization grid. Outer folds
hold out provenance groups when available; the original 40 files retain the
exact saved five-fold assignment for a paired legacy comparison. A nested
three-fold selection uses only each outer training partition. Unknown animal
or session mappings cannot establish animal-independent validation. No
augmentation is counted as a recording. No disease or healthy labels exist.

The complete Figshare download was recovered from the official public
`ndownloader.figshare.com` article endpoint. It is an outer 133,088,009-byte
ZIP containing the 133,087,841-byte `Calf dataset.zip` advertised by DataCite.
Both archives passed every member CRC. The nested archive contains 725 WAVs:
266 cough, 211 `ab`, 48 excretion and 200 metal. No README or animal/session
mapping is included. All files are under the author's `test/` folder. The
unexplained `ab` class is excluded rather than assigned a binary event label.
One excretion clip is shorter than 0.1 s and one metal clip duplicates decoded
PCM from another file. After these exclusions the new dataset contributes
512 distinct PCM recordings. Together with the original 40, there are 552
included originals (286 cough, 266 non_cough), without augmentations.

Expanded evaluation is a local research repartition of the supplied author
test folder, not a reproduction of the author's experiment. Before model
outcomes, group files by the casefold suffix after their leading event number,
with trailing digits removed; an empty suffix is one unmapped family. These
are **unverified filename families**, never invented animal/session IDs.
Merge families linked by duplicate PCM before deduplication. All 40 unknown
INRAE source files are one conservative development group. Reserve the first
five-fold StratifiedGroupKFold split of additional groups (seed 20261026) as
the final holdout; all original files remain development. Use five outer
development folds and three inner folds. Original-40 paired comparisons use
the exact old five file folds. A model is selected using development data only,
saved with a frozen hash before the reserved holdout is scored, and remains
trained only on development data. The final holdout is not added to runtime
training.

Each original clip contributes one feature vector from all its observed
samples. Long author-classified clips are not split into invented interval
labels. This yields whole-clip event metrics; it does not validate continuous
one-second streaming boundaries. Source durations and other collection
differences remain confounders even though explicit duration is excluded.
The seven candidates are balanced L2 logistic regression C=0.001/0.01/0.1/1
and balanced RBF SVC C=0.1/1/10 with gamma=scale. Select by mean inner balanced
accuracy with first candidate as the deterministic tie-break. The fixed old
baseline retains C=0.1, no class weights, old 14 features and threshold 0.5.

The actual development outer folds have train/test counts 307/71, 293/85,
316/62, 304/74 and 292/86. All parameter selection and StandardScaler fits
use only the corresponding training partition. No feature selection,
threshold tuning or final-candidate choice uses the reserved holdout.
`holdout_unseal_record.json` pins both model hashes and the development-only
selection before held-out scoring. Revalidation repeats the same fixed
calculations, without changing candidates or choosing from test results.

## Source access, provenance and license

Dataset: Ma, Juncheng (2026), *Dataset for "Boosting cough recognition of
livestock animals in farming environments through parameter-efficient tuning
of multimodal audio pre-trained models"*,
[10.6084/m9.figshare.31979640](https://doi.org/10.6084/m9.figshare.31979640).
DataCite describes it explicitly as the **calf dataset** and declares
**CC BY 4.0**. Archive directory labels are author labels; they do not supply
per-file veterinary evidence. Attribution and preprocessing changes are
retained in manifests, the model and this report.

Official successful endpoint:
[article package](https://ndownloader.figshare.com/articles/31979640/versions/1).
Direct curl returned HTTP 200, downloaded 133,088,009 bytes in 307.010194 s,
and matched Content-Length. The outer archive SHA256 is
`027eb0e4350260491e3c47bf444002e2f6e3bf453c9bc25e886cc28e8b139805`;
the nested dataset archive SHA256 is
`d82d1424b2666ed3a8a66b7589dc36341f7b6d9c90e4f1d7b785185532169829`.
The nested size matches the 133,087,841 bytes in independent DataCite metadata.
Both archives passed every member CRC; all 725 extracted WAV hashes also
match their archive members. No upstream file MD5 was available because the
article/file metadata APIs remained HTTP 403. SHA256 and CRC are recorded
without claiming an unavailable publisher checksum.

The first urllib transfer ended at 34,819,511 bytes despite a declared length
of 133,088,009. Its historical `complete=true` flag was incorrect and is
explicitly superseded by `figshare-download-record.json` and the complete
integrity record. The downloader now rejects length mismatches. Standard
Range requests returned 200 without Content-Range, so their bytes were never
appended. A complete fresh public download solved acquisition. The other
`figshare.com/ndownloader` route returned 202 with an AWS WAF challenge; that
challenge was not bypassed. API 403 responses and the challenge remain
source-access failures, not evidence that the dataset was empty.

Sixteen bounded public API checks are saved with raw responses, status,
timestamps, byte limits and hashes. Direct access was used for the successful
download; no credentials, global proxy changes or restriction bypass was
used. Current-source bounds:

| Candidate | Actual finding and contribution |
| --- | --- |
| Figshare 31979640 | Full 725-file public archive acquired and audited; 512 included originals |
| INRAE 10.57745/FP5LA9 | Existing 40 originals retained and repository MD5 rechecked; four long unannotated WAVs contribute zero labels |
| Zenodo 17764250 | Metadata HTTP 200, restricted access and zero public files; zero new audio |
| Other DataCite/Zenodo search results | Mostly unrelated or non-acoustic records; no additional verified cough audio acquired |
| GitHub calf-cough-array | Tree HTTP 200; tiny README/placeholders only, no audio, no license |
| Kaggle calf cough | HTTP 200, empty list |
| Hugging Face calf cough | Bounded connection failure; zero acquired, not a claim of absence |

Figshare excludes 211 `ab` WAVs because their meaning is undocumented here;
one 0.0570068 s excretion file is too short; one metal file duplicates another
file's decoded PCM. `metal_73w5.wav` duplicates `metal_32wang.wav`, linking the
`w` and `wang` filename families before deduplication. Neither duplicates nor
8 kHz conversion/padding fixtures count as new recordings. Formats are 722
44.1 kHz stereo files decoded as int16 and three 48 kHz stereo files decoded
as int32; the previous 40 INRAE files are 44.1 kHz mono int16.

INRAE attribution remains Mach et al. (2026), INRAE/ENVT,
[10.1016/j.animal.2026.101928](https://doi.org/10.1016/j.animal.2026.101928).
Its repository Etalab 2.0 license conflicts in scope with the preprint's
research/education wording, so the combined output remains research only.
No source provides auditable animal/session/parent or per-file clinical
records. `non_cough` never means healthy, and `cough` never identifies disease.

## Features and portable inference

The 133 features consist of old shape14, 40 log-mel means, 40 log-mel population
standard deviations, 13 MFCC means, 13 MFCC population standard deviations,
and 13 standard deviations of adjacent-frame MFCC differences. Features use
only observed samples after DC subtraction and AC-RMS normalization.
Spectral frames are 200 samples with 80-sample hop, periodic Hann and a
512-point FFT. Forty HTK mel triangles span 80-3800 Hz, each normalized to sum
one; use natural log with a 1e-10 floor. Orthonormal DCT-II coefficients 1-13
exclude coefficient zero. The new zero-crossing statistic treats unit-RMS
values within 1e-12 of zero as numeric zero, avoiding gain/DC fixture rounding
instability. The old fixed baseline's feature implementation is unchanged.

The JSON stores train-only scaler parameters, standardized support vectors,
dual coefficients and intercept. Inference computes
`z=(features-mean)/scale`, then the RBF signed margin
`m=sum(dual_i*exp(-gamma*sum((z-support_i)^2)))+intercept`.
The output score is `sigmoid(m)`, with cough at score >=0.5. This sigmoid is
an uncalibrated score, not an externally calibrated probability. Logistic
fold models also use numeric JSON and the same research scope.

## Runtime contract

Default model: `audio-training-data/artifacts/calf-cough-expanded-20261026/model.json`.
CLI: `python -B -X utf8 scripts/audio_expand_retrain_20261026.py predict <wav>`.
Import API: `predict(wav_path, model_path=ARTIFACTS / "model.json", valid_input_samples=None) -> dict`.
WAV rates >= 8000 Hz are converted with anti-aliased resampling, channels are
averaged in full-scale float, and each nominal 1 s window retains its offset,
observed samples, known input padding and algorithm padding. Optional
`--valid-input-samples N` declares an observed prefix at the native WAV rate;
the remaining decoded full-scale samples must be exactly zero (unsigned-8
silence is native value 128). Without it, all samples
are observed, including recorded silence.

Output has `research_only=true`, `clinical_diagnosis=false`,
`clinicalDiagnosis=false`, `allow_for_disease_labels=false`,
`non_cough_means_healthy=false`, `sample_rate_hz=8000`, `window_samples=8000`,
`model_version`, `model_sha256`, `input_duration_seconds` and `windows`.
Each window has `start_seconds`, nominal `end_seconds`,
`observed_end_seconds`, `status`, `label`, `score`, `abstention_reason`,
coverage and quality. Status is `scored` or `abstain_*`; label is `cough`,
`non_cough` or null. Aliases `cough_score`, `predicted_event` and
`source_label_scores` are retained for import users.

Unsigned 8-bit decoding is `(value-128)/128`; integer signed PCM uses the
dtype full-scale divisor and float WAV is unchanged. Arithmetic channel
averaging occurs in float. Source PCM saturation is measured before downmix.
Fixed engineering abstentions are no observed samples, AC RMS <=1e-8,
fewer than 800 observed 8 kHz samples, and >=1% native PCM frames touching
decoded integer rails or abs(float)>=1 in any channel. These are engineering
criteria, not veterinary or statistically calibrated rejection thresholds.
An 8-bit format fixture passed; microphone/gain/quantization score calibration
on independent ESP32 recordings is still absent.

Two-second aggregation is not validated and `aggregate_event` remains null.
A two-second padded fixture with explicit prefix 8000 produces one score and
one `abstain_no_observed_samples`; without coverage metadata, its second
window remains observed and returns `abstain_silence`. No zero trimming occurs.

The main agent separately verified an actual archived ESP32 WAV through HTTP
ingest, archive/rehash, its research endpoint and this CLI: endpoint and direct
CLI scores agreed within 1e-12, file tampering returned 409 before cache use,
and results stayed outside health fusion. That integration is owned by the
main agent; no backend, watcher, UI or hardware file was changed by this work.

## Artifacts and completed verification

Data root:
[calf-cough-expanded-20261026](D:/table/shumuzengxiao/audio-training-data/external/calf-cough-expanded-20261026/).
Artifact root:
[calf-cough-expanded-20261026](D:/table/shumuzengxiao/audio-training-data/artifacts/calf-cough-expanded-20261026/).

| Exact file under the respective root | Contents |
| --- | --- |
| Data: `raw/figshare-31979640/full-curl.zip` | Complete official article package |
| Data: `raw/figshare-31979640/unpacked/Calf dataset.zip` | Original nested dataset archive |
| Data: `raw/figshare-31979640/unpacked/dataset/Calf dataset/test/` | All 725 extracted original WAVs |
| Data: `evidence/`, `http_checks.jsonl`, `figshare_range_checks.jsonl` | Raw metadata/error snapshots and bounded request evidence |
| Data: `figshare-download-record.json`, `figshare-complete-integrity.json` | Correct full lengths, hashes, CRCs and partial-download correction |
| Data: `included_manifest.jsonl`, `excluded_manifest.jsonl`, `source_audit.json` | 552 included and 213 excluded files, labels, unknowns, grouping, licenses and hashes |
| Artifacts: `model.json`, `baseline_model.json` | Final development-only runtime model and comparable fixed baseline |
| Artifacts: `input_contract.json`, `feature_definition.json` | Stable runtime API, abstentions and exact ordered feature formulas |
| Artifacts: `protocol.json`, `split_plan.json`, `holdout_unseal_record.json` | Fixed grid, all memberships, group definitions and pre-score model hashes |
| Artifacts: `final_development_selection.json` | Actual three-fold development-only candidate scores and scaler means |
| Artifacts: `fold_models/original40_comparison/`, `fold_models/expanded_development/` | Ten spectral and ten baseline fold JSON models |
| Artifacts: `original40_comparison_report.json`, `expanded_development_report.json`, `final_holdout_report.json` | Actual paired metrics, candidates and nested audits |
| Artifacts: `original40_comparison_oof_predictions.jsonl`, `expanded_development_oof_predictions.jsonl`, `final_holdout_predictions.jsonl` | All held-out scores for both models |
| Artifacts: `features.npz`, `input_manifest.jsonl`, `provenance.json` | Numeric non-pickle features/targets/groups, full membership and source hashes |
| Artifacts: `training_report.json`, `unit_checks.json`, `verification.json` | Environment, actual results and completed behavioral/numeric checks |
| Artifacts: `examples/` | Actual runtime calls, coverage examples and a clearly marked derived unsigned-8 format fixture |
| Artifacts: `SHA256SUMS.txt` | Scope-wide SHA256 list, including source archives, WAVs, snapshots, code, tests and this report |

Completed revalidation: **14/14 behavioral tests**, 552 included and 213 excluded
source-file hashes, all 40 INRAE repository MD5 checks, two complete-archive CRC
checks, all **725 extracted WAV/archive hash matches**, and exact regeneration
of 552 feature vectors. The previous 40 baseline feature vectors and OOF scores
are exactly unchanged. All **22 saved models** were refit with train-only
scalers, all **11 nested choices** reproduced, and all **1,184 prediction
records** plus fold/aggregate metrics reproduced. Maximum JSON/sklearn score
absolute error was **5.773159728050814e-15**. Independently counting saved
holdout labels recovered both confusion matrices, accuracies and macro F1s.
The final holdout has zero training group/hash overlap; animal independence
remains unestablished. The scoped checksum list also verifies this report.

## Reproduction and limits

Working directory: `D:\table\shumuzengxiao`. Actual environment: Python
3.13.14, NumPy 2.4.3, SciPy 1.17.1, scikit-learn 1.8.0, Windows 11, CPU only,
one numeric thread. No package installation or GPU reservation was needed.

The successful full public download command was:

```powershell
curl.exe --noproxy '*' --connect-timeout 8 --max-time 720 --retry 2 --retry-delay 1 --retry-max-time 1500 --fail --location --silent --show-error --output 'audio-training-data/external/calf-cough-expanded-20261026/raw/figshare-31979640/full-curl.zip' --dump-header 'audio-training-data/external/calf-cough-expanded-20261026/evidence/figshare-full-curl.headers' --write-out 'HTTP %{http_code} BYTES %{size_download} SECONDS %{time_total}' 'https://ndownloader.figshare.com/articles/31979640/versions/1'
```

These commands were actually executed; `acquire` resumes named metadata
checks already saved rather than redownloading the successful full package:

```powershell
python -B -X utf8 D:\table\shumuzengxiao\scripts\audio_expand_retrain_20261026.py acquire
python -B -X utf8 D:\table\shumuzengxiao\scripts\audio_expand_retrain_20261026.py inspect-figshare
python -B -X utf8 D:\table\shumuzengxiao\scripts\audio_expand_retrain_20261026.py audit-data
python -B -X utf8 D:\table\shumuzengxiao\scripts\audio_expand_retrain_20261026.py train
python -B -X utf8 D:\table\shumuzengxiao\scripts\audio_expand_retrain_20261026.py verify
python -B -X utf8 D:\table\shumuzengxiao\scripts\audio_expand_retrain_20261026.py predict D:\table\shumuzengxiao\audio-training-data\external\20261025\derived\rdg-FP5LA9-8khz-2s\cough_001.wav --valid-input-samples 8000
python -B -X utf8 -m unittest discover -s D:\table\shumuzengxiao\tests -p test_audio_expand_retrain_20261026.py -v
```

Primary code and test:
[audio_expand_retrain_20261026.py](D:/table/shumuzengxiao/scripts/audio_expand_retrain_20261026.py),
[test_audio_expand_retrain_20261026.py](D:/table/shumuzengxiao/tests/test_audio_expand_retrain_20261026.py).
Input manifest SHA256:
`bca59147c3606cecd770e7a5c2ae95120311dc4310bb8f0f51bf2ef0f588ad73`.

Remaining limits are source/animal/session uncertainty, heuristic grouping,
the local reuse of an author `test/` folder with a new reserved holdout,
source-clip duration confounding, excluded ambiguous `ab` labels, only
metal/excretion and the original selected noncough controls, and unvalidated
one-second streaming boundaries. Neither disease diagnosis nor healthy labels
are supported. Independent farms/animals, continuous annotated barn audio,
ESP32 microphone/gain/quantization calibration and resolved combined license
scope remain necessary for broader use. No production threshold, firmware,
release gate, veterinary record or health-fusion mapping was created.
