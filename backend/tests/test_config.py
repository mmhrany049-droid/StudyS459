"""Foundation acceptance: spec-mandated defaults."""

from app.config import get_settings


def test_spec_defaults() -> None:
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert s.TIMEZONE == "Asia/Tehran"  # spec 13
        assert s.SINGLE_USER_ID == 1  # single-user MVP (spec 00)
        assert s.is_sqlite is True  # sqlite default, postgres-ready
        assert "http://localhost:5173" in s.cors_origins
    finally:
        get_settings.cache_clear()
