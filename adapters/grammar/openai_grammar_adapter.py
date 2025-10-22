# adapters/grammar/openai_grammar_adapter.py
import openai
import json
from typing import List, Optional
from core.domain.interfaces import GrammarService
from core.domain.models import GrammarNote
import logging

logger = logging.getLogger(__name__)

class OpenAIGrammarAdapter(GrammarService):
    """
    Uses OpenAI's GPT models to analyze a sentence for notable grammar points,
    idioms, metaphors, or cultural phrases relevant to the specified language.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initializes the adapter with the OpenAI API key and model.

        Args:
            api_key: Your OpenAI API key.
            model: The OpenAI model identifier (e.g., "gpt-4o-mini").
        """
        if not api_key:
            raise ValueError("OpenAI API key is required.")
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        logger.info(f"Using OpenAI grammar model: {self.model}")

    async def explain_grammar(
        self,
        sentence: str,
        language: str # Language code, e.g., 'fr', 'de'
    ) -> List[GrammarNote]:
        """
        Generates grammar explanations for a given sentence in a specific language.

        Args:
            sentence: The sentence to analyze.
            language: The language code of the sentence (e.g., 'fr', 'de').

        Returns:
            A list of GrammarNote objects, or an empty list if analysis fails or finds nothing notable.
        """
        if not sentence:
            logger.warning("Explain_grammar called with empty sentence.")
            return []

        # Construct the prompt using the provided language
        prompt = f"""Analyze the following {language} sentence for a language learner:
"{sentence}"

Identify and explain any notable grammar points, common idioms, metaphors, or cultural nuances present.
Focus on what would be useful for someone learning {language}.
If the sentence is grammatically simple, briefly explain the main verb tense or structure.

Return ONLY a JSON object with a single key "notes". The value should be an array of objects, where each object has:
- "title": A short, descriptive title (e.g., "Verb Tense: Passé Composé", "Idiom: 'Avoir le cafard'").
- "explanation": A concise explanation tailored for a language learner.
- "examples": (Optional) An array containing one or two short example sentences demonstrating the point, preferably different from the input sentence.

Example format:
{{
  "notes": [
    {{
      "title": "Idiom: 'Avoir le cafard'",
      "explanation": "Means 'to feel down' or 'to have the blues'. Literally 'to have the cockroach'.",
      "examples": ["Il pleut aujourd'hui, j'ai un peu le cafard."]
    }},
    {{
      "title": "Verb Tense: Présent",
      "explanation": "'Mange' is the present tense conjugation of the verb 'manger' (to eat) for 'je' (I)."
    }}
  ]
}}

If no particularly notable grammar points or phrases are found, return {{"notes": []}}.
Do not include any text outside the JSON object.
"""

        logger.info(f"Requesting OpenAI grammar analysis ({self.model}) for language '{language}': '{sentence[:50]}...'")

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.4 # Slightly creative but still factual
            )

            raw_json = response.choices[0].message.content
            logger.debug(f"Raw API Response (explain_grammar): {raw_json}") # Log raw response at debug level

            data = json.loads(raw_json)

            # Extract the list from the "notes" key, default to empty list if key missing
            note_list_data = data.get('notes', [])

            if not isinstance(note_list_data, list):
                 logger.warning(f"Expected a list under 'notes' key, but got {type(note_list_data)}. Response: {data}")
                 note_list_data = []

            # Process the notes, handling potential malformed entries
            notes = []
            for note_data in note_list_data:
                if isinstance(note_data, dict) and note_data.get('title') and note_data.get('explanation'):
                    notes.append(
                        GrammarNote(
                            title=note_data['title'],
                            explanation=note_data['explanation'],
                            examples=note_data.get('examples', []) # Handle optional examples
                        )
                    )
                elif isinstance(note_data, str):
                     # Handle unexpected case where AI returns list of strings instead of objects
                    logger.warning(f"Received string instead of object in notes list: '{note_data}'")
                    notes.append(
                        GrammarNote(
                            title="Grammar Note",
                            explanation=note_data,
                            examples=[]
                        )
                    )
                else:
                    logger.warning(f"Skipping invalid grammar note data item: {note_data}")

            logger.info(f"Successfully generated {len(notes)} grammar notes for sentence: '{sentence[:50]}...'")
            return notes

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response for grammar analysis: '{sentence[:50]}...'. Error: {e}\nRaw Response: {raw_json}")
            return []
        except openai.APIError as e:
            logger.error(f"OpenAI API request failed during grammar analysis: {e.status_code} - {e.message}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred during grammar analysis: {e}")
            return []
