import logging
from typing import Self

import aiohttp
from pydantic import BaseModel

from aidial_adapter_dial.utils.app_data import AppData
from aidial_adapter_dial.utils.storage import FileStorage

log = logging.getLogger(__name__)


class AttachmentTransformer(BaseModel):
    local_storage: FileStorage
    local_bucket: str
    local_app_data: str

    remote_storage: FileStorage
    remote_bucket: str

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
            local_bucket = AppData.parse(local_appdata).user_bucket

            remote = await remote_storage.get_bucket(session)

        return cls(
            remote_storage=remote_storage,
            remote_bucket=remote["bucket"],
            local_storage=local_storage,
            local_bucket=local_bucket,
            local_app_data=local_appdata,
        )

    async def get_remote_url(self, local_url: str) -> str:
        """
        local_url:
            - files/LOCAL_BUCKET/PATH
        remote_url:
            - files/REMOTE_BUCKET/LOCAL_BUCKET/PATH
        """

        local_bucket = self.local_bucket
        remote_bucket = self.remote_bucket

        if not local_url.startswith(f"files/{local_bucket}/"):
            raise ValueError(f"Unexpected local URL: {local_url!r}")

        return f"files/{remote_bucket}/{local_url.removeprefix('files/')}"

    async def get_local_url(
        self, remote_url: str, session: aiohttp.ClientSession
    ) -> str:
        """
        remote_url (prefixed by files/REMOTE_BUCKET):
            original:
                - /PATH
            reiterated:
                - /LOCAL_BUCKET/PATH
        local_url (try with files/LOCAL_BUCKET/, otherwise with files/LOCAL_BUCKET/appdata/THIS_APP_NAME/):
            original:
                - /PATH
            reiterated:
                - /PATH
        """

        remote_bucket = self.remote_bucket

        if not remote_url.startswith(f"files/{remote_bucket}/"):
            raise ValueError(f"Unexpected remote URL: {remote_url!r}")

        remote_url = remote_url.removeprefix(f"files/{remote_bucket}/")
        remote_url = remote_url.removeprefix(f"{self.local_bucket}/")

        local_url = f"files/{self.local_bucket}/{remote_url}"
        if await self.local_storage.is_accessible(local_url, session):
            return local_url

        local_url = f"files/{self.local_app_data}/{remote_url}"
        if await self.local_storage.is_accessible(local_url, session):
            return local_url

        raise ValueError(
            f"Can't find the local URL for the remote URL: {remote_url!r}"
        )

    async def upload_and_download_file(
        self,
        src_storage: FileStorage,
        src_url: str,
        dest_storage: FileStorage,
        dest_url: str,
        content_type: str | None,
        session: aiohttp.ClientSession,
    ):
        content = await src_storage.download(src_url, session)
        await dest_storage.upload(dest_url, content_type, content, session)

    async def modify_request_attachment(self, attachment: dict) -> None:
        if "url" not in attachment:
            return None

        local_url = self.local_storage.to_dial_url(attachment["url"])
        if local_url is None:
            return None

        remote_url = await self.get_remote_url(local_url)
        content_type = attachment.get("type")

        async with aiohttp.ClientSession() as session:
            await self.upload_and_download_file(
                self.local_storage,
                local_url,
                self.remote_storage,
                remote_url,
                content_type,
                session,
            )

        attachment["url"] = remote_url

        log.debug(
            f"uploaded from local to remote: from {local_url!r} to {remote_url!r}"
        )

    async def modify_response_attachment(self, attachment: dict) -> None:
        if "url" not in attachment:
            return None

        remote_url = self.remote_storage.to_dial_url(attachment["url"])
        if remote_url is None:
            return None

        async with aiohttp.ClientSession() as session:
            local_url = await self.get_local_url(remote_url, session)
            content_type = attachment.get("type")

            await self.upload_and_download_file(
                self.remote_storage,
                remote_url,
                self.local_storage,
                local_url,
                content_type,
                session,
            )
            attachment["url"] = local_url

            log.debug(
                f"uploaded from remote to local: from {remote_url!r} to {local_url!r}"
            )

    async def modify_request(self, request: dict) -> dict:
        if "messages" in request:
            messages = request["messages"]
            for message in messages:
                await self.modify_message(
                    message, self.modify_request_attachment
                )
        return request

    async def modify_message(self, message: dict, modify_attachment) -> None:
        cc = message.get("custom_content")
        if cc is None:
            return
        attachments = cc.get("attachments")
        if attachments is None:
            return
        for attachment in attachments:
            await modify_attachment(attachment)

    async def modify_response_chunk(self, response: dict) -> dict:
        choices = response.get("choices")
        if choices is None:
            return response

        for choice in choices:
            if "delta" in choice:
                await self.modify_message(
                    choice["delta"], self.modify_response_attachment
                )

        return response

    async def modify_response(self, response: dict) -> dict:
        choices = response.get("choices")
        if choices is None:
            return response

        for choice in choices:
            if "message" in choice:
                await self.modify_message(
                    choice["message"], self.modify_response_attachment
                )

        return response
