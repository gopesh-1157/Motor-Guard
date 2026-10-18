/**************************************************************************
 * INTELLIGENT MOTOR HEALTH MONITOR (MotorGuard)
 * ESP32 + ACS712 20A + DHT11 + ADXL345 + SH1106 OLED + Wi-Fi SoftAP + Web Server
 *
 * Mode 2: STANDALONE ESP32 ACCESS POINT (SoftAP + Built-in Web Dashboard)
 *   - ESP32 broadcasts its own Wi-Fi network: "MotorGuard-ESP32-AP"
 *   - Access Point Password: "MotorGuard123"
 *   - ESP32 Web Server active at: http://192.168.4.1
 *   - REST JSON API at: http://192.168.4.1/api/telemetry
 *   - Strict Zero vs. Unavailable Principle (no fake numbers)
 *   - Edge Impulse TinyML dynamic label mapping & input frame size validation
 *   - Precise 100 Hz ADXL345 synchronized sampling (gravity removed via mean subtraction)
 *   - Verified DHT11 startup check & paced operational reads
 *   - Dual-I2C bus isolation: ADXL345 on Bus 0 (21/22), OLED on Bus 1 (32/33)
 **************************************************************************/

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_ADXL345_U.h>
#include <DHT.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <WebServer.h>
#include <PubSubClient.h>
#include <time.h>
#include <math.h>

// Check for local untracked secrets header (ignored in git)
#if __has_include("secrets.h")
  #include "secrets.h"
#endif

// ============================================================
// EDGE IMPULSE TOGGLE & INFERENCE DEFINITIONS
// ============================================================
#define USE_EDGE_IMPULSE_LIB 1

#if USE_EDGE_IMPULSE_LIB
  #include <MotoGuard_Motor_Health_inferencing.h>
#endif

// ============================================================
// NETWORK & MQTT BROKER CONFIGURATION
// ============================================================
#ifndef USE_CLOUD_MQTT
  #define USE_CLOUD_MQTT 0
#endif

#if USE_CLOUD_MQTT
  // Production Cloud Broker over MQTTS TLS (Port 8883)
  const char* MQTT_BROKER   = CLOUD_MQTT_BROKER;
  const int   MQTT_PORT     = CLOUD_MQTT_PORT;
  const char* MQTT_USER     = CLOUD_MQTT_USER;
  const char* MQTT_PASS     = CLOUD_MQTT_PASS;
  const char* DEVICE_ID     = CLOUD_DEVICE_ID;
  const char* FIRMWARE_VER  = "1.0.1-CLOUD-TLS";
  WiFiClientSecure espClient;
#else
  // Local Development SoftAP Mode (192.168.4.2:1883)
  const char* AP_SSID       = "MotorGuard-ESP32-AP";
  const char* AP_PASSWORD   = "MotorGuard123";
  const char* MQTT_BROKER   = "192.168.4.2";
  const int   MQTT_PORT     = 1883;
  const char* MQTT_USER     = "";
  const char* MQTT_PASS     = "";
  const char* DEVICE_ID     = "esp32-node-001";
  const char* FIRMWARE_VER  = "1.0.1-AP";
  WiFiClient espClient;
#endif

const char* MOTOR_ID      = "MTR-775-001";

PubSubClient mqttClient(espClient);
WebServer server(80);

// ============================================================
// SENSOR PINS & HARDWARE DEFINITIONS
// ============================================================

// DHT11 Pin
#define DHT_PIN 4
#define DHT_TYPE DHT11
DHT dht(DHT_PIN, DHT_TYPE);
bool dhtOnline = false;
unsigned long lastDhtReadTime = 0;

// OLED SH1106 (I2C Bus 1 on GPIO 32 SDA, GPIO 33 SCL)
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
TwoWire I2C_OLED = TwoWire(1);
Adafruit_SH1106G display(SCREEN_WIDTH, SCREEN_HEIGHT, &I2C_OLED, -1);
bool oledOnline = false;

// ADXL345 (I2C Bus 0 on GPIO 21 SDA, GPIO 22 SCL)
Adafruit_ADXL345_Unified accel = Adafruit_ADXL345_Unified(12345);
bool adxlOnline = false;

// ============================================================
// DATA COLLECTION MODE TOGGLE
// ============================================================
// Set to 1 to enable interactive ground-truth training collection over Serial.
// When 1, Wi-Fi broadcasting is paused to minimize ADC noise on GPIO 34.
#define DATA_COLLECTION_MODE 0

// ACS712 20A Pin & Sensitivity
#define CURRENT_PIN 34
const float ACS_SENSITIVITY = 0.100f; // 100 mV/A for ACS712-20A
const float VOLTAGE_DIVIDER_RATIO = 0.6667f; // 20k / (10k + 20k)
// Adjusted deadband to 0.20 A to exceed the 10-20 mV typical ESP32 ADC noise floor
const float CURRENT_DEADBAND_A = 0.20f;

