# Calf Cough Acoustic Event Research (2026-10-26)

Status: implemented, actually trained and verified. Scope: **research_only**,
CPU only. This is an acoustic event experiment, not an approved disease model
or a production gate result.

## Actual Result

The fixed StandardScaler + L2 logistic regression achieved **29/40 correct
(72.5% accuracy)** in five exploratory folds holding out original files.
Macro F1 was **0.724828**, cough precision **0.736842**, cough recall **0.700000**,
and cough F1 **0.717949**. **Source group unknown**: animals, sessions and parent
recordings cannot be separated, so these figures are not animal-independent
validation and must not be used as production acceptance criteria.

| Metric | Actual pooled file-held-out value |
| --- | ---: |
| Accuracy / balanced accuracy | 0.725000 / 0.725000 |
| Macro F1 | 0.7248280175 |
| ROC AUC | 0.787500 |
| Cough average precision | 0.7330602929 |
| Cough Brier score | 0.1971112204 |
| Log loss | 0.6035267724 |

Confusion matrix, true labels in rows and predictions in columns, both ordered
`[non_cough, cough]`:

```text
[[15,  5],
 [ 6, 14]]
```

Each fold used 32 training files and 8 held-out files (4 of each class). Every
original file was held out once. File/hash overlap was zero in each fold;
the one conservative unknown source group appeared on both sides in all five
folds. This explicitly does not establish animal/session independence.

| Fold | Correct / 8 | Accuracy | Macro F1 |
| --- | ---: | ---: | ---: |
| 1 | 5 | 0.625 | 0.563636 |
| 2 | 5 | 0.625 | 0.619048 |
| 3 | 5 | 0.625 | 0.619048 |
| 4 | 7 | 0.875 | 0.873016 |
| 5 | 7 | 0.875 | 0.873016 |

Pooled macro F1 is calculated from all 40 held-out predictions, rather than
the mean of the five fold macro F1 values. No confidence interval or
statistical significance claim is made because the independent source units
are unknown. The final exported model fits all 40 originals; its training
predictions are explicitly named `resubstitution_not_validation`.

## Authorized Design

