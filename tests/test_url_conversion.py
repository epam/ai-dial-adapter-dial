import pytest

from aidial_adapter_dial.transformer import AttachmentTransformer
from aidial_adapter_dial.utils.storage import Bucket, FileStorage


async def _create_transformer(
    *, proxy_mode: bool = False
) -> AttachmentTransformer:
    local_storage = FileStorage(
        dial_url="http://local-dial.com",
        api_key="local-dial-key",
        bucket=Bucket(
            bucket="local-app-bucket",
            appdata="local-user-bucket/appdata/local-app-name",
        ),
    )
    remote_storage = FileStorage(
        dial_url="http://remote-dial.com",
        api_key="remote-remote-key",
        bucket=Bucket(
            bucket="remote-app-bucket",
            appdata="remote-user-bucket/appdata/remote-app-name",
        ),
    )
    return await AttachmentTransformer.create(
        local_storage=local_storage,
        remote_storage=local_storage if proxy_mode else remote_storage,
    )


@pytest.mark.parametrize(
    ("proxy_mode", "local_url", "expected"),
    [
        (
            True,
            "files/local-user-bucket/path/to/file.txt",
            "files/local-user-bucket/path/to/file.txt",
        ),
        (
            False,
            "files/local-user-bucket/path/to/file.txt",
            "files/remote-user-bucket/local-user-bucket/path/to/file.txt",
        ),
        (
            False,
            "files/unknown-user-bucket/path/to/shared/file.txt",
            "files/remote-user-bucket/unknown-user-bucket/path/to/shared/file.txt",
        ),
    ],
)
async def test_get_remote_url_success(
    proxy_mode: bool, local_url: str, expected: str
):
    transformer = await _create_transformer(proxy_mode=proxy_mode)
    assert transformer.get_remote_url(local_url) == expected


@pytest.mark.parametrize(
    "local_url",
    [
        "http://example.com/files/local-user/path",
        "LOCAL/files/local-user/path",
        "/files/local-user/path",
    ],
)
async def test_get_remote_url_invalid_prefix(local_url: str):
    transformer = await _create_transformer(proxy_mode=False)
    with pytest.raises(
        ValueError, match="Local URL is expected to point to files resource: "
    ):
        transformer.get_remote_url(local_url)


@pytest.mark.parametrize(
    ("proxy_mode", "remote_url", "expected"),
    [
        (
            False,
            "files/remote-user-bucket/appdata/remote-app-name/some/path.txt",
            "files/local-user-bucket/appdata/local-app-name/some/path.txt",
        ),
        (
            True,
            "files/local-user-bucket/appdata/local-app-name/some/path.txt",
            "files/local-user-bucket/appdata/local-app-name/some/path.txt",
        ),
        (
            False,
            "files/remote-user-bucket/unknown-user-bucket/path/to/shared/file.txt",
            "files/unknown-user-bucket/path/to/shared/file.txt",
        ),
        (
            False,
            "files/remote-user-bucket/path/to/shared.doc",
            "files/path/to/shared.doc",
        ),
    ],
)
async def test_get_local_url_success(
    proxy_mode: bool, remote_url: str, expected: str
):
    transformer = await _create_transformer(proxy_mode=proxy_mode)
    assert transformer.get_local_url(remote_url) == expected


async def test_get_local_url_rejects_wrong_bucket():
    transformer = await _create_transformer()
    with pytest.raises(
        ValueError,
        match=r"The remote file \([^\)]+\) is expected to be uploaded to the remote user bucket \([^\)]+\)",
    ):
        transformer.get_local_url(
            "files/unknown-user-bucket/appdata/unknown-app-name/path/to/file"
        )


@pytest.mark.parametrize(
    "remote_url",
    [
        "files/remote-user-bucket/appdata/",
        "files/remote-user-bucket/appdata/remote-app-name",
        "files/remote-user-bucket/appdata/remote-app-name/",
    ],
)
async def test_get_local_url_invalid_appdata_path(remote_url):
    transformer = await _create_transformer()
    with pytest.raises(ValueError, match="Invalid remote appdata path"):
        transformer.get_local_url(remote_url)