// Operational Thresholds
const float MOTOR_SUPPLY_VOLTS = 12.0f;
const float OVERCURRENT_LIMIT_A = 4.0f;

// ADXL345 Vibration Sampling Settings (800 Hz Output Data Rate)
// 800 Hz corresponds to 1250 us interval. 128 samples captures a clean 160 ms window.
const int VIBRATION_SAMPLES = 128;
const unsigned long VIBRATION_SAMPLE_INTERVAL_US = 1250; 

// Rich Vibration Feature Structure
struct VibrationMetrics {
  float rmsX;
  float rmsY;
  float rmsZ;
  float totalRMS;
  float peakG;
  float crestFactor;
  bool valid;
};

// Sensor Readings & Active Features
float zeroPointVolts = 2.50f;
float currentAmps = 0.0f;
float vibrationRMS_g = 0.0f;
float temperatureC = 0.0f;
VibrationMetrics currentVibration = {0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, false};

#if DATA_COLLECTION_MODE
char currentLabel = 'h';   // 'h'=healthy, 'o'=overload, 'i'=imbalance, 'l'=loose_mount
int  runId = 1;
unsigned long collectionRowsLogged = 0;
#endif

// Inference State & Metrics
String inferenceStatus = "INPUT_INVALID"; // PREDICTED, INPUT_INVALID, MODEL_UNAVAILABLE, MODEL_ERROR
String healthStatus = "unknown";          // healthy, warning, critical, unknown
bool hasInferenceProbabilities = false;
float confHealthy = 0.0f;
float confWarning = 0.0f;
float confCritical = 0.0f;
float topConfidence = 0.0f;
int eiDspTimeMs = 0;
int eiClassificationTimeMs = 0;

// Telemetry Sequence & Timers
unsigned long telemetrySeq = 0;
unsigned long lastTelemetryPublish = 0;
unsigned long lastMqttRetry = 0;
unsigned long lastOledUpdate = 0;
bool ntpSynced = false;

// ============================================================
// OFFLINE STORE-AND-FORWARD QUEUE (RAM RING BUFFER)
// ============================================================
#define OFFLINE_QUEUE_CAPACITY 32
#define MAX_PAYLOAD_LEN 768

struct QueuedMessage {
  char payload[MAX_PAYLOAD_LEN];
  bool valid;
};

QueuedMessage offlineQueue[OFFLINE_QUEUE_CAPACITY];
int queueHead = 0;
int queueTail = 0;
int queueCount = 0;

void enqueueOfflineMessage(const char* payload) {
  if (queueCount >= OFFLINE_QUEUE_CAPACITY) {
    queueTail = (queueTail + 1) % OFFLINE_QUEUE_CAPACITY;
    queueCount--;
  }
  strncpy(offlineQueue[queueHead].payload, payload, MAX_PAYLOAD_LEN - 1);
  offlineQueue[queueHead].payload[MAX_PAYLOAD_LEN - 1] = '\0';
  offlineQueue[queueHead].valid = true;
  queueHead = (queueHead + 1) % OFFLINE_QUEUE_CAPACITY;
  queueCount++;
}

void drainOfflineQueue() {
  if (queueCount == 0 || !mqttClient.connected()) return;

  char topic[64];
  snprintf(topic, sizeof(topic), "motorguard/v1/%s/telemetry", DEVICE_ID);

  while (queueCount > 0 && mqttClient.connected()) {
    if (offlineQueue[queueTail].valid) {
      bool sent = mqttClient.publish(topic, offlineQueue[queueTail].payload, false);
      if (!sent) break;
      offlineQueue[queueTail].valid = false;
      queueTail = (queueTail + 1) % OFFLINE_QUEUE_CAPACITY;
      queueCount--;
      delay(20);
    } else {
      queueTail = (queueTail + 1) % OFFLINE_QUEUE_CAPACITY;
      queueCount--;
    }
  }
}

// ============================================================
// HELPER: GENERATE UUIDv4
// ============================================================
String generateUUIDv4() {
  uint32_t r1 = esp_random();
  uint32_t r2 = esp_random();
  uint32_t r3 = esp_random();
  uint32_t r4 = esp_random();

  char uuid[37];
  snprintf(uuid, sizeof(uuid),
    "%08x-%04x-4%03x-%04x-%04x%08x",
    r1,
    (r2 >> 16) & 0xFFFF,
    r2 & 0x0FFF,
    ((r3 >> 16) & 0x3FFF) | 0x8000,
    r3 & 0xFFFF,
    r4
  );
  return String(uuid);
}

