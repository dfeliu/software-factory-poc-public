import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session


@pytest.mark.integration
def test_database_connection_uses_isolated_postgresql(db_session: Session) -> None:
    assert db_session.execute(text("SELECT 1")).scalar_one() == 1
