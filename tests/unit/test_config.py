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
        )
    assert "MQTT_PASSWORD must be configured in production" in str(exc_info.value)

    # Production with valid configuration must succeed
    valid_prod = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a" * 40,
        MQTT_PASSWORD="secure_broker_password",
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
            DEBUG=True,
        )
    assert "DEBUG must be set to False in production" in str(exc_info.value)

    # Production with wildcard CORS must fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 40,
            MQTT_PASSWORD="secure_broker_password",
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
            MQTT_USE_TLS=False,
        )
    assert "requires secure TLS" in str(exc_info.value)

    # 3. Production remote broker without TLS must fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 40,
            MQTT_PASSWORD="secure_broker_password",
            MQTT_BROKER_HOST="198.51.100.25",
            MQTT_USE_TLS=False,
        )
    assert "Remote MQTT broker connections in production must have MQTT_USE_TLS=True" in str(exc_info.value)

    # 4. Production with MQTT_TLS_INSECURE=True must fail
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 40,
            MQTT_PASSWORD="secure_broker_password",
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
        MQTT_BROKER_HOST="test-cluster.s1.eu.hivemq.cloud",
        MQTT_BROKER_PORT=8883,
        MQTT_USE_TLS=True,
    )
    assert valid_cloud.MQTT_USE_TLS is True
    assert valid_cloud.MQTT_BROKER_PORT == 8883
    assert valid_cloud.MQTT_TLS_INSECURE is False


