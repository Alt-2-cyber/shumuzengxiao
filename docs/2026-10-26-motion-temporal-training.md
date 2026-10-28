# Temporal Neck Acceleration Candidate, 2026-10-26

An actual CPU training run produced a four-class temporal neck classifier.
On two completely held-out cows, accuracy is **85.7948%**, balanced accuracy
**83.3855%**, and macro F1 **0.838629**. The original pointwise forest algorithm,
retrained on the same source animals and evaluated by majority vote on the
same windows, obtains **55.4679%**, **69.9383%**, and **0.598612**, respectively.
These are new-source, four-class results; they are not comparable to the old
six-class 64.32% or binary posture 86.91% reports.

The candidate is research-only. Existing production firmware, behavior and
posture headers, old raw data, and prior reports were not changed by this
work. Clinical lameness remains disabled. No back/leg channels, clinical
labels, or additional cows were synthesized.

## Files And Ownership

- Training: `D:/table/shumuzengxiao/scripts/train_motion_temporal_20261026.py`
- Tests: `D:/table/shumuzengxiao/scripts/test_train_motion_temporal_20261026.py`
- Artifacts: `D:/table/shumuzengxiao/牛行为识别数据集/esp32_motion_temporal_20261026/`
- Contract: `feature_model_contract.json`
- Portable inference: `cattle_motion_temporal_candidate.h`, `motion_temporal_features.h`
- Model data: `candidate_model.json`
- Results: `training_report.json`, `heldout_predictions.csv`
- Grouping: `raw_animal_split.csv`, `window_manifest.csv`
- Audits: `existing_data_audit.json`, `public_data_audit.json`, `binary_posture_support.json`
- Checks: `numerical_parity.json`, `verification_results.json`, `protected_inputs_before.json`
- Reproduction evidence: `train_only_model_selection.json`, `legacy_pointwise_refit.json`,
  `legacy_comparison_fit.log`, `evaluation_cache.npz`, `training_script_snapshot.py`,
  `artifact_manifest.json`, `training_status.json`, and `sources/`.

Only the new script, its tests, this document, and that dated artifact
directory are owned by this work. Main-task runtime integration is separate.

## Existing Data Inspection

