"""
MotorGuard — Canonical Threshold Resolution Service
===================================================

Single authoritative resolver for operational safety thresholds used across:
- Motor health calculations (MotorService)
- Alert evaluation and recovery (AlertService)
- Motor list and detail API responses (MotorOut.effective_thresholds)
- Effective-threshold API endpoint (/api/v1/motors/{motor_id}/effective-thresholds)
- Frontend threshold presentation and client-side limit displays

Precedence Order:
1. Explicit motor asset override (in motor document 'thresholds')
2. Persisted gateway operational settings (in 'system_settings' under 'gateway_operational_limits')
3. Built-in configuration defaults (from backend.app.config.settings)
"""

import logging
from typing import Any, Dict, Optional, Union
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.config import settings

logger = logging.getLogger("motorguard.threshold_resolver")

# Schema-default marker values generated when HealthThresholds() is instantiated without arguments.
# Used to ensure schema defaults do not masquerade as explicit asset-specific overrides.
SCHEMA_DEFAULT_PROVENANCE = "Provisional RS-775 baseline limits (uncalibrated)"
SCHEMA_DEFAULT_CALIBRATION_STATUS = "provisional"


def get_builtin_defaults() -> Dict[str, Any]:
    """Return immutable baseline built-in threshold defaults."""
    overcurrent_limit = float(getattr(settings, "DEFAULT_OVERCURRENT_LIMIT_A", 4.0))
    max_temp = float(getattr(settings, "DEFAULT_MAX_TEMP_C", 50.0))
    max_vib = float(getattr(settings, "DEFAULT_MAX_VIBRATION_G", 0.100))
    max_peak_vib = float(getattr(settings, "DEFAULT_MAX_PEAK_VIBRATION_G", 0.350))

    return {
        "current_warning_a": round(overcurrent_limit * 0.85, 3),
        "current_critical_a": overcurrent_limit,
        "current_hard_limit_a": None,
        "temperature_warning_c": max_temp,
        "temperature_critical_c": 75.0,
        "ambient_temp_warning_c": 45.0,
        "ambient_temp_critical_c": 55.0,
        "casing_temp_warning_c": None,
        "casing_temp_critical_c": None,
        "vibration_warning_g": max_vib,
        "vibration_critical_g": 0.400,
        "peak_vibration_g": max_peak_vib,
        "peak_vibration_critical_g": 0.800,
        "stale_timeout_sec": int(getattr(settings, "DEVICE_STALE_TIMEOUT_SEC", 15)),
        "offline_timeout_sec": int(getattr(settings, "DEVICE_OFFLINE_TIMEOUT_SEC", 35)),
        "startup_grace_period_sec": 0.5,
        "calibration_status": SCHEMA_DEFAULT_CALIBRATION_STATUS,
        "provenance": "builtin_config_default",
    }


def is_explicit_motor_override(m_th: Any, motor_doc: Optional[dict] = None) -> bool:
    """
    Determine if a motor's thresholds dict represents an explicit user/asset override,
    rather than a schema-generated default model.
    """
    if not isinstance(m_th, dict) or not m_th:
        return False

    # Explicit flag set on motor document or thresholds dict
    if m_th.get("has_custom_thresholds") is False:
        return False
    if motor_doc and motor_doc.get("has_custom_thresholds") is False:
        return False
    if m_th.get("has_custom_thresholds") is True:
        return True
    if motor_doc and motor_doc.get("has_custom_thresholds") is True:
        return True

    # If provenance is marked as motor override or custom, it is an explicit override
    prov = m_th.get("provenance")
    if prov and prov not in (SCHEMA_DEFAULT_PROVENANCE, "builtin_config_default"):
        return True

    # If calibration_status is non-provisional, it is an explicit calibrated override
    cal_stat = m_th.get("calibration_status")
    if cal_stat in ("manufacturer_verified", "measured_calibrated", "measured_and_calibrated"):
        return True

    # If provenance matches the exact schema default string, it's a generated default
    if prov == SCHEMA_DEFAULT_PROVENANCE:
        # Check if any numerical values diverge from standard schema defaults
        schema_defaults = {
            "temperature_warning_c": 45.0,
            "temperature_critical_c": 50.0,
            "current_warning_a": 3.0,
            "current_critical_a": 4.0,
            "vibration_warning_g": 0.5,
            "vibration_critical_g": 1.0,
        }
        has_divergence = False
        for k, def_val in schema_defaults.items():
            if k in m_th and m_th[k] is not None:
                try:
                    if abs(float(m_th[k]) - def_val) > 1e-5:
                        has_divergence = True
                        break
                except (ValueError, TypeError):
                    pass
        if not has_divergence:
            return False

    # Otherwise, presence of configured threshold keys is considered an override
    threshold_keys = (
        "current_warning_a", "current_critical_a", "current_hard_limit_a",
        "temperature_warning_c", "temperature_critical_c",
        "ambient_temp_warning_c", "ambient_temp_critical_c",
        "casing_temp_warning_c", "casing_temp_critical_c",
        "vibration_warning_g", "vibration_critical_g",
        "peak_vibration_g", "peak_vibration_critical_g",
    )
    return any(k in m_th and m_th[k] is not None for k in threshold_keys)


