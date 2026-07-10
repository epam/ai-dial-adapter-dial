import pytest
from aidial_sdk.exceptions import InvalidRequestError

from aidial_adapter_dial.utils import url as url_module
from aidial_adapter_dial.utils.storage import FileStorage
from aidial_adapter_dial.utils.url import (
    download_public_file,
    has_same_origin,
    validate_public_url,
)


class _FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ):
        self.status = status
        self.headers = headers or {}
        self._body = body

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise RuntimeError(f"unexpected status {self.status}")

    async def read(self) -> bytes:
        return self._body


class _FakeSession:
    """Minimal aiohttp.ClientSession stand-in that serves canned responses
    keyed by URL and records the requests it received."""

    def __init__(self, routes: dict[str, _FakeResponse], calls: list[dict]):
        self._routes = routes
        self._calls = calls

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    def get(self, url: str, **kwargs) -> _FakeResponse:
        self._calls.append({"url": url, **kwargs})
        return self._routes[url]


@pytest.fixture
def fake_http(monkeypatch):
    calls: list[dict] = []
    routes: dict[str, _FakeResponse] = {}

    def install(new_routes: dict[str, _FakeResponse]) -> list[dict]:
        routes.update(new_routes)
        monkeypatch.setattr(
            url_module.aiohttp,
            "ClientSession",
            lambda *a, **k: _FakeSession(routes, calls),
        )
        return calls

    return install


@pytest.mark.parametrize(
    "url",
    [
        # Cloud metadata endpoint.
        "http://169.254.169.254/metadata/v1/instanceinfo",
        "http://127.0.0.1/",
        "http://localhost/secret",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://0.0.0.0/",
        "https://[::1]/",
        # IPv4-mapped IPv6 form of the metadata endpoint.
        "http://[::ffff:169.254.169.254]/",
        # Decimal-encoded 127.0.0.1.
        "http://2130706433/",
    ],
)
async def test_rejects_non_public_address(url: str):
    with pytest.raises(InvalidRequestError, match="non-public address"):
        await validate_public_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://8.8.8.8/",
        "gopher://8.8.8.8/",
        "//8.8.8.8/no-scheme",
    ],
)
async def test_rejects_disallowed_scheme(url: str):
    with pytest.raises(InvalidRequestError, match="is not allowed"):
        await validate_public_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://8.8.8.8/file.txt",
        "https://1.1.1.1/file.txt",
        "https://[2606:4700:4700::1111]/file.txt",
    ],
)
async def test_allows_public_address(url: str):
    await validate_public_url(url)


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


async def test_download_public_file_follows_public_redirect(fake_http):
    fake_http(
        {
            "http://8.8.8.8/a": _FakeResponse(
                status=302, headers={"Location": "http://8.8.8.8/b"}
            ),
            "http://8.8.8.8/b": _FakeResponse(body=b"payload"),
        }
    )

    assert await download_public_file("http://8.8.8.8/a") == b"payload"


async def test_download_public_file_rejects_redirect_into_internal(fake_http):
    fake_http(
        {
            "http://8.8.8.8/a": _FakeResponse(
                status=302, headers={"Location": "http://169.254.169.254/"}
            ),
        }
    )

    with pytest.raises(InvalidRequestError, match="non-public address"):
        await download_public_file("http://8.8.8.8/a")


async def test_download_public_file_rejects_redirect_loop(fake_http):
    fake_http(
        {
            "http://8.8.8.8/a": _FakeResponse(
                status=302, headers={"Location": "http://8.8.8.8/a"}
            ),
        }
    )

    with pytest.raises(InvalidRequestError, match="too many redirects"):
        await download_public_file("http://8.8.8.8/a")


async def test_download_public_file_sends_no_credentials(fake_http):
    calls = fake_http(
        {"http://8.8.8.8/file.txt": _FakeResponse(body=b"payload")}
    )

    assert await download_public_file("http://8.8.8.8/file.txt") == b"payload"

    assert len(calls) == 1
    headers = {k.lower() for k in (calls[0].get("headers") or {})}
    assert "api-key" not in headers
    assert "authorization" not in headers


@pytest.mark.parametrize(
    "link",
    [
        # userinfo trick: prefix matches the trusted base URL but the real
        # host is the cloud metadata endpoint.
        "http://dial-core@169.254.169.254/v1/files/bucket/secret",
        # decimal-encoded loopback whose host differs from the base URL.
        "http://dial-core@2130706433/v1/files/bucket/secret",
    ],
)
async def test_prefix_lookalike_is_rejected(link: str):
    storage = FileStorage(dial_url="http://dial-core", api_key="secret")

    # A prefix look-alike merely starts with the base URL string but its real
    # host differs, so it is not recognised as a genuine DIAL URL. It is
    # rejected before any request is made and the api-key is never sent.
    with pytest.raises(ValueError, match="isn't DIAL url"):
        await storage.download(link, session=None)  # type: ignore[arg-type]
