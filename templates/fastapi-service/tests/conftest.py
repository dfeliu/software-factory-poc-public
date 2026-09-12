import pytest
from sqlalchemy.orm import Session

from application.db.session import engine


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
