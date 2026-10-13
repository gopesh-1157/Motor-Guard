"""
MotorGuard — MQTT Subscriber Client

Asynchronous MQTT subscriber using paho-mqtt v2 with a background thread.
Subscribes to motorguard/v1/+/telemetry, validates incoming payloads against
the TelemetryMessage Pydantic schema, and persists valid events via the
TelemetryIngestionService.
"""

import asyncio
import json
import logging
from typing import Optional, Callable, Awaitable, Any

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from backend.app.config import settings
from backend.app.schemas.telemetry import TelemetryMessage

logger = logging.getLogger("motorguard.mqtt")

# Topic pattern for telemetry subscription
TELEMETRY_TOPIC = "motorguard/v1/+/telemetry"
STATUS_TOPIC = "motorguard/v1/+/status"
HEARTBEAT_TOPIC = "motorguard/v1/+/heartbeat"


class MQTTSubscriber:
    """
    Manages the MQTT client lifecycle: connect, subscribe, receive, validate.
    Calls an async callback for each validated telemetry payload.
    """

    def __init__(self):
        self._client: Optional[mqtt.Client] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._on_telemetry_callback: Optional[Callable[[dict], Awaitable[Any]]] = None
        self._connected = False
        self._message_count = 0
        self._error_count = 0
        self._duplicate_count = 0

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def stats(self) -> dict:
        return {
            "connected": self._connected,
            "messages_processed": self._message_count,
            "validation_errors": self._error_count,
        }

    def set_telemetry_callback(self, callback: Callable[[dict], Awaitable[Any]]) -> None:
        """Register an async function to call with each validated telemetry dict."""
        self._on_telemetry_callback = callback

    async def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Initialize and connect the MQTT client."""
        self._loop = loop or asyncio.get_event_loop()

        client_id = settings.MQTT_CLIENT_ID
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv311,
            clean_session=True,
        )

        # Set credentials if configured
        if settings.MQTT_USERNAME:
            self._client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD or None)

        # Register callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        try:
            logger.info(
                "Connecting MQTT to %s:%d as '%s'",
                settings.MQTT_BROKER_HOST,
                settings.MQTT_BROKER_PORT,
                client_id,
            )
            self._client.connect_async(
                settings.MQTT_BROKER_HOST,
                settings.MQTT_BROKER_PORT,
                keepalive=settings.MQTT_KEEPALIVE_SEC,
            )
            self._client.loop_start()
        except Exception as exc:
            logger.error("Failed to initiate MQTT connection: %s", exc)

    async def stop(self) -> None:
        """Gracefully disconnect and stop the MQTT network loop."""
        if self._client:
            logger.info("Stopping MQTT subscriber")
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False

    # -- paho-mqtt callbacks (called from network thread) ----------------------

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            logger.info("MQTT connected successfully, subscribing to topics")
            self._connected = True
            # Subscribe to telemetry wildcard (both versioned v1 and unversioned)
            client.subscribe(TELEMETRY_TOPIC, qos=1)
            client.subscribe("motorguard/+/telemetry", qos=1)
            client.subscribe(STATUS_TOPIC, qos=1)
            client.subscribe("motorguard/+/status", qos=1)
            client.subscribe(HEARTBEAT_TOPIC, qos=0)
            logger.info("Subscribed to telemetry topics (QoS 1)")
        else:
            logger.error("MQTT connection refused: reason_code=%s", reason_code)
            self._connected = False

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self._connected = False
        if reason_code != 0:
            logger.warning("MQTT unexpected disconnect: reason_code=%s — will auto-reconnect", reason_code)
        else:
            logger.info("MQTT disconnected cleanly")

    def _on_message(self, client, userdata, msg: mqtt.MQTTMessage):
        """
        Called from paho network thread. Parses the topic, validates the
        payload, and schedules the async callback on the event loop.
        """
        topic = msg.topic
        # Only process telemetry for now (status/heartbeat handled in later phases)
        if "/telemetry" not in topic:
            return

        try:
            raw = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._error_count += 1
            logger.warning("Malformed MQTT payload on %s: %s", topic, exc)
            return

        # Validate against Pydantic contract
        try:
            validated = TelemetryMessage(**raw)
        except ValidationError as exc:
            self._error_count += 1
            logger.warning(
                "Invalid telemetry schema from %s on %s: %s",
                raw.get("device_id", "unknown"),
                topic,
                exc.error_count(),
            )
            logger.debug("Validation errors: %s", exc.errors())
            return

        self._message_count += 1
        payload_dict = validated.model_dump()

        # Schedule the async callback on the main event loop
        if self._on_telemetry_callback and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._on_telemetry_callback(payload_dict),
                self._loop,
            )


# Module-level singleton
mqtt_subscriber = MQTTSubscriber()
