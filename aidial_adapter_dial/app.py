import json
import logging
from collections.abc import Mapping
from typing import Protocol

from aidial_sdk.exceptions import InvalidRequestError
from aidial_sdk.telemetry.init import init_telemetry
from aidial_sdk.telemetry.types import TelemetryConfig
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from openai import AsyncAzureOpenAI, AsyncStream, BaseModel
from openai.types import CreateEmbeddingResponse
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from pydantic import ConfigDict

from aidial_adapter_dial.config import AppConfig
from aidial_adapter_dial.transformer import AttachmentTransformer
from aidial_adapter_dial.utils.dial_endpoint import DialEndpoint
from aidial_adapter_dial.utils.dict import censor_ci_dict
from aidial_adapter_dial.utils.exceptions import to_dial_exception
from aidial_adapter_dial.utils.http_client import get_http_client
from aidial_adapter_dial.utils.log_config import configure_loggers
from aidial_adapter_dial.utils.reflection import call_with_extra_body
from aidial_adapter_dial.utils.sse_stream import to_openai_sse_stream
from aidial_adapter_dial.utils.storage import FileStorage
from aidial_adapter_dial.utils.streaming import amap_stream, map_stream
from aidial_adapter_dial.utils.url import normalize_url

app = FastAPI()

init_telemetry(app, TelemetryConfig())
configure_loggers()

_log = logging.getLogger(__name__)
_is_debug = _log.isEnabledFor(logging.DEBUG)


_APP_CONFIG = AppConfig.from_env()


class _RequestLike(Protocol):
    @property
    def headers(self) -> Mapping[str, str]: ...

    @property
    def query_params(self) -> Mapping[str, str]: ...

    async def body(self) -> bytes: ...


UPSTREAM_KEY_HEADER = "X-UPSTREAM-KEY"
UPSTREAM_ENDPOINT_HEADER = "X-UPSTREAM-ENDPOINT"


class AzureClient(BaseModel):
    client: AsyncAzureOpenAI
    dial_client: AsyncAzureOpenAI
    attachment_transformer: AttachmentTransformer

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    async def parse(
        cls, conf: AppConfig, request: _RequestLike
    ) -> "AzureClient":
        headers = request.headers
        query_params = request.query_params

        if _is_debug:
            body = await request.body()
            _log.debug(f"request.body: {body}")
            secret_headers = ["api-key", "authorization", UPSTREAM_KEY_HEADER]
            _log.debug(
                f"request.headers: {censor_ci_dict(headers, secret_headers)}"
            )
            _log.debug(f"request.params: {query_params}")

        local_dial_api_key = headers.get("api-key", None)
        if not local_dial_api_key:
            raise InvalidRequestError("The 'api-key' request header is missing")

        upstream_endpoint = headers.get(UPSTREAM_ENDPOINT_HEADER, None)
        if not upstream_endpoint:
            raise InvalidRequestError(
                f"The {UPSTREAM_ENDPOINT_HEADER!r} request header is missing"
            )

        dial_endpoint = DialEndpoint.parse(upstream_endpoint)
        remote_dial_url = dial_endpoint.dial_url
        remote_dial_api_key = headers.get(UPSTREAM_KEY_HEADER, None)

        if not remote_dial_api_key:
            if normalize_url(remote_dial_url) != normalize_url(
                conf.local_dial_url
            ):
                raise InvalidRequestError(
                    f"Given that {UPSTREAM_KEY_HEADER!r} header is missing, "
                    f"it's expected that hostname of the upstream endpoint ({upstream_endpoint!r}) is "
                    f"the same as the local DIAL URL ({conf.local_dial_url!r}) "
                )

            local_dial_api_key = headers.get("api-key")
            if not local_dial_api_key:
                raise InvalidRequestError(
                    "The 'api-key' request header is missing"
                )

            remote_dial_api_key = local_dial_api_key

        extra_upstream_headers = {
            key: val
            for key in conf.headers_to_proxy
            if (val := headers.get(key)) is not None
        }

        client = AsyncAzureOpenAI(
            base_url=dial_endpoint.azure_base_url,
            api_key=remote_dial_api_key,
            # NOTE: defaulting missing api-version to an empty string, because
            # 1. openai library doesn't allow for a missing api-version
            # and a workaround for it would be a recreation of AsyncAzureOpenAI with a check disabled:
            # https://gitlab.deltixhub.com/Deltix/openai-apps/dial-interceptor-example/-/blob/62760a4c7a7be740b1c2bc60f14a0a568f31a0bc/aidial_interceptor_example/utils/azure.py#L1-5
            # 2. OpenAI adapter treats a missing api-version in the same way as an empty string and that's the only
            # place where api-version has any meaning, so the query param modification is safe.
            # https://github.com/epam/ai-dial-adapter-openai/blob/b462d1c26ce8f9d569b9c085a849206aad91becf/aidial_adapter_openai/app.py#L93
            api_version=query_params.get("api-version") or "",
            default_headers=extra_upstream_headers,
            http_client=get_http_client(),
        )

        dial_client = client.copy(base_url=dial_endpoint.dial_base_url)

        attachment_transformer = await AttachmentTransformer.create(
            local_storage=FileStorage(
                dial_url=conf.local_dial_url,
                api_key=local_dial_api_key,
            ),
            remote_storage=FileStorage(
                dial_url=remote_dial_url,
                api_key=remote_dial_api_key,
            ),
        )

        return cls(
            client=client,
            dial_client=dial_client,
            attachment_transformer=attachment_transformer,
        )


