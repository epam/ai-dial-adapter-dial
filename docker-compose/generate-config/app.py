import os
import re
import sys
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse, urlunparse

import httpx
import typer
from config import CoreConfig
from dotenv import load_dotenv
from pydantic import BaseModel as PydanticBaseModel


class BaseModel(PydanticBaseModel):
    class Config:
        extra = "allow"


class Pricing(BaseModel):
    unit: str
    prompt: Optional[str] = None
    completion: Optional[str] = None


class Limits(BaseModel):
    max_total_tokens: Optional[int] = None
    max_prompt_tokens: Optional[int] = None
    max_completion_tokens: Optional[int] = None


class Capabilities(BaseModel):
    scale_types: List[str]
    completion: bool
    chat_completion: bool
    embeddings: bool
    fine_tune: bool
    inference: bool


class Features(BaseModel):
    rate: bool
    tokenize: bool
    truncate_prompt: bool
    configuration: bool
    system_prompt: bool
    tools: bool
    seed: bool
    url_attachments: bool
    folder_attachments: bool


class Data(BaseModel):
    id: str
    model: Optional[str] = None
    display_name: Optional[str] = None
    icon_url: Optional[str] = None
    owner: str
    object: str
    status: str
    created_at: int
    updated_at: int
    features: Features
    defaults: Optional[Dict[str, Any]] = None
    lifecycle_status: Optional[str] = None
    capabilities: Optional[Capabilities] = None
    limits: Optional[Limits] = None
    pricing: Optional[Pricing] = None
    tokenizer_model: Optional[str] = None
    display_version: Optional[str] = None
    description: Optional[str] = None
    input_attachment_types: Optional[List[str]] = None
    max_input_attachments: Optional[int] = None


class RootObject(BaseModel):
    data: List[Data]
    object: str


def get_env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise ValueError(f"Environment variable {name!r} is not set")
    return value


def print_info(*args, **kwargs):
    print(*args, **kwargs, file=sys.stderr)


def modify_url(
    original_url: str, new_scheme: str, new_hostname: str, new_port: int
) -> str:
    parsed_url = urlparse(original_url)
    new_netloc = f"{new_hostname}:{new_port}" if new_port else new_hostname
    modified_url = parsed_url._replace(scheme=new_scheme, netloc=new_netloc)
    return urlunparse(modified_url)


load_dotenv()
REMOTE_DIAL_URL = get_env("REMOTE_DIAL_URL")
REMOTE_DIAL_API_KEY = get_env("REMOTE_DIAL_API_KEY")

app = typer.Typer()


@app.command()
def main(
    local_app_port: Optional[int] = None,
    deployment_id_regex: Optional[str] = None,
):
    regex: re.Pattern | None = None
    if deployment_id_regex is not None:
        regex = re.compile(deployment_id_regex, re.IGNORECASE)

    headers = {"api-key": REMOTE_DIAL_API_KEY}
    models_url = f"{REMOTE_DIAL_URL}/openai/models"
    applications_url = f"{REMOTE_DIAL_URL}/openai/applications"

    config = CoreConfig(
        {
            "routes": {},
            "keys": {
                "dial_api_key": {
                    "project": "TEST-PROJECT",
                    "role": "default",
                }
            },
        }
    )

    with httpx.Client() as client:
        response = client.get(models_url, headers=headers)
        models = RootObject.parse_obj(response.json())
        process_data(
            REMOTE_DIAL_URL,
            REMOTE_DIAL_API_KEY,
            models.data,
            config,
            "models",
            regex,
        )

        response = client.get(applications_url, headers=headers)
        applications = RootObject.parse_obj(response.json())
        process_data(
            REMOTE_DIAL_URL,
            REMOTE_DIAL_API_KEY,
            applications.data,
            config,
            "applications",
            regex,
        )

        if local_app_port is not None:
            config.add_application(
                "local-application",
                {
                    "displayName": "Locally hosted application",
                    "endpoint": f"http://host.docker.internal:{local_app_port}/openai/deployments/app/chat/completions",
                    "forwardAuthToken": True,
                    # Enable all kinds of attachments by default.
                    # The user will remove the ones that are not applicable.
                    "inputAttachmentTypes": ["*/*"],
                    "features": {
                        "urlAttachmentsSupported": True,
                        "folderAttachmentsSupported": True,
                    },
                },
            )

    config.print()


