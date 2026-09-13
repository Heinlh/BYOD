"""Single-process, loopback-only HTTP application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.staticfiles import StaticFiles

from byod.api import chat, documents, local, settings, workspaces
from byod.config import Config
from byod.db.migrations import initialize
from byod.diagnostics import lifecycle_log
from byod.index.embed import Embedder
from byod.ingest.jobs import JobQueue
from byod.llm.base import ProviderError
from byod.llm.chat import ChatService
from byod.llm.keys import KeyStore
from byod.llm.providers import ProviderFactory, provider_for
from byod.retrieve.search import Retriever


def create_app(
    config: Config | None = None,
    *,
    keys: KeyStore | None = None,
    provider_factory: ProviderFactory = provider_for,
) -> FastAPI:
    resolved = config or Config.resolve()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        initialize(resolved)
        app.state.embedder = Embedder(resolved)
        app.state.jobs = JobQueue(resolved, app.state.embedder.index_document)
        app.state.chat = ChatService(
            resolved, Retriever(resolved, app.state.embedder), app.state.keys, provider_factory
        )
        with lifecycle_log(resolved):
            try:
                yield
            finally:
                app.state.jobs.close()

    app = FastAPI(title="BYOD", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.config = resolved
    app.state.keys = keys or KeyStore()
    app.state.provider_factory = provider_factory
    app.include_router(workspaces.router)
    app.include_router(documents.router)
    app.include_router(settings.router)
    app.include_router(chat.router)
    app.include_router(local.router)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Default validation responses echo input values, including submitted secrets.
        return JSONResponse(
            {"detail": "Invalid input. Check the fields and try again."}, status_code=422
        )

    @app.exception_handler(ProviderError)
    async def provider_error(request: Request, exc: ProviderError) -> JSONResponse:
        return JSONResponse({"code": exc.code, "detail": exc.message}, status_code=503)

    @app.middleware("http")
    async def local_only(request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Host checks prevent DNS rebinding; origin checks block other websites
        # from reading local files or changing settings through the local API.
        try:
            host = urlsplit("http://" + request.headers.get("host", ""))
        except ValueError:
            return JSONResponse({"detail": "Local access only."}, status_code=403)
        if host.hostname not in {"127.0.0.1", "localhost", "::1"}:
            return JSONResponse({"detail": "Local access only."}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.headers['host']}":
            return JSONResponse({"detail": "Same-origin access required."}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Same-origin access required."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'"
        )
        return response

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    bundle = Path(__file__).parent / "ui" / "dist"
    if bundle.is_dir():
        app.mount("/", StaticFiles(directory=bundle, html=True), name="ui")
    return app
