import json
import logging
from urllib.parse import urlparse

from aidial_sdk.telemetry.init import init_telemetry
from aidial_sdk.telemetry.types import TelemetryConfig
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from openai import AsyncAzureOpenAI, AsyncStream, BaseModel, Timeout
from openai.types import CreateEmbeddingResponse
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk

from aidial_adapter_dial.transformer import AttachmentTransformer
from aidial_adapter_dial.utils.env import get_env
from aidial_adapter_dial.utils.exceptions import (
    HTTPException,
    dial_exception_decorator,
)
from aidial_adapter_dial.utils.log_config import configure_loggers
from aidial_adapter_dial.utils.reflection import call_with_extra_body
from aidial_adapter_dial.utils.sse_stream import to_openai_sse_stream
from aidial_adapter_dial.utils.storage import FileStorage
from aidial_adapter_dial.utils.streaming import (
    amap_stream,
    generate_stream,
    map_stream,
)

app = FastAPI()

init_telemetry(app, TelemetryConfig())
configure_loggers()

log = logging.getLogger(__name__)
is_debug = log.isEnabledFor(logging.DEBUG)

UPSTREAM_KEY_HEADER = "X-UPSTREAM-KEY"
UPSTREAM_ENDPOINT_HEADER = "X-UPSTREAM-ENDPOINT"

LOCAL_DIAL_URL = get_env("DIAL_URL")

DEFAULT_TIMEOUT = Timeout(600, connect=10)


def get_hostname(url: str) -> str:
    parsed_url = urlparse(url)
    hostname = f"{parsed_url.scheme}://{parsed_url.netloc}"
    return hostname


class AzureClient(BaseModel):
    client: AsyncAzureOpenAI
    attachment_transformer: AttachmentTransformer

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    async def parse(
        cls, request: Request, deployment_id: str, endpoint_name: str
    ) -> "AzureClient":

        body = await request.json()
        headers = request.headers.mutablecopy()
        query_params = request.query_params

        if is_debug:
            log.debug(f"request.body: {body}")
            log.debug(f"request.headers: {headers}")
            log.debug(f"request.params: {query_params}")

        local_dial_api_key = headers.get("api-key", None)
        if not local_dial_api_key:
            raise HTTPException(
                status_code=400,
                message="The 'api-key' request header is missing",
            )

        remote_dial_api_key = headers.get(UPSTREAM_KEY_HEADER, None)
        if not remote_dial_api_key:
            raise HTTPException(
                status_code=400,
                message=f"The {UPSTREAM_KEY_HEADER!r} request header is missing",
            )

        upstream_endpoint = headers.get(UPSTREAM_ENDPOINT_HEADER, None)
        if not upstream_endpoint:
            raise HTTPException(
                status_code=400,
                message=f"The {UPSTREAM_ENDPOINT_HEADER!r} request header is missing",
            )

        endpoint_suffix = f"/{deployment_id}/{endpoint_name}"
        if not upstream_endpoint.endswith(endpoint_suffix):
            raise HTTPException(
                status_code=400,
                message=f"The {UPSTREAM_ENDPOINT_HEADER!r} request header must end with {endpoint_suffix!r}",
            )
        upstream_endpoint = upstream_endpoint.removesuffix(f"/{endpoint_name}")

        client = AsyncAzureOpenAI(
            base_url=upstream_endpoint,
            api_key=remote_dial_api_key,
            api_version=query_params.get("api-version"),
            timeout=DEFAULT_TIMEOUT,
        )

        attachment_transformer = await AttachmentTransformer.create(
            local_storage=FileStorage(
                dial_url=LOCAL_DIAL_URL,
                api_key=local_dial_api_key,
            ),
            remote_storage=FileStorage(
                dial_url=get_hostname(upstream_endpoint),
                api_key=remote_dial_api_key,
            ),
        )

        return cls(
            client=client,
            attachment_transformer=attachment_transformer,
        )


@app.post("/openai/deployments/{deployment_id:path}/embeddings")
@dial_exception_decorator
async def embeddings_proxy(request: Request, deployment_id: str):
    body = await request.json()
    az_client = await AzureClient.parse(request, deployment_id, "embeddings")

    response: CreateEmbeddingResponse = await call_with_extra_body(
        az_client.client.embeddings.create, body
    )

    return response.to_dict()


@app.post("/openai/deployments/{deployment_id:path}/chat/completions")
@dial_exception_decorator
async def chat_completions_proxy(request: Request, deployment_id: str):

    az_client = await AzureClient.parse(
        request, deployment_id, "chat/completions"
    )

    transformer = az_client.attachment_transformer

    body = await request.json()
    body = await transformer.modify_request(body)

    if is_debug:
        log.debug(f"request.body transformed: {body}")

    response: AsyncStream[ChatCompletionChunk] | ChatCompletion = (
        await call_with_extra_body(
            az_client.client.chat.completions.create, body
        )
    )

    if isinstance(response, AsyncStream):

        async def modify_chunk(chunk: dict) -> dict:
            chunk = await transformer.modify_response_chunk(chunk)
            if is_debug:
                log.debug(f"chunk: {json.dumps(chunk)}")
            return chunk

        chunk_stream = map_stream(lambda obj: obj.to_dict(), response)
        return StreamingResponse(
            to_openai_sse_stream(
                amap_stream(modify_chunk, generate_stream(chunk_stream))
            ),
            media_type="text/event-stream",
        )
    else:
        resp = response.to_dict()
        resp = await transformer.modify_response(resp)
        if is_debug:
            log.debug(f"response: {json.dumps(resp)}")
        return resp


@app.get("/health")
def health():
    return {"status": "ok"}
