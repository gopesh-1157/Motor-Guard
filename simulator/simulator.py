"""
MotorGuard — Edge Virtual Motor Simulator

Simulates telemetry streams from physical DC motors under healthy,
degrading, and failure operating conditions. Complying strictly with
the v1.0.0 Telemetry Contract Specification.
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


class VirtualMotor:
    def __init__(self, motor_id: str, device_id: str, profile: str = "healthy"):
        self.motor_id = motor_id
        self.device_id = device_id
        self.profile = profile
        self.seq = 0
        self.start_time = time.time()

        # Baselines
        if profile == "healthy":
            self.base_temp = 38.0
            self.base_curr = 2.1
            self.base_vib = 0.08
        elif profile == "warning_temp":
            self.base_temp = 54.0
            self.base_curr = 3.2
            self.base_vib = 0.12
        elif profile == "critical_vib":
            self.base_temp = 42.0
            self.base_curr = 4.3
            self.base_vib = 0.85
        elif profile == "disconnected_temp":
            self.base_temp = None
            self.base_curr = 1.9
            self.base_vib = 0.09
        else:
            self.base_temp = 35.0
            self.base_curr = 1.8
            self.base_vib = 0.05

    def step(self) -> dict:
        self.seq += 1
        elapsed = time.time() - self.start_time

        # Compute sensor values with Gaussian noise and slight harmonic drift
        if self.base_temp is not None:
            temp = round(self.base_temp + math.sin(elapsed / 15.0) * 1.5 + random.uniform(-0.3, 0.3), 1)
            temp_status = "OK"
        else:
            temp = None
            temp_status = "DISCONNECTED"

        curr = round(self.base_curr + math.sin(elapsed / 8.0) * 0.2 + random.uniform(-0.05, 0.05), 2)
        curr = max(0.0, curr)
        curr_status = "OK"

        vib = round(self.base_vib + random.uniform(-0.015, 0.025), 3)
        vib = max(0.005, vib)
        vib_status = "OK"

        # Determine TinyML health prediction
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
                "current_a": curr,
                "vibration_g_rms": vib,
            },
            "sensor_status": {
                "temperature": temp_status,
                "current": curr_status,
                "vibration": vib_status,
            },
            "inference": {
                "status": "PREDICTED",
                "health_status": health,
                "confidence": conf,
                "probabilities": probs,
                "model_version": "ei-motoguard-v1.0.1",
                "inference_time_ms": random.randint(3, 8),
            },
            "diagnostics": {
                "wifi_rssi_dbm": random.randint(-65, -50),
                "free_heap_bytes": random.randint(170000, 190000),
                "uptime_seconds": int(elapsed),
            },
        }


def run_simulator():
    logger.info("Initializing MotorGuard Virtual Fleet Simulator...")
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

    simulate_hw_twin = os.getenv("SIMULATE_HARDWARE_NODE", "false").lower() in ("true", "1")
    motors = [
        VirtualMotor(motor_id="MTR-775-002", device_id="sim-node-002", profile="warning_temp"),
        VirtualMotor(motor_id="MTR-775-003", device_id="sim-node-003", profile="critical_vib"),
    ]
    if simulate_hw_twin:
        motors.insert(0, VirtualMotor(motor_id="MTR-775-001", device_id="sim-node-001", profile="healthy"))

    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_start()
        logger.info("Connected to MQTT Broker at %s:%d", MQTT_HOST, MQTT_PORT)
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
                logger.info("Published [%s] %s -> %s (Health: %s)",
                            motor.profile, motor.motor_id, topic, payload["inference"]["health_status"])
            time.sleep(PUBLISH_INTERVAL_SEC)
    except KeyboardInterrupt:
        logger.info("Simulator stopped by user.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    run_simulator()
