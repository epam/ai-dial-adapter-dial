import functools

import httpx

from aidial_adapter_dial.utils.env import get_env_int

# Defaults borrowed from openai._constants.DEFAULT_CONNECTION_LIMITS
HTTP_MAX_CONNECTIONS = get_env_int("HTTP_MAX_CONNECTIONS", 1000)
HTTP_MAX_KEEPALIVE_CONNECTIONS = get_env_int(
    "HTTP_MAX_KEEPALIVE_CONNECTIONS", 100
)
HTTP_POOL_TIMEOUT = get_env_int("HTTP_POOL_TIMEOUT", 10)

# connect timeout and total timeout.
# Fail fast when the connection pool is exhausted instead of queueing
# for the total timeout of 10 minutes.
DEFAULT_TIMEOUT = httpx.Timeout(600, connect=10, pool=HTTP_POOL_TIMEOUT)

DEFAULT_CONNECTION_LIMITS = httpx.Limits(
    max_connections=HTTP_MAX_CONNECTIONS,
    max_keepalive_connections=HTTP_MAX_KEEPALIVE_CONNECTIONS,
)


@functools.cache
def get_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        limits=DEFAULT_CONNECTION_LIMITS,
        follow_redirects=True,
    )
