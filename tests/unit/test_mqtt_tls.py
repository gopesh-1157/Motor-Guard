"""
Unit tests for MotorGuard MQTT Subscriber TLS configuration and negotiation.
"""

import ssl
from unittest.mock import MagicMock, patch
import pytest

from backend.app.config import Settings
from backend.app.mqtt.subscriber import MQTTSubscriber


@pytest.mark.asyncio
async def test_subscriber_local_default_no_tls():
    """Verify default local configuration does not initialize TLS context."""
    test_settings = Settings(
        ENVIRONMENT="development",
        MQTT_BROKER_HOST="127.0.0.1",
        MQTT_BROKER_PORT=1883,
        MQTT_USE_TLS=False,
    )

    with patch("backend.app.mqtt.subscriber.settings", test_settings), \
         patch("backend.app.mqtt.subscriber.mqtt.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        sub = MQTTSubscriber()
        await sub.start()

        # In local mode, tls_set_context must NOT be called
        mock_client.tls_set_context.assert_not_called()
        mock_client.tls_insecure_set.assert_not_called()
        mock_client.connect_async.assert_called_once_with("127.0.0.1", 1883, keepalive=60)


@pytest.mark.asyncio
async def test_subscriber_cloud_tls_configured():
    """Verify MQTTS TLS context is created with TLS 1.2+ minimum and passed to client."""
    test_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a" * 40,
        MQTT_PASSWORD="secure_broker_password",
        MQTT_BROKER_HOST="cluster-xyz.s1.eu.hivemq.cloud",
        MQTT_BROKER_PORT=8883,
        MQTT_USE_TLS=True,
        MQTT_TLS_INSECURE=False,
    )

    with patch("backend.app.mqtt.subscriber.settings", test_settings), \
         patch("backend.app.mqtt.subscriber.mqtt.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        sub = MQTTSubscriber()
        await sub.start()

        # In cloud TLS mode, tls_set_context MUST be called
        mock_client.tls_set_context.assert_called_once()
        ssl_ctx = mock_client.tls_set_context.call_args[0][0]

        assert isinstance(ssl_ctx, ssl.SSLContext)
        assert ssl_ctx.minimum_version == ssl.TLSVersion.TLSv1_2
        assert ssl_ctx.check_hostname is True
        assert ssl_ctx.verify_mode == ssl.CERT_REQUIRED
        mock_client.tls_insecure_set.assert_not_called()
        mock_client.connect_async.assert_called_once_with(
            "cluster-xyz.s1.eu.hivemq.cloud", 8883, keepalive=60
        )


@pytest.mark.asyncio
async def test_subscriber_insecure_tls_override_for_dev():
    """Verify insecure TLS override in development mode."""
    test_settings = Settings(
        ENVIRONMENT="development",
        MQTT_BROKER_HOST="192.168.1.100",
        MQTT_BROKER_PORT=8883,
        MQTT_USE_TLS=True,
        MQTT_TLS_INSECURE=True,
    )

    with patch("backend.app.mqtt.subscriber.settings", test_settings), \
         patch("backend.app.mqtt.subscriber.mqtt.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        sub = MQTTSubscriber()
        await sub.start()

        mock_client.tls_set_context.assert_called_once()
        ssl_ctx = mock_client.tls_set_context.call_args[0][0]
        assert ssl_ctx.check_hostname is False
        assert ssl_ctx.verify_mode == ssl.CERT_NONE
        mock_client.tls_insecure_set.assert_called_once_with(True)
