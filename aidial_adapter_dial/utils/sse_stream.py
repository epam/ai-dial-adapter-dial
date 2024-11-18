import json
import logging
from typing import Any, AsyncIterator, Mapping

from aidial_adapter_dial.utils.exceptions import (
    to_dial_exception,
    to_json_content,
)

DATA_PREFIX = "data: "
OPENAI_END_MARKER = "[DONE]"


def format_chunk(data: str | Mapping[str, Any]) -> str:
    if isinstance(data, str):
        return DATA_PREFIX + data.strip() + "\n\n"
    else:
        return DATA_PREFIX + json.dumps(data, separators=(",", ":")) + "\n\n"


END_CHUNK = format_chunk(OPENAI_END_MARKER)


log = logging.getLogger(__name__)


async def to_openai_sse_stream(
    stream: AsyncIterator[dict],
) -> AsyncIterator[str]:
    try:
        async for chunk in stream:
            yield format_chunk(chunk)
    except Exception as e:
        log.exception(
            f"caught exception while streaming: {type(e).__module__}.{type(e).__name__}"
        )

        dial_exception = to_dial_exception(e)
        error_chunk = to_json_content(dial_exception)

        yield format_chunk(error_chunk)

    yield END_CHUNK
