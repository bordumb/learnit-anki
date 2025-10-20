# adapters/dictionary/openai_dictionary_adapter.py
import openai
import json
from typing import List
from core.domain.interfaces import DictionaryService
from core.domain.models import Word, WordBreakdown

import logging
from pathlib import Path

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "dictionary_adapter.log"

logger = logging.getLogger('DictionaryAdapterLogger')
logger.setLevel(logging.INFO)

if not logger.handlers:
    fh = logging.FileHandler(log_file)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)


class OpenAIDictionaryAdapter(DictionaryService):
    """Use GPT-4o for word analysis (most flexible)"""
    
    def __init__(self, api_key: str):
        self.client = openai.AsyncOpenAI(api_key=api_key)
    
    async def lookup_word(
        self,
        word: str,
        source_lang: str,
        target_lang: str
    ) -> Word:
        
        prompt = f"""Analyze this {source_lang} word: "{word}"

Provide JSON:
{{
  "lemma": "base form of word",
  "pos": "noun/verb/adj/etc",
  "definition": "concise English definition (max 5 words)"
}}"""
        
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        data = json.loads(response.choices[0].message.content)
        
        return Word(
            text=word,
            lemma=data['lemma'],
            pos=data['pos'],
            definition=data['definition']
        )
    
    
    async def analyze_sentence(
        self,
        sentence: str,
        source_lang: str,
        target_lang: str
    ) -> WordBreakdown:
        
        prompt = f"""Analyze each word in this {source_lang} sentence:
"{sentence}"

Return a JSON array, where each object has:
- "text": The original word.
- "lemma": The base form (lemma) of the word.
- "pos": The part of speech.
- "definition": A brief {target_lang} definition.
- "definition_fr": A brief {source_lang} definition (monolingual).

Example format:
[
  {{
    "text": "comprenez",
    "lemma": "comprendre",
    "pos": "verb",
    "definition": "understand",
    "definition_fr": "saisir par l'esprit"
  }}
]

Skip punctuation."""
        
        logger.info(f"--- Analyzing Sentence ---")
        logger.info(f"Input: {sentence}")
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            raw_json = response.choices[0].message.content
            logger.info(f"Raw API Response: {raw_json}")
            
            data = json.loads(raw_json)
            
            # Handle inconsistent API responses
            word_list = []
            if isinstance(data, list):
                word_list = data  # This is the format we asked for
            elif isinstance(data, dict):
                # AI wrapped the list in an unexpected key. Check all known variations.
                word_list = data.get('words', 
                                data.get('analysis', 
                                data.get('result', [])))
            
            words = [
                Word(
                    text=word_data.get('text'),
                    lemma=word_data.get('lemma'),
                    pos=word_data.get('pos'),
                    definition=word_data.get('definition'),
                    definition_fr=word_data.get('definition_fr')
                ) 
                for word_data in word_list
                if word_data.get('text')
            ]
            
            logger.info(f"Successfully parsed {len(words)} words.")
            
            return WordBreakdown(words=words)

        except Exception as e:
            logger.error(f"Failed to parse response for sentence: {sentence}")
            logger.error(f"Error: {e}")
            return WordBreakdown(words=[]) # Return empty breakdown on failure