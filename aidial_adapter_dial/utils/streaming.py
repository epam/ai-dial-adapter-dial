from typing import AsyncIterator, Awaitable, Callable, Optional, TypeVar

_T = TypeVar("_T")
_V = TypeVar("_V")


async def map_stream(
    func: Callable[[_T], Optional[_V]], iterator: AsyncIterator[_T]
) -> AsyncIterator[_V]:
    async for item in iterator:
        new_item = func(item)
        if new_item is not None:
            yield new_item


async def amap_stream(
    func: Callable[[_T], Awaitable[Optional[_V]]], iterator: AsyncIterator[_T]
) -> AsyncIterator[_V]:
    async for item in iterator:
        new_item = await func(item)
        if new_item is not None:
            yield new_item
