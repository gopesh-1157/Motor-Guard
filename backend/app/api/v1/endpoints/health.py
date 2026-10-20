import logging
from fastapi import APIRouter, Response, status
from backend.app.config import settings
from backend.app.schemas.health import LiveHealthResponse, ReadyHealthResponse, DependencyHealth
from backend.app.db.mongodb import db_manager
from backend.app.mqtt.subscriber import mqtt_subscriber

logger = logging.getLogger("motorguard.health")
router = APIRouter()


@router.get("/live", response_model=LiveHealthResponse, summary="Liveness Probe")
async def get_live():
    """Liveness probe indicates if the gateway API process is active and running."""
    return LiveHealthResponse(status="ok", version=settings.APP_VERSION)


@router.get("/ready", response_model=ReadyHealthResponse, summary="Readiness Probe")
async def get_ready(response: Response, strict: bool = False):
    """
    Readiness probe evaluates connectivity to downstream dependencies (MongoDB, MQTT broker).
    Returns HTTP 200 when ready, or HTTP 503 if critical dependencies are unreachable in strict mode.
    """
    dependencies = {}
    all_healthy = True

    # Check MongoDB
    mongo_healthy, latency, err = await db_manager.ping()
    if mongo_healthy:
        dependencies["mongodb"] = DependencyHealth(
            status="healthy",
            details={"latency_ms": latency, "database": settings.MONGO_DB_NAME},
        )
    else:
        dependencies["mongodb"] = DependencyHealth(
            status="unavailable",
            details={"latency_ms": latency, "error": err or "Connection refused"},
        )
        all_healthy = False

    # Check MQTT broker connection status
    mqtt_stats = mqtt_subscriber.stats
    if mqtt_stats["connected"]:
        dependencies["mqtt_broker"] = DependencyHealth(
            status="healthy",
            details={
                "host": settings.MQTT_BROKER_HOST,
                "port": settings.MQTT_BROKER_PORT,
                "messages_processed": mqtt_stats["messages_processed"],
                "validation_errors": mqtt_stats["validation_errors"],
            },
        )
    else:
        dependencies["mqtt_broker"] = DependencyHealth(
            status="unavailable",
            details={
                "host": settings.MQTT_BROKER_HOST,
                "port": settings.MQTT_BROKER_PORT,
                "note": "MQTT subscriber not connected to broker",
            },
        )
        all_healthy = False

    if all_healthy:
        overall_status = "ok"
    else:
        overall_status = "degraded" if not strict and settings.ENVIRONMENT in ("development", "test") else "unavailable"
        if strict or overall_status == "unavailable":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadyHealthResponse(
        status=overall_status,
        version=settings.APP_VERSION,
        dependencies=dependencies,
    )
