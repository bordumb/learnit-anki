import base64
import json
from unittest.mock import patch

import pytest
import requests

from adapters.transcription.google_vision import GoogleVisionTranscriber


@pytest.fixture
def image(tmp_path):
    media = tmp_path / "selected.png"
    media.write_bytes(b"image content")
    return media


@pytest.fixture
def post():
    with (patch("adapters.transcription.google_vision.google.auth.default", return_value=(object(), "project")),
          patch("adapters.transcription.google_vision.AuthorizedSession") as session):
        yield session.return_value.__enter__.return_value.post


def vision_response(status, body):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(body).encode()
    return response


def test_vision_sends_selected_image_and_returns_text(post, image):
    post.return_value = vision_response(200, {"responses": [{"fullTextAnnotation": {"text": "週末"}}]})
    assert GoogleVisionTranscriber()._transcribe(image, "ja") == "週末"
    request = json.loads(post.call_args.kwargs["data"])["requests"][0]
    assert base64.b64decode(request["image"]["content"]) == image.read_bytes()
    assert request["imageContext"]["languageHints"] == ["ja"]


def test_vision_permission_error_retains_provider_reason(post, image):
    post.return_value = vision_response(403, {"error": {
        "message": "Cloud Vision API has not been used in this project before or it is disabled.",
        "status": "PERMISSION_DENIED",
        "details": [{"reason": "SERVICE_DISABLED"}],
    }})
    with pytest.raises(RuntimeError, match=r"403 SERVICE_DISABLED.*Cloud Vision API has not been used"):
        GoogleVisionTranscriber()._transcribe(image, "ja")


def test_vision_connection_error_offers_on_device_option(post, image):
    post.side_effect = requests.exceptions.ConnectionError("write operation timed out")
    with pytest.raises(RuntimeError, match="Check your network.*Read on Mac"):
        GoogleVisionTranscriber()._transcribe(image, "ja")


def test_vision_rejects_oversized_request_before_connecting(post, image, monkeypatch):
    monkeypatch.setattr(GoogleVisionTranscriber, "max_request_bytes", 40)
    with pytest.raises(ValueError, match="too large"):
        GoogleVisionTranscriber()._transcribe(image, "ja")
    post.assert_not_called()