Read the [prior evidence report](D:/table/shumuzengxiao/docs/2026-10-25-audio-data-evidence.md)
and INRAE/ENVT DOI [10.57745/FP5LA9](https://doi.org/10.57745/FP5LA9) manifest.
Training used only the 40 original 44.1 kHz mono, 16-bit PCM WAV files
(20 cough, 20 non_cough; 40 unique SHA256 values; 39.3879818594 seconds total).
The existing 8 kHz, two-second derivatives were hashed for provenance and used
as CLI coverage fixtures, and contributed **zero** training observations.
No data augmentation or other datasets were included.

The source manifest hash is pinned to
`12eef566e91552e380536581c930be7bcbd5f427bc0c832d12297bdc22dc73e6`.
All 40 original SHA256 values, byte sizes and repository MD5 values were
checked again. Forty excluded derivative hashes and seven source evidence
file hashes are also recorded. The original author-reported labels and null
animal/session fields are preserved in the new input manifest.

Use anti-aliased 8 kHz audio and one-second windows. Preserve window offsets,
observed sample counts, known input padding and algorithm padding separately.
Do not infer missing duration by trimming zero samples. A two-second live
recording has two observed windows even when one is silent. A known padded
container needs explicit valid-prefix metadata. Shape features use only
observed samples, with DC removal and RMS normalization; signal quality and
duration remain metadata, not classifier features. Original `cough_012.wav`
contains 17,110 source frames (0.3879818594 seconds), which resample to 3,104
observed samples (0.388 seconds). Its nominal one-second feature window records
4,896 algorithm-padding positions; those positions are excluded from feature
statistics. This fractional-sample rounding is recorded separately from the
original duration.

The resampler is `scipy.signal.resample_poly`, with the reduced integer
up/down ratio, Kaiser window beta 5.0 and constant boundary padding. An
already-8-kHz WAV bypasses resampling. Rates below 8 kHz are rejected.
Unsigned 8-bit, signed PCM and floating WAV inputs are decoded to full-scale
floating point; multichannel inputs use an arithmetic mean before resampling.
The current training files are all mono PCM16. Float conversion and stereo
downmix have separate unit checks.

Each scoreable window is independently DC-centered and divided by its AC RMS
over observed samples. The 14 fixed features are zero-crossing rate,
log peak/RMS, frame RMS coefficient of variation, active-frame fraction,
spectral centroid, spectral bandwidth, 85% rolloff, flatness, spectral flux,
and five relative power bands (0-250, 250-500, 500-1000, 1000-2000, 2000-4000 Hz).
Spectral frames use 200 samples, an 80-sample hop, periodic Hann and a
256-point FFT. Complete feature frames are used, leaving at most 79 observed
tail samples outside frame-based statistics; full observed duration and the
whole-window features remain intact.

Input and per-window quality records include rate, dtype, channel count,
source frames, original/resampled durations, RMS/dBFS, DC, peak, saturation,
exact-zero fraction, zero-tail length, and source spectral energy above 4 kHz.
Quality flags cover low RMS, near-full-scale signal and short windows. All
training files were scoreable; only the one short clip received a window flag.
The above-4-kHz energy fraction ranged from 0.30% to 55.29%, so resampling can
remove substantial source information. A near-silent window (AC RMS <= 1e-8),
an empty observed window, or an observed tail shorter than 800 samples receives
no class decision. These are fixed engineering checks, not clinically
validated rejection criteria.

Use 14 fixed time/spectral features and one fixed StandardScaler + L2 logistic
regression (C=0.1, threshold=0.5). The solver is lbfgs, tolerance 1e-8,
maximum 2,000 iterations, with intercept and no class weights. All fits
converged. Fit the scaler on each training fold only.
Five stratified file-held-out folds are exploratory engineering diagnostics.
Keep all views of a file together. Preserve the original conservative source
group: `rdg-FP5LA9:recording-session-unknown`. The source group is unknown;
animal/session independence cannot be established or claimed. Splitter:
`StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261026)`,
grouped by file ID. There was one fixed candidate, zero parameter searches
and no threshold selection from these results. All hypothetical views of a
file remain in one fold; the actual experiment has exactly one window per
original file and never copies a case label to new slices.

Implementation and verification sequence:

- [x] Read evidence, inspect manifest and confirm system Python 3.13 dependencies.
- [x] Run failing signal-contract tests, then implement preprocessing and features.
- [x] Run the fixed five-fold experiment and fit a final model on all 40 files.
- [x] Export numeric JSON parameters, feature definitions, hashes and predictions.
- [x] Verify JSON inference, split integrity, actual metrics and prediction CLI.
- [x] Record actual results, commands, licensing and remaining limitations.

## Artifacts And Verification

All outputs are in
[calf-cough-research-20261026](D:/table/shumuzengxiao/audio-training-data/artifacts/calf-cough-research-20261026/).

| File | Content |
| --- | --- |
| `model.json` | Final portable numeric model, 40 fit file IDs/hashes, scope, attribution and full feature definition |
| `fold_models/fold_1.json` through `fold_5.json` | Independently scaled numeric parameters for each exploratory fold |
| `feature_definition.json` | Ordered 14 features, formulas, FFT/framing, normalization and quality rules |
| `features.npz` | Numeric feature rows, targets, file IDs/hashes, fold IDs and held-out scores; no pickle |
| `input_manifest.jsonl` | All 40 original files, author labels, unknown grouping, quality and padding records |
| `provenance.json` | 40 original + 40 excluded derivative + 7 evidence hashes and license/source attribution |
| `fold_assignments.json` | Every training/held-out file membership, metrics and explicit unknown source-group overlap |
| `oof_predictions.jsonl` | Exactly one held-out score and decision for each of the 40 originals |
| `final_fit_predictions.jsonl` | Final model fit diagnostics, explicitly not validation |
| `training_report.json` | Actual metrics, fixed configuration, environment, script hash and limitations |
| `feature_unit_checks.json` | All 17 signal/coverage/portable-inference unit checks, with their output |
| `verification.json` | Regenerated features, refitted models, metric and two-second coverage checks |
| `examples/*.json` | Four actual CLI runs on original/known-padded/unspecified-coverage WAV inputs |
| `SHA256SUMS.txt` | SHA256 of output files, script, this report and input provenance files; excludes itself |

The portable scoring formula is:

```text
z = sum(((features - scaler_mean) / scaler_scale) * coefficients) + intercept
cough_score = 1 / (1 + exp(-z))
predicted_event = cough if cough_score >= 0.5 else non_cough
```

Class order is `[non_cough, cough]`. The JSON stores the scaler, coefficient
vector, intercept and feature schema, so no serialized sklearn object or
pickle is needed. The prediction command uses NumPy/SciPy and the saved JSON.
Scores have not been calibrated on external recordings.

Actual verification passed: 17/17 unit checks; 40/40 original SHA256 and MD5
matches; 40/40 excluded derivative hashes; all 40 feature vectors regenerated
exactly; all 40 held-out and 40 final-fit predictions reproduced; all five
train-only scalers checked by fixed refits; all six saved models checked
against sklearn. Maximum saved JSON/sklearn probability error was **0.0**.
All fold metrics and aggregate metrics were reproduced. A separate count of
the saved truth/prediction pairs independently recovered the same confusion
matrix, 29 correct files, accuracy, macro F1, cough precision and recall.

## Two-Second Input And CLI

The [training/prediction script](D:/table/shumuzengxiao/scripts/train_calf_cough_research_20261026.py)
returns the two fixed nonoverlapping one-second windows of an 8 kHz, 16,000-frame
ESP32 WAV at starts 0.0 and 1.0 seconds. It preserves each window's original
position, coverage and quality. It supplies per-window scores; there is no
validated two-second event aggregation rule. No backend, firmware or serial
integration was performed in this task.

Zero samples cannot distinguish actual recorded silence from missing audio.
Without coverage metadata, the CLI explicitly records
`all_wav_samples_assumed_observed` and retains the entire WAV duration.
For a container whose tail is known to be padding, supply
`--valid-input-samples` in the **native WAV sample rate**. The declared tail
must contain exact zeros. This option describes one contiguous observed
prefix; it cannot describe or reconstruct missing packets in the middle.

| Actual fixture | Declared coverage | Window observed samples | Second window |
| --- | --- | --- | --- |
| Two-second `cough_001.wav` derivative | Explicit prefix 8,000 | `[8000, 0]` | `abstain_no_observed_samples`, null score |
| Same derivative | Unspecified | `[8000, 8000]` (assumed) | `abstain_silence`, null score |
| Two-second `cough_012.wav` derivative | Explicit prefix 3,104 | `[3104, 0]` | `abstain_no_observed_samples`, null score |

Unit checks also verify actual observed two-second tone/silence inputs,
distinct tones in the two subwindows, a 1.25-second observed input, equality
of short-clip features before/after known tail padding, and suppression of a
6 kHz source tone by more than 40 dB when resampling to 8 kHz. These synthetic
signals are unit fixtures only and contribute no training samples or labels.

These commands were actually run using system Python 3.13:

```powershell
python -B -X utf8 D:\table\shumuzengxiao\scripts\train_calf_cough_research_20261026.py self-test
python -B -X utf8 D:\table\shumuzengxiao\scripts\train_calf_cough_research_20261026.py train
python -B -X utf8 D:\table\shumuzengxiao\scripts\train_calf_cough_research_20261026.py verify
python -B -X utf8 D:\table\shumuzengxiao\scripts\train_calf_cough_research_20261026.py predict D:\table\shumuzengxiao\audio-training-data\external\20261025\derived\rdg-FP5LA9-8khz-2s\cough_001.wav --valid-input-samples 8000 --output D:\table\shumuzengxiao\audio-training-data\artifacts\calf-cough-research-20261026\examples\cough_001_known_padding.json
```

For a new, fully observed WAV, replace the input path; omit
`--valid-input-samples`. For example:

```powershell
python -B -X utf8 D:\table\shumuzengxiao\scripts\train_calf_cough_research_20261026.py predict D:\recordings\new_esp32.wav
```

That last path is an example, not a claim that new field data were supplied
or tested. Optional JSON output paths are restricted to this experiment's
artifact directory. `verify` refreshes and verifies the SHA256 list after
regenerating its verification record; the checksum list paths are relative
to `D:\table\shumuzengxiao`.

Environment actually used: Python **3.13.14**, NumPy **2.4.3**, SciPy **1.17.1**,
scikit-learn **1.8.0**, Windows 11. Numeric worker threads are limited to one.
No dependencies were installed; no GPU runtime was imported or used.

## Restrictions

The labels describe author-reported acoustic events. `non_cough` is not a
healthy-animal diagnosis, and neither class maps to BRD, FMD or another disease.
There are no copied clinical case labels or fabricated animal/session IDs.
Repository metadata says Etalab Open License 2.0; the preprint restricts use to
research and education. Preserve attribution and changes, and treat all
outputs as research_only. Commercial rights remain unresolved.

Attribution: Mach et al. (2026), INRAE/ENVT, *AI-powered acoustic surveillance
for early detection of calf respiratory disease*, *Animal* 20(10):101928,
[10.1016/j.animal.2026.101928](https://doi.org/10.1016/j.animal.2026.101928).
Changes are the anti-aliased conversion, per-window normalization, feature
extraction and fixed logistic regression experiment described above.

The 40 short, selected author-annotated clips cannot establish sensitivity or
false-alarm rates on continuous barn recordings. The 0.388-second example is
also the only short original and is a cough, so duration-related confounding
cannot be ruled out even though duration is excluded from classifier inputs.
Clip boundaries, microphone response, gain, barn noise, 8-bit quantization,
firmware resampling and losses above 4 kHz require separate field validation.
The library's anti-aliasing does not undo aliasing already introduced during
capture. The reported accuracy cannot be compared directly with the prior
ESC-50 experiment or the paper's different 1,045-clip/92% author experiment.

Animal/session/parent-recording mappings, independently collected continuous
ESP32 recordings and an external holdout remain necessary before assessing
generalization. Disease use would separately require auditable clinical
labels, licensing resolution and the existing release process; this run
does not provide those.

Writes are restricted to the new training script, this report and
`audio-training-data/artifacts/calf-cough-research-20261026/`. Hardware,
serial ports, backend, firmware and existing gates were not touched. No
approved disease-model header was generated.
