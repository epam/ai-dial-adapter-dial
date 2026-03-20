import pytest
from aioresponses import aioresponses

from aidial_adapter_dial.app import UPSTREAM_ENDPOINT_HEADER, AzureClient
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
async def test_non_normalized_upstream_endpoint_url():
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

    with aioresponses() as mocked:
        response = {
            "bucket": "test-bucket",
            "appdata": "test-bucket/appdata/xyz",
        }
        mocked.get(
            "http://dial-core.dial.svc.cluster.local.:80/v1/bucket",
            payload=response,
        )
        mocked.get(
            "http://dial-core.dial.svc.cluster.local/v1/bucket",
            payload=response,
        )

        await AzureClient.parse(conf, request)
