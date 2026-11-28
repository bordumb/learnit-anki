from unittest.mock import AsyncMock

import httpx
import openai
import pytest

from adapters.translation.openai_adapter import OpenAITranslationAdapter
from core.domain.interfaces import TranslationError


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "code", "message"), [
    (401, "invalid_api_key", "OPENAI_API_KEY"),
    (429, "insufficient_quota", "billing and API credits"),
    (429, "rate_limit_exceeded", "rate limit"),
])
async def test_openai_translation_reports_actionable_error_without_provider_body(status, code, message):
    adapter = OpenAITranslationAdapter("test-key")
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status, request=request)
    error = openai.APIStatusError("private provider diagnostic", response=response, body={"code": code})
    adapter.client.chat.completions.create = AsyncMock(side_effect=error)
    async with adapter.client:
        with pytest.raises(TranslationError, match=message) as failure:
            await adapter.translate("次の駅で乗り換えます。", "ja", "en")
    assert "private provider diagnostic" not in str(failure.value)


@pytest.mark.asyncio
async def test_openai_translation_surfaces_connection_error():
    adapter = OpenAITranslationAdapter("test-key")
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    adapter.client.chat.completions.create = AsyncMock(side_effect=openai.APIConnectionError(request=request))
    async with adapter.client:
        with pytest.raises(TranslationError, match="Could not reach OpenAI"):
            await adapter.translate("次の駅で乗り換えます。", "ja", "en")
