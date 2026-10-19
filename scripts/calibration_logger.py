"""
MotorGuard — Calibration Logger & Safe Bench Measurement Protocol
==================================================================

Collects empirical baseline measurements from physical ESP32 + RS-775 DC motor test setups,
recording synchronized sensor outputs, calibration states, manual reference equipment readings,
and calculated measurement errors to a persistent CSV file.

MANDATORY SAFETY AND BENCH TEST PROTOCOL:
-----------------------------------------
1. Equipment Ratings:
   - Motor: RS-775 12V DC brushed permanent-magnet motor.
   - Power Supply: Regulated 12V DC bench supply with current-limiting (recommended 5A trip limit).
   - Sensor: ACS712-20A (100 mV/A nominal sensitivity, 20k/10k voltage divider to ESP32 ADC pin).
   - In-Line Verification: Connect a calibrated Digital Multimeter (DMM) in 10A DC series mode
     between supply (+) and motor (+) terminal to verify true current.
   - Temperature Reference: If motor casing temperature is evaluated, attach a Type-K thermocouple
     or contact thermal probe to the motor rear bearing housing. Do not rely on DHT11 (measures ambient air only).

2. Safe Operating Measurement Steps (Never short or deliberately stall the motor):
   - Step A (Baseline Resting): Power ESP32 with motor de-energized.
     Verify zero-point ADC pin voltage sits within 1.667 V ± 0.20 V.
     Verify firmware logs: "[ACS712] Zero calibration SUCCESS".
   - Step B (No-Load Free Spin): Energize motor at 12V with no shaft load.
     Record steady-state armature current (typical 0.35 A – 0.60 A).
     Record dynamic vibration baseline (typical 0.03 g – 0.08 g RMS).
   - Step C (Moderate Safe Load): Apply light mechanical drag using an approved dyno/brake or fan blade.
     Record current up to rated limit (approx. 2.0 A – 2.5 A).
     Observe dynamic vibration and ambient air temperature rise.
   - DANGEROUS OVERLOAD / STALL: DO NOT deliberately stall the motor or exceed power supply ratings.
     Use recorded synthetic test fixtures or controlled electrical resistance loads for overcurrent validation.

3. Zero-Fabrication Rule:
   - External reference measurement fields (reference_current_a, reference_case_temp_c) are NEVER
     populated with synthetic estimates. If reference instruments are not connected, leave as empty string.
"""

import os
import sys
import time
import json
import csv
import math
import argparse
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

try:
    import httpx
except ImportError:
    httpx = None

CSV_HEADERS = [
    "run_id",
    "timestamp_iso",
    "device_id",
    "motor_id",
    "source",
    "seq",
    "operating_phase",
    "supply_voltage_v",
    "reference_current_a",
    "current_a",
    "current_peak_a",
    "error_abs_current_a",
    "error_pct_current",
    "current_zero_offset_v",
    "current_calibrated",
    "reference_case_temp_c",
    "ambient_temperature_c",
    "error_abs_temp_c",
    "vibration_g_rms",
    "vibration_g_peak",
    "ml_health_status",
    "ml_confidence",
    "ml_model_version",
    "safety_status",
    "safety_reasons",
    "config_version",
    "calibration_status",
]