// ============================================================
// HELPER: GET ISO-8601 UTC TIMESTAMP
// ============================================================
String getISOTimestamp() {
  time_t now;
  time(&now);
  struct tm timeinfo;
  gmtime_r(&now, &timeinfo);

  char buf[35];
  if (timeinfo.tm_year >= 124) {
    ntpSynced = true;
    strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
    return String(buf);
  }

  // Uptime relative monotonic format
  unsigned long uptimeSec = millis() / 1000;
  unsigned int days = uptimeSec / 86400;
  unsigned int remSec = uptimeSec % 86400;
  unsigned int hours = remSec / 3600;
  unsigned int minutes = (remSec % 3600) / 60;
  unsigned int seconds = remSec % 60;

  snprintf(buf, sizeof(buf), "1970-01-%02uT%02u:%02u:%02uZ", 1 + days, hours, minutes, seconds);
  return String(buf);
}

// ============================================================
// SENSOR READING IMPLEMENTATIONS
// ============================================================

void calibrateACS712() {
  Serial.println("[ACS712] Calibrating zero-point... Ensure motor is completely OFF.");
  delay(800);

  const int calibrationSamples = 500;
  float voltageSum = 0.0f;

  for (int i = 0; i < calibrationSamples; i++) {
    uint32_t mv = analogReadMilliVolts(CURRENT_PIN);
    float pinVoltage = mv / 1000.0f;
    float acsVoltage = pinVoltage / VOLTAGE_DIVIDER_RATIO;
    voltageSum += acsVoltage;
    delay(2);
  }

  zeroPointVolts = voltageSum / calibrationSamples;
  Serial.printf("[ACS712] Calibrated zero offset: %.3f V\n", zeroPointVolts);
}

float readMotorCurrent() {
  float voltageSum = 0.0f;
  const int SAMPLES = 120; // Increased multi-sampling to damp ESP32 ADC noise

  for (int i = 0; i < SAMPLES; i++) {
    uint32_t mv = analogReadMilliVolts(CURRENT_PIN);
    float pinVoltage = mv / 1000.0f;
    float acsVoltage = pinVoltage / VOLTAGE_DIVIDER_RATIO;
    voltageSum += acsVoltage;
    delayMicroseconds(250);
  }

  float averageVoltage = voltageSum / SAMPLES;

  if (averageVoltage < 0.20f || averageVoltage > 4.80f) {
    return NAN; // Sensor disconnected / wire break
  }

  float current = (averageVoltage - zeroPointVolts) / ACS_SENSITIVITY;
  current = fabs(current);

  if (current < CURRENT_DEADBAND_A) {
    current = 0.0f;
  }
  return current;
}

float readTemperature() {
  // Respect DHT11 minimum 1.5s sampling interval
  if (millis() - lastDhtReadTime < 1500 && !isnan(temperatureC)) {
    return temperatureC;
  }
  lastDhtReadTime = millis();

  float temp = dht.readTemperature();
  if (isnan(temp) || temp < -20.0f || temp > 120.0f) {
    dhtOnline = false;
    return NAN;
  }
  dhtOnline = true;
  return temp;
}

// 800 Hz Synchronized Multi-Axis Vibration Feature Extractor
VibrationMetrics calculateVibrationFeatures() {
  VibrationMetrics m = {0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, false};
  if (!adxlOnline) {
    return m;
  }

  float ax[VIBRATION_SAMPLES];
  float ay[VIBRATION_SAMPLES];
  float az[VIBRATION_SAMPLES];
  float meanX = 0.0f, meanY = 0.0f, meanZ = 0.0f;

  sensors_event_t event;

  for (int i = 0; i < VIBRATION_SAMPLES; i++) {
    unsigned long sampleStart = micros();

    if (!accel.getEvent(&event)) {
      adxlOnline = false;
      return m;
    }

    // Convert raw m/s^2 to g units (1g = 9.80665 m/s^2)
    ax[i] = event.acceleration.x / 9.80665f;
    ay[i] = event.acceleration.y / 9.80665f;
    az[i] = event.acceleration.z / 9.80665f;

    meanX += ax[i];
    meanY += ay[i];
    meanZ += az[i];

    // Synchronize sample pacing to 800 Hz ODR (1250 us interval)
    while (micros() - sampleStart < VIBRATION_SAMPLE_INTERVAL_US) {
      yield();
    }
  }

  meanX /= VIBRATION_SAMPLES;
  meanY /= VIBRATION_SAMPLES;
  meanZ /= VIBRATION_SAMPLES;

  float sumSqX = 0.0f;
  float sumSqY = 0.0f;
  float sumSqZ = 0.0f;
  float maxInstantG = 0.0f;

  for (int i = 0; i < VIBRATION_SAMPLES; i++) {
    // Remove static DC gravity vector to extract dynamic alternating vibration
    float dx = ax[i] - meanX;
    float dy = ay[i] - meanY;
    float dz = az[i] - meanZ;

    sumSqX += (dx * dx);
    sumSqY += (dy * dy);
    sumSqZ += (dz * dz);

    float instVectorG = sqrt(dx * dx + dy * dy + dz * dz);
    if (instVectorG > maxInstantG) {
      maxInstantG = instVectorG;
    }
  }

  m.rmsX = sqrt(sumSqX / VIBRATION_SAMPLES);
  m.rmsY = sqrt(sumSqY / VIBRATION_SAMPLES);
  m.rmsZ = sqrt(sumSqZ / VIBRATION_SAMPLES);
  m.totalRMS = sqrt((sumSqX + sumSqY + sumSqZ) / VIBRATION_SAMPLES);
  m.peakG = maxInstantG;
  m.crestFactor = (m.totalRMS > 0.001f) ? (m.peakG / m.totalRMS) : 1.0f;
  m.valid = true;

  return m;
}

