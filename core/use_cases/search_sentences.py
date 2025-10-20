# core/use_cases/search_sentences.py
from typing import List
from ..domain.models import Sentence, CardDifficulty
from ..domain.interfaces import SentenceSearchService

class SearchSentencesUseCase:
    """Search for sentences to create cards from"""
    
    def __init__(self, search_service: SentenceSearchService):
        self.search = search_service
    
    async def by_topic(
        self,
        topic: str,
        limit: int = 20
    ) -> List[Sentence]:
        """Find sentences about a specific topic"""
        return await self.search.search_by_topic(
            topic=topic,
            language="fr",
            limit=limit
        )
    
    async def by_difficulty(
        self,
        difficulty: CardDifficulty,
        limit: int = 20
    ) -> List[Sentence]:
        """Find sentences at a difficulty level"""
        return await self.search.search_by_difficulty(
            difficulty=difficulty,
            language="fr",
            limit=limit
        )
