from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from application.db.models import IncidentPriority, IncidentStatus

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: str | None = Field(default=None, max_length=4000)
    status: IncidentStatus = IncidentStatus.OPEN
    priority: IncidentPriority = IncidentPriority.MEDIUM


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: str | None = Field(default=None, max_length=4000)
    status: IncidentStatus | None = None
    priority: IncidentPriority | None = None

    @model_validator(mode="after")
    def validate_partial_update(self) -> IncidentUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied")

        non_nullable_fields = {"title", "status", "priority"}
        null_fields = [
            field
            for field in non_nullable_fields & self.model_fields_set
            if getattr(self, field) is None
        ]
        if null_fields:
            raise ValueError(
                "Null is not allowed for: " + ", ".join(sorted(null_fields))
            )
        return self


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    status: IncidentStatus
    priority: IncidentPriority
    created_at: datetime
    updated_at: datetime