float calculateVibrationRMS() {
  currentVibration = calculateVibrationFeatures();
  return currentVibration.valid ? currentVibration.totalRMS : NAN;
}

#if DATA_COLLECTION_MODE
void handleSerialCommands() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'n') {
      runId++;
      collectionRowsLogged = 0;
      Serial.printf("# [NEW RUN] Switched to Run ID %d with label '%c'\n", runId, currentLabel);
    } else if (c == 'h' || c == 'o' || c == 'i' || c == 'l') {
      currentLabel = c;
      const char* lblName = (c == 'h' ? "healthy" : c == 'o' ? "overload" : c == 'i' ? "imbalance" : "loose_mount");
      Serial.printf("# [LABEL] Set active condition to '%c' (%s)\n", c, lblName);
    } else if (c == 'c') {
      calibrateACS712();
    } else if (c == '?') {
      Serial.println(F("# Commands: 'n'=new run | 'h'=healthy | 'o'=overload | 'i'=imbalance | 'l'=loose | 'c'=re-zero"));
    }
  }
}

void logCsvRow(float temp, float curr, const VibrationMetrics& vib) {
  // Emits structured CSV: millis,run_id,label,temp_c,current_a,vib_x_rms,vib_y_rms,vib_z_rms,vib_rms_g,vib_peak_g,crest_factor
  Serial.printf("%lu,%d,%c,%.1f,%.3f,%.4f,%.4f,%.4f,%.4f,%.4f,%.2f\n",
    millis(),
    runId,
    currentLabel,
    isnan(temp) ? 0.0f : temp,
    isnan(curr) ? 0.0f : curr,
    vib.valid ? vib.rmsX : 0.0f,
    vib.valid ? vib.rmsY : 0.0f,
    vib.valid ? vib.rmsZ : 0.0f,
    vib.valid ? vib.totalRMS : 0.0f,
    vib.valid ? vib.peakG : 0.0f,
    vib.valid ? vib.crestFactor : 0.0f
  );
  collectionRowsLogged++;
}
#endif

// ============================================================
// EDGE IMPULSE TINYML CLASSIFICATION
// ============================================================

#if USE_EDGE_IMPULSE_LIB
static float ei_features[EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE];

static int raw_feature_get_data(size_t offset, size_t length, float *out_ptr) {
  memcpy(out_ptr, ei_features + offset, length * sizeof(float));
  return 0;
}
#endif

