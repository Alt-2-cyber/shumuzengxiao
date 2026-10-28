#include <cassert>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include "motion_temporal_stream.h"

static void sample(unsigned i, float *out) {
  out[0] = 0.2f * std::sin(i * 0.21f);
  out[1] = 0.1f * std::cos(i * 0.31f);
  out[2] = 1.0f + 0.05f * std::sin(i * 0.11f);
}

int main() {
  MotionTemporalStream stream;
  float expected[80 * 3];
  for (unsigned i = 0; i < 79; ++i) {
    sample(i, expected + i * 3);
    assert(!stream.add(expected[i * 3], expected[i * 3 + 1], expected[i * 3 + 2], i * 50));
  }
  assert(stream.samples() == 79 && stream.prediction().rejected);
  sample(79, expected + 79 * 3);
  assert(stream.add(expected[237], expected[238], expected[239], 79 * 50));
  auto direct = motion_temporal_predict_window(expected, 80);
  assert(stream.prediction().label == direct.label);
  for (unsigned c = 0; c < 4; ++c) assert(std::fabs(stream.prediction().probabilities[c] - direct.probabilities[c]) < 1e-6f);
  for (unsigned i = 80; i < 120; ++i) {
    float xyz[3];
    sample(i, xyz);
    assert(stream.add(xyz[0], xyz[1], xyz[2], i * 50) == (i == 119));
  }
  for (unsigned i = 0; i < 80; ++i) sample(i + 40, expected + i * 3);
  direct = motion_temporal_predict_window(expected, 80);
  for (unsigned c = 0; c < 4; ++c) assert(std::fabs(stream.prediction().probabilities[c] - direct.probabilities[c]) < 1e-6f);
  assert(!stream.add(0, 0, 1, 7000));
  assert(stream.samples() == 1 && stream.prediction().rejected);
  assert(!stream.add(std::numeric_limits<float>::quiet_NaN(), 0, 1, 7050));
  assert(stream.samples() == 0 && stream.prediction().rejected);
  stream.reset();
  for (unsigned i = 0; i < 30; ++i) assert(!stream.add(0, 0, 1, UINT32_MAX - 250 + i * 50));
  assert(stream.samples() == 30);
  stream.reset();
  assert(!stream.add(0, 0, 1, 0));
  assert(!stream.add(0, 0, 1, 1));
  assert(stream.samples() == 1);
  stream.reset();
  for (unsigned i = 0; i < 80; ++i) stream.add(0, 0, 1, i * 75);
  assert(stream.prediction().rejected);
  stream.reset();
  for (unsigned i = 0; i < 80; ++i) stream.add(0, 0, 1, i * 35);
  assert(stream.prediction().rejected);
  stream.reset();
  for (unsigned i = 0; i < 80; ++i) stream.add(0, 0, 1, i * 50 + (i % 2 ? 10 : 0));
  assert(!stream.prediction().rejected);
  std::cout << "Temporal stream: warmup, hop, ring order, gap, invalid samples and millis rollover passed. Model "
            << MOTION_TEMPORAL_MODEL_VERSION << ": " << motion_temporal_class_names[direct.label] << '\n';
}
