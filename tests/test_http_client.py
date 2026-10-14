import httpx
import openai

from aidial_adapter_dial.utils.exceptions import to_dial_exception
from aidial_adapter_dial.utils.http_client import (
    HTTP_MAX_CONNECTIONS,
    HTTP_MAX_KEEPALIVE_CONNECTIONS,
    HTTP_POOL_TIMEOUT,
    get_http_client,
)

_REQUEST = httpx.Request("POST", "https://example.com")


def test_http_client_uses_configured_connection_limits():
    pool = get_http_client()._transport._pool  # type: ignore[attr-defined]
    assert pool._max_connections == HTTP_MAX_CONNECTIONS
    assert pool._max_keepalive_connections == HTTP_MAX_KEEPALIVE_CONNECTIONS


def test_http_client_uses_configured_pool_timeout():
    assert get_http_client().timeout.pool == HTTP_POOL_TIMEOUT


def test_pool_timeout_maps_to_503():
    pool_timeout = httpx.PoolTimeout("pool exhausted", request=_REQUEST)
    try:
        raise openai.APITimeoutError(request=_REQUEST) from pool_timeout
    except openai.APITimeoutError as wrapped:
        openai_error = wrapped

    for e in [pool_timeout, openai_error]:
        assert to_dial_exception(e).status_code == 503


def test_other_timeout_maps_to_504():
    read_timeout = httpx.ReadTimeout("read timed out", request=_REQUEST)
    try:
        raise openai.APITimeoutError(request=_REQUEST) from read_timeout
    except openai.APITimeoutError as wrapped:
        openai_error = wrapped

    assert to_dial_exception(openai_error).status_code == 504
