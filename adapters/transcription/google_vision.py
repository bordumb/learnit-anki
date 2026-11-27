import asyncio
import base64
from pathlib import Path

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials


class GoogleVisionTranscriber:
    """Read the chosen image region with document OCR."""

    url = "https://vision.googleapis.com/v1/images:annotate"
    scopes = ("https://www.googleapis.com/auth/cloud-platform",)

    def __init__(self, credentials_path: str | None = None):
        self.credentials_path = credentials_path

    async def transcribe(self, media: Path, language: str) -> str:
        return await asyncio.to_thread(self._transcribe, media, language)

    def _transcribe(self, media: Path, language: str) -> str:
        image = base64.b64encode(media.read_bytes()).decode("ascii")
        if self.credentials_path:
            credentials = Credentials.from_service_account_file(
                self.credentials_path, scopes=self.scopes
            )
        else:
            credentials, _ = google.auth.default(scopes=self.scopes)
        payload = {"requests": [{
            "image": {"content": image},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            "imageContext": {"languageHints": [language]},
        }]}
        with AuthorizedSession(credentials) as session:
            response = session.post(self.url, json=payload, timeout=(10, 60))
            response.raise_for_status()
            result = response.json()["responses"][0]
        if "error" in result:
            raise RuntimeError(result["error"].get("message", "Google Vision OCR failed"))
        return result.get("fullTextAnnotation", {}).get("text", "")