def process_data(
    upstream_base: str,
    upstream_key: str,
    data: List[Data],
    config: CoreConfig,
    key: Literal["models", "applications"],
    regex: Optional[re.Pattern] = None,
):
    data = [
        item
        for item in data
        if item.capabilities is None
        or item.capabilities.chat_completion
        or item.capabilities.embeddings
    ]

    n = len(data)
    print_info(f"\n{key} [{n}]:")

    for idx, item in enumerate(data, start=1):
        is_chat_model = (
            item.capabilities is None or item.capabilities.chat_completion
        )

        model_type = "chat" if is_chat_model else "embedding"

        endpoint = "chat/completions" if is_chat_model else "embeddings"

        if regex is not None and not regex.search(item.id):
            continue

        name = item.display_name or "NONAME"
        if item.display_version:
            name += f" ({item.display_version})"

        print_info(f"  {idx:>3}. {model_type:<10}. {item.id:<30}: {name}")

        endpoint_base = f"http://adapter-dial:5000/openai/deployments/{item.id}"

        icon_url = item.icon_url
        if icon_url is not None:
            icon_url = modify_url(icon_url, "http", "localhost", 3001)

        model = {
            "type": model_type,
            "displayName": f"{item.display_name} (Adapter)",
            "displayVersion": item.display_version,
            "description": item.description,
            "tokenizerModel": item.tokenizer_model,
            "iconUrl": icon_url,
            "endpoint": f"{endpoint_base}/{endpoint}",
            "forwardAuthToken": True,
            "upstreams": [
                {
                    "endpoint": f"{upstream_base}/openai/deployments/{item.id}/{endpoint}",
                    "key": upstream_key,
                }
            ],
            "features": {
                "rateEndpoint": (
                    f"{endpoint_base}/rate" if item.features.rate else None
                ),
                "tokenizeEndpoint": (
                    f"{endpoint_base}/tokenize"
                    if item.features.tokenize
                    else None
                ),
                "truncatePromptEndpoint": (
                    f"{endpoint_base}/truncate_prompt"
                    if item.features.truncate_prompt
                    else None
                ),
                "configurationEndpoint": (
                    f"{endpoint_base}/configuration"
                    if item.features.configuration
                    else None
                ),
                "systemPromptSupported": item.features.system_prompt,
                "toolsSupported": item.features.tools,
                "seedSupported": item.features.seed,
                "urlAttachmentsSupported": item.features.url_attachments,
                "folderAttachmentsSupported": item.features.folder_attachments,
            },
            "maxInputAttachments": item.max_input_attachments,
            "inputAttachmentTypes": item.input_attachment_types,
            "defaults": item.defaults,
            "limits": {
                "maxPromptTokens": (
                    item.limits.max_prompt_tokens if item.limits else None
                ),
                "maxTotalTokens": (
                    item.limits.max_total_tokens if item.limits else None
                ),
                "maxCompletionTokens": (
                    item.limits.max_completion_tokens if item.limits else None
                ),
            },
            "pricing": {
                "unit": item.pricing.unit if item.pricing else None,
                "prompt": item.pricing.prompt if item.pricing else None,
                "completion": (
                    item.pricing.completion if item.pricing else None
                ),
            },
        }

        # Note that
        # * even applications are declared as models,
        #   because only models have "upstreams" property.
        # * the local deployment id is different from the remote deployment id
        #   to highlight that the two are not required to be the same.
        config.add_model(f"{item.id}-adapter", model)


if __name__ == "__main__":
    typer.run(main)
