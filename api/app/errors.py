"""오류 형식 {"error": {"code", "message"}} (인계서 9.1절)."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def not_found(message: str = "요청한 대상을 찾을 수 없다.") -> ApiError:
    return ApiError(404, "not_found", message)


def unauthorized(message: str = "로그인이 필요하다.") -> ApiError:
    return ApiError(401, "unauthorized", message)


def invalid_transition(message: str) -> ApiError:
    return ApiError(409, "invalid_transition", message)


def validation_error(message: str) -> ApiError:
    return ApiError(422, "validation_error", message)


def rate_limited(message: str = "오늘 사용할 수 있는 횟수를 모두 썼다.") -> ApiError:
    return ApiError(429, "rate_limited", message)


def _body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


_STATUS_CODES = {401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "not_found"}


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return JSONResponse(_body(exc.code, exc.message), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        message = f"입력값이 올바르지 않다: {loc}" if loc else "입력값이 올바르지 않다."
        return JSONResponse(_body("validation_error", message), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = _STATUS_CODES.get(exc.status_code, "error")
        message = (
            "요청한 대상을 찾을 수 없다." if exc.status_code in (404, 405) else str(exc.detail)
        )
        return JSONResponse(_body(code, message), status_code=exc.status_code)
