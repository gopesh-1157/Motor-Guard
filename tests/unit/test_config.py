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
