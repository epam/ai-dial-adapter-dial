import os

import httpx
import pytest_asyncio


def pytest_configure():
    os.environ["DIAL_URL"] = "dummy"


@pytest_asyncio.fixture
async def test_app():
    from aidial_adapter_dial.app import app

    async with httpx.AsyncClient(
        app=app, base_url="http://test-app.com"
    ) as client:
        yield client
