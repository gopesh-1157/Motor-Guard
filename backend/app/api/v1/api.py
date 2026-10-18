from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    health,
    telemetry,
    auth,
    alerts,
    maintenance,
    work_orders,
    motors,
    devices,
    simulator,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(work_orders.router, prefix="/work-orders", tags=["work-orders"])
api_router.include_router(maintenance.router, prefix="/maintenance", tags=["maintenance"])
api_router.include_router(motors.router, prefix="/motors", tags=["motors"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(simulator.router, prefix="/simulator", tags=["simulator"])


