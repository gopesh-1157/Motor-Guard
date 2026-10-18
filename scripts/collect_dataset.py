#!/usr/bin/env python3
"""
MotorGuard — High-Speed ESP32 Serial Dataset Collection Tool

Features:
- Captures 800 Hz sampled vibration and electrical telemetry from ESP32.
- Interactive keyboard controls to change ground-truth labels and increment Run ID.
- Automatically records operating conditions (supply voltage, ambient temperature, motor variant).
- Saves raw runs to CSV in 'data/raw_runs/' with complete run-level metadata.

Usage:
    python scripts/collect_dataset.py --port COM3 --baud 115200 --voltage 12.0 --ambient 25.0
"""

import os
import sys
import time
import argparse
from datetime import datetime

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Error: 'pyserial' is required. Install with: pip install pyserial")
    sys.exit(1)


def find_default_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if "CP210" in p.description or "CH340" in p.description or "USB" in p.description:
            return p.device
    return ports[0].device if ports else "COM3"


def main():
    parser = argparse.ArgumentParser(description="MotorGuard ESP32 Dataset Collection Tool")
    parser.add_argument("--port", default=None, help="Serial port (e.g. COM3 or /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--voltage", type=float, default=12.0, help="Bench supply voltage (V)")
    parser.add_argument("--ambient", type=float, default=25.0, help="Ambient temperature (°C)")
    parser.add_argument("--motor", default="RS-775", help="Motor variant under test")
    parser.add_argument("--outdir", default="data/raw_runs", help="Output directory for raw runs")
    args = parser.parse_args()

    port = args.port or find_default_port()
    os.makedirs(args.outdir, exist_ok=True)

    print("=" * 70)
    print("  MOTORGUARD RAW SENSOR DATASET COLLECTOR (RUN-ISOLATED)")
    print(f"  Target Port:        {port} @ {args.baud} baud")
    print(f"  Operating Supply:   {args.voltage} VDC")
    print(f"  Ambient Temp:       {args.ambient} °C")
    print(f"  Motor Variant:      {args.motor}")
    print(f"  Output Directory:   {args.outdir}")
    print("=" * 70)
    print("  Interactive Key Controls (send via console or hardware):")
    print("    'h' -> Label Healthy")
    print("    'o' -> Label Overload (High Mechanical Torque / Friction)")
    print("    'i' -> Label Imbalance (Eccentric Rotor Mass / Weight)")
    print("    'l' -> Label Loose Mount (Chassis Resonant Vibration)")
    print("    'n' -> Start NEW Run ID (Increments run_id)")
    print("    'c' -> Re-zero ACS712 zero offset (motor must be off)")
    print("    'q' -> Quit session")
    print("=" * 70)

    try:
        ser = serial.Serial(port, args.baud, timeout=1.0)
        time.sleep(1.5)  # Allow ESP32 reboot / DTR settling
    except Exception as e:
        print(f"Failed to open serial port {port}: {e}")
        sys.exit(1)

    session_start_iso = datetime.now().strftime("%Y%m%d_%H%M%S")
    master_csv_path = os.path.join(args.outdir, f"session_{session_start_iso}.csv")

    header = (
        "timestamp_ms,run_id,label,temp_c,current_a,vib_x_rms,vib_y_rms,vib_z_rms,"
        "vib_rms_g,vib_peak_g,crest_factor,supply_voltage_v,ambient_temp_c,motor_variant\n"
    )

    with open(master_csv_path, "w", encoding="utf-8") as f_out:
        f_out.write(header)

    print(f"\n[RECORDING] Streaming telemetry to: {master_csv_path}")
    print("Press Ctrl+C to stop recording.\n")

    total_rows = 0
    current_run = 1
    current_label = "h"

    try:
        while True:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            # Skip comments and header echoes
            if line.startswith("#") or line.startswith("=") or "timestamp_ms" in line:
                print(f"[ESP32] {line}")
                continue

            # Expected 11 columns from firmware:
            # millis,run_id,label,temp_c,current_a,vib_x_rms,vib_y_rms,vib_z_rms,vib_rms_g,vib_peak_g,crest_factor
            parts = line.split(",")
            if len(parts) >= 11:
                try:
                    ts_ms = int(parts[0])
                    run_id = int(parts[1])
                    label_char = parts[2].strip()
                    temp_val = float(parts[3])
                    curr_val = float(parts[4])
                    vib_rms = float(parts[8])

                    current_run = run_id
                    current_label = label_char

                    # Append operational conditions
                    full_line = f"{line},{args.voltage},{args.ambient},{args.motor}\n"
                    with open(master_csv_path, "a", encoding="utf-8") as f_out:
                        f_out.write(full_line)

                    total_rows += 1
                    if total_rows % 20 == 0:
                        lbl_name = {
                            "h": "HEALTHY",
                            "o": "OVERLOAD",
                            "i": "IMBALANCE",
                            "l": "LOOSE_MOUNT",
                        }.get(label_char, label_char)
                        sys.stdout.write(
                            f"\r[RUN #{run_id:02d} | {lbl_name:12s}] Rows: {total_rows:6d} | "
                            f"I: {curr_val:5.2f}A | Vib: {vib_rms:5.3f}g | Temp: {temp_val:4.1f}°C"
                        )
                        sys.stdout.flush()

                except ValueError:
                    continue

    except KeyboardInterrupt:
        print("\n\n[STOPPED] Session recording finalized.")
    finally:
        ser.close()
        print(f"Total valid samples captured: {total_rows}")
        print(f"Master file saved to: {master_csv_path}")
        print("Run 'python scripts/split_dataset.py' to perform run-based train/test splits.")


if __name__ == "__main__":
    main()
