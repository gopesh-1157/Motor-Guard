"""
MotorGuard — Telemetry REST Endpoints

Provides query endpoints for retrieving persisted telemetry data from MongoDB.
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from backend.app.db.mongodb import db_manager
from backend.app.schemas.telemetry import TelemetryMessage

logger = logging.getLogger("motorguard.api.telemetry")
router = APIRouter()


@router.post("/ingest", summary="Direct Telemetry Ingestion")
async def ingest_telemetry_event(message: TelemetryMessage):
    """Direct HTTP ingestion endpoint for ESP32 AP mode or HTTP bridges."""
    from backend.app.main import _ingest_and_broadcast
    inserted = await _ingest_and_broadcast(message.model_dump())
    return {"success": inserted, "event_id": message.event_id}


@router.get("/recent", summary="Get Recent Telemetry")
async def get_recent_telemetry(
    motor_id: Optional[str] = Query(None, description="Filter by motor_id"),
    device_id: Optional[str] = Query(None, description="Filter by device_id"),
    limit: int = Query(20, ge=1, le=200, description="Number of records to return"),
):
    """Retrieve the most recent telemetry events, optionally filtered by motor or device."""
    if db_manager.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    collection = db_manager.db["telemetry"]
    query_filter = {}
    if motor_id:
        query_filter["motor_id"] = motor_id
    if device_id:
        query_filter["device_id"] = device_id

    cursor = collection.find(
        query_filter,
        {"_id": 0},  # Exclude MongoDB ObjectId from JSON response
    ).sort("server_received_at", -1).limit(limit)

    results = await cursor.to_list(length=limit)

    # Convert datetime objects to ISO strings for JSON serialization
    for doc in results:
        if "server_received_at" in doc and hasattr(doc["server_received_at"], "isoformat"):
            doc["server_received_at"] = doc["server_received_at"].isoformat() + "Z"

    return {"count": len(results), "telemetry": results}


@router.get("/historical", summary="Query Historical Telemetry")
async def get_historical_telemetry(
    motor_id: Optional[str] = Query(None, description="Filter by motor_id"),
    device_id: Optional[str] = Query(None, description="Filter by device_id"),
    source: Optional[str] = Query(None, description="Filter by source (hardware/simulator)"),
    start_time: Optional[str] = Query(None, description="ISO-8601 start timestamp"),
    end_time: Optional[str] = Query(None, description="ISO-8601 end timestamp"),
    limit: int = Query(500, ge=1, le=2000, description="Max points to return"),
):
    """Query historical telemetry with timestamp range and source filtering."""
    if db_manager.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    collection = db_manager.db["telemetry"]
    query_filter: dict = {}
    if motor_id:
        query_filter["motor_id"] = motor_id
    if device_id:
        query_filter["device_id"] = device_id
    if source:
        query_filter["source"] = source

    if start_time or end_time:
        time_filter: dict = {}
        if start_time:
            time_filter["$gte"] = start_time
        if end_time:
            time_filter["$lte"] = end_time
        query_filter["timestamp"] = time_filter

    cursor = collection.find(query_filter, {"_id": 0}).sort("timestamp", 1).limit(limit)
    results = await cursor.to_list(length=limit)

    for doc in results:
        if "server_received_at" in doc and hasattr(doc["server_received_at"], "isoformat"):
            doc["server_received_at"] = doc["server_received_at"].isoformat() + "Z"

    return {"count": len(results), "telemetry": results}


@router.get("/aggregates", summary="Get Motor Telemetry Aggregates")
async def get_motor_aggregates(
    motor_id: str = Query(..., description="Target motor_id"),
    source: Optional[str] = Query(None, description="Filter by source"),
):
    """Calculate statistical aggregates (min, max, mean) and health distribution for a motor."""
    if db_manager.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    collection = db_manager.db["telemetry"]
    match_stage: dict = {"motor_id": motor_id}
    if source:
        match_stage["source"] = source

    pipeline = [
        {"$match": match_stage},
        {
            "$group": {
                "_id": None,
                "count": {"$sum": 1},
                "avg_temp": {"$avg": "$sensors.temperature_c"},
                "min_temp": {"$min": "$sensors.temperature_c"},
                "max_temp": {"$max": "$sensors.temperature_c"},
                "avg_current": {"$avg": "$sensors.current_a"},
                "min_current": {"$min": "$sensors.current_a"},
                "max_current": {"$max": "$sensors.current_a"},
                "avg_vibration": {"$avg": "$sensors.vibration_g_rms"},
                "min_vibration": {"$min": "$sensors.vibration_g_rms"},
                "max_vibration": {"$max": "$sensors.vibration_g_rms"},
            }
        },
    ]

    agg_result = await collection.aggregate(pipeline).to_list(length=1)
    stats = agg_result[0] if agg_result else {
        "count": 0,
        "avg_temp": None, "min_temp": None, "max_temp": None,
        "avg_current": None, "min_current": None, "max_current": None,
        "avg_vibration": None, "min_vibration": None, "max_vibration": None,
    }
    stats.pop("_id", None)

    # Health distribution count
    health_pipeline = [
        {"$match": match_stage},
        {"$group": {"_id": "$inference.health_status", "count": {"$sum": 1}}},
    ]
    health_results = await collection.aggregate(health_pipeline).to_list(length=10)
    health_dist = {h["_id"]: h["count"] for h in health_results if h.get("_id")}

    return {
        "motor_id": motor_id,
        "statistics": stats,
        "health_distribution": health_dist,
    }


@router.get("/export", summary="Export Telemetry Dataset")
async def export_telemetry(
    motor_id: Optional[str] = Query(None, description="Filter by motor_id"),
    source: Optional[str] = Query(None, description="Filter by source"),
    export_format: str = Query("csv", pattern="^(csv|json)$", description="Format: csv or json"),
    limit: int = Query(5000, ge=1, le=10000, description="Max records to export"),
):
    """Export industrial telemetry records as CSV or JSON with full engineering metadata."""
    from fastapi.responses import Response
    import io
    import csv

    if db_manager.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    collection = db_manager.db["telemetry"]
    query_filter: dict = {}
    if motor_id:
        query_filter["motor_id"] = motor_id
    if source:
        query_filter["source"] = source

    cursor = collection.find(query_filter, {"_id": 0}).sort("timestamp", -1).limit(limit)
    records = await cursor.to_list(length=limit)

    for doc in records:
        if "server_received_at" in doc and hasattr(doc["server_received_at"], "isoformat"):
            doc["server_received_at"] = doc["server_received_at"].isoformat() + "Z"

    now_slug = records[0]["timestamp"].replace(":", "-").replace(".", "-") if records else "empty"
    filename_base = f"motorguard_telemetry_{motor_id or 'fleet'}_{now_slug}"

    if export_format == "json":
        import json
        return Response(
            content=json.dumps(records, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.json"'},
        )

    # Generate CSV with complete engineering columns
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Timestamp_UTC",
        "Motor_ID",
        "Device_ID",
        "Source",
        "Sequence",
        "Temperature_C",
        "Current_A",
        "Vibration_g_RMS",
        "Power_W",
        "Health_Status",
        "Model_Confidence",
        "Model_Version",
        "WiFi_RSSI_dBm",
        "Free_Heap_Bytes",
        "Uptime_Sec",
    ])

    for r in records:
        sensors = r.get("sensors") or {}
        inference = r.get("inference") or {}
        diag = r.get("diagnostics") or {}
        curr = sensors.get("current_a")
        # Approximate 12V DC power if current is measured
        power_w = round(12.0 * curr, 2) if curr is not None else None

        writer.writerow([
            r.get("timestamp", ""),
            r.get("motor_id", ""),
            r.get("device_id", ""),
            r.get("source", ""),
            r.get("seq", ""),
            sensors.get("temperature_c", ""),
            curr if curr is not None else "",
            sensors.get("vibration_g_rms", ""),
            power_w if power_w is not None else "",
            inference.get("health_status", ""),
            inference.get("confidence", ""),
            inference.get("model_version", ""),
            diag.get("wifi_rssi_dbm", ""),
            diag.get("free_heap_bytes", ""),
            diag.get("uptime_seconds", ""),
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename_base}.csv"'},
    )


@router.get("/stats", summary="Get Ingestion Statistics")
async def get_ingestion_stats():
    """Return aggregate telemetry ingestion statistics."""
    if db_manager.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    collection = db_manager.db["telemetry"]
    total_count = await collection.count_documents({})
    hardware_count = await collection.count_documents({"source": "hardware"})
    simulator_count = await collection.count_documents({"source": "simulator"})

    return {
        "total_events": total_count,
        "hardware_events": hardware_count,
        "simulator_events": simulator_count,
    }
