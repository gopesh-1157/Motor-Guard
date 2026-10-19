"""
MotorGuard — Unit Tests for Hardware-in-the-Loop (HIL) Simulator Tracking
"""

import time
import pytest
from simulator.simulator import LiveHardwareBaseline, VirtualMotor


def test_live_baseline_updates_from_hardware_payload():
    """HIL baseline must ingest valid hardware telemetry and update sensor seeds."""
    baseline = LiveHardwareBaseline(target_device_id="esp32-node-001", timeout_sec=10.0)
    assert not baseline.is_active()

    hw_payload = {
        "source": "hardware",
        "device_id": "esp32-node-001",
        "motor_id": "MTR-775-001",
        "sensors": {
            "temperature_c": 31.4,
            "current_a": 0.22,
            "vibration_g_rms": 0.018,
        },
    }

    updated = baseline.update_from_payload(hw_payload)
    assert updated is True
    assert baseline.is_active() is True
    assert baseline.temp_c == 31.4
    assert baseline.current_a == 0.22
    assert baseline.vibration_g_rms == 0.018
    assert baseline.packets_received == 1


def test_live_baseline_ignores_simulator_source():
    """HIL baseline must ignore virtual or simulator payloads to prevent circular feedback."""
    baseline = LiveHardwareBaseline(target_device_id="esp32-node-001")

    sim_payload = {
        "source": "simulator",
        "device_id": "esp32-node-001",
        "sensors": {"temperature_c": 55.0},
    }
    updated = baseline.update_from_payload(sim_payload)
    assert updated is False
    assert not baseline.is_active()


def test_live_baseline_stale_detection():
    """HIL baseline must detect stale readings after timeout expires."""
    baseline = LiveHardwareBaseline(target_device_id="esp32-node-001", timeout_sec=0.1)

    hw_payload = {
        "source": "hardware",
        "device_id": "esp32-node-001",
        "sensors": {"temperature_c": 28.5},
    }
    baseline.update_from_payload(hw_payload)
    assert baseline.is_active() is True

    # Wait past timeout
    time.sleep(0.15)
    assert baseline.is_active() is False


def test_virtual_motor_hil_seeding():
    """Virtual motor should dynamically couple its baseline to the physical sensor seed."""
    baseline = LiveHardwareBaseline(target_device_id="esp32-node-001", timeout_sec=5.0)

    # 1. Without physical telemetry: runs on synthetic fallback
    motor_warning = VirtualMotor(
        motor_id="MTR-775-002",
        device_id="sim-node-002",
        profile="warning_temp",
        live_baseline=baseline,
    )
    step1 = motor_warning.step()
    assert step1["diagnostics"]["hil_tracking"]["active"] is False
    # Default synthetic warning temperature is ~54°C
    assert 52.0 <= step1["sensors"]["temperature_c"] <= 56.5

    # 2. Feed live physical telemetry (e.g. ambient bench is 25.0°C)
    baseline.update_from_payload({
        "source": "hardware",
        "device_id": "esp32-node-001",
        "sensors": {
            "temperature_c": 25.0,
            "current_a": 0.18,
            "vibration_g_rms": 0.015,
        },
    })

    step2 = motor_warning.step()
    assert step2["diagnostics"]["hil_tracking"]["active"] is True
    assert step2["diagnostics"]["hil_tracking"]["seeded_from"] == "esp32-node-001"
    # Seeded: 25.0 + 22.0 = 47.0°C (coupled to physical reading)
    assert 45.0 <= step2["sensors"]["temperature_c"] <= 49.0


def test_virtual_motor_critical_vib_hil_coupling():
    """Critical vibration motor should float its vibration spike on top of physical noise."""
    baseline = LiveHardwareBaseline(target_device_id="esp32-node-001", timeout_sec=5.0)
    baseline.update_from_payload({
        "source": "hardware",
        "device_id": "esp32-node-001",
        "sensors": {
            "temperature_c": 30.0,
            "current_a": 0.20,
            "vibration_g_rms": 0.035,
        },
    })

    motor_critical = VirtualMotor(
        motor_id="MTR-775-003",
        device_id="sim-node-003",
        profile="critical_vib",
        live_baseline=baseline,
    )
    step = motor_critical.step()
    assert step["diagnostics"]["hil_tracking"]["active"] is True
    assert step["inference"]["health_status"] == "critical"
    # Physical 0.035 + 0.78 = ~0.815g
    assert step["sensors"]["vibration_g_rms"] >= 0.80
