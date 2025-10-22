# adapters/translation/openai_adapter.py
import openai
from typing import Optional
from core.domain.interfaces import TranslationService
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

        logger.info(f"Requesting OpenAI translation ({self.model}): {source_lang} -> {target_lang} for text: '{text[:50]}...'")

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,  # Lower temperature for more deterministic translation
                max_tokens=int(len(text) * 1.5) + 50 # Estimate max tokens needed
            )

            # Extract the translated text, stripping any extra whitespace/quotes
            translated_text = response.choices[0].message.content.strip().strip('"')

            if not translated_text:
                logger.warning(f"OpenAI returned an empty translation for: '{text}'")
                return None

            logger.info("OpenAI translation successful.")

            return Translation(
                text=translated_text,
                target_language=target_lang, # Set correctly based on input
                provider=f"openai-{self.model}",
                confidence=None # LLMs don't typically provide a confidence score
            )

        except openai.APIError as e:
            logger.error(f"OpenAI API request failed: {e.status_code} - {e.message}")
            if e.status_code == 401:
                 logger.error("Authentication failed. Check your OpenAI API key.")
            elif e.status_code == 429:
                 logger.error("OpenAI Rate limit exceeded or quota reached.")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during OpenAI translation: {e}")
            return None
