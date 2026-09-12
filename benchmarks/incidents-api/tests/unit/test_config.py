import pytest
from sqlalchemy.engine import make_url

from application.core.config import Settings


def test_database_url_takes_precedence_over_base_values() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://direct:secret@example.test/direct_db",
        postgres_db="ignored_db",
        postgres_user="ignored_user",
        postgres_password="ignored_secret",
    )

    assert settings.sqlalchemy_database_url.endswith("/direct_db")


def test_database_url_is_constructed_from_base_values() -> None:
    settings = Settings(
        _env_file=None,
        postgres_db="service_db",
        postgres_user="service_user",
        postgres_password="a password with spaces",
        postgres_host="database",
    )

    database_url = make_url(settings.sqlalchemy_database_url)

    assert database_url.drivername == "postgresql+psycopg"
    assert database_url.username == "service_user"
    assert database_url.password == "a password with spaces"


def test_missing_database_configuration_fails_explicitly() -> None:
    with pytest.raises(ValueError, match="Database configuration is missing"):
        Settings(_env_file=None)
