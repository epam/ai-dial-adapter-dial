import logging
import re
from typing import Any, Callable, Coroutine, Self

import aiohttp
from pydantic import BaseModel

from aidial_adapter_dial.utils.app_data import AppData
from aidial_adapter_dial.utils.storage import FileStorage

log = logging.getLogger(__name__)


class AttachmentTransformer(BaseModel):
    local_storage: FileStorage
    local_user_bucket: str
    local_appdata: str

    remote_storage: FileStorage
    remote_user_bucket: str

    proxy_mode: bool

    @classmethod
    async def create(
        cls, remote_storage: FileStorage, local_storage: FileStorage
    ) -> Self:
        async with aiohttp.ClientSession() as session:
            local = await local_storage.get_bucket(session)

            local_appdata = local.get("appdata")
            if local_appdata is None:
                raise ValueError(
                    "The local appdata bucket is expected to be set"
                )
            local_user_bucket = AppData.parse(local_appdata).user_bucket

            remote = await remote_storage.get_bucket(session)
            remote_appdata = remote.get("appdata")
            if remote_appdata is None:
                remote_user_bucket = remote["bucket"]
            else:
                remote_user_bucket = AppData.parse(remote_appdata).user_bucket

        proxy_mode = (
            remote_storage.dial_url == local_storage.dial_url
            and remote_storage.api_key == local_storage.api_key
        )

        log.debug(f"proxy_mode: {proxy_mode}")

        return cls(
            remote_storage=remote_storage,
            remote_user_bucket=remote_user_bucket,
            local_storage=local_storage,
            local_user_bucket=local_user_bucket,
            local_appdata=local_appdata,
            proxy_mode=proxy_mode,
        )

    def get_remote_url(self, local_url: str) -> str:
        """
        user/app files:
            if proxy_mode:
                < files/LOCAL_USER_BUCKET/PATH
                > files/REMOTE_USER_BUCKET/PATH
            else:
                < files/LOCAL_USER_BUCKET/PATH
                > files/REMOTE_USER_BUCKET/LOCAL_USER_BUCKET/PATH
        """

        if self.proxy_mode:
            return local_url

        if not local_url.startswith(f"files/{self.local_user_bucket}/"):
            raise ValueError(f"Unexpected local URL: {local_url!r}")

        return f"files/{self.remote_user_bucket}/{local_url.removeprefix('files/')}"

    def get_local_url(self, remote_url: str) -> str:
        """
        user/app files uploaded from local to remote earlier (reverse of get_remote_url):
            if proxy_mode:
                < files/REMOTE_USER_BUCKET/PATH
                > files/LOCAL_USER_BUCKET/PATH
            else:
                < files/REMOTE_USER_BUCKET/LOCAL_USER_BUCKET/PATH
                > files/LOCAL_USER_BUCKET/PATH

        created by remote (user):
            < files/REMOTE_USER_BUCKET/appdata/REMOTE_APP_NAME/PATH
            > files/LOCAL_USER_BUCKET/appdata/LOCAL_APP_NAME/PATH

        created by remote (app):
            < files/REMOTE_APP_BUCKET/PATH
            > This means an application has a bug in it.
                We reject such URLs right away since there is no way
                to read an application file by a user.
        """

        if not remote_url.startswith(f"files/{self.remote_user_bucket}/"):
            raise ValueError(
                f"The remote file ({remote_url!r}) is expected "
                f"to be uploaded to the remote user bucket ({self.remote_user_bucket!r})"
            )

        remote_path = remote_url.removeprefix(
            f"files/{self.remote_user_bucket}/"
        )

        if remote_path.startswith("appdata/"):
            regex = r"appdata/([^/]+)/(.+)"
            match = re.match(regex, remote_path)
            if match is None:
                raise ValueError(f"Invalid remote appdata path: {remote_url!r}")
            _remote_app_name, path = match.groups()
            return f"files/{self.local_appdata}/{path}"

        if not self.proxy_mode:
            if remote_path.startswith(f"{self.local_user_bucket}/"):
                path = remote_path.removeprefix(f"{self.local_user_bucket}/")
                return f"files/{self.local_user_bucket}/{path}"

            raise ValueError(
                f"The remote file ({remote_url!r}) is expected to be uploaded either "
                "to remote appdata path or "
                "to a local user bucket subpath of remote user bucket."
            )
        else:
            return remote_url

    async def modify_request_attachment(self, attachment: dict) -> None:
        if (ref_url := attachment.get("reference_url")) and (
            local_ref_url := self.local_storage.to_dial_url(ref_url)
        ):
            remote_ref_url = self.get_remote_url(local_ref_url)
            attachment["reference_url"] = remote_ref_url

        if (url := attachment.get("url")) and (
            local_url := self.local_storage.to_dial_url(url)
        ):
            remote_url = self.get_remote_url(local_url)

            await download_and_upload_file(
                self.local_storage,
                local_url,
                self.remote_storage,
                remote_url,
                attachment.get("type"),
            )

            attachment["url"] = remote_url

            log.debug(
                f"uploaded from local to remote: from {local_url!r} to {remote_url!r}"
            )

    async def modify_response_attachment(self, attachment: dict) -> None:
        if (ref_url := attachment.get("reference_url")) and (
            remote_ref_url := self.remote_storage.to_dial_url(ref_url)
        ):
            local_ref_url = self.get_local_url(remote_ref_url)
            attachment["reference_url"] = local_ref_url

        if (url := attachment.get("url")) and (
            remote_url := self.remote_storage.to_dial_url(url)
        ):
            local_url = self.get_local_url(remote_url)

            await download_and_upload_file(
                self.remote_storage,
                remote_url,
                self.local_storage,
                local_url,
                attachment.get("type"),
            )
            attachment["url"] = local_url

            log.debug(
                f"uploaded from remote to local: from {remote_url!r} to {local_url!r}"
            )

    async def modify_request(self, request: dict) -> dict:
        if "messages" in request:
            messages = request["messages"]
            for message in messages:
                await modify_message(message, self.modify_request_attachment)
        return request

    async def modify_response_chunk(self, response: dict) -> dict:
        choices = response.get("choices")
        if choices is None:
            return response

        for choice in choices:
            if "delta" in choice:
                await modify_message(
                    choice["delta"], self.modify_response_attachment
                )

        return response

    async def modify_response(self, response: dict) -> dict:
        choices = response.get("choices")
        if choices is None:
            return response

        for choice in choices:
            if "message" in choice:
                await modify_message(
                    choice["message"], self.modify_response_attachment
                )

        return response


async def download_and_upload_file(
    src_storage: FileStorage,
    src_url: str,
    dest_storage: FileStorage,
    dest_url: str,
    content_type: str | None,
):
    log.debug(f"downloading from {src_url!r} and uploading to {dest_url!r}")

    if src_url != dest_url:
        if _is_directory(src_url):
            raise ValueError("Directories aren't yet supported")

        async with aiohttp.ClientSession() as session:
            content = await src_storage.download(src_url, session)
            await dest_storage.upload(dest_url, content_type, content, session)


async def modify_message(
    message: dict,
    modify_attachment: Callable[[dict], Coroutine[Any, Any, None]],
) -> None:
    cc = message.get("custom_content")
    if cc is None:
        return
    attachments = cc.get("attachments")
    if attachments is None:
        return
    for attachment in attachments:
        await modify_attachment(attachment)


def _is_directory(url: str) -> bool:
    return url[-1] == "/"
