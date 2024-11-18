import logging
from functools import wraps

from aidial_sdk.exceptions import HTTPException as DialException
from fastapi import HTTPException as FastAPIException
from openai import APIConnectionError, APIStatusError, APITimeoutError

log = logging.getLogger(__name__)


def to_dial_exception(e: Exception) -> DialException | FastAPIException:
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
        return DialException("Request timed out", 504, "timeout")

    if isinstance(e, APIConnectionError):
        return DialException(
            "Error communicating with OpenAI", 502, "connection"
        )

    if isinstance(e, DialException):
        return e

    return DialException(
        status_code=500,
        type="internal_server_error",
        message=str(e),
    )


def to_fastapi_exception(
    e: DialException | FastAPIException,
) -> FastAPIException:
    if isinstance(e, FastAPIException):
        return e
    else:
        return e.to_fastapi_exception()


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
            fastapi_exception = to_fastapi_exception(dial_exception)
            raise fastapi_exception from e

    return wrapper
