# tests/unit/test_generate_card_use_case.py
import pytest
from core.use_cases.generate_card import GenerateCardUseCase
from core.domain.models import Translation, Word, WordBreakdown, AudioFile
from tests.mocks import (
    MockTranslationService,
    MockDictionaryService,
    MockAudioService
)

@pytest.mark.asyncio
async def test_generate_card_basic():
    """Test card generation with mock services"""
    
    # Arrange
    translator = MockTranslationService()
    dictionary = MockDictionaryService()
    audio = MockAudioService()
    
    use_case = GenerateCardUseCase(
        translation_service=translator,
        dictionary_service=dictionary,
        audio_service=audio
    )
    
    # Act
    card = await use_case.execute("Je mange une pomme.")
    
    # Assert
    assert card.sentence.text == "Je mange une pomme."
    assert card.translation.text == "I eat an apple."
    assert len(card.word_breakdown.words) == 4
    assert card.audio is not None

@pytest.mark.asyncio
async def test_generate_card_without_audio():
    """Test card generation without audio"""
    
    translator = MockTranslationService()
    dictionary = MockDictionaryService()
    audio = MockAudioService()
    
    use_case = GenerateCardUseCase(
        translation_service=translator,
        dictionary_service=dictionary,
        audio_service=audio
    )
    
    card = await use_case.execute(
        "Je mange une pomme.",
        include_audio=False
    )
    
    assert card.audio is None