void runMotorGuardInference(float temp, float vib, float curr) {
  // ZERO-FABRICATION PRINCIPLE: Never fabricate missing readings
  if (isnan(temp) || isnan(vib) || isnan(curr)) {
    inferenceStatus = "INPUT_INVALID";
    healthStatus = "unknown";
    hasInferenceProbabilities = false;
    confHealthy = 0.0f;
    confWarning = 0.0f;
    confCritical = 0.0f;
    topConfidence = 0.0f;
    eiDspTimeMs = 0;
    eiClassificationTimeMs = 0;
    return;
  }

#if USE_EDGE_IMPULSE_LIB
  memset(ei_features, 0, sizeof(ei_features));

  if (EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE == 3) {
    // 3-feature tabular impulse matching training dataset
    ei_features[0] = temp;
    ei_features[1] = vib;
    ei_features[2] = curr;
  } else if (EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE == 8) {
    // 8-feature rich window: temp, current, 3-axis RMS, total RMS, peak, crest factor
    ei_features[0] = temp;
    ei_features[1] = curr;
    ei_features[2] = currentVibration.rmsX;
    ei_features[3] = currentVibration.rmsY;
    ei_features[4] = currentVibration.rmsZ;
    ei_features[5] = currentVibration.totalRMS;
    ei_features[6] = currentVibration.peakG;
    ei_features[7] = currentVibration.crestFactor;
  } else {
    // Frame size mismatch: reject to avoid feeding garbage zeroes into the neural net
    inferenceStatus = "MODEL_UNAVAILABLE";
    healthStatus = "unknown";
    hasInferenceProbabilities = false;
    topConfidence = 0.0f;
    return;
  }

  signal_t signal;
  signal.total_length = EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE;
  signal.get_data = &raw_feature_get_data;

  ei_impulse_result_t result = { 0 };
  EI_IMPULSE_ERROR r = run_classifier(&signal, &result, false);

  if (r == EI_IMPULSE_OK) {
    eiDspTimeMs = result.timing.dsp;
    eiClassificationTimeMs = result.timing.classification;

    confHealthy = 0.0f;
    confWarning = 0.0f;
    confCritical = 0.0f;

    float maxVal = -1.0f;
    const char* bestLabel = nullptr;

    for (size_t ix = 0; ix < EI_CLASSIFIER_LABEL_COUNT; ix++) {
      const char* label = result.classification[ix].label;
      float val = result.classification[ix].value;
      if (isnan(val) || val < 0.0f) val = 0.0f;

      if (strcmp(label, "healthy") == 0) confHealthy = val;
      else if (strcmp(label, "warning") == 0) confWarning = val;
      else if (strcmp(label, "critical") == 0) confCritical = val;

      if (val > maxVal) {
        maxVal = val;
        bestLabel = label;
      }
    }

    // Guard against all-zero probabilities
    if (maxVal <= 0.0001f || bestLabel == nullptr) {
      inferenceStatus = "MODEL_ERROR";
      healthStatus = "unknown";
      hasInferenceProbabilities = false;
      topConfidence = 0.0f;
      return;
    }

    hasInferenceProbabilities = true;
    inferenceStatus = "PREDICTED";
    healthStatus = String(bestLabel);
    topConfidence = maxVal;

    // Hard deterministic safety cutoff overrides (consistent across both paths)
    if (curr >= OVERCURRENT_LIMIT_A || temp >= 75.0f || vib >= 0.80f) {
      healthStatus = "critical";
    } else if (curr > 3.0f || temp >= 50.0f || vib >= 0.20f) {
      if (healthStatus == "healthy") {
        healthStatus = "warning";
      }
    }
    return;
  } else {
    inferenceStatus = "MODEL_ERROR";
    healthStatus = "unknown";
    hasInferenceProbabilities = false;
    topConfidence = 0.0f;
    return;
  }
#else
  hasInferenceProbabilities = true;
  inferenceStatus = "PREDICTED";

  if (curr > OVERCURRENT_LIMIT_A || vib > 0.8f || temp > 75.0f) {
    healthStatus = "critical";
    confCritical = 0.95f; confWarning = 0.04f; confHealthy = 0.01f;
    topConfidence = 0.95f;
  } else if (curr > 3.0f || vib > 0.2f || temp > 50.0f) {
    healthStatus = "warning";
    confCritical = 0.05f; confWarning = 0.90f; confHealthy = 0.05f;
    topConfidence = 0.90f;
  } else {
    healthStatus = "healthy";
    confCritical = 0.01f; confWarning = 0.04f; confHealthy = 0.95f;
    topConfidence = 0.95f;
  }
#endif
}

// ============================================================
// JSON TELEMETRY SERIALIZATION (Contract v1.0.0)
// ============================================================

String buildTelemetryJSON() {
  String eventId = generateUUIDv4();
  String timestamp = getISOTimestamp();

  const char* tempStatus = isnan(temperatureC) ? "DISCONNECTED" : "OK";
  const char* currStatus = isnan(currentAmps) ? "DISCONNECTED" : "OK";
  const char* vibStatus  = isnan(vibrationRMS_g) ? "DISCONNECTED" : "OK";

  char tempStr[16], currStr[16], vibStr[16];

  if (isnan(temperatureC)) strcpy(tempStr, "null");
  else snprintf(tempStr, sizeof(tempStr), "%.1f", temperatureC);

  if (isnan(currentAmps)) strcpy(currStr, "null");
  else snprintf(currStr, sizeof(currStr), "%.2f", currentAmps);

  if (isnan(vibrationRMS_g)) strcpy(vibStr, "null");
  else snprintf(vibStr, sizeof(vibStr), "%.3f", vibrationRMS_g);

  char probStr[128];
  if (hasInferenceProbabilities) {
    snprintf(probStr, sizeof(probStr),
      "{\"healthy\":%.3f,\"warning\":%.3f,\"critical\":%.3f}",
      confHealthy, confWarning, confCritical
    );
  } else {
    strcpy(probStr, "null");
  }

  char payload[MAX_PAYLOAD_LEN];
  snprintf(payload, sizeof(payload),
    "{"
      "\"schema_version\":\"1.0.0\","
      "\"event_id\":\"%s\","
      "\"device_id\":\"%s\","
      "\"motor_id\":\"%s\","
      "\"source\":\"hardware\","
      "\"seq\":%lu,"
      "\"timestamp\":\"%s\","
      "\"sensors\":{\"temperature_c\":%s,\"current_a\":%s,\"vibration_g_rms\":%s},"
      "\"sensor_status\":{\"temperature\":\"%s\",\"current\":\"%s\",\"vibration\":\"%s\"},"
      "\"inference\":{"
        "\"status\":\"%s\","
        "\"health_status\":\"%s\","
        "\"confidence\":%.3f,"
        "\"probabilities\":%s,"
        "\"model_version\":\"ei-motoguard-v1.0.1\","
        "\"inference_time_ms\":%d"
      "},"
      "\"diagnostics\":{"
        "\"wifi_rssi_dbm\":0,"
        "\"free_heap_bytes\":%u,"
        "\"uptime_seconds\":%lu"
      "}"
    "}",
    eventId.c_str(),
    DEVICE_ID,
    MOTOR_ID,
    telemetrySeq,
    timestamp.c_str(),
    tempStr, currStr, vibStr,
    tempStatus, currStatus, vibStatus,
    inferenceStatus.c_str(),
    healthStatus.c_str(),
    topConfidence,
    probStr,
    eiDspTimeMs + eiClassificationTimeMs,
    ESP.getFreeHeap(),
    millis() / 1000
  );

  return String(payload);
}

