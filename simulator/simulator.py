"""
MotorGuard — Edge Virtual Motor Simulator with Hardware-in-the-Loop (HIL) Tracking

Simulates telemetry streams from physical DC motors under healthy,
degrading, and failure operating conditions, complying strictly with
the v1.0.0 Telemetry Contract Specification.

Features HIL Live Baseline Tracking:
Subscribes to physical ESP32 hardware telemetry and dynamically couples
virtual fleet motors to live bench readings (ambient temperature, vibration noise floor,
and electrical baseline).
"""

import os
import sys
import time
import json
import uuid
import math
import random
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("motorguard.simulator")

MQTT_HOST = os.getenv("MQTT_BROKER_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USERNAME", "motorguard_gateway")
MQTT_PASS = os.getenv("MQTT_PASSWORD", "")
MQTT_USE_TLS = os.getenv("MQTT_USE_TLS", "false").lower() in ("true", "1") or MQTT_PORT == 8883
MQTT_TLS_INSECURE = os.getenv("MQTT_TLS_INSECURE", "false").lower() in ("true", "1")
MQTT_TLS_CA_CERT = os.getenv("MQTT_TLS_CA_CERT", None)
PUBLISH_INTERVAL_SEC = float(os.getenv("SIMULATOR_INTERVAL_SEC", "1.5"))

HIL_TRACKING_ENABLED = os.getenv("HIL_TRACKING_ENABLED", "true").lower() in ("true", "1")
HIL_SOURCE_DEVICE = os.getenv("HIL_SOURCE_DEVICE", "esp32-node-001")
HIL_STALE_TIMEOUT_SEC = float(os.getenv("HIL_STALE_TIMEOUT_SEC", "15.0"))


class LiveHardwareBaseline:
    """Thread-safe state container tracking live physical readings from bench ESP32."""

    def __init__(self, target_device_id: str = "esp32-node-001", timeout_sec: float = 15.0):
        self.target_device_id = target_device_id
        self.timeout_sec = timeout_sec
        self.temp_c: Optional[float] = None
        self.current_a: Optional[float] = None
        self.vibration_g_rms: Optional[float] = None
        self.last_updated_epoch: float = 0.0
        self.packets_received: int = 0

    def update_from_payload(self, payload: Dict[str, Any]) -> bool:
        """Update live baseline from an incoming telemetry JSON payload."""
        # Only accept hardware telemetry
        if payload.get("source") != "hardware":
            return False

        device_id = payload.get("device_id")
        if self.target_device_id and device_id != self.target_device_id:
            return False

        sensors = payload.get("sensors", {})
        self.temp_c = sensors.get("temperature_c")
        self.current_a = sensors.get("current_a")
        self.vibration_g_rms = sensors.get("vibration_g_rms")
        self.last_updated_epoch = time.time()
        self.packets_received += 1
        return True

    def is_active(self) -> bool:
        """Check if fresh physical ESP32 telemetry was received within timeout."""
        if self.last_updated_epoch <= 0:
            return False
        return (time.time() - self.last_updated_epoch) <= self.timeout_sec

    def age_seconds(self) -> float:
        """Return seconds elapsed since last physical reading."""
        if self.last_updated_epoch <= 0:
            return float("inf")
        return time.time() - self.last_updated_epoch