def _safe_float(val: Any) -> Optional[float]:
    """Safely convert value to float, preserving 0.0, rejecting invalid strings/NaN."""
    if val is None:
        return None
    if isinstance(val, str) and val.strip() == "":
        return None
    try:
        f = float(val)
        if f != f:  # NaN check
            return None
        return f
    except (ValueError, TypeError):
        return None


class ThresholdResolver:
    """Canonical threshold resolver enforcing precedence and validation."""

    @staticmethod
    def resolve_from_docs(
        system_settings_doc: Optional[dict] = None,
        motor_doc: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Pure synchronous resolver given loaded documents.
        Enforces precedence:
          motor_doc (explicit) > system_settings_doc > builtin defaults.
        """
        effective = get_builtin_defaults()
        sources: Dict[str, str] = {k: "builtin_config_default" for k in effective}

        # 1. Apply Persisted Gateway Settings
        if isinstance(system_settings_doc, dict):
            numeric_fields = [
                "current_warning_a", "current_critical_a", "current_hard_limit_a",
                "temperature_warning_c", "temperature_critical_c",
                "ambient_temp_warning_c", "ambient_temp_critical_c",
                "casing_temp_warning_c", "casing_temp_critical_c",
                "vibration_warning_g", "vibration_critical_g",
                "peak_vibration_g", "peak_vibration_critical_g",
                "stale_timeout_sec", "offline_timeout_sec", "startup_grace_period_sec",
            ]
            gateway_updated = False
            for k in numeric_fields:
                if k in system_settings_doc:
                    val = _safe_float(system_settings_doc[k])
                    if val is not None:
                        if k.endswith("_sec"):
                            effective[k] = int(val) if "timeout" in k else float(val)
                        else:
                            effective[k] = float(val)
                        sources[k] = "gateway_system_settings"
                        gateway_updated = True

            if gateway_updated:
                effective["provenance"] = "gateway_system_settings"

            if "calibration_status" in system_settings_doc and system_settings_doc["calibration_status"]:
                effective["calibration_status"] = str(system_settings_doc["calibration_status"])
                sources["calibration_status"] = "gateway_system_settings"

        # 2. Apply Explicit Motor Asset Overrides
        if isinstance(motor_doc, dict):
            m_th = motor_doc.get("thresholds")
            # Also check legacy top-level threshold fields in seeded motors if 'thresholds' is absent
            if not m_th and any(k in motor_doc for k in ("overcurrent_limit_a", "max_temp_c", "max_vibration_g")):
                m_th = {}
                if "overcurrent_limit_a" in motor_doc:
                    m_th["current_critical_a"] = motor_doc["overcurrent_limit_a"]
                    m_th["current_warning_a"] = float(motor_doc["overcurrent_limit_a"]) * 0.85
                if "max_temp_c" in motor_doc:
                    m_th["temperature_warning_c"] = motor_doc["max_temp_c"]
                if "max_vibration_g" in motor_doc:
                    m_th["vibration_warning_g"] = motor_doc["max_vibration_g"]
                m_th["has_custom_thresholds"] = True

            if is_explicit_motor_override(m_th, motor_doc):
                motor_updated = False
                numeric_fields = [
                    "current_warning_a", "current_critical_a", "current_hard_limit_a",
                    "temperature_warning_c", "temperature_critical_c",
                    "ambient_temp_warning_c", "ambient_temp_critical_c",
                    "casing_temp_warning_c", "casing_temp_critical_c",
                    "vibration_warning_g", "vibration_critical_g",
                    "peak_vibration_g", "peak_vibration_critical_g",
                    "stale_timeout_sec", "offline_timeout_sec", "startup_grace_period_sec",
                ]
                for k in numeric_fields:
                    if k in m_th:
                        val = _safe_float(m_th[k])
                        if val is not None:
                            effective[k] = int(val) if "timeout" in k else float(val)
                            sources[k] = "motor_asset_override"
                            motor_updated = True

                # Support alternative naming conventions
                if "device_offline_timeout_sec" in m_th:
                    val = _safe_float(m_th["device_offline_timeout_sec"])
                    if val is not None:
                        effective["offline_timeout_sec"] = int(val)
                        sources["offline_timeout_sec"] = "motor_asset_override"
                        motor_updated = True

                if "calibration_status" in m_th and m_th["calibration_status"]:
                    effective["calibration_status"] = str(m_th["calibration_status"])
                    sources["calibration_status"] = "motor_asset_override"

                if motor_updated:
                    effective["provenance"] = m_th.get("provenance") or "motor_asset_override"

        # 3. Validation & Sanity Enforcement (warning must be strictly less than critical)
        _validate_relationships(effective)

        # Attach detailed per-field source provenance
        effective["sources"] = sources
        return effective

    @classmethod
    async def resolve(
        cls,
        db: Optional[AsyncIOMotorDatabase],
        motor_or_id: Union[dict, str, None] = None,
    ) -> Dict[str, Any]:
        """
        Asynchronous threshold resolution fetching persisted gateway limits and motor document.
        """
        sys_doc: Optional[dict] = None
        motor_doc: Optional[dict] = None

        if db is not None:
            # 1. Fetch gateway operational limits
            try:
                sys_doc = await db["system_settings"].find_one({"_id": "gateway_operational_limits"})
            except Exception as e:
                logger.debug("Could not fetch gateway operational limits: %s", e)

            # 2. Fetch motor document if motor_or_id is a string
            if isinstance(motor_or_id, str):
                try:
                    motor_doc = await db["motors"].find_one({"motor_id": motor_or_id})
                except Exception as e:
                    logger.debug("Could not fetch motor '%s': %s", motor_or_id, e)
            elif isinstance(motor_or_id, dict):
                motor_doc = motor_or_id
        elif isinstance(motor_or_id, dict):
            motor_doc = motor_or_id

        return cls.resolve_from_docs(system_settings_doc=sys_doc, motor_doc=motor_doc)


def _validate_relationships(th: Dict[str, Any]) -> None:
    """
    Ensure safety invariants: warning must be strictly less than critical.
    If an invalid relation exists, preserve safety by ensuring warning < critical.
    """
    pairs = [
        ("temperature_warning_c", "temperature_critical_c"),
        ("current_warning_a", "current_critical_a"),
        ("vibration_warning_g", "vibration_critical_g"),
        ("peak_vibration_g", "peak_vibration_critical_g"),
        ("ambient_temp_warning_c", "ambient_temp_critical_c"),
        ("casing_temp_warning_c", "casing_temp_critical_c"),
    ]
    for warn_k, crit_k in pairs:
        warn_val = th.get(warn_k)
        crit_val = th.get(crit_k)
        if warn_val is not None and crit_val is not None:
            if warn_val >= crit_val:
                logger.warning(
                    "Invalid threshold relationship: %s (%.2f) >= %s (%.2f). Clamping warning.",
                    warn_k, warn_val, crit_k, crit_val,
                )
                th[warn_k] = round(crit_val * 0.85, 3)
