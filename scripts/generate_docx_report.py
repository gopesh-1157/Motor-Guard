import os
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=80, bottom=80, left=120, right=120):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'''
        <w:tcMar {nsdecls("w")}>
            <w:top w:w="{top}" w:type="dxa"/>
            <w:bottom w:w="{bottom}" w:type="dxa"/>
            <w:left w:w="{left}" w:type="dxa"/>
            <w:right w:w="{right}" w:type="dxa"/>
        </w:tcMar>
    ''')
    tcPr.append(tcMar)

def set_table_borders(table, color="000000", sz="4", val="single"):
    tblPr = table._tbl.tblPr
    tblBorders = parse_xml(f'''
        <w:tblBorders {nsdecls("w")}>
            <w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:left w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:right w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:insideV w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
        </w:tblBorders>
    ''')
    tblPr.append(tblBorders)

def add_code_block(doc, code_str, language=""):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    
    cell = table.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_background(cell, "F8F8F8")
    set_cell_margins(cell, top=100, bottom=100, left=150, right=150)
    
    # Clean black and white border: thick left bar, clean thin outer box
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(f'''
        <w:tcBorders {nsdecls("w")}>
            <w:top w:val="single" w:sz="6" w:space="0" w:color="000000"/>
            <w:left w:val="single" w:sz="20" w:space="0" w:color="000000"/>
            <w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/>
            <w:right w:val="single" w:sz="6" w:space="0" w:color="000000"/>
        </w:tcBorders>
    ''')
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.15
    
    lines = code_str.strip().split("\n")
    for i, line in enumerate(lines):
        run = p.add_run(line)
        run.font.name = "Consolas"
        run.font.size = Pt(8.5)
        run.font.color.rgb = RGBColor(0, 0, 0)
        if i < len(lines) - 1:
            p.add_run("\n")