class VirtualMotor:
    """Simulates a DC motor, optionally seeded by real-time ESP32 hardware readings."""

    def __init__(
        self,
        motor_id: str,
        device_id: str,
        profile: str = "healthy",
        live_baseline: Optional[LiveHardwareBaseline] = None,
    ):
        self.motor_id = motor_id
        self.device_id = device_id
        self.profile = profile
        self.live_baseline = live_baseline
        self.seq = 0
        self.start_time = time.time()

        # Static fallback baselines when no physical hardware is broadcasting
        if profile == "healthy":
            self.default_temp = 38.0
            self.default_curr = 2.1
            self.default_vib = 0.08
        elif profile == "warning_temp":
            self.default_temp = 54.0
            self.default_curr = 3.2
            self.default_vib = 0.12
        elif profile == "critical_vib":
            self.default_temp = 42.0
            self.default_curr = 4.3
            self.default_vib = 0.85
        elif profile == "disconnected_temp":
            self.default_temp = None
            self.default_curr = 1.9
            self.default_vib = 0.09
        else:
            self.default_temp = 35.0
            self.default_curr = 1.8
            self.default_vib = 0.05

    def step(self) -> dict:
        self.seq += 1
        elapsed = time.time() - self.start_time

        # 1. Determine active base values (HIL Live Seed vs. Synthetic Fallback)
        hil_active = bool(self.live_baseline and self.live_baseline.is_active())
        seeded_device = self.live_baseline.target_device_id if hil_active else None

        if hil_active and self.live_baseline:
            # Seeded by live physical bench readings
            hw_temp = self.live_baseline.temp_c
            hw_curr = self.live_baseline.current_a or 0.15
            hw_vib = self.live_baseline.vibration_g_rms or 0.015

            if self.profile == "healthy":
                base_temp = hw_temp if hw_temp is not None else self.default_temp
                base_curr = max(0.5, hw_curr * 1.05)
                base_vib = max(0.01, hw_vib * 1.02)
            elif self.profile == "warning_temp":
                # Elevated thermal load on top of physical ambient baseline
                base_temp = (hw_temp + 22.0) if hw_temp is not None else 54.0
                base_curr = max(2.5, hw_curr * 1.8 + 1.2)
                base_vib = max(0.10, hw_vib + 0.09)
            elif self.profile == "critical_vib":
                # Bearing fault vibration spike on top of physical vibration
                base_temp = (hw_temp + 8.0) if hw_temp is not None else 42.0
                base_curr = max(3.8, hw_curr * 2.2 + 1.8)
                base_vib = max(0.80, hw_vib + 0.78)
            elif self.profile == "disconnected_temp":
                base_temp = None
                base_curr = max(1.0, hw_curr * 1.1)
                base_vib = max(0.05, hw_vib * 1.1)
            else:
                base_temp = hw_temp if hw_temp is not None else self.default_temp
                base_curr = hw_curr
                base_vib = hw_vib
        else:
            # Synthetic standalone baseline
            base_temp = self.default_temp
            base_curr = self.default_curr
            base_vib = self.default_vib

        # 2. Add realistic physical noise and harmonic dynamics
        if base_temp is not None:
            temp = round(base_temp + math.sin(elapsed / 15.0) * 0.8 + random.uniform(-0.2, 0.2), 1)
            temp_status = "OK"
        else:
            temp = None
            temp_status = "DISCONNECTED"

        curr = round(base_curr + math.sin(elapsed / 8.0) * 0.15 + random.uniform(-0.04, 0.04), 2)
        curr = max(0.0, curr)
        curr_status = "OK"

        vib = round(base_vib + random.uniform(-0.012, 0.018), 3)
        vib = max(0.005, vib)
        vib_status = "OK"

        current_peak = round(curr * random.uniform(1.05, 1.25), 2)
        vib_peak = round(vib * random.uniform(1.4, 2.2), 3)

        # 3. Determine Edge Impulse TinyML health prediction (pure ML classification)
        if (curr > 4.0) or (vib > 0.8) or (temp is not None and temp > 75.0):
            health = "critical"
            probs = {"healthy": 0.02, "warning": 0.08, "critical": 0.90}
            conf = 0.90
        elif (curr > 3.0) or (vib > 0.2) or (temp is not None and temp > 50.0):
            health = "warning"
            probs = {"healthy": 0.10, "warning": 0.85, "critical": 0.05}
            conf = 0.85
        else:
            health = "healthy"
            probs = {"healthy": 0.96, "warning": 0.03, "critical": 0.01}
            conf = 0.96

        # 4. Independent Deterministic Safety Evaluation (Never suppressed by ML)
        safety_reasons = []
        c_state = "NORMAL"
        v_state = "NORMAL"
        t_state = "NORMAL"

        if curr > 4.0 or current_peak >= 5.0:
            c_state = "CRITICAL"
            safety_reasons.append("CURRENT_CRITICAL_EXCEEDED")
        elif curr > 3.0:
            c_state = "WARNING"
            safety_reasons.append("CURRENT_WARNING_EXCEEDED")

        if vib > 0.400 or vib_peak >= 0.800:
            v_state = "CRITICAL"
            safety_reasons.append("VIBRATION_CRITICAL_EXCEEDED")
        elif vib > 0.100 or vib_peak >= 0.350:
            v_state = "WARNING"
            safety_reasons.append("VIBRATION_WARNING_EXCEEDED")

        if temp is None:
            t_state = "UNKNOWN"
            safety_reasons.append("TEMPERATURE_SENSOR_DISCONNECTED")
        elif temp > 60.0:
            t_state = "CRITICAL"
            safety_reasons.append("AMBIENT_TEMP_CRITICAL_EXCEEDED")
        elif temp > 50.0:
            t_state = "WARNING"
            safety_reasons.append("AMBIENT_TEMP_WARNING_EXCEEDED")

        if c_state == "CRITICAL" or v_state == "CRITICAL" or t_state == "CRITICAL":
            safety_status = "CRITICAL"
        elif c_state == "WARNING" or v_state == "WARNING" or t_state == "WARNING":
            safety_status = "WARNING"
        elif c_state == "UNKNOWN" or v_state == "UNKNOWN" or t_state == "UNKNOWN":
            safety_status = "UNKNOWN"
        else:
            safety_status = "SAFE"

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        return {
            "schema_version": "1.0.0",
            "event_id": str(uuid.uuid4()),
            "device_id": self.device_id,
            "motor_id": self.motor_id,
            "source": "simulator",
            "seq": self.seq,
            "timestamp": now_iso,
            "sensors": {
                "temperature_c": temp,
                "ambient_temperature_c": temp,
                "case_temperature_c": None,
                "current_a": curr,
                "current_peak_a": current_peak,
                "vibration_g_rms": vib,
                "vibration_g_peak": vib_peak,
            },
            "sensor_status": {
                "temperature": temp_status,
                "current": curr_status,
                "vibration": vib_status,
                "current_calibrated": True,
                "current_zero_offset_v": 2.501,
            },
            "inference": {
                "status": "PREDICTED",
                "health_status": health,
                "confidence": conf,
                "probabilities": probs,
                "model_version": "ei-motoguard-v1.0.1",
                "input_feature_version": "1.0.0-3f",
                "inference_time_ms": random.randint(3, 8),
            },
            "safety": {
                "status": safety_status,
                "current_state": c_state,
                "vibration_state": v_state,
                "temperature_state": t_state,
                "active_reasons": safety_reasons,
                "configuration_version": 1,
                "calibration_status": "provisional",
            },
            "diagnostics": {
                "wifi_rssi_dbm": random.randint(-65, -50),
                "free_heap_bytes": random.randint(170000, 190000),
                "uptime_seconds": int(elapsed),
                "hil_tracking": {
                    "enabled": HIL_TRACKING_ENABLED,
                    "active": hil_active,
                    "seeded_from": seeded_device,
                    "seed_age_sec": round(self.live_baseline.age_seconds(), 1) if (self.live_baseline and hil_active) else None,
                },
            },
        }


