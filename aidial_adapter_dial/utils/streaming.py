import logging
from typing import AsyncIterator, Awaitable, Callable, Optional, TypeVar

from openai import APIError

from aidial_adapter_dial.utils.exceptions import create_error

log = logging.getLogger(__name__)


async def generate_stream(stream: AsyncIterator[dict]) -> AsyncIterator[dict]:
    try:
        async for chunk in stream:
            yield chunk
    except APIError as e:
        log.error(f"error during steaming: {e.body}")

        display_message = None
        if e.body is not None and isinstance(e.body, dict):
            display_message = e.body.get("display_message", None)

        yield create_error(
            message=e.message,
            type=e.type,
            param=e.param,
            code=e.code,
            display_message=display_message,
        )
        return


T = TypeVar("T")
V = TypeVar("V")


async def map_stream(
    func: Callable[[T], Optional[V]], iterator: AsyncIterator[T]
) -> AsyncIterator[V]:
    async for item in iterator:
        new_item = func(item)
        if new_item is not None:
            yield new_item


async def amap_stream(
    func: Callable[[T], Awaitable[Optional[V]]], iterator: AsyncIterator[T]
) -> AsyncIterator[V]:
    async for item in iterator:
        new_item = await func(item)
        if new_item is not None:
            yield new_item
