# adapters/dictionary/openai_dictionary_adapter.py
import openai
import json
from typing import List, Optional
from core.domain.interfaces import DictionaryService
from core.domain.models import Word, WordBreakdown

import logging
from pathlib import Path

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "dictionary_adapter.log"

logger = logging.getLogger('DictionaryAdapterLogger')
logger.setLevel(logging.INFO)

# Prevent duplicate handlers if script is reloaded
if not logger.handlers:
    fh = logging.FileHandler(log_file)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

class OpenAIDictionaryAdapter(DictionaryService):
    """
    Uses OpenAI's GPT models (specifically GPT-4o-mini by default)
    for dictionary lookups and sentence analysis. Provides flexibility
    in handling different languages.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initializes the adapter with the OpenAI API key and desired model.

        Args:
            api_key: Your OpenAI API key.
            model: The OpenAI model identifier (e.g., "gpt-4o-mini").
        """
        # Use AsyncOpenAI for compatibility with async use cases
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model

    async def lookup_word(
        self,
        word: str,
        source_lang: str,
        target_lang: str
    ) -> Optional[Word]:
        """
        Looks up a single word using the OpenAI API.

        Args:
            word: The word to look up in the source language.
            source_lang: The language code of the input word (e.g., 'fr').
            target_lang: The language code for the definition (e.g., 'en').

        Returns:
            A Word object with details, or None if the lookup fails.
        """
        prompt = f"""Analyze this {source_lang} word: "{word}"

Provide JSON with:
{{
  "lemma": "base form of the word (lemma)",
  "pos": "part of speech (noun, verb, adj, etc.)",
  "definition": "concise definition in {target_lang} (max 5-7 words)"
}}"""

        logger.info(f"--- Looking up Word ---")
        logger.info(f"Word: '{word}', Source: {source_lang}, Target: {target_lang}")

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3 # Lower temperature for more factual responses
            )

            raw_json = response.choices[0].message.content
            logger.info(f"Raw API Response (lookup_word): {raw_json}")
            data = json.loads(raw_json)

            # Basic validation
            if not all(k in data for k in ['lemma', 'pos', 'definition']):
                logger.warning(f"Missing expected keys in response for word '{word}'. Response: {data}")
                return None

            return Word(
                text=word,
                lemma=data.get('lemma', word), # Fallback lemma to original word
                pos=data.get('pos', 'unknown'),
                definition=data['definition'], # Target language definition
                definition_native=None # Not requested in this method
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response for word '{word}'. Error: {e}\nRaw Response: {raw_json}")
            return None
        except Exception as e:
            logger.error(f"API call failed for word '{word}'. Error: {e}")
            return None


    async def analyze_sentence(
        self,
        sentence: str,
        source_lang: str,
        target_lang: str
    ) -> WordBreakdown:
        """
        Analyzes each word in a sentence using the OpenAI API.

        Requests lemma, part of speech, definition in the target language,
        and definition in the source language (native).

        Args:
            sentence: The sentence to analyze in the source language.
            source_lang: The language code of the input sentence (e.g., 'fr').
            target_lang: The language code for the primary definition (e.g., 'en').

        Returns:
            A WordBreakdown object containing a list of Word objects.
            Returns an empty WordBreakdown on failure.
        """
        prompt = f"""Analyze each word in this {source_lang} sentence:
"{sentence}"

Return a JSON object containing a single key "words", which holds an array. Each object in the array should have:
- "text": The original word from the sentence.
- "lemma": The base form (lemma) of the word.
- "pos": The part of speech (e.g., verb, noun, adj).
- "definition": A clear, dictionary-style definition in {target_lang}, suitable for a language learner. Include nuance if relevant.
- "definition_native": A clear, dictionary-style definition in {source_lang} (monolingual).

Example format:
{{
  "words": [
    {{
      "text": "comprenez",
      "lemma": "comprendre",
      "pos": "verb",
      "definition": "understand",
      "definition_native": "saisir par l'esprit"
    }},
    {{ ... next word ... }}
  ]
}}

Skip punctuation marks like commas, periods, quotes, etc."""

        logger.info(f"--- Analyzing Sentence ---")
        logger.info(f"Sentence: '{sentence}', Source: {source_lang}, Target: {target_lang}")

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3 # Lower temperature for more consistent structure
            )

            raw_json = response.choices[0].message.content
            logger.info(f"Raw API Response (analyze_sentence): {raw_json}")

            # Attempt to parse the JSON
            data = json.loads(raw_json)

            # Extract the list of words, expecting it under the "words" key
            word_list_data = data.get("words")
            if not isinstance(word_list_data, list):
                raise ValueError("Dictionary response is missing the words list.")

            # Create Word objects from the list
            words = []
            for word_data in word_list_data:
                # Check if it's a dictionary and has the essential 'text' key
                if isinstance(word_data, dict) and word_data.get('text'):
                    words.append(
                        Word(
                            text=word_data['text'],
                            lemma=word_data.get('lemma', word_data['text']), # Fallback lemma
                            pos=word_data.get('pos', 'unknown'),
                            definition=word_data.get('definition', ''), # Target lang def
                            definition_native=word_data.get('definition_native', '') # Source lang def
                        )
                    )
                else:
                    logger.warning(f"Skipping invalid word data item: {word_data}")

            if word_list_data and not words:
                raise ValueError("Dictionary response contains no usable words.")
            logger.info(f"Successfully parsed {len(words)} words for sentence: '{sentence}'")
            return WordBreakdown(words=words)

        except Exception as error:
            raise RuntimeError(f"Word breakdown analysis failed: {error}") from error