[andssuu/cattle_classification](https://github.com/andssuu/cattle_classification)
contains `dataset_6.csv`: 13,088 rows, six labels, and 671 contiguous label runs.
The labels contain 5,732 grazing, 2,034 lying-ruminating, 1,702 lying-resting,
1,559 standing-resting, 1,229 walking, and 832 standing-ruminating rows.
Run length quartiles are 4, 9, and 22 rows; the range is 1 to 177.

The file has no timestamps, animal IDs, session IDs, or sampling-rate column.
The local source README does not establish sensor placement or the 16,384
LSB/g conversion used by the old trainer. Existing firmware calls the model
neck-only, but that is not independent source evidence. Original chronology
cannot be certified from label runs. Therefore this CSV was audited and left
unchanged, and was not converted into purportedly verified temporal windows.

[HannahJames123/cattle-behavior](https://github.com/HannahJames123/cattle-behavior)
was inspected at the raw-file level:

| File | Actual rows | Evidence and decision |
| --- | ---: | --- |
| `AX3_RAW_DATA06272024_ok.csv` | 3,255 | Every adjacent timestamp is 1 second apart. 2,987 standing and 268 walking; two locomotion observers agree on all rows. Feeding observers also agree: 1,056 eating and 2,199 other. No animal ID or verified sensor placement; not pooled with 20 Hz neck data. |
| `Accelerometer_RawData_0815-08162024.csv` | 679,799 | Clock is only minute:second.tenth; 563,400 increments of 0.1 s, 116,382 repeated clock values, and 16 hourly wraps. No raw behavior labels, hours, dates, or animal ID. |
| `Observer2_0815-0816_datalabeling.csv` | 276 | Dated observation events, including 16 lying events, but no certified offset/join to the hour-less accelerometer clock. Two spelling variants of standing remain in the audit. |

The June file supports a one-row-per-second observation rate, not a verified
raw-device sampling rate. The August data were not joined by guessing an
hour/date. Existing local SHA-256 hashes and schemas are saved in the audit.

The prior clinical review in
`D:/table/shumuzengxiao/docs/2026-10-25-imu-data-evidence.md` remains applicable:
UCD has rear-leg Z sequences and farm groups but no independently verified
per-cow clinical `High` labels. It is incompatible with synchronous neck/back/
leg XYZ windows. Behavior was not substituted for those missing clinical labels.

## Public Source And Label Provenance

Source: [Ito et al., Japanese Black Beef Cow Behavior Classification Dataset,
v2.0.0, DOI 10.5281/zenodo.5849025](https://doi.org/10.5281/zenodo.5849025).
The downloaded archive contains `ReadMe.md` and `cow1.csv` through `cow6.csv`.
The source documents six Japanese Black Beef cows, neck-mounted Kionix
KX122-1037 acceleration, nominal 25 Hz, and collection at one Shinshu University
farm on 2020-06-12. Labels derive from synchronized video and majority voting
by three annotators; the source reports 69 person-hours of annotation.

The complete 14,460,415-byte ZIP was downloaded into the new candidate
directory. Interrupted transfer recovery used verified HTTP byte ranges.
The ZIP matches the API's MD5 `1ba658c6091461730c57e2b378218a39` and passes CRC.
Its SHA-256 is
`e715bdef153b8fa67ace914764fa6c62bf377b2ce519995db9c17dda5d9ff78e`.
The API response, byte-range responses, original ZIP, extracted README, six
unmodified CSVs, and per-file SHA-256 hashes remain under `sources/`.

There is a source licensing conflict: the API license field says CC BY 4.0,
while its description explicitly says CC BY-NC-ND 4.0. This work does not
resolve that conflict or confer production/commercial eligibility.

Actual files contain **1,391,224 native samples**. Of these, **271,171** carry
the four selected source labels: RES 150,130; RUS 53,229; MOV 50,199; GRZ 17,613.
The other rows include 540,695 blank labels (called BLN in the source README),
554,855 ETC rows, and the other named behaviors. None are treated as negatives
or relabeled into a selected class.

CSV UNIX timestamps are integer **milliseconds**, not seconds. They are
explicitly divided by 1,000. The raw order is preserved. Across the six files,
1,803 adjacent intervals differ from 40 ms by more than 12 ms, including 27
non-increasing intervals. Each such boundary breaks a segment. Clock reversals
are not sorted away or bridged. One file per animal and the collection date
are documented; no independent physical session identifiers are supplied.
The manifest's date field is not a claim of separate independently sampled sessions.

The source describes a +/-2g device, but actual CSV axes exceed that range in
5,152 rows, with observed extremes about -2.823 to +3.960 g. Values are retained
and audited rather than silently clipped or recalibrated. This is an additional
reason to require local sensor and mounting validation.

## Raw Split And Window Construction

The animal assignment was fixed in the early contract before training:

| Cow | Role | Native rows | GRZ windows | RUS windows | RES windows | MOV windows | All windows |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | train | 311,876 | 36 | 17 | 561 | 55 | 669 |
| 2 | train | 269,772 | 21 | 407 | 758 | 73 | 1,259 |
| 3 | train | 269,903 | 0 | 170 | 291 | 74 | 535 |
| 6 | train | 179,857 | 121 | 0 | 291 | 74 | 486 |
| 4 | heldout test | 224,912 | 33 | 210 | 221 | 191 | 655 |
| 5 | heldout test | 134,904 | 26 | 0 | 165 | 41 | 232 |
| Total | | 1,391,224 | 237 | 804 | 2,287 | 508 | 3,836 |

Training has 1,031,408 total native rows, of which 202,645 have selected labels,
and **2,949 windows**. Test has 359,816 total native rows, 68,526 selected-label
rows, and **887 windows**. The 3,836 windows use 423 distinct contiguous segments.

Animal groups are assigned before resampling or overlapping windows. A segment
ends at a record boundary, label change, invalid sample, or irregular timestamp.
Unknown/unselected labels interrupt continuity. Each selected segment is
separately resampled 25 -> 20 Hz with fixed
`scipy.signal.resample_poly(up=4, down=5, window=('kaiser', 5.0), padtype='constant')`.
The FIR radius is conservatively tracked as 13 native samples. The first and
last 20 resampled samples (one second each) are discarded. Eighty-sample
windows advance by 40 samples and their entire FIR support stays in the same
raw record, source label, and contiguous segment. The manifest records that
raw support using zero-based start and exclusive stop indices.

No raw animal contributes to both partitions. Because partitions are whole
animals, no temporal boundary exists within a raw recording between train and
test. Edge purges additionally protect label and timestamp discontinuities.
The resampling filter is fixed and has no learned parameters. There is no
scaler, imputer, PCA, SMOTE, or fitted transform using heldout data.

## Model Selection And Fair Comparison

Window duration and the 24-feature contract were fixed before test evaluation.
Three forest budgets, `(trees,max_leaves) = (16,16), (24,32), (32,48)`, were
compared by leave-one-training-cow-out validation using only cows 1/2/3/6.
Mean per-cow macro F1 was 0.589572, 0.576222, and 0.558345. Missing labels
contribute zero to this fixed four-label selection metric. Cows 4/5 never
participated in fitting or selection. The exported final forest remains fit
on cows 1/2/3/6; it was not refit on the heldout cows.

The selected candidate has 16 trees, at most 16 leaves/tree, maximum depth 8,
minimum 3 samples/leaf, square-root feature subsampling, balanced bootstrap
class weights, and random seed 20261026. CPU workers and numerical libraries
are limited to four threads; no GPU libraries or GPU training are used.

The legacy comparison imports the existing `CompactRandomForest` without
calling its export/main function. It changes the four task names only in the
in-memory module and retrains with 40 trees, maximum depth 11, minimum leaf 8,
3 features/split, 800 bootstrap samples/class/tree, and seed 20260719. Overlap
is deduplicated before pointwise fitting: 130,200 unique resampled training
points and 40,160 unique test points. Predictions on the identical test
windows use majority vote, with lowest-index tie breaking. Original legacy
source and production headers are never written.

| Model, same 887 test windows | Accuracy | Balanced accuracy | Macro F1 |
| --- | ---: | ---: | ---: |
| Temporal 24 features | 85.7948% | 83.3855% | 0.838629 |
| Legacy pointwise XYZ, refit + window vote | 55.4679% | 69.9383% | 0.598612 |
| Window mean XYZ only, same selected forest budget | 44.4194% | 46.3793% | 0.482995 |

| Class | Test windows | Temporal precision | Temporal recall | Temporal F1 | Legacy refit F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| grazing (GRZ) | 59 | 0.8727 | 0.8136 | 0.8421 | 0.7619 |
| standing_ruminating (RUS) | 210 | 0.8699 | 0.6048 | 0.7135 | 0.8142 |
| standing_resting (RES) | 386 | 0.8762 | 0.9171 | 0.8962 | 0.2637 |
| moving (MOV) | 232 | 0.8227 | 1.0000 | 0.9027 | 0.5546 |

The temporal candidate improves aggregate performance but **regresses on
standing rumination**, including recall 60.48% versus 76.19% for the refit
pointwise baseline. It must not be described as an improvement in every class.
Cow 4 accuracy is 83.9695%; cow 5 accuracy is 90.9483%. Cow 5 contains no RUS,
so its fixed-four-label macro F1 (0.674373) and supported-label macro F1
(0.899164) are both recorded to avoid hiding missing support.

Overlapping windows are not independent observations. An additional
predefined subset takes every third 2-second hop within each test segment,
giving 339 windows with disjoint raw FIR contexts. Temporal accuracy is
87.6106%, balanced accuracy 84.1079%, macro F1 0.857131; legacy refit results
are 54.8673%, 68.8181%, and 0.586949. These remain observations from only two
test animals, one farm and one day, rather than 339 independent animals.

## Standing And Lying Evidence

All 13 named source behaviors, ETC, and blank labels were inspected. REL
explicitly means resting in lying position; RES and RUS explicitly mean
standing resting and standing ruminating. MOV and GRZ are **not** remapped to
standing for a new posture ground truth. No lying-ruminating label exists.

REL occurs only in cow 2 (360 native samples = 14.4 seconds) and cow 4
(404 samples = 16.16 seconds), one contiguous run each. Under the actual
4-second window and edge-purge protocol these give only **5 training** and
**6 test** lying windows. The minimum support rule requires at least two
training animals with explicit lying for internal animal validation and one
untouched test animal with lying. This source fails it. A new binary posture
model was therefore not trained, and no binary header or invented metrics
were exported.

The existing binary posture model remains the default. Its prior accuracy
86.91% and macro F1 0.8555 are explicitly prior contiguous-run validation
results, not an animal-independent guarantee and not a comparison against
this four-class task. Its missing animal/session and sampling/placement
provenance remain limitations. The August observation events cannot fix
those gaps without a certified clock join and animal/location metadata.

## Portable Inference Contract

Input is one real neck XYZ stream, calibrated **g**, float32 interleaved as
`xyz[80][3]`, nominal 20 Hz, four seconds per window and a 40-sample hop.
First-to-last sample separation is 3.95 seconds. Runtime is responsible for
timestamps: reset after dropped, nonfinite or delayed samples and location/
configuration changes, and require 80 actual consecutive samples. Never fill
missing samples by duplication. Convert m/s^2 by 9.80665 exactly once.

Features are channel-major X, Y, Z, then Euclidean norm. For each channel:
mean, population standard deviation, min, max, mean absolute adjacent delta,
and RMS adjacent delta. XYZ is promoted from float32 to double; norm and
accumulations use double; the 24 outputs are float32. Variance uses a centered
second pass. No gyroscope, spectral model, learned normalization, or location
replication is required.

The C99/C++11 API is standalone, with no Arduino dependency:

```c
int motion_temporal_extract_features(const float *xyz, size_t samples, float *features);
MotionTemporalPrediction motion_temporal_predict_features(const float *features);
MotionTemporalPrediction motion_temporal_predict_window(const float *xyz, size_t samples);
```

The prediction contains `label`, `confidence`, `rejected`, and four
`probabilities`. Labels are **0 GRZ/grazing; 1 RUS/standing_ruminating;
2 RES/standing_resting; 3 MOV/moving**. MOV stays moving, rather than being
renamed to walking, standing, or clinical lameness. Null pointers, wrong
window size, and nonfinite input are rejected with label 255. Confidence is
the uncalibrated mean leaf probability, not a diagnostic probability or a
validated field/OOD rejection score. Array inference cannot validate timing
or sensor location; callers must enforce the contract.

Forest soft voting is preserved. Thresholds are rounded down to float32 when
necessary so every finite float32 feature follows the original scikit-learn
branch semantics. Leaf probabilities are float32; accumulation is double.
Lowest class index wins a tie. The forest has **496 nodes and 256 leaves**.
Arrays use an estimated **10,080 bytes** assuming a 12-byte node, plus class
strings; the text header is 28,487 bytes. Feature scratch is 640 bytes and the
raw XYZ window is 960 bytes. These are data-layout estimates, not an ESP32
flash/RAM/linker or latency measurement.

Offline source preprocessing uses a symmetric antialias FIR, with its context
explicitly included in each manifest record. A live 20 Hz sensor bypasses
that 25 -> 20 conversion. Its bandwidth, calibration, axis convention, and
mounting are an unvalidated hardware domain difference; matching sample
count alone does not establish field compatibility.

## Fresh Verification

Eleven tests pass, including physical stationary/alternating inputs, NaN/Inf
and wrong-length rejection, class/gap/unknown-label boundaries, overlapping
windows within whole-animal partitions, explicit leakage rejection,
millisecond timestamps, conservative lying support, float32 threshold
rounding, and native compiled C99/C++11 parity.

Eighteen artifact checks pass. They reconstruct all windows/features from
the original six CSVs, match raw labels/animal assignments and manifest FIR
contexts, verify train/test animal separation, independently infer from the
saved legacy trees, recompute metrics, prove the sparse subset's raw support
is disjoint, check source hashes/ZIP CRC, and check disabled clinical flags.
All **14 protected old inputs/scripts/model headers** match their pre-run
SHA-256 hashes. The existing lameness header still has `kEnabled = false`.

Both actual native C99 and C++11 executables were compiled with warnings as
errors. Each processed all **887 real heldout windows**, plus NaN and Inf
rejection fixtures: **zero prediction mismatches**, feature maximum absolute
error **0**, and maximum probability difference from scikit-learn about
**3.65e-8**. This is Windows desktop numerical parity; ESP32 execution and
timing were not tested.

Fixed artifact SHA-256 values:

| Artifact | SHA-256 |
| --- | --- |
| `cattle_motion_temporal_candidate.h` | `aa8b19b6dc4614a176efe34f70f034a90ef16aedec7e61cce9569cba7491510f` |
| `motion_temporal_features.h` | `3f40e7e5165467feb2d2c54339a3838b092c45d36f4b59964eb831c81922bc4a` |
| `candidate_model.json` | `39dead8456783e5ab362593bfad573d3bd3b9e554ad2b04fa6d55c2d428c9906` |
| `training_report.json` | `bcdac2c558ce64be0fbaeeb9d89e9a66a915146811dbd4f92e6cee4fcff9f505` |
| `numerical_parity.json` | `ec1db001edb477e1526975be9fdae75d80ec7df4fc10b31dd8d07ca35442c187` |
| `verification_results.json` | `f83ce4c1147cac999ed635491328c108daf8e7768178e6835276160c9fd20ee5` |

The last two hashes identify the final handoff verification snapshot. Running
verification again refreshes timing fields and changes those report hashes.

Environment: Python 3.13.14, NumPy 2.4.3, SciPy 1.17.1, scikit-learn 1.8.0,
MinGW GCC/G++ available locally. No package installation was required.

```powershell
Set-Location D:\table\shumuzengxiao
python -m unittest scripts.test_train_motion_temporal_20261026 -v
python scripts/train_motion_temporal_20261026.py
python scripts/train_motion_temporal_20261026.py --verify-only
```

The normal command trains and checks the new candidate directory. Once
sources are cached, it requires no network. `--verify-only` performs a fresh
offline verification without fitting or rewriting model JSON/headers/report.
It refreshes the parity/verification reports and artifact manifest.

## Integration Boundary And Remaining Gaps

The published contract permits main to add explicitly configured **shadow
inference**, with `research_only` metadata, beside the existing neck output.
It supplies no automatic replacement of the six-class behavior or binary
posture output and no change in clinical lameness/disease gates. Production
eligibility and clinical lameness flags are both false in the new artifacts.

Remaining gaps are local ADXL345/mounting/orientation and bandwidth validation,
real mixed/transition and unknown behavior evaluation, more independent farms/
animals/dates, standing-rumination recall, real independently grouped lying
data, calibrated rejection/confidence, and resolution of source licensing.
Synchronized real neck/back/leg data with verified clinical labels are still
needed for a learned three-position clinical lameness model.
