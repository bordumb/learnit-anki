# adapters/translation/openai_adapter.py
import openai
from core.domain.interfaces import TranslationService
from core.domain.models import Translation

class OpenAITranslationAdapter(TranslationService):
    """OpenAI GPT-4o translation (more context-aware)"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Translation:
        
        prompt = f"""Translate this {source_lang} text to {target_lang}.
Provide ONLY the translation, no explanations.

Text: {text}"""
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3  # Lower = more consistent
        )
        
        translated_text = response.choices[0].message.content.strip()
        
        return Translation(
            text=translated_text,
            target_language=target_lang,
            provider=f"openai-{self.model}"
        )