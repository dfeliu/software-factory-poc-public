from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Return process liveness without checking dependencies."""
    return HealthResponse(status="ok")
