import pytest
from pydantic import ValidationError
from backend.app.config import Settings


def test_default_dev_settings():
    """Verify default development configuration loads successfully."""
    s = Settings(ENVIRONMENT="development")
    assert s.ENVIRONMENT == "development"
    assert s.PORT == 8000
    assert len(s.cors_origins_list) > 0


def test_production_settings_validation():
    """Phase 1 Criterion: Missing required production secrets aborts validation with error."""
    # Production with default/insecure secret must fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="change_this_to_a_secure_random_64_character_hex_string_in_production",
            MQTT_PASSWORD="valid_password",
        )
    assert "SECRET_KEY must be a secure random string" in str(exc_info.value)

    # Production without MQTT password must fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 40,
            MQTT_PASSWORD="",
            GATEWAY_INGEST_SECRET="prod-gateway-secret-1234",
            ADMIN_INITIAL_PASSWORD="SecureAdminPass2026!",
        )
    assert "MQTT_PASSWORD must be configured in production" in str(exc_info.value)

    # Production with default GATEWAY_INGEST_SECRET must fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 40,
            MQTT_PASSWORD="secure_broker_password",
            GATEWAY_INGEST_SECRET="motorguard-dev-ingest-key",
            ADMIN_INITIAL_PASSWORD="SecureAdminPass2026!",
        )
    assert "GATEWAY_INGEST_SECRET must be configured" in str(exc_info.value)

    # Production without ADMIN_INITIAL_PASSWORD must fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 40,
            MQTT_PASSWORD="secure_broker_password",
            GATEWAY_INGEST_SECRET="prod-gateway-secret-1234",
            ADMIN_INITIAL_PASSWORD=None,
        )
    assert "ADMIN_INITIAL_PASSWORD must be explicitly configured" in str(exc_info.value)

    # Production with default / weak ADMIN_INITIAL_PASSWORD must fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 40,
            MQTT_PASSWORD="secure_broker_password",
            GATEWAY_INGEST_SECRET="prod-gateway-secret-1234",
            ADMIN_INITIAL_PASSWORD="adminpassword123",
        )
    assert "cannot use default passwords" in str(exc_info.value)

    # Production with short ADMIN_INITIAL_PASSWORD (<12 chars) must fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 40,
            MQTT_PASSWORD="secure_broker_password",
            GATEWAY_INGEST_SECRET="prod-gateway-secret-1234",
            ADMIN_INITIAL_PASSWORD="ShortPass1!",
        )
    assert "must be at least 12 characters" in str(exc_info.value)

    # Production with valid configuration must succeed
    valid_prod = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a" * 40,
        MQTT_PASSWORD="secure_broker_password",
        GATEWAY_INGEST_SECRET="prod-gateway-secret-1234",
        ADMIN_INITIAL_PASSWORD="SecureAdminPass2026!",
    )
    assert valid_prod.ENVIRONMENT == "production"
    assert valid_prod.DEBUG is False
    assert valid_prod.ENABLE_DOCS is False

    # Production with DEBUG=True must fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 40,
            MQTT_PASSWORD="secure_broker_password",
            GATEWAY_INGEST_SECRET="prod-gateway-secret-1234",
            ADMIN_INITIAL_PASSWORD="SecureAdminPass2026!",
            DEBUG=True,
        )
    assert "DEBUG must be set to False in production" in str(exc_info.value)

    # Production with wildcard CORS must fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 40,
            MQTT_PASSWORD="secure_broker_password",
            GATEWAY_INGEST_SECRET="prod-gateway-secret-1234",
            ADMIN_INITIAL_PASSWORD="SecureAdminPass2026!",
            CORS_ORIGINS="*",
        )
    assert "Explicit CORS_ORIGINS must be configured in production" in str(exc_info.value)


