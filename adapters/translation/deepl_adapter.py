# adapters/translation/deepl_adapter.py
import httpx
from typing import Optional
from core.domain.interfaces import TranslationService
from core.domain.models import Translation
import logging

logger = logging.getLogger(__name__)

class DeepLTranslationAdapter(TranslationService):
    """
    TranslationService implementation using the DeepL API.
    Handles free vs paid API endpoints based on the key format.
    """

    def __init__(self, api_key: str):
        """
        Initializes the DeepL adapter.

        Args:
            api_key: Your DeepL API key.
        """
        if not api_key:
            raise ValueError("DeepL API key is required.")
        self.api_key = api_key
        # Determine API endpoint based on key suffix
        if api_key.endswith(":fx"):
            self.base_url = "https://api-free.deepl.com/v2"
            logger.info("Using DeepL Free API endpoint.")
        else:
            self.base_url = "https://api.deepl.com/v2"
            logger.info("Using DeepL Pro API endpoint.")

    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Optional[Translation]:
        """
        Translates text using the DeepL API.

        Args:
            text: The text to translate.
            source_lang: The source language code (e.g., 'fr').
            target_lang: The target language code (e.g., 'en').

        Returns:
            A Translation object, or None if translation fails.
        """
        if not text:
            logger.warning("Translate called with empty text.")
            return None

        # DeepL expects uppercase language codes (e.g., 'FR', 'EN-US')
        # We assume simple 2-letter codes for now, adjust if more specific codes needed
        params = {
            'auth_key': self.api_key,
            'text': text,
            'source_lang': source_lang.upper(),
            'target_lang': target_lang.upper()
        }

        logger.info(f"Requesting DeepL translation: {source_lang.upper()} -> {target_lang.upper()} for text: '{text[:50]}...'")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client: # Add timeout
                response = await client.post(f"{self.base_url}/translate", data=params)
                response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
                data = response.json()

            if not data or 'translations' not in data or not data['translations']:
                logger.error(f"DeepL response missing 'translations'. Response: {data}")
                return None

            translated_text = data['translations'][0]['text']
            detected_source_lang = data['translations'][0].get('detected_source_language', source_lang.upper()) # Use provided if not detected

            logger.info(f"DeepL translation successful. Detected source: {detected_source_lang}")

            return Translation(
                text=translated_text,
                target_language=target_lang, # Set correctly based on input
                provider="deepl",
                confidence=None # DeepL doesn't provide confidence score in V2
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"DeepL API request failed: {e.response.status_code} - {e.response.text}")
            # Specific handling for common errors
            if e.response.status_code == 403:
                logger.error("Authentication failed. Check your DeepL API key.")
            elif e.response.status_code == 456:
                 logger.error("DeepL Quota exceeded.")
            return None
        except httpx.RequestError as e:
            logger.error(f"DeepL request failed: Network error - {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during DeepL translation: {e}")
            return None
