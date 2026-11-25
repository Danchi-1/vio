"""The API error envelope from docs/api/ENDPOINT_PROPOSAL.md, applied uniformly.

Raise ApiError(status_code, code, message, fields=...) from endpoint code for
a specific error code. Plain fastapi.HTTPException(status_code, detail=str)
calls (used by the original health/catalogue endpoints) are still wrapped
into the same envelope with a sensible default code, so every endpoint
returns a consistent shape without needing to be rewritten.
"""

from collections.abc import Mapping
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        fields: Mapping[str, list[str]] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = dict(fields) if fields else None


_DEFAULT_CODE_BY_STATUS = {
    400: "invalid_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    410: "expired_link",
    422: "validation_failed",
    429: "rate_limited",
    503: "service_unavailable",
}


def _envelope(
    request: Request, code: str, message: str, fields: Mapping[str, list[str]] | None = None
) -> dict:
    request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex
    body: dict = {"error": {"code": code, "message": message, "request_id": request_id}}
    if fields:
        body["error"]["fields"] = dict(fields)
    return body


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(request, exc.code, exc.message, exc.fields),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, Mapping) and "code" in exc.detail and "message" in exc.detail:
            code = exc.detail["code"]
            message = exc.detail["message"]
            fields = exc.detail.get("fields")
        else:
            code = _DEFAULT_CODE_BY_STATUS.get(exc.status_code, "internal_error")
            message = exc.detail if isinstance(exc.detail, str) else "An unexpected error occurred."
            fields = None
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(request, code, message, fields),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, list[str]] = {}
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"] if part != "body")
            fields.setdefault(location or "body", []).append(error["msg"])
        return JSONResponse(
            status_code=422,
            content=_envelope(
                request, "validation_failed", "Check the highlighted fields and try again.", fields
            ),
        )
