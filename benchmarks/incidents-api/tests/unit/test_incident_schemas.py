import pytest
from pydantic import ValidationError

from application.api.schemas import (
    IncidentCreate,
    IncidentPriority,
    IncidentStatus,
    IncidentUpdate,
)


def test_incident_create_uses_defaults() -> None:
    incident = IncidentCreate(title="Broken lift")

    assert incident.status is IncidentStatus.OPEN
    assert incident.priority is IncidentPriority.MEDIUM
    assert incident.description is None


@pytest.mark.parametrize("field", ["status", "priority"])
def test_incident_create_rejects_unknown_enum_values(field: str) -> None:
    with pytest.raises(ValidationError):
        IncidentCreate(title="Broken lift", **{field: "UNKNOWN"})


def test_incident_update_allows_clearing_description() -> None:
    update = IncidentUpdate(description=None)

    assert update.model_dump(exclude_unset=True) == {"description": None}


@pytest.mark.parametrize("field", ["title", "status", "priority"])
def test_incident_update_rejects_null_for_required_fields(field: str) -> None:
    with pytest.raises(ValidationError, match="Null is not allowed"):
        IncidentUpdate(**{field: None})


def test_incident_update_rejects_an_empty_payload() -> None:
    with pytest.raises(ValidationError, match="At least one field"):
        IncidentUpdate()
