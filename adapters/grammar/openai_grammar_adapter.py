# adapters/grammar/openai_grammar_adapter.py
import openai
import json
from typing import List
from core.domain.interfaces import GrammarService
from core.domain.models import GrammarNote

class OpenAIGrammarAdapter(GrammarService):
    """
    Use GPT-4o to analyze a sentence for complex grammar,
    idioms, and metaphors.
    """
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def explain_grammar(
        self, 
        sentence: str,
        language: str
    ) -> List[GrammarNote]:
        
        prompt = f"""Analyze the following {language} sentence:
"{sentence}"

Identify and explain any notable grammar, idioms, metaphors, or cultural phrases.
If the sentence is simple, just explain the main verb tense.

Return a JSON object with a single key "notes", containing an array of objects:
{{
  "notes": [
    {{
      "title": "e.g., Idiom: 'Avoir le cafard'",
      "explanation": "A concise explanation of the phrase.",
      "examples": ["An example of the phrase in another sentence (optional)"]
    }},
    {{
      "title": "e.g., Verb Tense: 'Présent'",
      "explanation": "Explanation of the verb '...' and its conjugation."
    }}
  ]
}}

If no notable phrases are found, return {{"notes": []}}.
"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.4
            )
            
            data = json.loads(response.choices[0].message.content)
            
            # Extract the list from the "notes" key
            note_list = data.get('notes', [])
            
            notes = []
            for note in note_list:
                if isinstance(note, dict):
                    # This is the expected format
                    notes.append(
                        GrammarNote(
                            title=note.get('title', 'Note'),
                            explanation=note.get('explanation', 'N/A'),
                            examples=note.get('examples', [])
                        )
                    )
                elif isinstance(note, str):
                    # This handles the error case where AI returns a list of strings
                    notes.append(
                        GrammarNote(
                            title="Grammar Note",
                            explanation=note,
                            examples=[]
                        )
                    )
            
            return notes
            
        except Exception as e:
            print(f"Error parsing grammar notes: {e}")
            return []