def run_simulator():
    logger.info("Initializing MotorGuard Virtual Fleet Simulator...")
    logger.info("HIL Live Baseline Tracking: %s (Source device: %s, Stale timeout: %.1fs)",
                "ENABLED" if HIL_TRACKING_ENABLED else "DISABLED", HIL_SOURCE_DEVICE, HIL_STALE_TIMEOUT_SEC)

    # Initialize shared HIL baseline
    live_baseline = LiveHardwareBaseline(
        target_device_id=HIL_SOURCE_DEVICE,
        timeout_sec=HIL_STALE_TIMEOUT_SEC,
    ) if HIL_TRACKING_ENABLED else None

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"motorguard-simulator-{uuid.uuid4().hex[:6]}",
    )

    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    if MQTT_USE_TLS:
        import ssl
        ssl_ctx = ssl.create_default_context(cafile=MQTT_TLS_CA_CERT)
        ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        if MQTT_TLS_INSECURE:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            client.tls_set_context(ssl_ctx)
            client.tls_insecure_set(True)
        else:
            ssl_ctx.check_hostname = True
            ssl_ctx.verify_mode = ssl.CERT_REQUIRED
            client.tls_set_context(ssl_ctx)
        logger.info("Simulator MQTTS TLS context configured (TLS 1.2+)")

    # MQTT incoming message handler for HIL subscription
    def on_message(client_instance, userdata, message):
        if not live_baseline:
            return
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            if live_baseline.update_from_payload(payload):
                logger.info(
                    "HIL TRACKING [SYNC]: Updated seed from physical %s -> Temp: %s°C, Curr: %sA, Vib: %sg",
                    payload.get("device_id"),
                    payload.get("sensors", {}).get("temperature_c"),
                    payload.get("sensors", {}).get("current_a"),
                    payload.get("sensors", {}).get("vibration_g_rms"),
                )
        except Exception as err:
            logger.debug("HIL telemetry parse error: %s", err)

    client.on_message = on_message

    simulate_hw_twin = os.getenv("SIMULATE_HARDWARE_NODE", "false").lower() in ("true", "1")
    motors = [
        VirtualMotor(motor_id="MTR-775-002", device_id="sim-node-002", profile="warning_temp", live_baseline=live_baseline),
        VirtualMotor(motor_id="MTR-775-003", device_id="sim-node-003", profile="critical_vib", live_baseline=live_baseline),
    ]
    if simulate_hw_twin:
        motors.insert(0, VirtualMotor(motor_id="MTR-775-001", device_id="sim-node-001", profile="healthy", live_baseline=live_baseline))

    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_start()
        logger.info("Connected to MQTT Broker at %s:%d", MQTT_HOST, MQTT_PORT)

        # Subscribe to physical hardware telemetry stream for HIL
        if HIL_TRACKING_ENABLED:
            sub_topic = f"motorguard/v1/{HIL_SOURCE_DEVICE}/telemetry"
            client.subscribe(sub_topic, qos=1)
            logger.info("HIL: Subscribed to live hardware telemetry topic: %s", sub_topic)
    except Exception as e:
        logger.error("Could not connect to MQTT Broker: %s", e)
        sys.exit(1)

    try:
        while True:
            for motor in motors:
                payload = motor.step()
                topic = f"motorguard/v1/{motor.device_id}/telemetry"
                payload_str = json.dumps(payload)
                client.publish(topic, payload_str, qos=1)
                hil_meta = payload["diagnostics"]["hil_tracking"]
                hil_status = f"HIL-ACTIVE({hil_meta['seeded_from']})" if hil_meta["active"] else "SYNTHETIC-FALLBACK"
                logger.info("Published [%s][%s] %s -> %s (Health: %s, Vib: %sg, Temp: %s°C)",
                            motor.profile, hil_status, motor.motor_id, topic,
                            payload["inference"]["health_status"],
                            payload["sensors"]["vibration_g_rms"],
                            payload["sensors"]["temperature_c"])
            time.sleep(PUBLISH_INTERVAL_SEC)
    except KeyboardInterrupt:
        logger.info("Simulator stopped by user.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    run_simulator()