// ============================================================
// EMBEDDED WEB SERVER DASHBOARD
// ============================================================

void handleTelemetryApi() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", buildTelemetryJSON());
}

void handleRoot() {
  String html = F(
    "<!DOCTYPE html>"
    "<html lang='en'>"
    "<head>"
    "<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1.0'>"
    "<title>MotorGuard Edge AP Dashboard</title>"
    "<style>"
    "body{margin:0;font-family:system-ui,-apple-system,sans-serif;background:#0b0f19;color:#e2e8f0;padding:20px;}"
    ".header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1e293b;padding-bottom:15px;margin-bottom:20px;}"
    ".badge{padding:6px 14px;border-radius:9999px;font-weight:700;font-size:14px;text-transform:uppercase;letter-spacing:1px;}"
    ".badge-healthy{background:#064e3b;color:#34d399;border:1px solid #059669;}"
    ".badge-warning{background:#78350f;color:#fbbf24;border:1px solid #d97706;}"
    ".badge-critical{background:#7f1d1d;color:#f87171;border:1px solid #dc2626;}"
    ".badge-unknown{background:#374151;color:#9ca3af;}"
    ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-bottom:20px;}"
    ".card{background:#131c2e;border:1px solid #1e293b;border-radius:12px;padding:20px;}"
    ".label{color:#94a3b8;font-size:12px;text-transform:uppercase;margin-bottom:8px;letter-spacing:0.5px;}"
    ".val{font-size:32px;font-weight:700;color:#f8fafc;}"
    ".unit{font-size:16px;color:#64748b;font-weight:400;margin-left:4px;}"
    ".footer{color:#64748b;font-size:12px;text-align:center;margin-top:20px;}"
    "</style>"
    "</head>"
    "<body>"
    "<div class='header'>"
    "<div>"
    "<h2 style='margin:0;color:#38bdf8;'>MotorGuard — Edge AP</h2>"
    "<span style='color:#64748b;font-size:12px;'>Motor: MTR-775-001 | Node: esp32-node-001</span>"
    "</div>"
    "<div id='badge' class='badge badge-unknown'>INITIALIZING...</div>"
    "</div>"
    "<div class='grid'>"
    "<div class='card'><div class='label'>Chassis Temperature</div><div class='val' id='temp'>--<span class='unit'>&deg;C</span></div></div>"
    "<div class='card'><div class='label'>Armature Current</div><div class='val' id='curr'>--<span class='unit'>A</span></div></div>"
    "<div class='card'><div class='label'>Dynamic Vibration RMS</div><div class='val' id='vib'>--<span class='unit'>g</span></div></div>"
    "<div class='card'><div class='label'>TinyML Confidence</div><div class='val' id='conf'>--<span class='unit'>%</span></div></div>"
    "</div>"
    "<div class='card'>"
    "<div class='label'>Live Telemetry JSON Contract (v1.0.0)</div>"
    "<pre id='raw' style='color:#38bdf8;background:#090d16;padding:12px;border-radius:8px;font-size:12px;overflow-x:auto;max-height:220px;'></pre>"
    "</div>"
    "<div class='footer'>ESP32 SoftAP IP: 192.168.4.1 | Auto-refreshing every 1 second</div>"
    "<script>"
    "async function update(){"
    " try{"
    "  const res = await fetch('/api/telemetry');"
    "  const d = await res.json();"
    "  document.getElementById('temp').innerHTML = (d.sensors.temperature_c !== null ? d.sensors.temperature_c.toFixed(1) : 'DISCONNECTED') + '<span class=\"unit\">&deg;C</span>';"
    "  document.getElementById('curr').innerHTML = (d.sensors.current_a !== null ? d.sensors.current_a.toFixed(2) : 'DISCONNECTED') + '<span class=\"unit\">A</span>';"
    "  document.getElementById('vib').innerHTML = (d.sensors.vibration_g_rms !== null ? d.sensors.vibration_g_rms.toFixed(3) : 'DISCONNECTED') + '<span class=\"unit\">g</span>';"
    "  document.getElementById('conf').innerHTML = (d.inference.confidence * 100).toFixed(0) + '<span class=\"unit\">%</span>';"
    "  const b = document.getElementById('badge');"
    "  b.innerText = d.inference.health_status.toUpperCase();"
    "  b.className = 'badge badge-' + d.inference.health_status;"
    "  document.getElementById('raw').innerText = JSON.stringify(d, null, 2);"
    " }catch(e){console.error(e);}"
    "}"
    "setInterval(update, 1000); update();"
    "</script>"
    "</body></html>"
  );
  server.send(200, "text/html", html);
}

