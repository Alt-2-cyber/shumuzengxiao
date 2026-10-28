#pragma once

#include <stdint.h>
#include "cattle_motion_temporal_candidate.h"

class MotionTemporalStream {
 public:
  void reset(const char *reason = "waiting_for_window") {
    count_ = next_ = hop_ = 0;
    prediction_ = motion_temporal_rejected();
    reason_ = reason;
  }

  bool add(float x, float y, float z, uint32_t now) {
    if (!isfinite(x) || !isfinite(y) || !isfinite(z)) {
      reset("invalid_sample");
      return false;
    }
    if (count_) {
      uint32_t elapsed = now - last_sample_;
      if (elapsed < 35 || elapsed > 75) reset("timing_gap");
    }
    last_sample_ = now;
    xyz_[next_ * 3] = x;
    xyz_[next_ * 3 + 1] = y;
    xyz_[next_ * 3 + 2] = z;
    timestamps_[next_] = now;
    next_ = (next_ + 1) % MOTION_TEMPORAL_WINDOW_SAMPLES;
    if (count_ < MOTION_TEMPORAL_WINDOW_SAMPLES) ++count_;
    uint32_t span = spanMs();
    uint32_t expected = (count_ - 1) * (1000U / MOTION_TEMPORAL_SAMPLE_RATE_HZ);
    uint32_t drift = span > expected ? span - expected : expected - span;
    if (drift > 50) {
      reset("timing_drift");
      return false;
    }
    if (count_ < MOTION_TEMPORAL_WINDOW_SAMPLES) return false;
    if (!prediction_.rejected && ++hop_ < MOTION_TEMPORAL_HOP_SAMPLES) return false;
    float ordered[MOTION_TEMPORAL_WINDOW_SAMPLES * 3];
    for (uint16_t i = 0; i < MOTION_TEMPORAL_WINDOW_SAMPLES; ++i) {
      uint16_t from = (next_ + i) % MOTION_TEMPORAL_WINDOW_SAMPLES;
      for (uint8_t axis = 0; axis < 3; ++axis) ordered[i * 3 + axis] = xyz_[from * 3 + axis];
    }
    prediction_ = motion_temporal_predict_window(ordered, MOTION_TEMPORAL_WINDOW_SAMPLES);
    hop_ = 0;
    return !prediction_.rejected;
  }

  uint16_t samples() const { return count_; }
  uint32_t spanMs() const {
    if (count_ < 2) return 0;
    uint16_t oldest = count_ == MOTION_TEMPORAL_WINDOW_SAMPLES ? next_ : 0;
    return last_sample_ - timestamps_[oldest];
  }
  const MotionTemporalPrediction &prediction() const { return prediction_; }
  const char *status() const { return prediction_.rejected ? reason_ : "research_only"; }

 private:
  float xyz_[MOTION_TEMPORAL_WINDOW_SAMPLES * 3] = {};
  uint32_t timestamps_[MOTION_TEMPORAL_WINDOW_SAMPLES] = {};
  uint16_t count_ = 0;
  uint16_t next_ = 0;
  uint16_t hop_ = 0;
  uint32_t last_sample_ = 0;
  MotionTemporalPrediction prediction_ = motion_temporal_rejected();
  const char *reason_ = "waiting_for_window";
};
