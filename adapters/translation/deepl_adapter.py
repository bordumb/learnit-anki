# adapters/translation/deepl_adapter.py
import httpx
from core.domain.interfaces import TranslationService
from core.domain.models import Translation

class DeepLTranslationAdapter(TranslationService):
    """DeepL API implementation"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api-free.deepl.com/v2"
    
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Translation:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/translate",
                data={
                    'auth_key': self.api_key,
                    'text': text,
                    'source_lang': source_lang.upper(),
                    'target_lang': target_lang.upper()
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return Translation(
                text=data['translations'][0]['text'],
                target_language=target_lang,
                provider="deepl",
                confidence=1.0  # DeepL doesn't provide confidence
            )
            