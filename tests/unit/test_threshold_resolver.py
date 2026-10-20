"""
MotorGuard — Unit Tests for Canonical ThresholdResolver
========================================================

Verifies:
- 3-tier Precedence: explicit motor override > gateway system settings > builtin defaults
- Partial overrides: selective overriding preserves non-overridden tiers
- Explicit zero values: 0.0 / 0 preserved and not treated as missing/falsy
- Missing & null settings: safe fallback to next tier
- Malformed inputs: invalid strings, NaN safely fall back to defaults
- Schema-default distinction: uncalibrated schema defaults do not masquerade as overrides
- Invariant validation: warning < critical enforced
- Consistency: MotorService and AlertService produce identical resolved thresholds
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.app.services.threshold_service import (
    ThresholdResolver,
    get_builtin_defaults,
    SCHEMA_DEFAULT_PROVENANCE,
)
from backend.app.services.alert_service import AlertService
from backend.app.services.motor_service import MotorService


def test_builtin_defaults_structure():
    """Verify built-in defaults contain all required keys and valid relationships."""
    defaults = get_builtin_defaults()
    assert defaults["current_warning_a"] < defaults["current_critical_a"]
    assert defaults["temperature_warning_c"] < defaults["temperature_critical_c"]
    assert defaults["vibration_warning_g"] < defaults["vibration_critical_g"]
    assert defaults["peak_vibration_g"] < defaults["peak_vibration_critical_g"]
    assert defaults["provenance"] == "builtin_config_default"


def test_precedence_hierarchy_resolution():
    """Verify explicit motor overrides > gateway system settings > builtin defaults."""
    gateway_doc = {
        "_id": "gateway_operational_limits",
        "current_warning_a": 2.5,
        "temperature_warning_c": 55.0,
        "vibration_warning_g": 0.20,
    }

    motor_doc = {
        "motor_id": "MTR-001",
        "thresholds": {
            "current_warning_a": 3.2,
            "has_custom_thresholds": True,
        },
    }

    resolved = ThresholdResolver.resolve_from_docs(
        system_settings_doc=gateway_doc,
        motor_doc=motor_doc,
    )

    # Motor override wins for current_warning_a
    assert resolved["current_warning_a"] == 3.2
    assert resolved["sources"]["current_warning_a"] == "motor_asset_override"

    # Gateway setting wins for temperature_warning_c and vibration_warning_g
    assert resolved["temperature_warning_c"] == 55.0
    assert resolved["sources"]["temperature_warning_c"] == "gateway_system_settings"
    assert resolved["vibration_warning_g"] == 0.20
    assert resolved["sources"]["vibration_warning_g"] == "gateway_system_settings"

    # Builtin default wins for current_critical_a (4.0)
    assert resolved["current_critical_a"] == 4.0
    assert resolved["sources"]["current_critical_a"] == "builtin_config_default"


def test_partial_overrides_provenance():
    """Verify partial overrides only override specified fields."""
    gateway_doc = {
        "_id": "gateway_operational_limits",
        "temperature_warning_c": 52.0,
    }
    motor_doc = {
        "motor_id": "MTR-PARTIAL",
        "thresholds": {
            "vibration_warning_g": 0.180,
            "provenance": "Engineer calibrated baseline",
        },
    }

    resolved = ThresholdResolver.resolve_from_docs(
        system_settings_doc=gateway_doc,
        motor_doc=motor_doc,
    )

    assert resolved["vibration_warning_g"] == 0.180
    assert resolved["sources"]["vibration_warning_g"] == "motor_asset_override"
    assert resolved["temperature_warning_c"] == 52.0
    assert resolved["sources"]["temperature_warning_c"] == "gateway_system_settings"
    assert resolved["provenance"] == "Engineer calibrated baseline"


def test_explicit_zero_values_preserved():
    """Verify explicitly configured zero values are not dropped via falsiness checks."""
    gateway_doc = {
        "_id": "gateway_operational_limits",
        "startup_grace_period_sec": 0,
    }
    motor_doc = {
        "motor_id": "MTR-ZERO",
        "thresholds": {
            "startup_grace_period_sec": 0.0,
            "has_custom_thresholds": True,
        },
    }

    resolved = ThresholdResolver.resolve_from_docs(
        system_settings_doc=gateway_doc,
        motor_doc=motor_doc,
    )

    assert resolved["startup_grace_period_sec"] == 0.0
    assert resolved["sources"]["startup_grace_period_sec"] == "motor_asset_override"


def test_missing_and_null_settings_handled_safely():
    """Verify None or omitted keys fallback gracefully without exception."""
    gateway_doc = {
        "_id": "gateway_operational_limits",
        "current_warning_a": None,
        "temperature_warning_c": None,
    }
    motor_doc = {
        "motor_id": "MTR-NULLS",
        "thresholds": {
            "current_warning_a": None,
            "vibration_warning_g": None,
        },
    }

    resolved = ThresholdResolver.resolve_from_docs(
        system_settings_doc=gateway_doc,
        motor_doc=motor_doc,
    )

    # Should safely retain builtin defaults
    builtin = get_builtin_defaults()
    assert resolved["current_warning_a"] == builtin["current_warning_a"]
    assert resolved["temperature_warning_c"] == builtin["temperature_warning_c"]
    assert resolved["vibration_warning_g"] == builtin["vibration_warning_g"]


def test_malformed_settings_handled_safely():
    """Verify invalid strings, empty strings, and NaN are rejected safely."""
    gateway_doc = {
        "_id": "gateway_operational_limits",
        "current_warning_a": "not_a_number",
        "temperature_warning_c": "",
        "vibration_warning_g": float("nan"),
    }

    resolved = ThresholdResolver.resolve_from_docs(
        system_settings_doc=gateway_doc,
        motor_doc=None,
    )

    builtin = get_builtin_defaults()
    assert resolved["current_warning_a"] == builtin["current_warning_a"]
    assert resolved["temperature_warning_c"] == builtin["temperature_warning_c"]
    assert resolved["vibration_warning_g"] == builtin["vibration_warning_g"]


def test_schema_default_does_not_masquerade_as_override():
    """
    Ensure schema-generated default models do NOT override gateway operational settings.
    If motor document has uncalibrated schema-defaults, gateway settings must win.
    """
    gateway_doc = {
        "_id": "gateway_operational_limits",
        "current_warning_a": 2.2,
        "temperature_warning_c": 48.0,
        "vibration_warning_g": 0.150,
    }

    # Generated schema default model
    motor_doc_schema_default = {
        "motor_id": "MTR-DEFAULT",
        "thresholds": {
            "current_warning_a": 3.0,
            "current_critical_a": 4.0,
            "temperature_warning_c": 45.0,
            "temperature_critical_c": 50.0,
            "vibration_warning_g": 0.5,
            "vibration_critical_g": 1.0,
            "calibration_status": "provisional",
            "provenance": SCHEMA_DEFAULT_PROVENANCE,
        },
    }

    resolved = ThresholdResolver.resolve_from_docs(
        system_settings_doc=gateway_doc,
        motor_doc=motor_doc_schema_default,
    )

    # Gateway settings must win because motor thresholds are merely schema defaults
    assert resolved["current_warning_a"] == 2.2
    assert resolved["temperature_warning_c"] == 48.0
    assert resolved["vibration_warning_g"] == 0.150
    assert resolved["sources"]["current_warning_a"] == "gateway_system_settings"


def test_warning_critical_invariant_enforcement():
    """Verify warning < critical invariant is clamped safely if an invalid override is supplied."""
    motor_doc = {
        "motor_id": "MTR-INVALID-RELATION",
        "thresholds": {
            "temperature_warning_c": 80.0,
            "temperature_critical_c": 75.0,  # Warning > Critical!
            "has_custom_thresholds": True,
        },
    }

    resolved = ThresholdResolver.resolve_from_docs(motor_doc=motor_doc)
    assert resolved["temperature_critical_c"] == 75.0
    assert resolved["temperature_warning_c"] < 75.0
    assert resolved["temperature_warning_c"] == round(75.0 * 0.85, 3)


@pytest.mark.asyncio
async def test_consistent_resolution_across_health_alerts_and_api():
    """Verify MotorService and AlertService produce identical resolved threshold values."""
    mock_db = MagicMock()
    gateway_doc = {
        "_id": "gateway_operational_limits",
        "current_warning_a": 2.8,
        "current_critical_a": 3.9,
        "temperature_warning_c": 49.0,
        "temperature_critical_c": 68.0,
        "vibration_warning_g": 0.120,
        "vibration_critical_g": 0.450,
    }
    motor_doc = {
        "motor_id": "MTR-CONSISTENCY",
        "thresholds": {
            "temperature_warning_c": 51.0,
            "provenance": "Custom asset tuning",
        },
    }

    async def mock_find_one(query):
        if query.get("_id") == "gateway_operational_limits":
            return gateway_doc
        if query.get("motor_id") == "MTR-CONSISTENCY":
            return motor_doc
        return None

    mock_settings_col = AsyncMock()
    mock_settings_col.find_one = AsyncMock(side_effect=mock_find_one)
    mock_motors_col = AsyncMock()
    mock_motors_col.find_one = AsyncMock(side_effect=mock_find_one)

    mock_db.__getitem__.side_effect = lambda name: {
        "system_settings": mock_settings_col,
        "motors": mock_motors_col,
    }.get(name, AsyncMock())

    alert_svc = AlertService(mock_db)
    motor_svc = MotorService(mock_db)

    alert_th = await alert_svc.get_effective_thresholds("MTR-CONSISTENCY")
    motor_th = await motor_svc.get_effective_thresholds(motor_doc)

    assert alert_th["current_warning_a"] == motor_th["current_warning_a"] == 2.8
    assert alert_th["temperature_warning_c"] == motor_th["temperature_warning_c"] == 51.0
    assert alert_th["vibration_warning_g"] == motor_th["vibration_warning_g"] == 0.120
    assert alert_th["provenance"] == motor_th["provenance"] == "Custom asset tuning"
