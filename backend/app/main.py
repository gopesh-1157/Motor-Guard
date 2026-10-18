import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request

from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.api.v1.api import api_router
from backend.app.db.mongodb import db_manager
from backend.app.mqtt.subscriber import mqtt_subscriber
from backend.app.services.telemetry_ingestion import TelemetryIngestionService
from backend.app.services.user_service import UserService
from backend.app.services.alert_service import AlertService
from backend.app.services.maintenance_service import MaintenanceService
from backend.app.services.motor_service import MotorService
from backend.app.services.device_service import DeviceService
from backend.app.api.v1.endpoints.websocket import ws_manager

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("motorguard.app")


# Module-level references
ingestion_service: TelemetryIngestionService | None = None
alert_service: AlertService | None = None
device_service: DeviceService | None = None
motor_service: MotorService | None = None


async def _ingest_and_broadcast(payload: dict) -> bool:
    """Ingest telemetry into MongoDB, evaluate safety rules, and broadcast."""
    global ingestion_service, alert_service, device_service
    if ingestion_service is None:
        return False

    # Validate device registry and motor assignment
    if device_service is not None:
        device_id = payload.get("device_id")
        motor_id = payload.get("motor_id")
        if device_id and motor_id:
            authorized = await device_service.record_heartbeat_or_telemetry(device_id, motor_id)
            if not authorized:
                logger.warning(
                    "Dropping telemetry from mismatched/unauthorized assignment: device=%s motor=%s",
                    device_id, motor_id,
                )
                return False

    inserted = await ingestion_service.ingest(payload)
    if inserted:
        # Broadcast telemetry to live dashboard
        await ws_manager.broadcast({"type": "telemetry", "data": payload})

        # Evaluate rules engine thresholds for automatic alerts
        if alert_service is not None:
            try:
                alerts = await alert_service.evaluate_telemetry_for_alerts(payload)
                for alert in alerts:
                    await ws_manager.broadcast({
                        "type": "alert",
                        "data": alert.model_dump(mode="json"),
                    })
            except Exception as e:
                logger.error("Error evaluating alert rules: %s", e)

    return inserted


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ingestion_service, alert_service, device_service, motor_service

    # Startup tasks
    logger.info("Initializing %s (version: %s)...", settings.APP_NAME, settings.APP_VERSION)

    # 1. Connect MongoDB
    await db_manager.connect_to_database()

    # 2. Initialize database services and ensure indexes
    if db_manager.db is not None:
        ingestion_service = TelemetryIngestionService(db_manager.db)
        await ingestion_service.ensure_indexes()

        user_service = UserService(db_manager.db)
        await user_service.ensure_indexes()
        await user_service.seed_default_admin()

        alert_service = AlertService(db_manager.db)
        await alert_service.ensure_indexes()

        maintenance_service = MaintenanceService(db_manager.db)
        await maintenance_service.ensure_indexes()

        from backend.app.services.work_order_service import WorkOrderService
        work_order_service = WorkOrderService(db_manager.db)
        await work_order_service.ensure_indexes()

        device_service = DeviceService(db_manager.db)
        await device_service.ensure_indexes()
        await device_service.seed_default_devices()

        motor_service = MotorService(db_manager.db)
        await motor_service.ensure_indexes()
        await motor_service.seed_default_motors()

        logger.info("MongoDB collections, motor registry, and safety services ready")

        # 3. Wire MQTT subscriber -> ingestion + broadcast pipeline
        mqtt_subscriber.set_telemetry_callback(_ingest_and_broadcast)

    # 4. Start MQTT subscriber
    loop = asyncio.get_event_loop()
    await mqtt_subscriber.start(loop=loop)

    # 5. Background ESP32 SoftAP auto-bridge (polls http://192.168.4.1/api/telemetry)
    async def _poll_esp32_ap_loop():
        import httpx
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                while True:
                    try:
                        res = await client.get("http://192.168.4.1/api/telemetry")
                        if res.status_code == 200:
                            data = res.json()
                            await _ingest_and_broadcast(data)
                    except Exception:
                        pass
                    await asyncio.sleep(1.2)
        except asyncio.CancelledError:
            pass

    poller_task = asyncio.create_task(_poll_esp32_ap_loop())

    yield

    # Shutdown tasks
    logger.info("Shutting down %s...", settings.APP_NAME)
    poller_task.cancel()
    await mqtt_subscriber.stop()
    await db_manager.close_database_connection()
    ingestion_service = None
    alert_service = None
    device_service = None
    motor_service = None


from backend.app.core.middleware import SecurityHeadersMiddleware, RateLimitMiddleware
from starlette.responses import JSONResponse

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="MotorGuard Local-First Edge Gateway Ingestion, Monitoring, and REST API.",
    lifespan=lifespan,
    debug=settings.DEBUG,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
)

# 1. CORS middleware with explicit whitelist, methods, and headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["Content-Disposition"],
    max_age=600,
)

# 2. Rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# 3. Security headers middleware (CSP, X-Frame-Options, XSS, nosniff)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Prevent internal server tracebacks from leaking to API clients in production."""
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    if settings.ENVIRONMENT == "production":
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Please contact the administrator."},
        )
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


# Include API v1 router
app.include_router(api_router, prefix="/api/v1")


from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Production static frontend bundle paths
DIST_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
ASSETS_DIR = DIST_DIR / "assets"

if ASSETS_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="production_assets")

if DIST_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=str(DIST_DIR), html=True), name="production_dashboard")


@app.get("/")
async def root(request: Request):
    """Serve production dashboard SPA to web browsers; return JSON service discovery to API clients."""
    accept = request.headers.get("accept", "")
    index_file = DIST_DIR / "index.html"
    if "text/html" in accept and index_file.is_file():
        return FileResponse(str(index_file))
    res = {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "health": "/api/v1/health/live",
        "dashboard": "/app/",
    }
    if settings.ENABLE_DOCS:
        res["docs"] = "/docs"
    return res



@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    """WebSocket endpoint for live telemetry streaming to dashboard clients."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; client can send pings/messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
