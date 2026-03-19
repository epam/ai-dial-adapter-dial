import pytest
from aidial_sdk.exceptions import InvalidRequestError

from aidial_adapter_dial.app import (
    UPSTREAM_ENDPOINT_HEADER,
    UPSTREAM_KEY_HEADER,
    AzureClient,
)
from aidial_adapter_dial.config import AppConfig


class _MockRequest:
    def __init__(
        self,
        *,
        headers: dict[str, str],
        query_params: dict[str, str] | None = None,
        body: bytes | None = None,
    ):
        self._headers = headers
        self._query_params = query_params or {}
        self._body = body or b""

    @property
    def headers(self) -> dict[str, str]:
        return self._headers

    @property
    def query_params(self) -> dict[str, str]:
        return self._query_params

    async def body(self) -> bytes:
        return self._body


@pytest.mark.asyncio
async def test_parse_rejects_missing_upstream_key_with_hostname_mismatch():
    local_dial_url = "http://dial-core.dial.svc.cluster.local"
    upstream_endpoint = (
        "http://dial-core.dial.svc.cluster.local.:80/"
        "openai/deployments/gpt-4o-2024-05-13/chat/completions"
    )

    request = _MockRequest(
        headers={
            "api-key": "local-api-key",
            UPSTREAM_ENDPOINT_HEADER: upstream_endpoint,
        }
    )

    conf = AppConfig(local_dial_url=local_dial_url, headers_to_proxy=[])

    with pytest.raises(InvalidRequestError) as excinfo:
        await AzureClient.parse(conf, request)

    expected_message = (
        f"Given that {UPSTREAM_KEY_HEADER!r} header is missing, "
        f"it's expected that hostname of upstream endpoint ({upstream_endpoint!r}) is "
        f"the same as the local DIAL URL ({local_dial_url!r}) "
    )
    assert str(excinfo.value) == expected_message
