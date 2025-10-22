# core/use_cases/search_sentences.py
from typing import List, Optional
# Assuming LanguageCode is defined elsewhere (e.g., core.domain.models)
# If not, define it here:
from typing import NewType
LanguageCode = NewType('LanguageCode', str)

from ..domain.models import Sentence, CardDifficulty
from ..domain.interfaces import SentenceSearchService
import logging

logger = logging.getLogger(__name__)

class SearchSentencesUseCase:
    """
    Use case for searching example sentences based on topic or difficulty.
    Orchestrates calls to a SentenceSearchService implementation.
    """

    def __init__(self, search_service: SentenceSearchService):
        """
        Initializes the use case with a sentence search service.

        Args:
            search_service: An implementation of the SentenceSearchService interface.
        """
        if search_service is None:
            raise ValueError("Search service cannot be None")
        self.search = search_service

    async def by_topic(
        self,
        topic: str,
        language: LanguageCode, # Added language parameter
        limit: int = 20
    ) -> List[Sentence]:
        """
        Find sentences related to a specific topic in a given language.

        Args:
            topic: The topic to search for (e.g., "food", "travel").
            language: The language code for the sentences (e.g., "fr", "de").
            limit: The maximum number of sentences to return.

        Returns:
            A list of Sentence objects matching the criteria, or an empty list.
            Returns an empty list on error.
        """
        if not topic or not language:
            logger.warning("Search by topic requires both topic and language.")
            return []
        if limit <= 0:
            logger.warning("Search limit must be positive.")
            return []

        try:
            logger.info(f"Searching for {limit} sentences about '{topic}' in language '{language}'...")
            sentences = await self.search.search_by_topic(
                topic=topic,
                language=language, # Pass the language parameter
                limit=limit
            )
            logger.info(f"Found {len(sentences)} sentences for topic '{topic}' ({language}).")
            return sentences if sentences else []
        except Exception as e:
            logger.error(f"Error searching sentences by topic '{topic}' ({language}): {e}", exc_info=True)
            return [] # Return empty list on error

    async def by_difficulty(
        self,
        difficulty: CardDifficulty,
        language: LanguageCode, # Added language parameter
        limit: int = 20
    ) -> List[Sentence]:
        """
        Find sentences at a specific difficulty level in a given language.

        Args:
            difficulty: The desired difficulty level (e.g., CardDifficulty.A1).
            language: The language code for the sentences (e.g., "fr", "de").
            limit: The maximum number of sentences to return.

        Returns:
            A list of Sentence objects matching the criteria, or an empty list.
            Returns an empty list on error.
        """
        if not difficulty or not language:
             logger.warning("Search by difficulty requires both difficulty and language.")
             return []
        if limit <= 0:
            logger.warning("Search limit must be positive.")
            return []

        try:
            logger.info(f"Searching for {limit} sentences at difficulty '{difficulty.name}' in language '{language}'...")
            sentences = await self.search.search_by_difficulty(
                difficulty=difficulty,
                language=language, # Pass the language parameter
                limit=limit
            )
            logger.info(f"Found {len(sentences)} sentences for difficulty '{difficulty.name}' ({language}).")
            return sentences if sentences else []
        except Exception as e:
            logger.error(f"Error searching sentences by difficulty '{difficulty.name}' ({language}): {e}", exc_info=True)
            return [] # Return empty list on error
