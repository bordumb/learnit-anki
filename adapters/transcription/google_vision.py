import asyncio
import base64
import json
from pathlib import Path

import google.auth
from google.auth.exceptions import TransportError
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials
from requests.exceptions import ConnectionError, Timeout


class GoogleVisionTranscriber:
    """Read the chosen image region with document OCR."""

    url = "https://vision.googleapis.com/v1/images:annotate"
    scopes = ("https://www.googleapis.com/auth/cloud-platform",)
    max_request_bytes = 10_000_000

    def __init__(self, credentials_path: str | None = None):
        self.credentials_path = credentials_path

    async def transcribe(self, media: Path, language: str) -> str:
        return await asyncio.to_thread(self._transcribe, media, language)

    def _transcribe(self, media: Path, language: str) -> str:
        size = media.stat().st_size
        if 4 * ((size + 2) // 3) >= self.max_request_bytes:
            raise self._oversized_image()
        image = base64.b64encode(media.read_bytes()).decode("ascii")
        payload = json.dumps({"requests": [{
            "image": {"content": image},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            "imageContext": {"languageHints": [language]},
        }]}).encode("utf-8")
        if len(payload) >= self.max_request_bytes:
            raise self._oversized_image()

        try:
            if self.credentials_path:
                credentials = Credentials.from_service_account_file(
                    self.credentials_path, scopes=self.scopes
                )
            else:
                credentials, _ = google.auth.default(scopes=self.scopes)
            with AuthorizedSession(credentials, refresh_timeout=15) as session:
                response = session.post(
                    self.url, data=payload, headers={"Content-Type": "application/json"},
                    timeout=(30, 60),
                )
        except (ConnectionError, Timeout, TransportError) as error:
            raise RuntimeError(
                "Could not complete the request to Google Cloud Vision. Check your network "
                "connection, try a smaller selection, or choose Read on Mac."
            ) from error

        if not response.ok:
            try:
                problem = response.json().get("error", {})
            except ValueError:
                problem = {}
            hint = (" Check that Cloud Vision API is enabled, billing is active, and the "
                    "configured credentials have access to the Google Cloud project."
                    if response.status_code == 403 else "")
            if problem.get("message") or hint:
                self._raise_api_error(problem, response.status_code, hint)
            response.raise_for_status()
        result = response.json()["responses"][0]
        if "error" in result:
            self._raise_api_error(result["error"])
        return result.get("fullTextAnnotation", {}).get("text", "")

    @staticmethod
    def _oversized_image() -> ValueError:
        return ValueError(
            "This image is too large to send to Google Cloud Vision. "
            "Choose a smaller selection or use Read on Mac."
        )

    @staticmethod
    def _raise_api_error(problem: dict, status_code: int | None = None, hint: str = "") -> None:
        reason = next((detail["reason"] for detail in problem.get("details", [])
                       if detail.get("reason")), None)
        code = " ".join(str(value) for value in (status_code, reason or problem.get("status")) if value)
        label = f"Google Cloud Vision ({code})" if code else "Google Cloud Vision"
        raise RuntimeError(f"{label}: {problem.get('message') or 'Request rejected.'}{hint}")
