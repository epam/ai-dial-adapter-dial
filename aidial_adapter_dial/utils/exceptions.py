import logging
from functools import wraps
from typing import Optional

from fastapi import HTTPException as FastAPIException
from openai import APIConnectionError, APIStatusError, APITimeoutError

log = logging.getLogger(__name__)


class HTTPException(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        type: str = "runtime_error",
        param: Optional[str] = None,
        code: Optional[str] = None,
        display_message: Optional[str] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.type = type
        self.param = param
        self.code = code
        self.display_message = display_message

    def __repr__(self):
        return (
            "%s(message=%r, status_code=%r, type=%r, param=%r, code=%r, display_message=%r)"
            % (
                self.__class__.__name__,
                self.message,
                self.status_code,
                self.type,
                self.param,
                self.code,
                self.display_message,
            )
        )


def remove_nones(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def create_error(
    message: str,
    type: Optional[str] = None,
    param: Optional[str] = None,
    code: Optional[str] = None,
    display_message: Optional[str] = None,
):
    return {
        "error": remove_nones(
            {
                "message": message,
                "type": type,
                "param": param,
                "code": code,
                "display_message": display_message,
            }
        )
    }


def to_dial_exception(e: Exception) -> HTTPException | FastAPIException:
    if isinstance(e, APIStatusError):
        r = e.response
        headers = r.headers

        if "Content-Length" in headers:
            del headers["Content-Length"]

        return FastAPIException(
            detail=r.text,
            status_code=r.status_code,
            headers=dict(headers),
        )

    if isinstance(e, APITimeoutError):
        return HTTPException("Request timed out", 504, "timeout")

    if isinstance(e, APIConnectionError):
        return HTTPException(
            "Error communicating with OpenAI", 502, "connection"
        )

    if isinstance(e, HTTPException):
        return e

    return HTTPException(
        status_code=500,
        type="internal_server_error",
        message=str(e),
        code=None,
        param=None,
    )


def to_starlette_exception(
    e: HTTPException | FastAPIException,
) -> FastAPIException:
    if isinstance(e, FastAPIException):
        return e

    return FastAPIException(
        status_code=e.status_code,
        detail=create_error(
            message=e.message,
            type=e.type,
            param=e.param,
            code=e.code,
            display_message=e.display_message,
        ),
    )


def dial_exception_decorator(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            log.exception(
                f"caught exception: {type(e).__module__}.{type(e).__name__}"
            )
            dial_exception = to_dial_exception(e)
            raise to_starlette_exception(dial_exception) from e

    return wrapper