class CalibrationLogger:
    def __init__(
        self,
        output_csv_path: str,
        run_id: str,
        operating_phase: str = "no_load",
        supply_voltage_v: float = 12.0,
        ref_current_a: Optional[float] = None,
        ref_case_temp_c: Optional[float] = None,
    ):
        self.output_csv_path = output_csv_path
        self.run_id = run_id
        self.operating_phase = operating_phase
        self.supply_voltage_v = supply_voltage_v
        self.ref_current_a = ref_current_a
        self.ref_case_temp_c = ref_case_temp_c
        self.records_logged = 0

        # Ensure directory and initialize CSV with headers if not present
        os.makedirs(os.path.dirname(os.path.abspath(output_csv_path)), exist_ok=True)
        file_exists = os.path.exists(output_csv_path)
        with open(output_csv_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists or os.path.getsize(output_csv_path) == 0:
                writer.writerow(CSV_HEADERS)

    def log_telemetry_packet(self, payload: Dict[str, Any]) -> None:
        """Parse incoming validated telemetry, calculate errors vs reference, and append to CSV."""
        sensors = payload.get("sensors", {})
        sensor_status = payload.get("sensor_status", {})
        inference = payload.get("inference", {})
        safety = payload.get("safety", {})

        current_a = sensors.get("current_a")
        temp_c = sensors.get("ambient_temperature_c") if sensors.get("ambient_temperature_c") is not None else sensors.get("temperature_c")

        # Calculate error metrics against external reference equipment if provided
        err_abs_curr = ""
        err_pct_curr = ""
        if current_a is not None and self.ref_current_a is not None:
            try:
                curr_val = float(current_a)
                ref_curr = float(self.ref_current_a)
                err_abs = abs(curr_val - ref_curr)
                err_abs_curr = f"{err_abs:.4f}"
                if ref_curr > 0.05:  # mathematically meaningful threshold
                    err_pct = (err_abs / ref_curr) * 100.0
                    err_pct_curr = f"{err_pct:.2f}%"
            except (ValueError, TypeError):
                pass

        err_abs_temp = ""
        if temp_c is not None and self.ref_case_temp_c is not None:
            try:
                err_temp = abs(float(temp_c) - float(self.ref_case_temp_c))
                err_abs_temp = f"{err_temp:.2f}"
            except (ValueError, TypeError):
                pass

        row = [
            self.run_id,
            payload.get("timestamp", datetime.now(timezone.utc).isoformat() + "Z"),
            payload.get("device_id", ""),
            payload.get("motor_id", ""),
            payload.get("source", "hardware"),
            payload.get("seq", 0),
            self.operating_phase,
            self.supply_voltage_v,
            self.ref_current_a if self.ref_current_a is not None else "",
            sensors.get("current_a", ""),
            sensors.get("current_peak_a", ""),
            err_abs_curr,
            err_pct_curr,
            sensor_status.get("current_zero_offset_v", ""),
            sensor_status.get("current_calibrated", ""),
            self.ref_case_temp_c if self.ref_case_temp_c is not None else "",
            temp_c if temp_c is not None else "",
            err_abs_temp,
            sensors.get("vibration_g_rms", ""),
            sensors.get("vibration_g_peak", ""),
            inference.get("health_status", ""),
            inference.get("confidence", ""),
            inference.get("model_version", ""),
            safety.get("status", ""),
            ";".join(safety.get("active_reasons", [])),
            safety.get("configuration_version", ""),
            safety.get("calibration_status", ""),
        ]

        with open(self.output_csv_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)

        self.records_logged += 1
        print(
            f"[{self.records_logged:04d}] Logged: I={sensors.get('current_a')}A (Ref: {self.ref_current_a or '-'}) "
            f"| Vib={sensors.get('vibration_g_rms')}g | T={temp_c}C "
            f"| Safety={safety.get('status')} | AI={inference.get('health_status')}"
        )


def analyze_csv(csv_path: str, report_json_path: Optional[str] = None) -> Dict[str, Any]:
    """Read a calibration run CSV and compute statistical metrics, error analysis, and baseline distributions."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    rows: List[Dict[str, str]] = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    total_records = len(rows)
    if total_records == 0:
        return {"total_records": 0, "status": "EMPTY"}

    currents: List[float] = []
    ref_currents: List[float] = []
    curr_errors_abs: List[float] = []
    curr_errors_pct: List[float] = []
    vibrations_rms: List[float] = []
    vibrations_peak: List[float] = []
    temperatures: List[float] = []
    zero_offsets: List[float] = []

    for r in rows:
        try:
            c = float(r.get("current_a", ""))
            currents.append(c)
        except (ValueError, TypeError):
            pass

        try:
            rc = float(r.get("reference_current_a", ""))
            ref_currents.append(rc)
            if currents:
                err_abs = abs(currents[-1] - rc)
                curr_errors_abs.append(err_abs)
                if rc > 0.05:
                    curr_errors_pct.append((err_abs / rc) * 100.0)
        except (ValueError, TypeError):
            pass

        try:
            v = float(r.get("vibration_g_rms", ""))
            vibrations_rms.append(v)
        except (ValueError, TypeError):
            pass

        try:
            vp = float(r.get("vibration_g_peak", ""))
            vibrations_peak.append(vp)
        except (ValueError, TypeError):
            pass

        try:
            t = float(r.get("ambient_temperature_c", ""))
            temperatures.append(t)
        except (ValueError, TypeError):
            pass

        try:
            zo = float(r.get("current_zero_offset_v", ""))
            zero_offsets.append(zo)
        except (ValueError, TypeError):
            pass

    def calc_stats(vals: List[float]) -> Dict[str, float]:
        if not vals:
            return {"count": 0, "mean": 0.0, "min": 0.0, "max": 0.0, "std": 0.0}
        n = len(vals)
        mean_v = sum(vals) / n
        var = sum((x - mean_v) ** 2 for x in vals) / (n if n > 1 else 1)
        return {
            "count": n,
            "mean": round(mean_v, 4),
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
            "std": round(math.sqrt(var), 4),
        }

    analysis: Dict[str, Any] = {
        "csv_path": csv_path,
        "total_records": total_records,
        "zero_offset_v": calc_stats(zero_offsets),
        "measured_current_a": calc_stats(currents),
        "reference_current_a": calc_stats(ref_currents),
        "current_error_abs_a": calc_stats(curr_errors_abs),
        "current_error_pct": calc_stats(curr_errors_pct),
        "vibration_rms_g": calc_stats(vibrations_rms),
        "vibration_peak_g": calc_stats(vibrations_peak),
        "temperature_c": calc_stats(temperatures),
    }

    if vibrations_rms and vibrations_peak:
        mean_rms = sum(vibrations_rms) / len(vibrations_rms)
        mean_peak = sum(vibrations_peak) / len(vibrations_peak)
        analysis["crest_factor_mean"] = round(mean_peak / mean_rms, 2) if mean_rms > 0.001 else 1.0

    print("\n=======================================================")
    print("  MOTORGUARD CALIBRATION RUN ANALYSIS REPORT          ")
    print("=======================================================")
    print(f"  Source CSV:             {csv_path}")
    print(f"  Total Valid Records:    {total_records}")
    if zero_offsets:
        zo_st = analysis["zero_offset_v"]
        print(f"  Zero Offset Voltage:    Mean = {zo_st['mean']:.3f} V | Spread = {zo_st['max'] - zo_st['min']:.3f} V (Std: {zo_st['std']:.4f})")
    if currents:
        c_st = analysis["measured_current_a"]
        print(f"  Measured Current:       Mean = {c_st['mean']:.3f} A | Min = {c_st['min']:.3f} A | Max = {c_st['max']:.3f} A")
    if curr_errors_abs:
        ea_st = analysis["current_error_abs_a"]
        ep_st = analysis["current_error_pct"]
        print(f"  Current Accuracy Error: MAE = {ea_st['mean']:.4f} A | Max = {ea_st['max']:.4f} A | Mean % Error = {ep_st['mean']:.2f}%")
    if vibrations_rms:
        v_st = analysis["vibration_rms_g"]
        vp_st = analysis["vibration_peak_g"]
        print(f"  Dynamic Vibration:      Mean RMS = {v_st['mean']:.4f} g | Max RMS = {v_st['max']:.4f} g | Mean Peak = {vp_st['mean']:.4f} g")
    if temperatures:
        t_st = analysis["temperature_c"]
        print(f"  Ambient Temperature:    Mean = {t_st['mean']:.1f} °C | Min = {t_st['min']:.1f} °C | Max = {t_st['max']:.1f} °C")
    print("=======================================================\n")

    if report_json_path:
        os.makedirs(os.path.dirname(os.path.abspath(report_json_path)), exist_ok=True)
        with open(report_json_path, mode="w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2)
        print(f"Saved analysis JSON report to: {report_json_path}")

    return analysis


def main():
    parser = argparse.ArgumentParser(description="MotorGuard Calibration Logger CLI")
    parser.add_argument("--output", default="data/calibration_runs.csv", help="Destination CSV file path")
    parser.add_argument("--run-id", default=f"RUN-{int(time.time())}", help="Unique run identifier")
    parser.add_argument("--phase", default="no_load", choices=["resting", "no_load", "moderate_load", "transient_startup"], help="Test operating phase")
    parser.add_argument("--supply-v", type=float, default=12.0, help="Bench power supply rail voltage")
    parser.add_argument("--ref-current", type=float, default=None, help="External reference DMM current in Amps (optional)")
    parser.add_argument("--ref-case-temp", type=float, default=None, help="External reference contact thermocouple temp in °C (optional)")
    parser.add_argument("--mode", default="mqtt", choices=["mqtt", "http_poll"], help="Ingestion transport mode")
    parser.add_argument("--mqtt-host", default="127.0.0.1", help="MQTT broker host")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--http-url", default="http://192.168.4.1/api/telemetry", help="ESP32 SoftAP telemetry URL")
    parser.add_argument("--max-records", type=int, default=100, help="Number of samples to collect before stopping")
    parser.add_argument("--analyze", type=str, default=None, help="Path to CSV file to analyze offline")
    parser.add_argument("--report", type=str, default=None, help="Path to output JSON analysis report")

    args = parser.parse_args()

    if args.analyze:
        analyze_csv(args.analyze, args.report)
        return

    logger = CalibrationLogger(
        output_csv_path=args.output,
        run_id=args.run_id,
        operating_phase=args.phase,
        supply_voltage_v=args.supply_v,
        ref_current_a=args.ref_current,
        ref_case_temp_c=args.ref_case_temp,
    )

    print("\n=======================================================")
    print("  MOTORGUARD CALIBRATION & BENCH LOGGER ACTIVE        ")
    print("=======================================================")
    print(f"  Run ID:           {args.run_id}")
    print(f"  Operating Phase:  {args.phase}")
    print(f"  Supply Voltage:   {args.supply_v:.1f} V")
    print(f"  Ref Current:      {args.ref_current if args.ref_current is not None else 'UNCONFIGURED (None)'}")
    print(f"  Ref Casing Temp:  {args.ref_case_temp if args.ref_case_temp is not None else 'UNCONFIGURED (None)'}")
    print(f"  Output CSV:       {args.output}")
    print(f"  Max Records:      {args.max_records}")
    print("=======================================================\n")

    if args.mode == "http_poll":
        if not httpx:
            print("ERROR: httpx is required for http_poll mode. Run: pip install httpx")
            sys.exit(1)
        print(f"Polling SoftAP REST API at {args.http_url} every 1.5 seconds...")
        client = httpx.Client(timeout=2.0)
        while logger.records_logged < args.max_records:
            try:
                res = client.get(args.http_url)
                if res.status_code == 200:
                    payload = res.json()
                    logger.log_telemetry_packet(payload)
            except Exception as e:
                print(f"[HTTP POLL] Connection retry: {e}")
            time.sleep(1.5)
        print(f"\nCompleted collecting {logger.records_logged} records to {args.output}")

    else:
        if not mqtt:
            print("ERROR: paho-mqtt is required for mqtt mode. Run: pip install paho-mqtt")
            sys.exit(1)

        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                print(f"[MQTT] Connected to {args.mqtt_host}:{args.mqtt_port}. Subscribing to telemetry...")
                client.subscribe("motorguard/v1/+/telemetry", qos=1)
                client.subscribe("motorguard/+/telemetry", qos=1)
            else:
                print(f"[MQTT] Connection failed with code {rc}")

        def on_message(client, userdata, msg):
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
                logger.log_telemetry_packet(payload)
                if logger.records_logged >= args.max_records:
                    print(f"\nReached target of {args.max_records} records. Disconnecting...")
                    client.disconnect()
            except Exception as e:
                print(f"[MQTT] Error parsing payload: {e}")

        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = on_connect
        client.on_message = on_message

        try:
            client.connect(args.mqtt_host, args.mqtt_port, 60)
            client.loop_forever()
        except KeyboardInterrupt:
            print("\nCollection stopped by user.")
        except Exception as e:
            print(f"[MQTT] Error: {e}")


if __name__ == "__main__":
    main()
