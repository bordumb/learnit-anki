# adapters/translation/openai_adapter.py
import openai
from typing import Optional
from core.domain.interfaces import TranslationError, TranslationService
from core.domain.models import Translation
import logging

logger = logging.getLogger(__name__)

class OpenAITranslationAdapter(TranslationService):
    """
    TranslationService implementation using OpenAI's GPT models (e.g., GPT-4o-mini).
    Potentially more context-aware than traditional translation services.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initializes the OpenAI adapter.

        Args:
            api_key: Your OpenAI API key.
            model: The OpenAI model identifier (e.g., "gpt-4o-mini").
        """
        if not api_key:
            raise ValueError("OpenAI API key is required.")
        # Use AsyncOpenAI for compatibility with async use cases
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        logger.info(f"Using OpenAI translation model: {self.model}")

    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Optional[Translation]:
        """
        Translates text using the specified OpenAI model.

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

        # Construct a clear prompt for the LLM
        prompt = f"""Translate the following text from {source_lang} to {target_lang}.
Provide ONLY the translated text, without any introductory phrases, explanations, or quotation marks.

Original ({source_lang}): "{text}"

Translation ({target_lang}):"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=int(len(text) * 1.5) + 50,
            )
        except openai.APITimeoutError as error:
            raise TranslationError("The OpenAI translation request timed out. Try again.") from error
        except openai.APIConnectionError as error:
            raise TranslationError(
                "Could not reach OpenAI for translation. Check your network connection."
            ) from error
        except openai.APIStatusError as error:
            if error.status_code == 401:
                hint = "Check OPENAI_API_KEY in the project’s .env file."
            elif error.status_code == 403:
                hint = f"Check that your OpenAI project can use {self.model}."
            elif error.status_code == 429 and error.code == "insufficient_quota":
                hint = "Check billing and API credits for your OpenAI project."
            elif error.status_code == 429:
                hint = "The API rate limit was reached. Wait a moment and try again."
            elif error.status_code == 404:
                hint = f"Model {self.model} is unavailable for this OpenAI project."
            else:
                hint = "Try again or enter a translation manually."
            raise TranslationError(f"OpenAI translation failed (HTTP {error.status_code}). {hint}") from error

        if not response.choices:
            raise TranslationError("OpenAI returned no translation.")
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise TranslationError("The OpenAI translation was cut off. Try a shorter passage.")
        translated_text = (choice.message.content or "").strip().strip('"').strip()
        if not translated_text:
            raise TranslationError("OpenAI returned no translation.")

        return Translation(text=translated_text, target_language=target_lang, provider=f"openai-{self.model}")
