import pytest
import httpx
from httpx import Response
from httpx._exceptions import HTTPStatusError
from app.core.providers.base import BaseProvider
from loguru import logger
import re

class MockProvider(BaseProvider):
    async def complete(self, *, prompt: str, **kwargs):
        pass

    async def complete_json(self, *, prompt: str, **kwargs):
        raise NotImplementedError

@pytest.mark.asyncio
async def test_retry_on_malformed_json_logs():
    # Simulating a provider with malformed JSON responses
    async def transport(request):
        return Response(200, text='{"malformed_json": "missing_end_brace"', request=request)
    
    transport = httpx.MockTransport(transport)
    provider = MockProvider(api_key="fake_key", model="dummy-model")
    provider._client = httpx.AsyncClient(transport=transport)

    with logger.catch() as log_capture:
        try:
            await provider._make_request("GET", "http://example.com")
        except httpx.HTTPStatusError:
            pass

    error_logs = [rec["message"] for rec in log_capture.records if rec["level"].name == "WARNING"]
    retry_logs = [log for log in error_logs if re.search("HTTP request retry", log)]

    assert len(retry_logs) == 3, f"Expected 3 retry logs, got {len(retry_logs)}"

