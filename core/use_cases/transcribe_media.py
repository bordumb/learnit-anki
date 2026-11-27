from dataclasses import dataclass
from pathlib import Path

from core.domain.interfaces import TranscriptionService


@dataclass(frozen=True)
class CardDraft:
    text: str
    language: str
    source: str


class TranscribeMediaUseCase:
    """Read one selected image or audio clip into a draft for review."""

    def __init__(self, transcriber: TranscriptionService):
        self.transcriber = transcriber

    async def execute(
        self,
        media: Path,
        language: str,
        source: str | None = None,
    ) -> CardDraft:
        text = await self.transcriber.transcribe(media, language)
        return CardDraft(text=text.strip(), language=language, source=source or media.name)
