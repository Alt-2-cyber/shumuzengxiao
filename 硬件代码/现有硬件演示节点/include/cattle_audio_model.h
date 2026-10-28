#pragma once

#include <Arduino.h>
#include <math.h>

// This is a public-data acoustic event baseline. It detects cow vocalization
// versus non-cattle audio for evidence collection only. It is not a disease
// model; the server must still reject it from respiratory-risk fusion.
namespace cattle_audio_model {

constexpr bool kEnabled = true;
constexpr uint8_t kFeatureCount = 10;
constexpr uint8_t kClassCount = 2;
constexpr const char *kVersion = "cattle-vocalization-baseline-v2-bedc334739f4";
constexpr float kMinimumConfidence = 0.625f;
static const char *const kLabels[kClassCount] = {"cow_vocalization", "non_cattle_audio"};
static const float kMean[kFeatureCount] = {-2.6048834f, 0.19744386f, 6.3616638f, -3.7092133f, -3.1982586f, -2.4641747f, -2.2423441f, -3.788753f, -5.6709719f, -0.59750462f};
static const float kScale[kFeatureCount] = {1.6869375f, 0.10879078f, 2.4200802f, 2.136997f, 2.3254046f, 2.354286f, 2.2018511f, 2.5513434f, 2.1668727f, 2.0112562f};
static const float kWeights[kClassCount][kFeatureCount] = {
  {0.28698081f, 0.19015612f, -0.84313494f, -0.11972252f, 1.6802874f, -0.21409591f, 0.25828439f, 0.077831887f, 0.10241494f, -0.04313923f},
  {-0.28698081f, -0.19015612f, 0.84313494f, 0.11972252f, -1.6802874f, 0.21409591f, -0.25828439f, -0.077831887f, -0.10241494f, 0.04313923f}
};
static const float kBias[kClassCount] = {-1.2284056f, 1.2284056f};
static const float kCentroids[kClassCount][kFeatureCount] = {
  {0.38303337f, -0.20157243f, -0.79555893f, 0.48857841f, 0.85752863f, 0.07808046f, -0.090114266f, -0.135686f, -0.12166093f, 0.055799864f},
  {-0.14479181f, 0.076198779f, 0.30073327f, -0.18469024f, -0.32416046f, -0.029516675f, 0.034064915f, 0.051292539f, 0.045989219f, -0.021093057f}
};
static const float kDistanceLimits[kClassCount] = {9.1797581f, 202.94093f};

struct Prediction {
  const char *label;
  float score;
};

inline Prediction predict(const float *features) {
  float scores[kClassCount];
  float highest = -INFINITY;
  for (uint8_t category = 0; category < kClassCount; category++) {
    float score = kBias[category];
    for (uint8_t feature = 0; feature < kFeatureCount; feature++) {
      score += ((features[feature] - kMean[feature]) / kScale[feature]) *
               kWeights[category][feature];
    }
    scores[category] = score;
    highest = max(highest, score);
  }
  float total = 0.0f;
  for (uint8_t category = 0; category < kClassCount; category++) {
    scores[category] = expf(scores[category] - highest);
    total += scores[category];
  }
  uint8_t best = scores[1] > scores[0] ? 1 : 0;
  const float confidence = total > 0.0f ? scores[best] / total : 0.0f;
  float distance = 0.0f;
  for (uint8_t feature = 0; feature < kFeatureCount; feature++) {
    const float normalized = (features[feature] - kMean[feature]) / kScale[feature];
    const float delta = normalized - kCentroids[best][feature];
    distance += delta * delta;
  }
  if (confidence < kMinimumConfidence || distance > kDistanceLimits[best]) {
    return {"unknown", confidence};
  }
  return {kLabels[best], confidence};
}

inline bool isRespiratoryLabel(const char *) {
  return false;
}

inline bool isAbnormalVocalizationLabel(const char *) {
  return false;
}

inline bool isScreeningLabel(const char *label) {
  return label != nullptr && strcmp(label, "cow_vocalization") == 0;
}

}  // namespace cattle_audio_model
