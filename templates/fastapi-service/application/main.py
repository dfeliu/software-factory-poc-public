from fastapi import FastAPI

from application.api.health import router as health_router
from application.core.config import get_settings
from application.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    application = FastAPI(title=settings.app_name)
    application.include_router(health_router)
    return application


app = create_app()
