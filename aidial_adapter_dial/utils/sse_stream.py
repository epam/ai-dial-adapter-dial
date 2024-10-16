import json
import logging
from typing import Any, AsyncIterator, Mapping

from aidial_adapter_dial.utils.exceptions import (
    create_error,
    to_dial_exception,
    to_starlette_exception,
)

DATA_PREFIX = "data: "
OPENAI_END_MARKER = "[DONE]"


def format_chunk(data: str | Mapping[str, Any]) -> str:
    if isinstance(data, str):
        return DATA_PREFIX + data.strip() + "\n\n"
    else:
        return DATA_PREFIX + json.dumps(data, separators=(",", ":")) + "\n\n"


END_CHUNK = format_chunk(OPENAI_END_MARKER)


async def parse_openai_sse_stream(
    stream: AsyncIterator[bytes],
) -> AsyncIterator[dict]:
    async for line in stream:
        try:
            payload = line.decode("utf-8-sig").lstrip()  # type: ignore
        except Exception:
            yield create_error(
                message="Can't decode chunk to a string", type="runtime_error"
            )
            return

        if payload.strip() == "":
            continue

        if not payload.startswith(DATA_PREFIX):
            yield create_error(
                message="Invalid chunk format", type="runtime_error"
            )
            return

        payload = payload[len(DATA_PREFIX) :]

        if payload.strip() == OPENAI_END_MARKER:
            break

        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            yield create_error(
                message="Can't parse chunk to JSON", type="runtime_error"
            )
            return

        yield chunk


log = logging.getLogger(__name__)


async def to_openai_sse_stream(
    stream: AsyncIterator[dict],
) -> AsyncIterator[str]:
    try:
        async for chunk in stream:
            yield format_chunk(chunk)
        yield END_CHUNK
    except Exception as e:
        log.exception(
            f"caught exception while streaming: {type(e).__module__}.{type(e).__name__}"
        )

        dial_exception = to_dial_exception(e)
        starlette_exception = to_starlette_exception(dial_exception)

        yield format_chunk(starlette_exception.detail)
