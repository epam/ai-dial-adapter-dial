import dataclasses
import logging
from typing import Any

from aidial_sdk.exceptions import HTTPException as DialException
from fastapi.responses import JSONResponse as FastAPIResponse
from httpx import Headers
from openai import APIConnectionError, APIStatusError, APITimeoutError

log = logging.getLogger(__name__)


@dataclasses.dataclass
class ResponseWrapper:
    status_code: int
    headers: Headers | None
    content: Any

    def to_fastapi_response(self) -> FastAPIResponse:
        return FastAPIResponse(
            content=self.content,
            status_code=self.status_code,
            headers=self.headers,
        )


def to_dial_exception(exc: Exception) -> DialException | ResponseWrapper:
    if isinstance(exc, APIStatusError):
        r = exc.response
        headers = r.headers

        if "Content-Length" in headers:
            del headers["Content-Length"]

        try:
            content = r.json()
        except Exception:
            content = r.text

        return ResponseWrapper(
            status_code=r.status_code,
            headers=headers,
            content=content,
        )

    if isinstance(exc, APITimeoutError):
        return DialException("Request timed out", 504, "timeout")

    if isinstance(exc, APIConnectionError):
        return DialException(
            "Error communicating with OpenAI", 502, "connection"
        )

    if isinstance(exc, DialException):
        return exc

    return DialException(
        status_code=500,
        type="internal_server_error",
        message=str(exc),
    )


def to_json_content(exc: DialException | ResponseWrapper) -> Any:
    if isinstance(exc, DialException):
        return exc.json_error()
    else:
        return exc.content