for endpoint in ["configuration"]:

    @app.get(f"/{endpoint}")
    @app.get("/openai/deployments/{deployment_id:path}/" + endpoint)
    async def get_endpoint_proxy(request: Request, endpoint=endpoint):
        az_client = await AzureClient.parse(_APP_CONFIG, request)
        return await az_client.dial_client.get(path=endpoint, cast_to=object)


for endpoint in ["tokenize", "truncate_prompt"]:

    @app.post(f"/{endpoint}")
    @app.post("/openai/deployments/{deployment_id:path}/" + endpoint)
    async def post_endpoint_proxy(request: Request, endpoint=endpoint):
        body = await request.json()
        az_client = await AzureClient.parse(_APP_CONFIG, request)
        return await az_client.dial_client.post(
            path=endpoint, cast_to=object, body=body
        )


@app.post("/embeddings")
@app.post("/openai/deployments/{deployment_id:path}/embeddings")
async def embeddings_proxy(request: Request):
    body = await request.json()
    az_client = await AzureClient.parse(_APP_CONFIG, request)
    response: CreateEmbeddingResponse = await call_with_extra_body(
        az_client.client.embeddings.create, body
    )
    return response.to_dict()


@app.post("/chat/completions")
@app.post("/openai/deployments/{deployment_id:path}/chat/completions")
async def chat_completions_proxy(request: Request):
    az_client = await AzureClient.parse(_APP_CONFIG, request)

    transformer = az_client.attachment_transformer

    body = await request.json()
    body = await transformer.modify_request(body)

    if _is_debug:
        _log.debug(f"request.body transformed: {body}")

    response: (
        AsyncStream[ChatCompletionChunk] | ChatCompletion
    ) = await call_with_extra_body(
        az_client.client.chat.completions.create, body
    )

    if isinstance(response, AsyncStream):

        async def modify_chunk(chunk: dict) -> dict:
            chunk = await transformer.modify_response_chunk(chunk)
            if _is_debug:
                _log.debug(f"chunk: {json.dumps(chunk)}")
            return chunk

        chunk_stream = map_stream(lambda obj: obj.to_dict(), response)
        return StreamingResponse(
            to_openai_sse_stream(amap_stream(modify_chunk, chunk_stream)),
            media_type="text/event-stream",
        )
    else:
        resp = response.to_dict()
        resp = await transformer.modify_response(resp)
        if _is_debug:
            _log.debug(f"response: {json.dumps(resp)}")
        return resp


@app.exception_handler(Exception)
def exception_handler(request: Request, e: Exception):
    dial_exception = to_dial_exception(e)

    _log.exception(
        f"Caught exception: {type(e).__module__}.{type(e).__name__}. "
        f"The exception converted to the dial exception: {dial_exception!r}."
    )

    fastapi_response = dial_exception.to_fastapi_response()
    return fastapi_response


@app.get("/health")
def health():
    return {"status": "ok"}
