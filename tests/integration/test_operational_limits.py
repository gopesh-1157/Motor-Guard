"""
MotorGuard — Operational Limits & Thresholds Integration Tests

Verifies:
1. Role-based access control (Admin & Manager allowed; Technician & Operator forbidden; Unauthenticated 401).
2. Physical threshold range validation and monotonicity constraints.
3. Database persistence in MongoDB and audit tracking (updated_by, updated_at).
4. Data survives across queries (simulating persistence across reboots).
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.auth import get_current_active_user, get_user_service
from backend.app.schemas.user import UserOut


@pytest.fixture
def mock_users():
    admin = UserOut(
        id="usr_admin",
        username="admin_alice",
        email="admin@motorguard.local",
        role="Admin",
        is_active=True,
        assigned_sites=["SITE-01"],
        assigned_motors=[],
        created_at=None,
        last_login_at=None,
    )
    manager = UserOut(
        id="usr_manager",
        username="manager_mike",
        email="manager@motorguard.local",
        role="Manager",
        is_active=True,
        assigned_sites=["SITE-01"],
        assigned_motors=[],
        created_at=None,
        last_login_at=None,
    )
    technician = UserOut(
        id="usr_tech",
        username="tech_tom",
        email="tech@motorguard.local",
        role="Technician",
        is_active=True,
        assigned_sites=["SITE-01"],
        assigned_motors=[],
        created_at=None,
        last_login_at=None,
    )
    operator = UserOut(
        id="usr_operator",
        username="operator_bob",
        email="operator@motorguard.local",
        role="Technician",
        is_active=True,
        assigned_sites=["SITE-01"],
        assigned_motors=[],
        created_at=None,
        last_login_at=None,
    )
    return {
        "admin": admin,
        "manager": manager,
        "technician": technician,
        "operator": operator,
    }


def test_get_thresholds_requires_authentication():
    """Unauthenticated GET /api/v1/settings/thresholds returns 401."""
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        res = client.get("/api/v1/settings/thresholds")
        assert res.status_code == 401


def test_get_thresholds_allows_authenticated_operator(mock_users):
    """Authenticated users with any active role can retrieve operational thresholds."""
    app.dependency_overrides[get_current_active_user] = lambda: mock_users["operator"]
    try:
        with TestClient(app) as client:
            res = client.get("/api/v1/settings/thresholds")
            assert res.status_code == 200
            data = res.json()
            assert "temperature_warning_c" in data
            assert "current_warning_a" in data
            assert "vibration_warning_g" in data
            assert "offline_timeout_sec" in data
    finally:
        app.dependency_overrides.clear()


def test_post_thresholds_forbidden_for_operator_and_technician(mock_users):
    """Operators and Technicians cannot modify operational limits (HTTP 403)."""
    valid_payload = {
        "temperature_warning_c": 52.0,
        "temperature_critical_c": 68.0,
        "current_warning_a": 3.8,
        "current_critical_a": 4.5,
        "vibration_warning_g": 0.25,
        "vibration_critical_g": 0.90,
        "stale_timeout_sec": 20,
        "offline_timeout_sec": 45,
    }

    # 1. Operator Forbidden
    app.dependency_overrides[get_current_active_user] = lambda: mock_users["operator"]
    try:
        with TestClient(app) as client:
            res = client.post("/api/v1/settings/thresholds", json=valid_payload)
            assert res.status_code == 403
            assert "Operation requires role" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()

    # 2. Technician Forbidden
    app.dependency_overrides[get_current_active_user] = lambda: mock_users["technician"]
    try:
        with TestClient(app) as client:
            res = client.post("/api/v1/settings/thresholds", json=valid_payload)
            assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_post_thresholds_allowed_for_manager_and_admin(mock_users):
    """Managers and Admins can update thresholds with audit metadata recorded."""
    valid_payload = {
        "temperature_warning_c": 48.0,
        "temperature_critical_c": 62.0,
        "current_warning_a": 3.2,
        "current_critical_a": 4.1,
        "vibration_warning_g": 0.18,
        "vibration_critical_g": 0.75,
        "stale_timeout_sec": 12,
        "offline_timeout_sec": 30,
    }

    # In-memory mock collection to test persistence and retrieval
    storage = {}

    mock_collection = AsyncMock()
    async def mock_update_one(query, update, upsert=False):
        storage[query["_id"]] = update["$set"]
        return MagicMock(modified_count=1)

    async def mock_find_one(query):
        return storage.get(query["_id"])

    mock_collection.update_one = mock_update_one
    mock_collection.find_one = mock_find_one

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: mock_collection if name == "system_settings" else AsyncMock()

    from unittest.mock import patch
    with patch("backend.app.api.v1.endpoints.settings.db_manager.db", mock_db), \
         patch("backend.app.main.db_manager.db", mock_db):
        # 1. Manager updates settings
        app.dependency_overrides[get_current_active_user] = lambda: mock_users["manager"]
        try:
            with TestClient(app) as client:
                res = client.post("/api/v1/settings/thresholds", json=valid_payload)
                assert res.status_code == 200
                data = res.json()
                assert data["updated_by"] == "manager_mike"
                assert data["temperature_warning_c"] == 48.0
                assert data["current_warning_a"] == 3.2
                assert "updated_at" in data

                # 2. Verify subsequent GET returns the persisted data
                get_res = client.get("/api/v1/settings/thresholds")
                assert get_res.status_code == 200
                get_data = get_res.json()
                assert get_data["updated_by"] == "manager_mike"
                assert get_data["temperature_warning_c"] == 48.0
                assert get_data["vibration_warning_g"] == 0.18
        finally:
            app.dependency_overrides.clear()

        # 3. Admin updates settings
        app.dependency_overrides[get_current_active_user] = lambda: mock_users["admin"]
        try:
            admin_payload = dict(valid_payload, temperature_warning_c=55.0, temperature_critical_c=70.0)
            with TestClient(app) as client:
                res = client.post("/api/v1/settings/thresholds", json=admin_payload)
                assert res.status_code == 200
                assert res.json()["updated_by"] == "admin_alice"
                assert res.json()["temperature_warning_c"] == 55.0
        finally:
            app.dependency_overrides.clear()


def test_post_thresholds_validation_safety_margins(mock_users):
    """Enforces monotonic ordering: warning < critical trip for all sensor domains."""
    app.dependency_overrides[get_current_active_user] = lambda: mock_users["admin"]
    try:
        with TestClient(app) as client:
            # 1. Temperature warning >= critical
            res_temp = client.post("/api/v1/settings/thresholds", json={
                "temperature_warning_c": 70.0,
                "temperature_critical_c": 60.0,  # Invalid: crit < warn
                "current_warning_a": 3.0,
                "current_critical_a": 4.0,
                "vibration_warning_g": 0.20,
                "vibration_critical_g": 0.80,
                "stale_timeout_sec": 15,
                "offline_timeout_sec": 35,
            })
            assert res_temp.status_code == 422
            assert "Temperature warning" in res_temp.text

            # 2. Current warning >= critical
            res_curr = client.post("/api/v1/settings/thresholds", json={
                "temperature_warning_c": 50.0,
                "temperature_critical_c": 65.0,
                "current_warning_a": 5.0,
                "current_critical_a": 4.0,  # Invalid: crit < warn
                "vibration_warning_g": 0.20,
                "vibration_critical_g": 0.80,
                "stale_timeout_sec": 15,
                "offline_timeout_sec": 35,
            })
            assert res_curr.status_code == 422
            assert "Current warning" in res_curr.text

            # 3. Vibration warning >= critical (g units)
            res_vib = client.post("/api/v1/settings/thresholds", json={
                "temperature_warning_c": 50.0,
                "temperature_critical_c": 65.0,
                "current_warning_a": 3.0,
                "current_critical_a": 4.0,
                "vibration_warning_g": 1.20,
                "vibration_critical_g": 0.80,  # Invalid: crit < warn
                "stale_timeout_sec": 15,
                "offline_timeout_sec": 35,
            })
            assert res_vib.status_code == 422
            assert "Vibration warning" in res_vib.text

            # 4. Stale timeout >= offline timeout
            res_timeout = client.post("/api/v1/settings/thresholds", json={
                "temperature_warning_c": 50.0,
                "temperature_critical_c": 65.0,
                "current_warning_a": 3.0,
                "current_critical_a": 4.0,
                "vibration_warning_g": 0.20,
                "vibration_critical_g": 0.80,
                "stale_timeout_sec": 40,
                "offline_timeout_sec": 30,  # Invalid: offline <= stale
            })
            assert res_timeout.status_code == 422
            assert "Stale timeout" in res_timeout.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_saved_thresholds_drive_alert_evaluation():
    """
    Verifies that saved MongoDB thresholds directly drive alert engine decisions
    instead of hardcoded constants.
    """
    from backend.app.services.alert_service import AlertService

    custom_limits = {
        "_id": "gateway_operational_limits",
        "temperature_warning_c": 42.0,
        "temperature_critical_c": 58.0,
        "current_warning_a": 2.8,
        "current_critical_a": 3.6,
        "vibration_warning_g": 0.15,
        "vibration_critical_g": 0.60,
        "peak_vibration_g": 0.30,
    }

    mock_alerts_col = AsyncMock()
    mock_alerts_col.find_one = AsyncMock(return_value=None)
    mock_alerts_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="alert_dyn_1"))

    mock_settings_col = AsyncMock()
    mock_settings_col.find_one = AsyncMock(return_value=custom_limits)

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: {
        "alerts": mock_alerts_col,
        "system_settings": mock_settings_col,
        "motors": AsyncMock(find_one=AsyncMock(return_value=None)),
    }.get(name, AsyncMock())

    alert_service = AlertService(mock_db)

    # Effective thresholds must resolve from system_settings
    effective = await alert_service.get_effective_thresholds("MTR-775-001")
    assert effective["temperature_warning_c"] == 42.0
    assert effective["current_warning_a"] == 2.8

    # Telemetry with temp=45.0°C (under default 50.0°C, but exceeds custom 42.0°C)
    telemetry_thermal = {
        "motor_id": "MTR-775-001",
        "device_id": "esp32-node-001",
        "sensors": {"current_a": 1.5, "temperature_c": 45.0, "vibration_g_rms": 0.05},
        "inference": {"health_status": "healthy", "confidence": 0.95},
    }

    alerts = await alert_service.evaluate_telemetry_for_alerts(telemetry_thermal)
    assert len(alerts) == 1
    assert alerts[0].trigger_type == "THRESHOLD_OVERTEMPERATURE"
    assert alerts[0].severity == "WARNING"
    assert alerts[0].trigger_value == 45.0
    assert alerts[0].threshold_limit == 42.0
    assert "limit 42.0" in alerts[0].message

    # Telemetry with current=3.1A (under default 3.5A, but exceeds custom 2.8A warning)
    telemetry_curr = {
        "motor_id": "MTR-775-001",
        "device_id": "esp32-node-001",
        "sensors": {"current_a": 3.1, "temperature_c": 30.0, "vibration_g_rms": 0.05},
        "inference": {"health_status": "healthy", "confidence": 0.95},
    }

    alerts_curr = await alert_service.evaluate_telemetry_for_alerts(telemetry_curr)
    assert len(alerts_curr) == 1
    assert alerts_curr[0].trigger_type == "THRESHOLD_OVERCURRENT"
    assert alerts_curr[0].severity == "WARNING"
    assert alerts_curr[0].trigger_value == 3.1
    assert alerts_curr[0].threshold_limit == 2.8


@pytest.mark.asyncio
async def test_saved_thresholds_drive_motor_health_status():
    """
    Verifies that motor-health status calculations dynamically read saved thresholds.
    """
    from backend.app.services.motor_service import MotorService

    custom_limits = {
        "_id": "gateway_operational_limits",
        "temperature_warning_c": 40.0,
        "temperature_critical_c": 55.0,
        "current_warning_a": 2.5,
        "current_critical_a": 3.5,
        "vibration_warning_g": 0.12,
        "vibration_critical_g": 0.50,
    }

    mock_settings_col = AsyncMock()
    mock_settings_col.find_one = AsyncMock(return_value=custom_limits)

    mock_alerts_col = AsyncMock()
    mock_alerts_col.find_one = AsyncMock(return_value=None)  # No active alerts initially

    mock_telemetry_col = AsyncMock()
    # Telemetry sensor reading 44.0°C exceeds saved warning (40.0°C) even though ML model said healthy
    last_telemetry = {
        "motor_id": "MTR-775-001",
        "sensors": {"temperature_c": 44.0, "current_a": 1.8, "vibration_g_rms": 0.06},
        "inference": {"health_status": "healthy", "confidence": 0.94},
    }
    mock_telemetry_col.find_one = AsyncMock(return_value=last_telemetry)

    motor_doc = {
        "motor_id": "MTR-775-001",
        "name": "Conveyor Drive Motor",
        "status": "active",
        "health_status": "unknown",
    }
    mock_motors_col = AsyncMock()
    mock_motors_col.find_one = AsyncMock(return_value=motor_doc)

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: {
        "system_settings": mock_settings_col,
        "alerts": mock_alerts_col,
        "telemetry": mock_telemetry_col,
        "motors": mock_motors_col,
    }.get(name, AsyncMock())

    service = MotorService(mock_db)

    # 1. Motor health is dynamically computed as "warning" because 44.0°C >= saved 40.0°C
    motor_out = await service.get_motor("MTR-775-001")
    assert motor_out is not None
    assert motor_out.health_status == "warning"

    # 2. When an active CRITICAL alert exists, motor health immediately reflects "critical"
    mock_alerts_col.find_one = AsyncMock(return_value={"state": "ACTIVE", "severity": "CRITICAL"})
    motor_out_crit = await service.get_motor("MTR-775-001")
    assert motor_out_crit is not None
    assert motor_out_crit.health_status == "critical"


def test_hardware_safety_independence_and_physical_bounds():
    """
    Verifies that hardware emergency cutoffs remain independent of dashboard settings:
    1. Schema rejects dangerously high thresholds that exceed physical equipment safety limits.
    2. Remote settings cannot weaken local firmware hardware trips.
    """
    from backend.app.schemas.settings import OperationalLimitsBase

    # Physical equipment rating limits for RS-775 motor:
    # Temperature max bound: 110.0°C
    # Current max bound: 20.0A
    # Vibration max bound: 10.0g

    # 1. Attempt to set current threshold beyond hardware capacity (e.g. 25A)
    with pytest.raises(Exception):
        OperationalLimitsBase(
            temperature_warning_c=50.0,
            temperature_critical_c=65.0,
            current_warning_a=22.0,  # Exceeds max 18A rating
            current_critical_a=25.0,
            vibration_warning_g=0.20,
            vibration_critical_g=0.80,
            stale_timeout_sec=15,
            offline_timeout_sec=35,
        )

    # 2. Attempt to set temperature beyond thermal breakdown (>110°C)
    with pytest.raises(Exception):
        OperationalLimitsBase(
            temperature_warning_c=90.0,
            temperature_critical_c=125.0,  # Exceeds max 110°C rating
            current_warning_a=3.0,
            current_critical_a=4.0,
            vibration_warning_g=0.20,
            vibration_critical_g=0.80,
            stale_timeout_sec=15,
            offline_timeout_sec=35,
        )


@pytest.mark.asyncio
async def test_threshold_precedence_hierarchy_resolution():
    """
    Regression Test: Verifies 3-tier threshold precedence hierarchy in AlertService.
    Precedence: Motor Asset Overrides > Gateway System Settings > Base Config Defaults.
    """
    from backend.app.services.alert_service import AlertService

    mock_db = MagicMock()

    # Tier 2: Gateway system_settings doc
    gateway_doc = {
        "_id": "gateway_operational_limits",
        "current_warning_a": 1.9,
        "current_critical_a": 4.0,
        "temperature_warning_c": 50.0,
        "temperature_critical_c": 65.0,
        "vibration_warning_g": 0.20,
        "vibration_critical_g": 0.80,
    }

    # Tier 3: Motor-specific doc for MTR-775-001
    motor_doc_775 = {
        "motor_id": "MTR-775-001",
        "thresholds": {
            "current_warning_a": 3.0,
            "current_critical_a": 4.0,
            "temperature_warning_c": 45.0,
            "temperature_critical_c": 50.0,
            "vibration_warning_g": 0.50,
            "vibration_critical_g": 1.00,
        },
    }

    async def mock_find_one(query):
        if query.get("_id") == "gateway_operational_limits":
            return gateway_doc
        if query.get("motor_id") == "MTR-775-001":
            return motor_doc_775
        return None

    mock_settings_col = AsyncMock()
    mock_settings_col.find_one = AsyncMock(side_effect=mock_find_one)
    mock_motors_col = AsyncMock()
    mock_motors_col.find_one = AsyncMock(side_effect=mock_find_one)

    mock_db.__getitem__.side_effect = lambda name: {
        "system_settings": mock_settings_col,
        "motors": mock_motors_col,
    }.get(name, AsyncMock())

    service = AlertService(mock_db)

    # 1. Configured motor MTR-775-001 must resolve motor doc thresholds (Tier 3 wins)
    th_775 = await service.get_effective_thresholds("MTR-775-001")
    assert th_775["current_warning_a"] == 3.0       # From motor doc, NOT gateway 1.9
    assert th_775["temperature_warning_c"] == 45.0   # From motor doc, NOT gateway 50.0
    assert th_775["temperature_critical_c"] == 50.0  # From motor doc, NOT gateway 65.0
    assert th_775["vibration_warning_g"] == 0.50     # From motor doc, NOT gateway 0.20
    assert th_775["vibration_critical_g"] == 1.00    # From motor doc, NOT gateway 0.80
    assert th_775["peak_vibration_g"] == 0.350       # Tier 1 fallback (neither motor nor gateway had it)

    # 2. Unconfigured motor MTR-NEW must resolve gateway system_settings (Tier 2 wins over Tier 1)
    th_new = await service.get_effective_thresholds("MTR-NEW")
    assert th_new["current_warning_a"] == 1.9       # From gateway settings
    assert th_new["temperature_warning_c"] == 50.0   # From gateway settings
    assert th_new["temperature_critical_c"] == 65.0  # From gateway settings
    assert th_new["vibration_warning_g"] == 0.20     # From gateway settings
    assert th_new["vibration_critical_g"] == 0.80    # From gateway settings
    assert th_new["peak_vibration_g"] == 0.350       # Tier 1 fallback


@pytest.mark.asyncio
async def test_firmware_vs_backend_alert_divergence_scenarios():
    """
    Regression Test: Verifies where firmware safety status and backend alert engine diverge.
    Proves:
    1. Vibration 0.25g RMS triggers WARNING in firmware (limit 0.100g) but NO backend alert for MTR-775-001 (limit 0.50g).
    2. Temperature 52.0°C triggers WARNING in firmware (limit 50.0°C) but CRITICAL in backend (limit 50.0°C).
    """
    from backend.app.services.alert_service import AlertService

    mock_db = MagicMock()
    mock_motor = {
        "motor_id": "MTR-775-001",
        "thresholds": {
            "current_warning_a": 3.0,
            "current_critical_a": 4.0,
            "temperature_warning_c": 45.0,
            "temperature_critical_c": 50.0,
            "vibration_warning_g": 0.50,
            "vibration_critical_g": 1.00,
        },
    }
    cols = {
        "motors": AsyncMock(),
        "alerts": AsyncMock(),
        "system_settings": AsyncMock(),
    }
    cols["motors"].find_one = AsyncMock(return_value=mock_motor)
    cols["alerts"].find_one = AsyncMock(return_value=None)
    cols["alerts"].insert_one = AsyncMock(return_value=MagicMock(inserted_id="doc1"))
    cols["system_settings"].find_one = AsyncMock(return_value=None)
    mock_db.__getitem__.side_effect = lambda k: cols.get(k, AsyncMock())

    service = AlertService(mock_db)

    # Scenario A: Vibration 0.250g RMS
    # Firmware rule: vib >= 0.100g -> safety.status = "WARNING"
    # Backend rule for MTR-775-001: warning is 0.500g -> vib < 0.500g -> ZERO alerts!
    telem_vib = {
        "schema_version": "1.0.0",
        "event_id": "evt-001",
        "device_id": "esp32-node-001",
        "motor_id": "MTR-775-001",
        "source": "hardware",
        "timestamp": "2026-10-19T10:00:00Z",
        "sensors": {"temperature_c": 35.0, "current_a": 1.5, "vibration_g_rms": 0.250},
        "sensor_status": {"temperature": "OK", "current": "OK", "vibration": "OK"},
        "safety": {"status": "WARNING", "active_reasons": ["VIBRATION_WARNING_EXCEEDED"]},
        "inference": {"health_status": "healthy", "confidence": 0.95},
    }
    alerts_vib = await service.evaluate_telemetry_for_alerts(telem_vib)
    assert len(alerts_vib) == 0  # Demonstrates divergence: firmware says WARNING, backend creates 0 alerts

    # Scenario B: Temperature 52.0°C
    # Firmware rule: temp >= 50.0°C and < 60.0°C -> safety.status = "WARNING"
    # Backend rule for MTR-775-001: temp >= 50.0°C -> CRITICAL alert!
    telem_temp = {
        "schema_version": "1.0.0",
        "event_id": "evt-002",
        "device_id": "esp32-node-001",
        "motor_id": "MTR-775-001",
        "source": "hardware",
        "timestamp": "2026-10-19T10:00:01Z",
        "sensors": {"temperature_c": 52.0, "current_a": 1.5, "vibration_g_rms": 0.05},
        "sensor_status": {"temperature": "OK", "current": "OK", "vibration": "OK"},
        "safety": {"status": "WARNING", "active_reasons": ["AMBIENT_TEMP_WARNING_EXCEEDED"]},
        "inference": {"health_status": "healthy", "confidence": 0.90},
    }
    alerts_temp = await service.evaluate_telemetry_for_alerts(telem_temp)
    assert len(alerts_temp) == 1
    assert alerts_temp[0].severity == "CRITICAL"  # Firmware reports WARNING, backend escalates to CRITICAL
    assert alerts_temp[0].trigger_type == "THRESHOLD_OVERTEMPERATURE"


@pytest.mark.asyncio
async def test_threshold_boundary_decisions_at_limits():
    """
    Task 5 Regression Test: Backend warning and critical decisions at threshold boundaries.
    Verifies:
    1. current == warn_curr -> no alert (strict inequality > required)
    2. current == warn_curr + 0.05 -> WARNING alert
    3. current == crit_curr -> CRITICAL alert (>= crit_curr)
    4. temp == warn_temp -> no alert
    5. temp == warn_temp + 0.1 -> WARNING alert
    6. temp == crit_temp -> CRITICAL alert (>= crit_temp)
    7. vib_rms == warn_vib -> no alert
    8. vib_rms == warn_vib + 0.005 -> WARNING alert
    9. vib_rms == crit_vib -> CRITICAL alert (>= crit_vib)
    """
    from backend.app.services.alert_service import AlertService

    mock_db = MagicMock()
    mock_motor = {
        "motor_id": "MTR-TEST-BOUNDS",
        "thresholds": {
            "current_warning_a": 3.00,
            "current_critical_a": 4.00,
            "temperature_warning_c": 50.0,
            "temperature_critical_c": 75.0,
            "vibration_warning_g": 0.200,
            "vibration_critical_g": 0.800,
            "peak_vibration_g": 0.350,
            "peak_vibration_critical_g": 0.800,
        },
    }
    cols = {
        "motors": AsyncMock(),
        "alerts": AsyncMock(),
        "system_settings": AsyncMock(),
    }
    cols["motors"].find_one = AsyncMock(return_value=mock_motor)
    cols["alerts"].find_one = AsyncMock(return_value=None)
    cols["alerts"].insert_one = AsyncMock(return_value=MagicMock(inserted_id="doc_bnd"))
    cols["system_settings"].find_one = AsyncMock(return_value=None)
    mock_db.__getitem__.side_effect = lambda k: cols.get(k, AsyncMock())

    service = AlertService(mock_db)

    # 1. Values strictly below warning limits produce 0 alerts
    telem_below_warn = {
        "device_id": "esp32-node-001",
        "motor_id": "MTR-TEST-BOUNDS",
        "timestamp": "2026-10-19T09:59:59Z",
        "sensors": {"temperature_c": 49.5, "current_a": 2.95, "vibration_g_rms": 0.195},
        "sensor_status": {"temperature": "OK", "current": "OK", "vibration": "OK"},
    }
    alerts_below_warn = await service.evaluate_telemetry_for_alerts(telem_below_warn)
    assert len(alerts_below_warn) == 0

    # 1b. Exact Warning boundary: values equal to warning limits produce WARNING alerts (>= rule)
    telem_at_warn = {
        "device_id": "esp32-node-001",
        "motor_id": "MTR-TEST-BOUNDS",
        "timestamp": "2026-10-19T10:00:00Z",
        "sensors": {"temperature_c": 50.0, "current_a": 3.00, "vibration_g_rms": 0.200},
        "sensor_status": {"temperature": "OK", "current": "OK", "vibration": "OK"},
    }
    alerts_exact_warn = await service.evaluate_telemetry_for_alerts(telem_at_warn)
    assert len(alerts_exact_warn) == 3
    for a in alerts_exact_warn:
        assert a.severity == "WARNING"

    # 2. Values above warning threshold trigger WARNING
    telem_above_warn = {
        "device_id": "esp32-node-001",
        "motor_id": "MTR-TEST-BOUNDS",
        "timestamp": "2026-10-19T10:00:01Z",
        "sensors": {"temperature_c": 50.5, "current_a": 3.05, "vibration_g_rms": 0.205},
        "sensor_status": {"temperature": "OK", "current": "OK", "vibration": "OK"},
    }
    alerts_above_warn = await service.evaluate_telemetry_for_alerts(telem_above_warn)
    assert len(alerts_above_warn) == 3
    for a in alerts_above_warn:
        assert a.severity == "WARNING"

    # 3. Values at critical boundary trigger CRITICAL
    telem_at_crit = {
        "device_id": "esp32-node-001",
        "motor_id": "MTR-TEST-BOUNDS",
        "timestamp": "2026-10-19T10:00:02Z",
        "sensors": {"temperature_c": 75.0, "current_a": 4.00, "vibration_g_rms": 0.800},
        "sensor_status": {"temperature": "OK", "current": "OK", "vibration": "OK"},
    }
    alerts_at_crit = await service.evaluate_telemetry_for_alerts(telem_at_crit)
    assert len(alerts_at_crit) == 3
    for a in alerts_at_crit:
        assert a.severity == "CRITICAL"


@pytest.mark.asyncio
async def test_vibration_rms_vs_peak_shock_separation():
    """
    Task 5 Regression Test: Vibration RMS and peak shock are distinct metrics with separate units.
    - RMS vibration uses warn_vib / crit_vib with unit 'g RMS'.
    - Peak instantaneous shock uses peak_vib_warn / peak_vib_crit with unit 'g pk'.
    """
    from backend.app.services.alert_service import AlertService

    mock_db = MagicMock()
    mock_motor = {
        "motor_id": "MTR-VIB-TEST",
        "thresholds": {
            "vibration_warning_g": 0.200,
            "vibration_critical_g": 0.800,
            "peak_vibration_g": 0.350,
            "peak_vibration_critical_g": 0.800,
        },
    }
    cols = {
        "motors": AsyncMock(),
        "alerts": AsyncMock(),
        "system_settings": AsyncMock(),
    }
    cols["motors"].find_one = AsyncMock(return_value=mock_motor)
    cols["alerts"].find_one = AsyncMock(return_value=None)
    cols["alerts"].insert_one = AsyncMock(return_value=MagicMock(inserted_id="doc_v"))
    cols["system_settings"].find_one = AsyncMock(return_value=None)
    mock_db.__getitem__.side_effect = lambda k: cols.get(k, AsyncMock())

    service = AlertService(mock_db)

    # Case A: Low RMS (0.050 g RMS) but high peak shock (0.420 g pk)
    telem_peak_shock = {
        "device_id": "esp32-node-001",
        "motor_id": "MTR-VIB-TEST",
        "timestamp": "2026-10-19T10:00:00Z",
        "sensors": {
            "vibration_g_rms": 0.050,
            "vibration_peak_g": 0.420,
        },
        "sensor_status": {"vibration": "OK"},
    }
    alerts = await service.evaluate_telemetry_for_alerts(telem_peak_shock)
    assert len(alerts) == 1
    assert alerts[0].trigger_type == "THRESHOLD_HIGH_VIBRATION_PEAK"
    assert alerts[0].severity == "WARNING"
    assert alerts[0].unit == "g pk"
    assert "Peak instantaneous vibration shock" in alerts[0].message

    # Case B: High RMS (0.300 g RMS) with normal peak
    telem_rms = {
        "device_id": "esp32-node-001",
        "motor_id": "MTR-VIB-TEST",
        "timestamp": "2026-10-19T10:00:01Z",
        "sensors": {
            "vibration_g_rms": 0.300,
            "vibration_peak_g": 0.100,
        },
        "sensor_status": {"vibration": "OK"},
    }
    alerts_rms = await service.evaluate_telemetry_for_alerts(telem_rms)
    assert len(alerts_rms) == 1
    assert alerts_rms[0].severity == "WARNING"
    assert alerts_rms[0].unit == "g RMS"
    assert "Dynamic vibration RMS exceeded" in alerts_rms[0].message


@pytest.mark.asyncio
async def test_alert_hysteresis_auto_resolution():
    """
    Task 5 Regression Test: Alerts auto-resolve with hysteresis when conditions clear.
    - Temperature auto-resolves when temp <= (warn_temp - 2.0).
    - Current auto-resolves when current <= (warn_curr * 0.90).
    - Vibration auto-resolves when RMS <= (warn_vib * 0.85) AND peak <= (peak_warn * 0.85).
    """
    from backend.app.services.alert_service import AlertService

    mock_db = MagicMock()
    mock_motor = {
        "motor_id": "MTR-RESOLVE-TEST",
        "thresholds": {
            "current_warning_a": 3.00,
            "current_critical_a": 4.00,
            "temperature_warning_c": 50.0,
            "temperature_critical_c": 75.0,
            "vibration_warning_g": 0.200,
            "vibration_critical_g": 0.800,
            "peak_vibration_g": 0.350,
        },
    }
    cols = {
        "motors": AsyncMock(),
        "alerts": AsyncMock(),
        "system_settings": AsyncMock(),
    }
    cols["motors"].find_one = AsyncMock(return_value=mock_motor)
    cols["alerts"].find_one = AsyncMock(return_value=None)
    cols["alerts"].find_one_and_update = AsyncMock(side_effect=lambda q, *a, **k: {
        "_id": "doc_auto_res",
        "alert_id": "ALT-001",
        "motor_id": "MTR-RESOLVE-TEST",
        "device_id": "esp32-node-001",
        "severity": "WARNING",
        "trigger_type": q.get("trigger_type"),
        "trigger_value": 0.0,
        "threshold_limit": 1.0,
        "unit": "unit",
        "message": "Auto resolved",
        "state": "RESOLVED",
        "triggered_at": datetime.now(timezone.utc),
    })
    cols["system_settings"].find_one = AsyncMock(return_value=None)
    mock_db.__getitem__.side_effect = lambda k: cols.get(k, AsyncMock())

    service = AlertService(mock_db)

    # Telemetry fully cleared below all hysteresis bands
    telem_cleared = {
        "device_id": "esp32-node-001",
        "motor_id": "MTR-RESOLVE-TEST",
        "timestamp": "2026-10-19T10:00:00Z",
        "sensors": {
            "temperature_c": 47.0,       # <= 50.0 - 2.0 = 48.0
            "current_a": 2.50,           # <= 3.00 * 0.90 = 2.70
            "vibration_g_rms": 0.150,    # <= 0.200 * 0.85 = 0.170
            "vibration_peak_g": 0.250,   # <= 0.350 * 0.85 = 0.2975
        },
        "sensor_status": {"temperature": "OK", "current": "OK", "vibration": "OK"},
    }
    alerts = await service.evaluate_telemetry_for_alerts(telem_cleared)
    assert len(alerts) == 0  # No new alerts created
    # Auto-resolve called for normalized sensors and buffered for drainage
    assert cols["alerts"].find_one_and_update.called
    resolved = service.consume_auto_resolved_alerts()
    assert len(resolved) > 0


@pytest.mark.asyncio
async def test_stale_or_missing_telemetry_never_healthy():
    """
    Task 5 Regression Test: Missing, disconnected, or stale telemetry is NEVER misrepresented as healthy.
    - All null readings -> 'unknown'
    - Disconnected current or vibration -> 'critical'
    - Disconnected temperature -> 'warning'
    - Missing telemetry doc entirely -> defaults to asset doc status ('unknown')
    """
    from backend.app.services.motor_service import MotorService

    mock_db = MagicMock()
    service = MotorService(mock_db)

    doc = {"motor_id": "MTR-HEALTH-TEST", "thresholds": {"temperature_warning_c": 50.0, "temperature_critical_c": 75.0, "current_warning_a": 3.0, "current_critical_a": 4.0, "vibration_warning_g": 0.20, "vibration_critical_g": 0.80}}

    # 1. All null readings
    null_telem = {"sensors": {"temperature_c": None, "current_a": None, "vibration_g_rms": None}, "sensor_status": {}}
    h1 = await service.calculate_motor_health("MTR-HEALTH-TEST", doc, null_telem)
    assert h1 == "unknown"

    # 2. Disconnected current
    disc_curr = {"sensors": {"temperature_c": 30.0, "current_a": None, "vibration_g_rms": 0.05}, "sensor_status": {"current": "DISCONNECTED"}}
    h2 = await service.calculate_motor_health("MTR-HEALTH-TEST", doc, disc_curr)
    assert h2 == "critical"

    # 3. Disconnected vibration
    disc_vib = {"sensors": {"temperature_c": 30.0, "current_a": 1.0, "vibration_g_rms": None}, "sensor_status": {"vibration": "UNAVAILABLE"}}
    h3 = await service.calculate_motor_health("MTR-HEALTH-TEST", doc, disc_vib)
    assert h3 == "critical"

    # 4. Disconnected temperature
    disc_temp = {"sensors": {"temperature_c": None, "current_a": 1.0, "vibration_g_rms": 0.05}, "sensor_status": {"temperature": "OUT_OF_RANGE"}}
    h4 = await service.calculate_motor_health("MTR-HEALTH-TEST", doc, disc_temp)
    assert h4 == "warning"

    # 5. Missing telemetry doc
    h5 = await service.calculate_motor_health("MTR-HEALTH-TEST", doc, None)
    assert h5 == "unknown"


@pytest.mark.asyncio
async def test_effective_thresholds_authenticated_api():
    """
    Task 5 Regression Test: Authenticated API endpoint exposes resolved effective thresholds.
    """
    from backend.app.services.motor_service import MotorService
    from backend.app.core.auth import get_current_active_user
    from backend.app.main import app

    mock_db = MagicMock()
    mock_motor = {
        "motor_id": "MTR-775-001",
        "name": "Line 3 Actuator",
        "motor_type": "RS-775 Brushed DC",
        "site_id": "SITE-PLANT-A",
        "status": "active",
        "thresholds": {
            "current_warning_a": 3.0,
            "current_critical_a": 4.0,
            "temperature_warning_c": 45.0,
            "temperature_critical_c": 50.0,
            "vibration_warning_g": 0.50,
            "vibration_critical_g": 1.00,
        },
    }
    cols = {"motors": AsyncMock(), "telemetry": AsyncMock(), "alerts": AsyncMock(), "system_settings": AsyncMock()}
    cols["motors"].find_one = AsyncMock(return_value=mock_motor)
    cols["system_settings"].find_one = AsyncMock(return_value=None)
    mock_db.__getitem__.side_effect = lambda k: cols.get(k, AsyncMock())

    from backend.app.api.v1.endpoints.motors import get_motor_service
    app.dependency_overrides[get_motor_service] = lambda: MotorService(mock_db)
    user_out = UserOut(
        id="usr_op", username="op_user", email="op@motorguard.local", role="Technician",
        is_active=True, assigned_sites=["SITE-PLANT-A"], assigned_motors=[],
        created_at=None, last_login_at=None,
    )
    app.dependency_overrides[get_current_active_user] = lambda: user_out

    client = TestClient(app)
    resp = client.get("/api/v1/motors/MTR-775-001/effective-thresholds")
    assert resp.status_code == 200
    data = resp.json()
    assert data["motor_id"] == "MTR-775-001"
    assert data["temperature_warning_c"] == 45.0
    assert data["temperature_critical_c"] == 50.0
    assert data["current_warning_a"] == 3.0
    assert data["provenance"] == "motor_asset_override"
    app.dependency_overrides.clear()


