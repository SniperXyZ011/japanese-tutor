import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import assessment, audio, auth, conversations, curriculum, profile, progress, review
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import RequestContextMiddleware
from app.db.session import SessionLocal


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-request-id"],
    )
    register_error_handlers(app)
    for r in (auth, profile, curriculum, assessment, review, progress, conversations, audio):
        app.include_router(r.router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        db_status = "ok"
        try:
            with SessionLocal() as db:
                db.execute(text("select 1"))
        except Exception:
            db_status = "unavailable"
        return {"status": "ok" if db_status == "ok" else "degraded", "database": db_status}

    return app


app = create_app()