def generate_report():
    doc = Document()
    
    # Page Margins: 0.8 inch standard academic margins
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)
        
    # Styles: Pure Black & White typography
    styles = doc.styles
    normal_style = styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = RGBColor(0, 0, 0)

    # Document Header / Title (Black & White)
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(3)
    r_title = title_p.add_run("MotorGuard — Industrial IoT Platform")
    r_title.font.name = 'Arial'
    r_title.font.size = Pt(22)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor(0, 0, 0)
    
    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_before = Pt(0)
    sub_p.paragraph_format.space_after = Pt(12)
    r_sub = sub_p.add_run("Comprehensive Source Code & Implementation Documentation")
    r_sub.font.name = 'Arial'
    r_sub.font.size = Pt(12)
    r_sub.font.bold = True
    r_sub.font.color.rgb = RGBColor(0, 0, 0)
    
    desc_p = doc.add_paragraph(
        "This document contains the verified production source code modules for the MotorGuard "
        "Intelligent Motor Health Monitoring and Predictive Maintenance System. It details all 10 "
        "core engineering implementations spanning ESP32 edge firmware, digital signal processing, "
        "MQTTS telemetry, FastAPI backend pipelines, rule-based threshold evaluation, Edge Impulse TinyML "
        "neural network inferencing, WebSocket telemetry streaming, MongoDB persistence, and the React industrial dashboard."
    )
    desc_p.paragraph_format.space_after = Pt(16)
    
    # =========================================================================
    # SECTION: # SDGs ALIGNMENT (Pure Black & White)
    # =========================================================================
    h_sdg = doc.add_heading(level=1)
    r_sdg = h_sdg.add_run("# SDGs ALIGNMENT")
    r_sdg.font.name = 'Arial'
    r_sdg.font.bold = True
    r_sdg.font.color.rgb = RGBColor(0, 0, 0)
    h_sdg.paragraph_format.space_before = Pt(14)
    h_sdg.paragraph_format.space_after = Pt(6)
    
    sdg_intro = doc.add_paragraph(
        "The MotorGuard system aligns with the following United Nations Sustainable Development Goals (SDGs) "
        "through IoT-based motor condition monitoring, early fault detection, and predictive maintenance."
    )
    sdg_intro.paragraph_format.space_after = Pt(10)
    
    sdg_table_data = [
        ("SDG Goal", "Relevance in Project Context", "Section Name(s)", "Page No."),
        (
            "SDG 9 – Industry, Innovation and Infrastructure",
            "Integrates ESP32, IoT sensors, cloud-based monitoring, and machine learning to monitor motor health and detect abnormal operating conditions. It supports the development of intelligent and reliable industrial monitoring systems.",
            "Introduction, Proposed System, System Architecture, Implementation",
            "Update according to the final report"
        ),
        (
            "SDG 12 – Responsible Consumption and Production",
            "Enables early identification of abnormal motor conditions, supporting timely maintenance and potentially extending equipment life. This can help reduce premature motor replacement and associated electronic waste.",
            "Proposed System, Condition Monitoring, Predictive Maintenance",
            "Update according to the final report"
        ),
        (
            "SDG 8 – Decent Work and Economic Growth",
            "Provides real-time motor condition information and alerts to help maintenance personnel identify potential equipment problems. It supports safer maintenance decisions and improved operational efficiency.",
            "Introduction, System Implementation, Alert Management",
            "Update according to the final report"
        ),
    ]
    
    t_sdg = doc.add_table(rows=len(sdg_table_data), cols=4)
    t_sdg.alignment = WD_TABLE_ALIGNMENT.CENTER
    t_sdg.autofit = False
    set_table_borders(t_sdg, color="000000", sz="6", val="single")
    
    sdg_col_widths = [Inches(1.5), Inches(2.7), Inches(1.4), Inches(0.9)]
    for r_idx, row in enumerate(t_sdg.rows):
        for c_idx, cell in enumerate(row.cells):
            cell.width = sdg_col_widths[c_idx]
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)
            set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            
            raw_text = sdg_table_data[r_idx][c_idx]
            
            if r_idx == 0:
                # Header row: Light grayscale shading, bold black text
                set_cell_background(cell, "EAEAEA")
                run = p.add_run(raw_text)
                run.font.bold = True
                run.font.name = "Arial"
                run.font.size = Pt(9.5)
                run.font.color.rgb = RGBColor(0, 0, 0)
            else:
                set_cell_background(cell, "FAFAFA" if r_idx % 2 == 1 else "FFFFFF")
                run = p.add_run(raw_text)
                run.font.name = "Calibri"
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(0, 0, 0)
                if c_idx == 0:
                    run.font.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(14)

    # =========================================================================
    # SECTION: Priority Code Modules Index (Pure Black & White)
    # =========================================================================
    h2 = doc.add_heading(level=1)
    r_h2 = h2.add_run("1. Priority Code Modules Index")
    r_h2.font.name = 'Arial'
    r_h2.font.bold = True
    r_h2.font.color.rgb = RGBColor(0, 0, 0)
    h2.paragraph_format.space_before = Pt(14)
    h2.paragraph_format.space_after = Pt(8)
    
    table_data = [
        ("S. No.", "Source Code Module", "What It Demonstrates", "Priority"),
        ("1", "ESP32 sensor data acquisition", "Reads current (ACS712), temperature (DHT11), and vibration (ADXL345)", "Essential"),
        ("2", "Sensor data processing", "Calculates dynamic vibration RMS and peak shock values (ISO 10816)", "Essential"),
        ("3", "MQTT telemetry publishing", "Publishes JSON telemetry from ESP32 to MQTTS Cloud broker with RAM ring buffer", "Essential"),
        ("4", "FastAPI telemetry API", "Receives, validates (Pydantic), and processes motor telemetry via REST", "Essential"),
        ("5", "Motor health monitoring", "Evaluates sensor readings against dynamic thresholds with 10% hysteresis", "Essential"),
        ("6", "ML prediction integration", "Executes Edge Impulse TinyML neural network on ESP32 for anomaly diagnosis", "Essential"),
        ("7", "Alert generation", "Generates de-duplicated active alarms and commits tamper-proof audit events", "Essential"),
        ("8", "WebSocket live updates", "Broadcasts 100 Hz real-time telemetry frames to connected dashboards", "Recommended"),
        ("9", "MongoDB data storage", "Stores telemetry records with 90-day TTL index retention and deduplication", "Recommended"),
        ("10", "React dashboard", "Industrial dark navy UI displaying fleet health, alarms, and live sensor readings", "Recommended"),
    ]
    
    t = doc.add_table(rows=len(table_data), cols=4)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    set_table_borders(t, color="000000", sz="6", val="single")
    
    col_widths = [Inches(0.6), Inches(2.0), Inches(2.8), Inches(1.1)]
    for row_idx, row in enumerate(t.rows):
        for col_idx, cell in enumerate(row.cells):
            cell.width = col_widths[col_idx]
            cell.text = table_data[row_idx][col_idx]
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
            
            # Header row styling: Grayscale shading with bold black text
            if row_idx == 0:
                set_cell_background(cell, "EAEAEA")
                for run in p.runs:
                    run.font.bold = True
                    run.font.name = "Arial"
                    run.font.size = Pt(9.5)
                    run.font.color.rgb = RGBColor(0, 0, 0)
            else:
                set_cell_background(cell, "FAFAFA" if row_idx % 2 == 1 else "FFFFFF")
                for run in p.runs:
                    run.font.name = "Calibri"
                    run.font.size = Pt(9)
                    run.font.color.rgb = RGBColor(0, 0, 0)
                    if col_idx == 3:
                        run.font.bold = True
    
    doc.add_page_break()
    
    # =========================================================================
    # 10 Detailed Code Sections (Pure Black & White)
    # =========================================================================
    sections_content = [
        (
            "1. ESP32 Sensor Data Acquisition",
            "firmware/esp32_motor_node/esp32_motor_node.ino",
            "Essential",
            "This module performs physical data acquisition across three hardware sensors attached to an industrial DC motor: the ACS712-20A Hall-effect current transducer, DHT11 ambient temperature sensor, and ADXL345 digital accelerometer. It implements oversampling (120 ADC samples per current reading) and disconnections/wire-break safety detection.",
            """// 1. Current Sensor (ACS712 20A) Multi-Sample Reading
float readMotorCurrent() {
  float pinVoltageSum = 0.0f;
  float maxInstantCurrent = 0.0f;
  const int SAMPLES = 120; // 120 samples damped over ~30 ms

  for (int i = 0; i < SAMPLES; i++) {
    uint32_t mv = analogReadMilliVolts(CURRENT_PIN);
    float pinVoltage = mv / 1000.0f;

    // Disconnection / wire break detection:
    if (pinVoltage < 0.15f || pinVoltage > 3.15f) {
      currentPeakAmps = NAN;
      return NAN;
    }
    pinVoltageSum += pinVoltage;
    float instCurrent = fabs((pinVoltage - zeroPointPinVolts) / EFFECTIVE_SENSITIVITY_AT_PIN);
    if (instCurrent > maxInstantCurrent) maxInstantCurrent = instCurrent;
    delayMicroseconds(250);
  }

  float avgPinVoltage = pinVoltageSum / SAMPLES;
  float current = fabs((avgPinVoltage - zeroPointPinVolts) / EFFECTIVE_SENSITIVITY_AT_PIN);
  if (current < CURRENT_DEADBAND_A) current = 0.0f;

  currentPeakAmps = maxInstantCurrent;
  return current;
}

// 2. Temperature Sensor (DHT11) Reading with Pacing
float readTemperature() {
  if (millis() - lastDhtReadTime < 1500 && !isnan(temperatureC)) return temperatureC;
  lastDhtReadTime = millis();
  float temp = dht.readTemperature();
  if (isnan(temp) || temp < -20.0f || temp > 120.0f) {
    dhtOnline = false;
    return NAN;
  }
  dhtOnline = true;
  return temp;
}"""
        ),
        (
            "2. Sensor Data Processing (Vibration RMS & Peak)",
            "firmware/esp32_motor_node/esp32_motor_node.ino",
            "Essential",
            "Computes authoritative dynamic vibration RMS and instantaneous peak shock in accordance with ISO 10816 standards. It synchronizes sampling to precisely 100 Hz (10,000 µs intervals), removes the static 1g Earth gravity bias via dynamic per-axis mean subtraction, and extracts crest factors.",
            """VibrationMetrics calculateVibrationFeatures() {
  VibrationMetrics m = {0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, false};
  float ax[VIBRATION_SAMPLES], ay[VIBRATION_SAMPLES], az[VIBRATION_SAMPLES];
  float meanX = 0.0f, meanY = 0.0f, meanZ = 0.0f;
  sensors_event_t event;

  // Synchronized 100 Hz sampling loop (128 samples over 1.28 s)
  for (int i = 0; i < VIBRATION_SAMPLES; i++) {
    unsigned long sampleStart = micros();
    accel.getEvent(&event);
    ax[i] = event.acceleration.x / 9.80665f; // Convert raw m/s^2 to g
    ay[i] = event.acceleration.y / 9.80665f;
    az[i] = event.acceleration.z / 9.80665f;

    meanX += ax[i]; meanY += ay[i]; meanZ += az[i];
    while (micros() - sampleStart < VIBRATION_SAMPLE_INTERVAL_US) yield();
  }

  meanX /= VIBRATION_SAMPLES; meanY /= VIBRATION_SAMPLES; meanZ /= VIBRATION_SAMPLES;
  float sumDynSq = 0.0f, maxInstantG = 0.0f;

  for (int i = 0; i < VIBRATION_SAMPLES; i++) {
    // Dynamic AC vibration (gravity offset removed via mean subtraction)
    float dx = ax[i] - meanX;
    float dy = ay[i] - meanY;
    float dz = az[i] - meanZ;

    float instVectorG = sqrt(dx * dx + dy * dy + dz * dz);
    sumDynSq += (dx * dx + dy * dy + dz * dz);
    if (instVectorG > maxInstantG) maxInstantG = instVectorG;
  }

  // Dynamic Vibration RMS: sqrt(mean(dx^2 + dy^2 + dz^2))
  m.totalRMS = sqrt(sumDynSq / VIBRATION_SAMPLES);
  m.peakG = maxInstantG;
  m.crestFactor = (m.totalRMS > 0.001f) ? (m.peakG / m.totalRMS) : 1.0f;
  return m;
}"""
        ),
        (
            "3. MQTT Telemetry Publishing",
            "firmware/esp32_motor_node/esp32_motor_node.ino",
            "Essential",
            "Handles network transmission of industrial telemetry payloads using MQTT over TLS (Port 8883) to EMQX Cloud. Implements an on-chip RAM store-and-forward circular buffer that queues up to 32 packets during wireless network dropouts and automatically drains when connectivity resumes.",
            """void publishTelemetry() {
  telemetrySeq++;
  String payload = buildTelemetryJSON();

  char topic[64];
  snprintf(topic, sizeof(topic), "motorguard/v1/%s/telemetry", DEVICE_ID);

  if (mqttClient.connected()) {
    // Flush store-and-forward queue if reconnected
    drainOfflineQueue();
    // Publish live telemetry packet
    mqttClient.publish(topic, payload.c_str(), false);
  } else {
    // Buffer in RAM ring buffer when connection drops to prevent data loss
    enqueueOfflineMessage(payload.c_str());
  }

  Serial.printf("[TELEMETRY #%lu] Published to %s (Length: %d bytes)\n",
    telemetrySeq, topic, payload.length());
}"""
        ),
        (
            "4. FastAPI Telemetry Ingestion Endpoint",
            "backend/app/api/v1/endpoints/telemetry.py",
            "Essential",
            "Provides an enterprise dual-authenticated HTTP REST ingestion endpoint. Validates edge gateway tokens against pre-shared keys (X-Device-API-Key) or Bearer JWT tokens, validates strict Pydantic schemas, and routes data into the pipeline.",
            """@router.post("/ingest", summary="Direct Telemetry Ingestion")
async def ingest_telemetry_event(
    message: TelemetryMessage,
    auth_identity: str = Depends(validate_telemetry_ingest_auth),
):
    \"\"\"
    Direct HTTP/MQTT ingestion gateway endpoint for ESP32 and edge nodes.
    Validates Pydantic schema, ingests to MongoDB, checks rules, and broadcasts.
    \"\"\"
    from backend.app.main import _ingest_and_broadcast
    inserted = await _ingest_and_broadcast(message.model_dump())
    return {"success": inserted, "event_id": message.event_id}

@router.get("/recent", summary="Get Recent Telemetry")
async def get_recent_telemetry(
    motor_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
    current_user: UserOut = Depends(get_current_active_user),
):
    collection = db_manager.db["telemetry"]
    query = {"motor_id": motor_id} if motor_id else {}
    cursor = collection.find(query, {"_id": 0}).sort("server_received_at", -1).limit(limit)
    return {"telemetry": await cursor.to_list(length=limit)}"""
        ),
        (
            "5. Motor Health Monitoring & Threshold Evaluation",
            "backend/app/services/alert_service.py",
            "Essential",
            "Executes continuous rules-based safety evaluation on incoming sensor readings against motor-specific operational limits. Includes hard ceiling cutoffs and a 10% hysteresis band to eliminate threshold chatter and false alarm cycling.",
            """# Overcurrent evaluation with hysteresis normalization
crit_curr = thresholds.get("current_critical_a", 4.0)
warn_curr = thresholds.get("current_warning_a", crit_curr * 0.85)

if current_a is not None and current_a >= warn_curr:
    curr_sev: AlertSeverity = "CRITICAL" if current_a >= crit_curr else "WARNING"
    curr_limit = float(crit_curr) if current_a >= crit_curr else float(warn_curr)
    alert = await self._trigger_or_update_alert(
        motor_id=motor_id,
        device_id=device_id,
        severity=curr_sev,
        trigger_type="THRESHOLD_OVERCURRENT",
        trigger_value=float(current_a),
        threshold_limit=curr_limit,
        unit="A",
        message=f"Overcurrent trip limit exceeded on {motor_id}: measured {current_a:.2f} A (limit {curr_limit:.1f} A)",
        site_id=site_id,
    )
    if alert:
        created_alerts.append(alert)
elif current_a is not None and current_a <= (warn_curr * 0.90):
    # Safe return below 90% threshold triggers auto-resolution
    await self._auto_resolve_if_active(
        motor_id=motor_id,
        trigger_type="THRESHOLD_OVERCURRENT",
        notes="Armature current normalized safely below threshold hysteresis band",
    )"""
        ),
        (
            "6. ML Prediction Integration (Edge Impulse TinyML)",
            "firmware/esp32_motor_node/esp32_motor_node.ino",
            "Essential",
            "Integrates an on-device quantized int8 deep learning neural network model directly onto the ESP32 microcontroller using Edge Impulse inferencing. Classifies motor behavior into healthy, warning, and critical states with associated confidence probabilities.",
            """void runMotorGuardInference(float temp, float vib, float curr) {
  // Zero-Fabrication Principle: Do not predict on invalid or disconnected sensors
  if (isnan(temp) || isnan(vib) || isnan(curr)) {
    inferenceStatus = "INPUT_INVALID";
    healthStatus = "unknown";
    return;
  }

  // Load feature buffer matching neural network DSP input frame
  ei_features[0] = temp;
  ei_features[1] = vib;
  ei_features[2] = curr;

  signal_t signal;
  signal.total_length = EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE;
  signal.get_data = &raw_feature_get_data;

  // Execute Edge Impulse TinyML Classifier on ESP32 Xtensa core
  ei_impulse_result_t result = { 0 };
  EI_IMPULSE_ERROR r = run_classifier(&signal, &result, false);

  if (r == EI_IMPULSE_OK) {
    for (size_t ix = 0; ix < EI_CLASSIFIER_LABEL_COUNT; ix++) {
      if (strcmp(result.classification[ix].label, "healthy") == 0) confHealthy = result.classification[ix].value;
      if (strcmp(result.classification[ix].label, "warning") == 0) confWarning = result.classification[ix].value;
      if (strcmp(result.classification[ix].label, "critical") == 0) confCritical = result.classification[ix].value;
    }
    // Determine winning classification and top confidence score
    topConfidence = max(confHealthy, max(confWarning, confCritical));
    healthStatus = (topConfidence == confCritical) ? "critical" : (topConfidence == confWarning) ? "warning" : "healthy";
    inferenceStatus = "OK";
  }
}"""
        ),
        (
            "7. De-duplicated Alert Generation",
            "backend/app/services/alert_service.py",
            "Essential",
            "Generates unique alert tickets (ALT-YYYYMMDD-XXXX) and state machines (ACTIVE -> ACKNOWLEDGED -> RESOLVED). Leverages partial MongoDB unique indices to de-duplicate alerts across concurrent edge gateways and prevent alert fatigue.",
            """async def _trigger_or_update_alert(
    self, motor_id: str, device_id: str, severity: AlertSeverity, trigger_type: AlertTriggerType,
    trigger_value: float, threshold_limit: float, unit: str, message: str, site_id: Optional[str] = None
) -> Optional[AlertOut]:
    now = datetime.now(timezone.utc)

    # 1. Check for existing ACTIVE alert to de-duplicate and prevent alert fatigue
    existing = await self.collection.find_one({"motor_id": motor_id, "trigger_type": trigger_type, "state": "ACTIVE"})
    if existing:
        updated_severity = "CRITICAL" if existing.get("severity") == "CRITICAL" else severity
        await self.collection.update_one(
            {"_id": existing["_id"]},
            {"$set": {"trigger_value": trigger_value, "severity": updated_severity, "last_observed_at": now}}
        )
        return None

    # 2. Insert new ACTIVE alert record
    alert_id = f"ALT-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    doc = {
        "alert_id": alert_id, "motor_id": motor_id, "device_id": device_id, "site_id": site_id,
        "severity": severity, "trigger_type": trigger_type, "trigger_value": trigger_value,
        "threshold_limit": threshold_limit, "unit": unit, "message": message,
        "state": "ACTIVE", "triggered_at": now, "last_observed_at": now
    }
    await self.collection.insert_one(doc)
    await self._audit("ALERT_TRIGGERED", "RulesEngine", alert_id, {"motor_id": motor_id, "severity": severity})
    return AlertOut(**doc)"""
        ),
        (
            "8. WebSocket Live Telemetry Hub",
            "backend/app/api/v1/endpoints/websocket.py & main.py",
            "Recommended",
            "Manages persistent full-duplex WebSocket connections with browser clients. Streams live high-frequency telemetry packets and alert notifications with RBAC scoping and site authorization.",
            """class WebSocketManager:
    def __init__(self):
        self._connections: Dict[WebSocket, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user: Optional[Any] = None) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = {"username": getattr(user, "username", "operator")}

    async def broadcast(self, message: dict) -> None:
        \"\"\"Broadcast live telemetry or alert JSON payload to all active clients.\"\"\"
        async with self._lock:
            for ws in list(self._connections.keys()):
                try:
                    await ws.send_json(message)
                except Exception:
                    self._connections.pop(ws, None)

# In backend/app/main.py _ingest_and_broadcast():
# Broadcast live telemetry frame to all dashboards
await ws_manager.broadcast({"type": "telemetry", "data": payload})"""
        ),
        (
            "9. MongoDB Telemetry Persistence & Storage",
            "backend/app/services/telemetry_ingestion.py",
            "Recommended",
            "Handles asynchronous storage of validated telemetry packets into MongoDB collections. Configures automated 90-day time-to-live (TTL) expiration indices and compound indexes for fast query resolution.",
            """async def ingest(self, payload: dict) -> bool:
    \"\"\"
    Persists valid telemetry event into MongoDB with TTL expiration and indexing.
    Enforces deduplication on (device_id, event_id) and records receipt timestamp.
    \"\"\"
    now = datetime.now(timezone.utc)
    doc = dict(payload)
    doc["server_received_at"] = now

    try:
        # Atomic insertion with unique key de-duplication
        await self.collection.insert_one(doc)
        logger.debug("Ingested telemetry frame: device=%s motor=%s", doc.get("device_id"), doc.get("motor_id"))
        return True
    except DuplicateKeyError:
        logger.warning("Duplicate telemetry payload dropped: event_id=%s", doc.get("event_id"))
        return False"""
        ),
        (
            "10. React Dashboard UI (Fleet KPI & Health Roster)",
            "frontend/src/components/OverviewView.tsx",
            "Recommended",
            "Industrial dashboard component presenting operational fleet status, asset health counters (Nominal Run, Advisory, Critical Alarms), tabular sensor readings, and real-time status indicators.",
            """export const OverviewView: FC<OverviewViewProps> = ({ stats, motors, alerts, wsConnected }) => {
  return (
    <div className="overview-container">
      {/* 1. Fleet Condition KPI Metric Row */}
      <div className="kpi-summary-row">
        <div className="kpi-summary-card">
          <div className="kpi-header"><span>TOTAL ASSETS</span><Activity size={14} /></div>
          <div className="kpi-value-row">
            <span className="kpi-value tabular-nums">{stats.totalMotors}</span>
            <span className="kpi-unit">DRIVES</span>
          </div>
        </div>

        <div className="kpi-summary-card healthy">
          <div className="kpi-header"><span>NOMINAL RUN</span><CheckCircle size={14} /></div>
          <div className="kpi-value-row">
            <span className="kpi-value tabular-nums">{stats.healthyCount}</span>
            <span className="kpi-unit">OPTIMAL</span>
          </div>
        </div>

        <div className="kpi-summary-card critical">
          <div className="kpi-header"><span>CRITICAL ALARMS</span><XCircle size={14} /></div>
          <div className="kpi-value-row">
            <span className="kpi-value tabular-nums">{stats.criticalCount}</span>
            <span className="kpi-unit">TRIPPED</span>
          </div>
        </div>
      </div>

      {/* 2. Plant Floor Drive Roster Table */}
      <table className="industrial-table">
        <thead>
          <tr>
            <th>ASSET TAG</th><th>STATUS</th><th>TEMP [°C]</th><th>CURRENT [A]</th><th>VIB [g RMS]</th>
          </tr>
        </thead>
        <tbody>
          {motors.map((m) => (
            <tr key={m.motor_id}>
              <td className="font-mono">{m.motor_id}</td>
              <td><span className={`status-pill ${m.latest.inference.health_status}`}>{m.latest.inference.health_status.toUpperCase()}</span></td>
              <td className="tabular-nums font-mono">{m.latest.sensors.temperature_c?.toFixed(1) ?? '—'}</td>
              <td className="tabular-nums font-mono">{m.latest.sensors.current_a?.toFixed(2) ?? '—'}</td>
              <td className="tabular-nums font-mono">{m.latest.sensors.vibration_g_rms?.toFixed(3) ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};"""
        ),
    ]
    
    for title, filepath, priority, explanation, code in sections_content:
        h = doc.add_heading(level=2)
        r_h = h.add_run(title)
        r_h.font.name = "Arial"
        r_h.font.bold = True
        r_h.font.color.rgb = RGBColor(0, 0, 0)
        h.paragraph_format.space_before = Pt(14)
        h.paragraph_format.space_after = Pt(2)
        
        # Metadata line in pure black & white
        meta_p = doc.add_paragraph()
        meta_p.paragraph_format.space_before = Pt(0)
        meta_p.paragraph_format.space_after = Pt(4)
        
        r_fp_label = meta_p.add_run("Source File: ")
        r_fp_label.font.bold = True
        r_fp_label.font.size = Pt(9.5)
        r_fp_label.font.color.rgb = RGBColor(0, 0, 0)
        
        r_fp = meta_p.add_run(filepath + "   |   ")
        r_fp.font.name = "Consolas"
        r_fp.font.size = Pt(9)
        r_fp.font.color.rgb = RGBColor(0, 0, 0)
        
        r_pri_label = meta_p.add_run("Priority: ")
        r_pri_label.font.bold = True
        r_pri_label.font.size = Pt(9.5)
        r_pri_label.font.color.rgb = RGBColor(0, 0, 0)
        
        r_pri = meta_p.add_run(priority)
        r_pri.font.bold = True
        r_pri.font.size = Pt(9.5)
        r_pri.font.color.rgb = RGBColor(0, 0, 0)
        
        exp_p = doc.add_paragraph(explanation)
        exp_p.paragraph_format.space_before = Pt(2)
        exp_p.paragraph_format.space_after = Pt(6)
        
        add_code_block(doc, code)
        doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # Save Document
    output_path = os.path.abspath("MotorGuard_Source_Code_Report.docx")
    doc.save(output_path)
    print(f"Generated DOCX report successfully at: {output_path}")

if __name__ == "__main__":
    generate_report()
