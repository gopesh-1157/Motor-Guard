"""
MotorGuard — USB Serial to Gateway Telemetry Bridge

Bridges physical ESP32 hardware plugged in via USB (COM7 / CP210x / CH340)
directly into the local MotorGuard platform (MQTT + REST API).
Enables zero-configuration hardware telemetry without requiring Wi-Fi reconfiguration.
"""

import os
import sys
import time
import re
import uuid
import logging
from datetime import datetime, timezone
import requests
import serial
import serial.tools.list_ports

try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("motorguard.serial_bridge")

BAUD_RATE = int(os.getenv("SERIAL_BAUD", "115200"))
TARGET_PORT = os.getenv("SERIAL_PORT", "COM7")
API_INGEST_URL = os.getenv("INGEST_URL", "http://127.0.0.1:8000/api/v1/telemetry/ingest")
MQTT_HOST = os.getenv("MQTT_BROKER_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USERNAME", "motorguard_gateway")
MQTT_PASS = os.getenv("MQTT_PASSWORD", "")
MQTT_USE_TLS = os.getenv("MQTT_USE_TLS", "false").lower() in ("true", "1") or MQTT_PORT == 8883
MQTT_TLS_INSECURE = os.getenv("MQTT_TLS_INSECURE", "false").lower() in ("true", "1")
MQTT_TLS_CA_CERT = os.getenv("MQTT_TLS_CA_CERT", None)

SAMPLE_REGEX = re.compile(
    r"\[SAMPLE #(\d+)\] T:\s*([\d\.-]+|nan)\s*C\s*\|\s*I:\s*([\d\.-]+|nan)\s*A\s*\|\s*Vib:\s*([\d\.-]+|nan)\s*g\s*\|\s*AI:\s*(\w+)\s*\((\d+)%\)",
    re.IGNORECASE,
)


def find_esp32_port() -> str | None:
    """Detect available ESP32 serial port or fallback to TARGET_PORT."""
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = (p.description or "").lower()
        if "cp210" in desc or "ch340" in desc or "usb-serial" in desc or "uart" in desc:
            return p.device
        if p.device.upper() == TARGET_PORT.upper():
            return p.device
    return TARGET_PORT if ports else None


def build_payload(seq: int, temp: float | None, curr: float | None, vib: float | None, health: str, conf: float) -> dict:
    """Build compliant v1.0.0 telemetry packet."""
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    t_status = "OK" if temp is not None else "DISCONNECTED"
    c_status = "OK" if curr is not None else "DISCONNECTED"
    v_status = "OK" if vib is not None else "DISCONNECTED"
    
    health_norm = health.lower()
    if health_norm not in ("healthy", "warning", "critical"):
        health_norm = "unknown"

    prob_healthy = conf if health_norm == "healthy" else round((1.0 - conf) / 2, 3)
    prob_warning = conf if health_norm == "warning" else round((1.0 - conf) / 2, 3)
    prob_critical = conf if health_norm == "critical" else round((1.0 - conf) / 2, 3)

    return {
        "schema_version": "1.0.0",
        "event_id": str(uuid.uuid4()),
        "device_id": "esp32-node-001",
        "motor_id": "MTR-775-001",
        "source": "hardware",
        "seq": seq,
        "timestamp": now_iso,
        "sensors": {
            "temperature_c": temp,
            "current_a": curr,
            "vibration_g_rms": vib,
        },
        "sensor_status": {
            "temperature": t_status,
            "current": c_status,
            "vibration": v_status,
        },
        "inference": {
            "status": "PREDICTED",
            "health_status": health_norm,
            "confidence": conf,
            "probabilities": {
                "healthy": prob_healthy,
                "warning": prob_warning,
                "critical": prob_critical,
            },
            "model_version": "ei-motoguard-v1.0.1",
            "inference_time_ms": 6,
        },
        "diagnostics": {
            "wifi_rssi_dbm": 0,
            "free_heap_bytes": 174000,
            "uptime_seconds": seq * 2,
        },
    }


def run_bridge():
    logger.info("Starting MotorGuard USB Serial Hardware Bridge...")
    mqtt_client = None
    if HAS_MQTT:
        try:
            mqtt_client = mqtt.Client()
            if MQTT_USER:
                mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
            if MQTT_USE_TLS:
                import ssl
                ssl_ctx = ssl.create_default_context(cafile=MQTT_TLS_CA_CERT)
                ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
                if MQTT_TLS_INSECURE:
                    ssl_ctx.check_hostname = False
                    ssl_ctx.verify_mode = ssl.CERT_NONE
                    mqtt_client.tls_set_context(ssl_ctx)
                    mqtt_client.tls_insecure_set(True)
                else:
                    ssl_ctx.check_hostname = True
                    ssl_ctx.verify_mode = ssl.CERT_REQUIRED
                    mqtt_client.tls_set_context(ssl_ctx)
            mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
            mqtt_client.loop_start()
            logger.info("Connected to MQTT broker at %s:%d (TLS=%s)", MQTT_HOST, MQTT_PORT, MQTT_USE_TLS)
        except Exception as e:
            logger.warning("Could not connect to MQTT: %s (will use REST HTTP ingestion)", e)
            mqtt_client = None

    while True:
        port = find_esp32_port()
        if not port:
            logger.warning("No ESP32 serial port detected. Retrying in 2s...")
            time.sleep(2)
            continue

        try:
            logger.info("Opening serial connection to %s at %d baud...", port, BAUD_RATE)
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = BAUD_RATE
            ser.dtr = False
            ser.rts = False
            ser.timeout = 2.0
            ser.open()
            logger.info("Connected to ESP32 on %s. Streaming live hardware telemetry...", port)

            while True:
                line_bytes = ser.readline()
                if not line_bytes:
                    continue
                line = line_bytes.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                m = SAMPLE_REGEX.search(line)
                if m:
                    seq_str, t_str, c_str, v_str, h_str, conf_str = m.groups()
                    seq = int(seq_str)
                    temp = None if t_str.lower() == "nan" else float(t_str)
                    curr = None if c_str.lower() == "nan" else float(c_str)
                    vib = None if v_str.lower() == "nan" else float(v_str)
                    conf = float(conf_str) / 100.0

                    payload = build_payload(seq, temp, curr, vib, h_str, conf)
                    logger.info("Ingesting Hardware Sample #%d -> T: %s°C, I: %sA, Vib: %sg [%s %d%%]",
                                seq, temp, curr, vib, h_str, int(conf * 100))

                    # 1. Post to FastAPI Ingestion Endpoint
                    try:
                        requests.post(API_INGEST_URL, json=payload, timeout=1.0)
                    except Exception as http_err:
                        logger.debug("HTTP ingest notice: %s", http_err)

                    # 2. Publish to MQTT topic if available
                    if mqtt_client and mqtt_client.is_connected():
                        import json
                        mqtt_client.publish(
                            f"motorguard/v1/{payload['device_id']}/telemetry",
                            json.dumps(payload),
                            qos=1,
                        )

        except (serial.SerialException, OSError) as e:
            logger.warning("Serial port error (%s). Reconnecting in 2s...", e)
            time.sleep(2)
        except KeyboardInterrupt:
            logger.info("Serial bridge terminated by user.")
            break


if __name__ == "__main__":
    run_bridge()
