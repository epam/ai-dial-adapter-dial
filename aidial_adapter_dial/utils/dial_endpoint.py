from typing import Literal
from urllib.parse import urlsplit

from aidial_sdk.exceptions import InvalidRequestError
from openai import BaseModel


class DialEndpoint(BaseModel):
    dial_url: str
    deployment_id: str
    type_: Literal["chat", "embedding"]

    @classmethod
    def parse(cls, url: str) -> "DialEndpoint":
        parsed_url = urlsplit(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise InvalidRequestError(
                f"Upstream endpoint must be an absolute URL: {url!r}"
            )

        dial_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        segments = [s for s in parsed_url.path.split("/") if s]

        if segments[0:2] != ["openai", "deployments"]:
            raise InvalidRequestError(
                f"Cannot parse the upstream endpoint: {url!r}"
            )

        if segments[-2:] == ["chat", "completions"]:
            type_: Literal["chat", "embedding"] = "chat"
            deployment_segments = segments[2:-2]
        elif segments[-1] == "embeddings":
            type_ = "embedding"
            deployment_segments = segments[2:-1]
        else:
            raise InvalidRequestError(
                f"The upstream endpoint {url!r} is expected to end with "
                f"'/chat/completions' or '/embeddings'."
            )

        if not deployment_segments:
            raise InvalidRequestError(
                f"Missing deployment_id in upstream endpoint: {url!r}"
            )

        deployment_id = "/".join(deployment_segments)

        return cls(type_=type_, dial_url=dial_url, deployment_id=deployment_id)

    @property
    def azure_base_url(self) -> str:
        return f"{self.dial_url}/openai/deployments/{self.deployment_id}"

    @property
    def dial_base_url(self) -> str:
        return f"{self.dial_url}/v1/deployments/{self.deployment_id}"
