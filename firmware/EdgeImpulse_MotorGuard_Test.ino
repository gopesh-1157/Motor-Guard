/**************************************************************************
 * MOTORGUARD - EDGE IMPULSE STANDALONE VERIFICATION SKETCH
 * Tests your deployed Edge Impulse model on ESP32 without requiring sensors.
 *
 * Model: MotoGuard Motor Health (Edge Impulse Project #1133176)
 * Library: MotoGuard_Motor_Health_inferencing.h
 *
 * Inputs (3 Tabular Features):
 *   [0] = temperature_C (°C)
 *   [1] = vibration_g   (g RMS)
 *   [2] = current_A     (A)
 *
 * Output Classes:
 *   - healthy
 *   - warning
 *   - critical
 **************************************************************************/

#include <Arduino.h>
#include <MotoGuard_Motor_Health_inferencing.h>

// Static buffer for zero-heap-allocation inference
static float ei_features[EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE];

static int raw_feature_get_data(size_t offset, size_t length, float *out_ptr) {
  memcpy(out_ptr, ei_features + offset, length * sizeof(float));
  return 0;
}

// Function to run inference on given test values
void testInference(const char* testName, float tempC, float vibG, float currA) {
  Serial.println("==================================================");
  Serial.printf("TEST CASE: %s\n", testName);
  Serial.printf("Inputs   : Temp = %.1f C | Vib = %.3f g | Curr = %.2f A\n", tempC, vibG, currA);

  ei_features[0] = tempC;
  ei_features[1] = vibG;
  ei_features[2] = currA;

  signal_t signal;
  signal.total_length = EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE;
  signal.get_data = &raw_feature_get_data;

  ei_impulse_result_t result = { 0 };
  EI_IMPULSE_ERROR res = run_classifier(&signal, &result, false);

  if (res != EI_IMPULSE_OK) {
    Serial.printf("ERROR: run_classifier returned error code %d\n", res);
    return;
  }

  Serial.printf("Timing   : DSP = %d ms | Inference = %d ms\n", result.timing.dsp, result.timing.classification);
  Serial.println("Predictions:");

  const char* topLabel = "unknown";
  float topVal = -1.0f;

  for (size_t ix = 0; ix < EI_CLASSIFIER_LABEL_COUNT; ix++) {
    const char* label = result.classification[ix].label;
    float val = result.classification[ix].value;
    Serial.printf("  - %-10s : %.2f%% (prob = %.4f)\n", label, val * 100.0f, val);

    if (val > topVal) {
      topVal = val;
      topLabel = label;
    }
  }

  Serial.printf("RESULT   : %s (Confidence: %.1f%%)\n", topLabel, topVal * 100.0f);
  Serial.println("==================================================\n");
}

void setup() {
  Serial.begin(115200);
  delay(1500);

  Serial.println("\n");
  Serial.println("**************************************************");
  Serial.println("   MOTORGUARD EDGE IMPULSE ESP32 VERIFICATION   ");
  Serial.println("**************************************************");
  Serial.printf("Model Project   : MotoGuard Motor Health\n");
  Serial.printf("Input Features  : %d axes (temp, vib, curr)\n", EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE);
  Serial.printf("Label Count     : %d\n", EI_CLASSIFIER_LABEL_COUNT);
  Serial.println("Running test validation vectors...\n");

  // 1. Expected Healthy
  testInference("Normal / Healthy Motor", 28.0f, 0.050f, 0.80f);

  // 2. Expected Warning
  testInference("Degraded / Warning Motor", 37.0f, 0.150f, 1.50f);

  // 3. Expected Critical
  testInference("Overheating & Severe Vibration / Critical", 42.0f, 0.250f, 2.20f);
}

void loop() {
  // Idle after running test vectors
  delay(5000);
}
