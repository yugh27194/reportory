"""FastAPI 앱. 실행: `uvicorn app.main:app`."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import errors
from app.config import get_settings
from app.db import dispose_engine
from app.routers import (
    documents,
    entries,
    evidence,
    files,
    followups,
    imports,
    internal,
    items,
    jobs,
    me,
    proposals,
    public,
)

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(title="re:portory API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    errors.install(app)
    for module in (
        me,
        entries,
        proposals,
        followups,
        items,
        evidence,
        imports,
        documents,
        jobs,
        public,
        internal,
        files,
    ):
        app.include_router(module.router, prefix=API_PREFIX)

    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        return {"ok": True}

    return app


app = create_app()