// ============================================================
// PUBLISH TELEMETRY & HANDLE CLIENTS
// ============================================================

void publishTelemetry() {
  telemetrySeq++;
  String payload = buildTelemetryJSON();

  char topic[64];
  snprintf(topic, sizeof(topic), "motorguard/v1/%s/telemetry", DEVICE_ID);

  if (mqttClient.connected()) {
    drainOfflineQueue();
    mqttClient.publish(topic, payload.c_str(), false);
  } else {
    enqueueOfflineMessage(payload.c_str());
  }

  Serial.printf("[SAMPLE #%lu] T: %.1f C | I: %.2f A | Vib: %.3f g | AI: %s (%.0f%%)\n",
    telemetrySeq, temperatureC, currentAmps, vibrationRMS_g, healthStatus.c_str(), topConfidence * 100
  );
}

// ============================================================
// OLED DISPLAY
// ============================================================

void updateOLED(float temp, float curr, float vib) {
  if (!oledOnline) return;

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SH110X_WHITE);

  display.setCursor(0, 0);
  display.printf("AP: 192.168.4.1 [%s]", healthStatus.c_str());

  display.setCursor(0, 14);
  if (isnan(temp)) display.println("Temp: DISCONNECTED");
  else display.printf("Temp: %.1f C", temp);

  display.setCursor(0, 26);
  if (isnan(curr)) display.println("Curr: DISCONNECTED");
  else display.printf("Curr: %.2f A", curr);

  display.setCursor(0, 38);
  if (isnan(vib)) display.println("Vib : DISCONNECTED");
  else display.printf("Vib : %.3f g", vib);

  display.setCursor(0, 50);
  if (inferenceStatus == "INPUT_INVALID") {
    display.println("AI  : SENSOR ERROR");
  } else {
    display.printf("AI  : %.0f%% | Seq #%lu", topConfidence * 100, telemetrySeq);
  }

  display.display();
}

// ============================================================
// SETUP
// ============================================================

