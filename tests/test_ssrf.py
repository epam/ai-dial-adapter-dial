import pytest

from aidial_adapter_dial.utils import storage as storage_module
from aidial_adapter_dial.utils.storage import FileStorage
from aidial_adapter_dial.utils.url import has_same_origin


class _FakeResponse:
    def __init__(self, body: bytes = b""):
        self._body = body

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    def raise_for_status(self) -> None:
        pass

    async def read(self) -> bytes:
        return self._body


class _FakeSession:
    """Minimal aiohttp.ClientSession stand-in that records requests."""

    def __init__(self, calls: list[dict]):
        self._calls = calls

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    def get(self, url: str, **kwargs) -> _FakeResponse:
        self._calls.append({"url": url, **kwargs})
        return _FakeResponse(b"payload")


@pytest.fixture
def http_calls(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(
        storage_module.aiohttp,
        "ClientSession",
        lambda *a, **k: _FakeSession(calls),
    )
    return calls


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("http://dial-core/v1/files/x", "http://dial-core"),
        ("http://dial-core:80/v1/files/x", "http://dial-core"),
        ("https://dial-core:443/v1/files/x", "https://dial-core"),
        ("http://DIAL-CORE/v1/files/x", "http://dial-core"),
        ("http://dial-core.:7001/v1", "http://dial-core:7001"),
    ],
)
def test_has_same_origin_true(a: str, b: str):
    assert has_same_origin(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        # userinfo trick: prefix matches but the real host differs.
        ("http://dial-core@169.254.169.254/v1", "http://dial-core"),
        # look-alike domain that merely starts with the base URL string.
        ("http://dial-core.attacker.example/v1", "http://dial-core"),
        # different scheme.
        ("https://dial-core/v1", "http://dial-core"),
        # different port.
        ("http://dial-core:7001/v1", "http://dial-core"),
    ],
)
def test_has_same_origin_false(a: str, b: str):
    assert not has_same_origin(a, b)


async def test_download_sends_api_key_to_dial_origin(http_calls):
    storage = FileStorage(dial_url="http://dial-core", api_key="secret")

    content = await storage.download(
        "files/bucket/doc.txt",
        session=None,  # type: ignore[arg-type]
    )

    assert content == b"payload"
    assert len(http_calls) == 1
    assert http_calls[0]["url"] == "http://dial-core/v1/files/bucket/doc.txt"
    assert http_calls[0]["headers"]["api-key"] == "secret"


@pytest.mark.parametrize(
    "link",
    [
        # userinfo trick: prefix matches the DIAL base URL but the real host
        # is the cloud metadata endpoint.
        "http://dial-core@169.254.169.254/v1/files/bucket/secret",
        # look-alike host that merely starts with the base URL string.
        "http://dial-core.attacker.example/v1/files/bucket/secret",
    ],
)
async def test_download_rejects_prefix_lookalikes(http_calls, link: str):
    storage = FileStorage(dial_url="http://dial-core", api_key="secret")

    # A prefix look-alike is not the DIAL origin, so it is rejected before any
    # request is made and the api-key is never sent.
    with pytest.raises(ValueError, match="isn't DIAL url"):
        await storage.download(link, session=None)  # type: ignore[arg-type]

    assert http_calls == []
