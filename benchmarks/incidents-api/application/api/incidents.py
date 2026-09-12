import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from application.api.schemas import IncidentCreate, IncidentRead, IncidentUpdate
from application.db.models import Incident
from application.db.session import get_session

router = APIRouter(prefix="/incidents", tags=["incidents"])
logger = logging.getLogger(__name__)
SessionDependency = Annotated[Session, Depends(get_session)]


def get_active_incident_or_404(session: Session, incident_id: int) -> Incident:
    incident = session.get(Incident, incident_id)
    if incident is None or incident.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found"
        )
    return incident


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate, response: Response, session: SessionDependency
) -> IncidentRead:
    incident = Incident(
        title=payload.title,
        description=payload.description,
        status=payload.status.value,
        priority=payload.priority.value,
    )
    session.add(incident)
    session.commit()
    session.refresh(incident)
    response.headers["Location"] = f"/incidents/{incident.id}"
    logger.info("incident.created", extra={"incident_id": incident.id})
    return IncidentRead.model_validate(incident)


@router.get("", response_model=list[IncidentRead])
def list_incidents(session: SessionDependency) -> list[IncidentRead]:
    incidents = session.scalars(
        select(Incident).where(Incident.deleted_at.is_(None)).order_by(Incident.id)
    ).all()
    return [IncidentRead.model_validate(incident) for incident in incidents]


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(
    incident_id: Annotated[int, Path(gt=0)], session: SessionDependency
) -> IncidentRead:
    return IncidentRead.model_validate(get_active_incident_or_404(session, incident_id))


@router.patch("/{incident_id}", response_model=IncidentRead)
def update_incident(
    incident_id: Annotated[int, Path(gt=0)],
    payload: IncidentUpdate,
    session: SessionDependency,
) -> IncidentRead:
    incident = get_active_incident_or_404(session, incident_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(value, StrEnum):
            value = value.value
        setattr(incident, field, value)
    incident.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(incident)
    logger.info("incident.updated", extra={"incident_id": incident.id})
    return IncidentRead.model_validate(incident)


@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_incident(
    incident_id: Annotated[int, Path(gt=0)], session: SessionDependency
) -> Response:
    incident = get_active_incident_or_404(session, incident_id)
    deleted_at = datetime.now(UTC)
    incident.deleted_at = deleted_at
    incident.updated_at = deleted_at
    session.commit()
    logger.info("incident.deleted", extra={"incident_id": incident.id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
