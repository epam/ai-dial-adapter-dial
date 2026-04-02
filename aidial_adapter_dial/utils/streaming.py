from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

_T = TypeVar("_T")
_V = TypeVar("_V")


async def map_stream(
    func: Callable[[_T], _V | None], iterator: AsyncIterator[_T]
) -> AsyncIterator[_V]:
    async for item in iterator:
        new_item = func(item)
        if new_item is not None:
            yield new_item


async def amap_stream(
    func: Callable[[_T], Awaitable[_V | None]], iterator: AsyncIterator[_T]
) -> AsyncIterator[_V]:
    async for item in iterator:
        new_item = await func(item)
        if new_item is not None:
            yield new_item
