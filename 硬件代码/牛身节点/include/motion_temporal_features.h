/* Generated research candidate; neck XYZ only, calibrated g at 20 Hz. */
#ifndef MOTION_TEMPORAL_FEATURES_20261026_H
#define MOTION_TEMPORAL_FEATURES_20261026_H
#include <stddef.h>
#include <stdint.h>
#include <math.h>
#define MOTION_TEMPORAL_SAMPLE_RATE_HZ 20
#define MOTION_TEMPORAL_WINDOW_SAMPLES 80
#define MOTION_TEMPORAL_HOP_SAMPLES 40
#define MOTION_TEMPORAL_FEATURE_COUNT 24
#define MOTION_TEMPORAL_CLASS_COUNT 4
#define MOTION_TEMPORAL_UNKNOWN_LABEL 255
#define MOTION_TEMPORAL_PRODUCTION_ELIGIBLE 0
#define MOTION_TEMPORAL_CLINICAL_LAMENESS_ENABLED 0

/* Interleaved X,Y,Z float32 samples, channel-major feature output. */
static inline int motion_temporal_extract_features(const float *xyz, size_t samples, float *out) {
  size_t i;
  int channel;
  double values[MOTION_TEMPORAL_WINDOW_SAMPLES];
  if (!xyz || !out || samples != MOTION_TEMPORAL_WINDOW_SAMPLES) return 0;
  for (i = 0; i < samples * 3; ++i) if (!isfinite(xyz[i])) return 0;
  for (channel = 0; channel < 4; ++channel) {
    double sum = 0.0, variance = 0.0, abs_delta = 0.0, delta_energy = 0.0;
    double mean, minimum, maximum;
    for (i = 0; i < samples; ++i) {
      double x = xyz[i * 3], y = xyz[i * 3 + 1], z = xyz[i * 3 + 2];
      values[i] = channel < 3 ? (double)xyz[i * 3 + (size_t)channel] : sqrt(x*x + y*y + z*z);
      sum += values[i];
    }
    mean = sum / (double)samples;
    minimum = maximum = values[0];
    for (i = 0; i < samples; ++i) {
      double centered = values[i] - mean;
      variance += centered * centered;
      if (values[i] < minimum) minimum = values[i];
      if (values[i] > maximum) maximum = values[i];
      if (i) {
        double delta = values[i] - values[i-1];
        abs_delta += fabs(delta);
        delta_energy += delta * delta;
      }
    }
    out[channel*6] = (float)mean;
    out[channel*6+1] = (float)sqrt(variance / (double)samples);
    out[channel*6+2] = (float)minimum;
    out[channel*6+3] = (float)maximum;
    out[channel*6+4] = (float)(abs_delta / (double)(samples-1));
    out[channel*6+5] = (float)sqrt(delta_energy / (double)(samples-1));
  }
  return 1;
}
#endif
