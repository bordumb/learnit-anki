from pathlib import Path

from openai import AsyncOpenAI


class OpenAISpeechTranscriber:
    """Transcribe an audio clip into its source language."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def transcribe(self, media: Path, language: str) -> str:
        # GPT-Transcribe takes a list, while the older models take one language.
        language_hint = {"languages": [language]} if self.model == "gpt-transcribe" else {"language": language}
        async with AsyncOpenAI(api_key=self.api_key, timeout=90) as client:
            with media.open("rb") as audio:
                result = await client.audio.transcriptions.create(
                    model=self.model,
                    file=audio,
                    extra_body=language_hint,
                )
        return result.text
