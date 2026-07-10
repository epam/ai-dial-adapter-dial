import io
import logging
import mimetypes
from collections.abc import Mapping
from urllib.parse import urljoin

import aiohttp
from pydantic import BaseModel
from typing_extensions import TypedDict

from aidial_adapter_dial.utils.url import (
    download_public_file,
    has_same_origin,
)

log = logging.getLogger(__name__)


class FileMetadata(TypedDict):
    name: str
    parentPath: str
    bucket: str
    url: str


class Bucket(TypedDict):
    bucket: str
    appdata: str | None  # Users do not have appdata


class AccessDeniedError(Exception):
    def __init__(self, url: str):
        super().__init__(f"Access denied: {url!r}")
        self.url = url


class FileStorage(BaseModel):
    dial_url: str
    api_key: str

    bucket: Bucket | None = None

    @property
    def headers(self) -> Mapping[str, str]:
        return {"api-key": self.api_key}

    async def get_bucket(self, session: aiohttp.ClientSession) -> Bucket:
        if self.bucket is not None:
            return self.bucket

        log.debug(f"retrieving bucket for {self.dial_url!r}")

        async with session.get(
            f"{self.dial_url}/v1/bucket",
            headers=self.headers,
        ) as response:
            response.raise_for_status()
            bucket = await response.json()
            self.bucket = bucket
            log.debug(f"bucket: {self.bucket}")
            return bucket

    @staticmethod
    def _to_form_data(
        filename: str, content_type: str | None, content: bytes
    ) -> aiohttp.FormData:
        data = aiohttp.FormData()
        data.add_field(
            "file",
            io.BytesIO(content),
            filename=filename,
            content_type=content_type,
        )
        return data

    async def is_accessible(
        self, url: str, session: aiohttp.ClientSession
    ) -> bool:
        try:
            await self._get_metadata(url, session)
            log.debug(f"file is accessible: url={url!r}")
            return True
        except AccessDeniedError:
            log.debug(f"file isn't accessible: url={url!r}")
            return False

    def to_metadata_url(self, url: str) -> str:
        """
        The file metadata URL given url like: files/BUCKET/foo/baz/document.pdf
        """
        metadata_url = f"{self.dial_url}/v1/metadata/"
        return urljoin(metadata_url, url, allow_fragments=True)

    async def _get_metadata(
        self,
        url: str,
        session: aiohttp.ClientSession,
    ) -> dict:
        metadata_url = self.to_metadata_url(url)

        log.debug(f"retrieving metadata: file={url!r}, url={metadata_url!r}")

        async with session.get(metadata_url, headers=self.headers) as response:
            if not response.ok:
                match response.status:
                    case 403:
                        raise AccessDeniedError(url)
                    case _:
                        response.raise_for_status()

            metadata = await response.json()

            log.debug(
                f"retrieved metadata: file={url!r}, url={metadata_url!r}, metadata={metadata}"
            )

            return metadata

    async def upload_file(
        self,
        filename: str,
        content_type: str | None,
        content: bytes,
        session: aiohttp.ClientSession,
    ) -> FileMetadata:
        bucket = await self.get_bucket(session)
        appdata = bucket["appdata"]
        ext = (content_type and mimetypes.guess_extension(content_type)) or ""
        url = f"{self.dial_url}/v1/files/{appdata}/{filename}{ext}"
        return await self.upload(url, content_type, content, session)

    async def upload(
        self,
        url: str,
        content_type: str | None,
        content: bytes,
        session: aiohttp.ClientSession,
    ) -> FileMetadata:
        log.debug(f"uploading file {url!r}")

        if self.to_dial_url(url) is None:
            raise ValueError(f"URL isn't DIAL url: {url!r}")
        url = self.to_abs_url(url)

        data = FileStorage._to_form_data(url, content_type, content)
        async with session.put(
            url=url,
            data=data,
            headers=self.headers,
        ) as response:
            response.raise_for_status()
            meta = await response.json()
            log.debug(f"uploaded file: url={url!r}, metadata={meta}")
            return meta

    def to_dial_url(self, link: str) -> str | None:
        url = self.to_abs_url(link)
        base_url = f"{self.dial_url}/v1/"
        if url.startswith(base_url):
            return url.removeprefix(base_url)
        return None

    def to_abs_url(self, link: str) -> str:
        base_url = f"{self.dial_url}/v1/"
        ret = urljoin(base_url, link)
        return ret

    async def download(self, url: str, session: aiohttp.ClientSession) -> bytes:
        log.debug(f"downloading file {url!r}")

        url = self.to_abs_url(url)

        # DIAL Core is trusted infrastructure: when the URL resolves to its
        # origin, fetch it directly with the api-key. The storage may
        # legitimately live on a private address, so SSRF checks would be
        # counterproductive here. The origin is matched by scheme/host/port,
        # never by string prefix: a URL like
        # ``http://<dial_url>@169.254.169.254`` shares the base-URL prefix yet
        # resolves to a different, internal host - a prefix check would treat
        # it as trusted, skip SSRF validation and leak the api-key.
        if has_same_origin(url, self.dial_url):
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, headers=self.headers) as response,
            ):
                response.raise_for_status()
                return await response.read()

        # Any other (attacker-controllable) URL is validated against SSRF and
        # never receives credentials.
        return await download_public_file(url)
