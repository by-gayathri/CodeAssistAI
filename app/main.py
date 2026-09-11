"""FastAPI application entrypoint for CodeAssistAI."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import health, reviews
from app.core.config import get_settings
from app.core.exceptions import CodeAssistAIError, NotFoundError, ParseError, ProviderError
from app.core.logging import setup_logging


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    application = FastAPI(
        title="CodeAssistAI",
        description=(
            "LLM-based code review assistant. Accepts source code through an API and "
            "returns structured review feedback. Supported languages: python, javascript, "
            "typescript, java, go. Supported review categories: logic, readability, "
            "security, performance, testing, maintainability, code_quality. "
            "Configure PROVIDER=mock|transformer|external."
        ),
        version=settings.app_version or __version__,
        contact={"name": "CodeAssistAI"},
    )

    application.include_router(health.router)
    application.include_router(reviews.router)

    @application.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content=exc.to_dict())

    @application.exception_handler(ProviderError)
    async def provider_error_handler(_: Request, exc: ProviderError) -> JSONResponse:
        return JSONResponse(status_code=502, content=exc.to_dict())

    @application.exception_handler(ParseError)
    async def parse_error_handler(_: Request, exc: ParseError) -> JSONResponse:
        return JSONResponse(status_code=502, content=exc.to_dict())

    @application.exception_handler(CodeAssistAIError)
    async def app_error_handler(_: Request, exc: CodeAssistAIError) -> JSONResponse:
        status = 400 if exc.code == "validation_error" else 500
        return JSONResponse(status_code=status, content=exc.to_dict())

    @application.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        issues = []
        for err in exc.errors():
            cleaned = {k: v for k, v in err.items() if k != "ctx"}
            if "ctx" in err:
                cleaned["ctx"] = {key: str(value) for key, value in err["ctx"].items()}
            issues.append(cleaned)
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": {"issues": issues},
                }
            },
        )

    @application.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        # Do not expose stack traces or internals to clients.
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred",
                }
            },
        )

    return application


app = create_app()