def test_mqtt_tls_validation_guardrails():
    """Verify strict validation rejects contradictory or insecure MQTT configurations."""
    # 1. Port 8883 without TLS must fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="development",
            MQTT_BROKER_PORT=8883,
            MQTT_USE_TLS=False,
        )
    assert "Port 8883 is designated for MQTTS and requires MQTT_USE_TLS=True" in str(exc_info.value)

    # 2. Cloud domain without TLS must fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="development",
            MQTT_BROKER_HOST="test-cluster.s1.eu.hivemq.cloud",
            MQTT_BROKER_PORT=1883,
            MQTT_USE_TLS=False,
        )
    assert "requires secure TLS" in str(exc_info.value)

    # 3. Production remote broker without TLS must fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 40,
            MQTT_PASSWORD="secure_broker_password",
            GATEWAY_INGEST_SECRET="prod-gateway-secret-1234",
            ADMIN_INITIAL_PASSWORD="SecureAdminPass2026!",
            MQTT_BROKER_HOST="198.51.100.25",
            MQTT_BROKER_PORT=1883,
            MQTT_USE_TLS=False,
        )
    assert "Remote MQTT broker connections in production must have MQTT_USE_TLS=True" in str(exc_info.value)

    # 4. Production with MQTT_TLS_INSECURE=True must fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 40,
            MQTT_PASSWORD="secure_broker_password",
            GATEWAY_INGEST_SECRET="prod-gateway-secret-1234",
            ADMIN_INITIAL_PASSWORD="SecureAdminPass2026!",
            MQTT_BROKER_HOST="198.51.100.25",
            MQTT_BROKER_PORT=8883,
            MQTT_USE_TLS=True,
            MQTT_TLS_INSECURE=True,
        )
    assert "MQTT_TLS_INSECURE=True is strictly forbidden in production" in str(exc_info.value)

    # 5. Valid Cloud MQTTS configuration must succeed
    valid_cloud = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a" * 40,
        MQTT_PASSWORD="secure_broker_password",
        GATEWAY_INGEST_SECRET="prod-gateway-secret-1234",
        ADMIN_INITIAL_PASSWORD="SecureAdminPass2026!",
        MQTT_BROKER_HOST="test-cluster.s1.eu.hivemq.cloud",
        MQTT_BROKER_PORT=8883,
        MQTT_USE_TLS=True,
    )
    assert valid_cloud.MQTT_USE_TLS is True
    assert valid_cloud.MQTT_BROKER_PORT == 8883
    assert valid_cloud.MQTT_TLS_INSECURE is False


@pytest.mark.asyncio
async def test_admin_seeding_fails_closed_in_production():
    """Verify UserService.seed_default_admin strictly aborts if ADMIN_INITIAL_PASSWORD is omitted in production."""
    from unittest.mock import AsyncMock, patch
    from backend.app.services.user_service import UserService
    from backend.app.config import settings

    mock_coll = AsyncMock()
    mock_coll.count_documents.return_value = 0

    mock_db = AsyncMock()
    mock_db.__getitem__.return_value = mock_coll
    svc = UserService(mock_db)

    with patch.object(settings, "ENVIRONMENT", "production"):
        with patch.object(settings, "ADMIN_INITIAL_PASSWORD", None):
            with pytest.raises(RuntimeError) as exc_info:
                await svc.seed_default_admin()
            assert "ADMIN_INITIAL_PASSWORD environment variable is required" in str(exc_info.value)


@pytest.mark.asyncio
async def test_admin_seeding_development_fallback_preserved():
    """Verify UserService.seed_default_admin preserves local development fallback when not in production."""
    from unittest.mock import AsyncMock, patch
    from backend.app.services.user_service import UserService
    from backend.app.config import settings

    mock_coll = AsyncMock()
    mock_coll.count_documents.return_value = 0
    mock_coll.find_one.return_value = None  # user doesn't exist yet
    mock_coll.insert_one.return_value = AsyncMock(inserted_id="mock_admin_id")

    mock_db = AsyncMock()
    mock_db.__getitem__.side_effect = lambda name: mock_coll if name == "users" else AsyncMock()
    svc = UserService(mock_db)

    with patch.object(settings, "ENVIRONMENT", "development"):
        with patch.object(settings, "ADMIN_INITIAL_PASSWORD", None):
            await svc.seed_default_admin()
            # Successfully invoked insert_one with dev fallback password
            assert mock_coll.insert_one.called
            doc = mock_coll.insert_one.call_args[0][0]
            assert doc["username"] == "admin"
            assert doc["role"] == "Admin"



