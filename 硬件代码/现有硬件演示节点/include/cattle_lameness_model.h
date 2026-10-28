#pragma once

#include <Arduino.h>

// This placeholder is intentionally disabled. tools/train_lameness_model.py
// replaces it only after animal-grouped clinical validation and release gates
// pass. It must never be enabled with a public behavior dataset.
namespace cattle_lameness_model {

constexpr bool kEnabled = false;
constexpr uint8_t kFeatureCount = 12;
constexpr const char *kVersion = "untrained-three-position-accel-lameness-v1";
constexpr float kProbabilityThreshold = 1.0f;

struct Prediction {
  bool suspect;
  bool rejected;
  float score;
};

inline Prediction predict(const float *features) {
  (void)features;
  return {false, false, 0.0f};
}

}  // namespace cattle_lameness_model