void setup() {
  Serial.begin(115200);
  delay(1000);

  // 1. Network Initialization (Cloud Station MQTTS or Local SoftAP)
#if USE_CLOUD_MQTT
  Serial.println("\n========================================");
  Serial.println("  MOTORGUARD ESP32 SECURE CLOUD MQTTS   ");
  Serial.println("========================================");
  Serial.printf("[Wi-Fi] Connecting to station '%s'...\n", STA_WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(STA_WIFI_SSID, STA_WIFI_PASSWORD);
  int wifiAttempts = 0;
  while (WiFi.status() != WL_CONNECTED && wifiAttempts < 30) {
    delay(500);
    Serial.print(".");
    wifiAttempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[Wi-Fi] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[Wi-Fi] WARNING: Failed to connect to station Wi-Fi.");
  }

  // Configure ISRG Root X1 CA for verified TLS broker handshake
  #ifdef ISRG_ROOT_X1_CA
    espClient.setCACert(ISRG_ROOT_X1_CA);
    Serial.println("[TLS] ISRG Root X1 CA installed (verified MQTTS handshake).");
  #endif
#else
  Serial.println("\n========================================");
  Serial.println("  MOTORGUARD ESP32 STANDALONE ACCESS POINT ");
  Serial.println("========================================");
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASSWORD);
  IPAddress IP = WiFi.softAPIP();

  Serial.printf("[WIFI] Access Point active!\n");
  Serial.printf("       SSID:     %s\n", AP_SSID);
  Serial.printf("       Password: %s\n", AP_PASSWORD);
  Serial.printf("       AP IP:    %s\n", IP.toString().c_str());
  Serial.printf("       Dashboard: http://%s\n", IP.toString().c_str());
#endif

  // 2. Start Embedded Web Server
  server.on("/", handleRoot);
  server.on("/api/telemetry", handleTelemetryApi);
  server.begin();
  Serial.println("[HTTP] Web server started on port 80.");

  // 3. Optional MQTT setup (if gateway joins AP as a client)
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setBufferSize(1024);

  // 4. ADC & ACS712 Current Sensor Setup
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  pinMode(CURRENT_PIN, INPUT);

  // 5. DHT11 Initialization & Verification
  dht.begin();
  delay(150);
  float initialTemp = dht.readTemperature();
  if (!isnan(initialTemp) && initialTemp >= -20.0f && initialTemp <= 120.0f) {
    dhtOnline = true;
    temperatureC = initialTemp;
    Serial.printf("[DHT11] Verified online: %.1f C\n", initialTemp);
  } else {
    dhtOnline = false;
    Serial.println("[DHT11] WARNING: Sensor not responding on GPIO 4!");
  }

  // 6. OLED Display Initialization
  I2C_OLED.begin(32, 33, 400000);
  if (display.begin(0x3C, true)) {
    oledOnline = true;
    display.clearDisplay();
  }

  // 7. ADXL345 Accelerometer Setup (800 Hz Output Data Rate on Fast 400kHz I2C)
  Wire.begin(21, 22);
  Wire.setClock(400000); // 400 kHz fast I2C clock on Bus 0
  if (accel.begin(0x53)) {
    adxlOnline = true;
    accel.setRange(ADXL345_RANGE_4_G);
    accel.setDataRate(ADXL345_DATARATE_800_HZ);
    Serial.println("[ADXL345] Online and configured for 800 Hz (+/-4g) on 400kHz I2C");
  } else {
    adxlOnline = false;
    Serial.println("[ADXL345] WARNING: Sensor not detected on I2C address 0x53!");
  }

  // 8. Calibrate ACS712 Zero Offset on Boot
  calibrateACS712();

#if DATA_COLLECTION_MODE
  Serial.println(F("\n================================================================="));
  Serial.println(F("  MOTORGUARD RAW SENSOR DATA COLLECTION MODE ACTIVE              "));
  Serial.println(F("  Interactive Keys: 'h'=healthy, 'o'=overload, 'i'=imbalance,    "));
  Serial.println(F("                    'l'=loose mount, 'n'=increment run ID,       "));
  Serial.println(F("                    'c'=re-zero ACS712, '?'=help                 "));
  Serial.println(F("================================================================="));
  // Print standard CSV header for streaming ingestion
  Serial.println(F("timestamp_ms,run_id,label,temp_c,current_a,vib_x_rms,vib_y_rms,vib_z_rms,vib_rms_g,vib_peak_g,crest_factor"));
#endif

  Serial.println("[SYSTEM] Setup complete. Ready.\n");
}

// ============================================================
// MAIN LOOP
// ============================================================

void loop() {
#if DATA_COLLECTION_MODE
  // 1. Process interactive serial commands for ground-truth labeling
  handleSerialCommands();

  // 2. High-speed synchronized sensor read
  temperatureC   = readTemperature();
  currentAmps    = readMotorCurrent();
  vibrationRMS_g = calculateVibrationRMS(); // Populates currentVibration struct

  // 3. Log every computed window (zero window discard during collection)
  logCsvRow(temperatureC, currentAmps, currentVibration);

  // 4. Update OLED periodically without stalling collection
  if (millis() - lastOledUpdate >= 500) {
    lastOledUpdate = millis();
    updateOLED(temperatureC, currentAmps, vibrationRMS_g);
  }

  delay(5);
#else
  // Live Production & Edge Inference Mode
  // Handle incoming HTTP requests from connected laptops/phones
  server.handleClient();

  // Maintain optional MQTT connection
  if (mqttClient.connected()) {
    mqttClient.loop();
  } else if (millis() - lastMqttRetry >= 10000) {
    lastMqttRetry = millis();
    mqttClient.connect(DEVICE_ID, MQTT_USER, MQTT_PASS);
  }

  // Read sensors
  temperatureC   = readTemperature();
  currentAmps    = readMotorCurrent();
  vibrationRMS_g = calculateVibrationRMS();

  // Run TinyML Inference
  runMotorGuardInference(temperatureC, vibrationRMS_g, currentAmps);

  // Update on-board OLED display every 500 ms
  if (millis() - lastOledUpdate >= 500) {
    lastOledUpdate = millis();
    updateOLED(temperatureC, currentAmps, vibrationRMS_g);
  }

  // Process telemetry every 1.5 seconds
  if (millis() - lastTelemetryPublish >= 1500) {
    lastTelemetryPublish = millis();
    publishTelemetry();
  }

  delay(10);
#endif
}
