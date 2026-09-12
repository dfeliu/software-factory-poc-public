import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from application.db.session import engine, get_session
from application.main import app


@pytest.fixture
def db_session() -> Session:
    """Provide transaction-isolated database access when a test needs it."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> TestClient:
    def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
