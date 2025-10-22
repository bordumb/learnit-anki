# tests/unit/test_generate_card_use_case.py
import pytest
from core.use_cases.generate_card import GenerateCardUseCase
from core.domain.models import AudioFile, GrammarNote
from tests.mocks import (
    MockTranslationService,
    MockDictionaryService,
    MockAudioService,
    MockGrammarService,
    MockStorageService # Added StorageService mock
)
import logging

# Configure basic logging for tests
logging.basicConfig(level=logging.INFO)

# --- Test Fixtures ---

@pytest.fixture
def mock_services():
    """Provides a dictionary of mock services for use case initialization."""
    return {
        "translator": MockTranslationService(),
        "dictionary": MockDictionaryService(),
        "audio": MockAudioService(),
        "storage": MockStorageService(),
        "grammar": MockGrammarService()
    }

# --- Test Cases ---

@pytest.mark.asyncio
async def test_generate_card_french_to_english_basic(mock_services):
    """Test basic card generation for French to English."""
    # Arrange
    use_case = GenerateCardUseCase(
        translation_service=mock_services["translator"],
        dictionary_service=mock_services["dictionary"],
        audio_service=mock_services["audio"],
        storage_service=mock_services["storage"],
        grammar_service=mock_services["grammar"],
        default_source_lang="fr", # Set defaults
        default_target_lang="en"
    )
    sentence_text = "Je mange une pomme."
    source_lang = "fr"
    target_lang = "en"

    # Act
    card = await use_case.execute(
        sentence_text=sentence_text,
        source_lang=source_lang, # Explicitly pass languages
        target_lang=target_lang,
        include_audio=True,
        include_grammar=True
    )

    # Assert
    assert card is not None, "Card generation should succeed"
    assert card.sentence.text == sentence_text
    assert card.sentence.language == source_lang
    assert card.translation.text == "I eat an apple."
    assert card.translation.target_language == target_lang
    assert len(card.word_breakdown.words) == 4
    assert card.word_breakdown.words[0].text == "Je"
    assert card.word_breakdown.words[0].definition == f"Mock definition of 'Je' ({target_lang})"
    assert card.word_breakdown.words[0].definition_native == f"Mock native def of 'Je' ({source_lang})"
    assert card.audio is not None
    assert isinstance(card.audio, AudioFile)
    assert card.audio.language == source_lang
    assert card.audio.filename.startswith(f"{source_lang}_") # Check filename prefix
    assert card.grammar_notes is not None
    assert len(card.grammar_notes) > 0
    assert isinstance(card.grammar_notes[0], GrammarNote)
    assert "Manger" in card.grammar_notes[0].title # Check specific grammar note added by mock

    # Check if audio was saved (mock storage check)
    assert card.audio.filename in mock_services["storage"].storage

@pytest.mark.asyncio
async def test_generate_card_german_to_english(mock_services):
    """Test card generation for German to English."""
    # Arrange
    use_case = GenerateCardUseCase(
        translation_service=mock_services["translator"],
        dictionary_service=mock_services["dictionary"],
        audio_service=mock_services["audio"],
        storage_service=mock_services["storage"],
        grammar_service=mock_services["grammar"],
        default_source_lang="fr", # Defaults are French
        default_target_lang="en"
    )
    sentence_text = "Ich esse einen Apfel."
    source_lang = "de" # Override default source
    target_lang = "en" # Use default target

    # Act
    card = await use_case.execute(
        sentence_text=sentence_text,
        source_lang=source_lang, # Explicitly pass German
        target_lang=target_lang,
        include_audio=True,
        include_grammar=True
    )

    # Assert
    assert card is not None
    assert card.sentence.text == sentence_text
    assert card.sentence.language == source_lang
    assert card.translation.text == "I eat an apple." # Mock returns this
    assert card.translation.target_language == target_lang
    assert len(card.word_breakdown.words) == 4
    assert card.word_breakdown.words[0].text == "Ich"
    assert card.word_breakdown.words[0].definition_native == f"Mock native def of 'Ich' ({source_lang})"
    assert card.audio is not None
    assert card.audio.language == source_lang
    assert card.audio.filename.startswith(f"{source_lang}_")
    assert len(card.grammar_notes) > 0
    assert "Essen" in card.grammar_notes[0].title # Check German grammar note

    # Check if audio was saved
    assert card.audio.filename in mock_services["storage"].storage

@pytest.mark.asyncio
async def test_generate_card_uses_default_languages(mock_services):
    """Test card generation relies on default languages when not provided."""
    # Arrange
    use_case = GenerateCardUseCase(
        translation_service=mock_services["translator"],
        dictionary_service=mock_services["dictionary"],
        audio_service=mock_services["audio"],
        storage_service=mock_services["storage"],
        grammar_service=mock_services["grammar"],
        default_source_lang="fr", # Set defaults
        default_target_lang="en"
    )
    sentence_text = "Bonjour"
    expected_source_lang = "fr"
    expected_target_lang = "en"

    # Act
    # Do NOT pass source_lang or target_lang to execute
    card = await use_case.execute(sentence_text=sentence_text)

    # Assert
    assert card is not None
    assert card.sentence.language == expected_source_lang
    assert card.translation.target_language == expected_target_lang
    assert card.translation.text == "Hello" # Mock translation
    assert card.audio.language == expected_source_lang
    assert card.audio.filename.startswith(f"{expected_source_lang}_")

@pytest.mark.asyncio
async def test_generate_card_without_audio(mock_services):
    """Test card generation works when audio is disabled."""
    # Arrange
    use_case = GenerateCardUseCase(
        translation_service=mock_services["translator"],
        dictionary_service=mock_services["dictionary"],
        # Provide a service explicitly configured to be disabled
        audio_service=MockAudioService(disable=True),
        storage_service=mock_services["storage"],
        grammar_service=mock_services["grammar"],
        default_source_lang="fr",
        default_target_lang="en"
    )
    sentence_text = "Comment allez-vous ?"

    # Act
    card = await use_case.execute(
        sentence_text=sentence_text,
        include_audio=False # Also explicitly disable in execute call
    )

    # Assert
    assert card is not None
    assert card.sentence.text == sentence_text
    assert card.translation.text == "How are you?"
    # Crucially, audio should be None
    assert card.audio is None
    # Check that storage was not called
    assert len(mock_services["storage"].storage) == 0

@pytest.mark.asyncio
async def test_generate_card_without_grammar(mock_services):
    """Test card generation works when grammar is disabled."""
    # Arrange
    use_case = GenerateCardUseCase(
        translation_service=mock_services["translator"],
        dictionary_service=mock_services["dictionary"],
        audio_service=mock_services["audio"],
        storage_service=mock_services["storage"],
        # Provide grammar service, but disable in execute
        grammar_service=mock_services["grammar"],
        default_source_lang="fr",
        default_target_lang="en"
    )
    sentence_text = "Je mange une pomme."

    # Act
    card = await use_case.execute(
        sentence_text=sentence_text,
        include_grammar=False # Explicitly disable grammar
    )

    # Assert
    assert card is not None
    assert card.sentence.text == sentence_text
    assert card.translation.text == "I eat an apple."
    # Crucially, grammar notes should be empty
    assert card.grammar_notes == []
    assert card.audio is not None # Audio should still generate by default

@pytest.mark.asyncio
async def test_generate_card_handles_translation_failure(mock_services):
    """Test graceful handling if translation service returns None."""
    # Arrange
    # Configure mock translator to fail for a specific input
    class FailingTranslator(MockTranslationService):
        async def translate(self, text: str, source_lang: str, target_lang: str) -> Optional[Translation]:
            if text == "Fail this":
                return None
            return await super().translate(text, source_lang, target_lang)

    use_case = GenerateCardUseCase(
        translation_service=FailingTranslator(),
        dictionary_service=mock_services["dictionary"],
        audio_service=mock_services["audio"],
        storage_service=mock_services["storage"],
        grammar_service=mock_services["grammar"],
        default_source_lang="fr",
        default_target_lang="en"
    )
    sentence_text = "Fail this"

    # Act & Assert
    with pytest.raises(ValueError, match="Translation failed"):
        await use_case.execute(sentence_text=sentence_text)

@pytest.mark.asyncio
async def test_generate_card_handles_dictionary_failure(mock_services):
    """Test graceful handling if dictionary service returns None."""
    # Arrange
    class FailingDictionary(MockDictionaryService):
         async def analyze_sentence(self, sentence: str, source_lang: str, target_lang: str) -> Optional[WordBreakdown]:
             if "fail analysis" in sentence:
                 return None
             return await super().analyze_sentence(sentence, source_lang, target_lang)

    use_case = GenerateCardUseCase(
        translation_service=mock_services["translator"],
        dictionary_service=FailingDictionary(),
        audio_service=mock_services["audio"],
        storage_service=mock_services["storage"],
        grammar_service=mock_services["grammar"],
        default_source_lang="fr",
        default_target_lang="en"
    )
    sentence_text = "This should fail analysis"

    # Act & Assert
    with pytest.raises(ValueError, match="Word breakdown analysis failed"):
        await use_case.execute(sentence_text=sentence_text)


@pytest.mark.asyncio
async def test_generate_card_handles_audio_generation_failure(mock_services):
    """Test card is still generated (without audio) if audio generation fails."""
    # Arrange
    use_case = GenerateCardUseCase(
        translation_service=mock_services["translator"],
        dictionary_service=mock_services["dictionary"],
        audio_service=MockAudioService(simulate_failure=True), # Configure mock to fail
        storage_service=mock_services["storage"],
        grammar_service=mock_services["grammar"],
        default_source_lang="fr",
        default_target_lang="en"
    )
    sentence_text = "Bonjour"

    # Act
    # Should not raise an exception, but log a warning (handled in use case)
    card = await use_case.execute(sentence_text=sentence_text, include_audio=True)

    # Assert
    assert card is not None, "Card generation should still succeed"
    assert card.sentence.text == sentence_text
    assert card.translation.text == "Hello"
    # Audio should be None due to simulated failure
    assert card.audio is None
    # Storage should not have been called for saving
    assert len(mock_services["storage"].storage) == 0

@pytest.mark.asyncio
async def test_generate_card_handles_audio_storage_failure(mock_services):
    """Test card is generated (without audio) if storage fails."""
    # Arrange
    class FailingStorage(MockStorageService):
        async def save_audio(self, audio: AudioFile, data: bytes) -> Optional[str]:
            print("MOCK STORAGE: Simulating save failure")
            return None # Simulate failure

    use_case = GenerateCardUseCase(
        translation_service=mock_services["translator"],
        dictionary_service=mock_services["dictionary"],
        audio_service=mock_services["audio"],
        storage_service=FailingStorage(), # Use failing storage mock
        grammar_service=mock_services["grammar"],
        default_source_lang="fr",
        default_target_lang="en"
    )
    sentence_text = "Bonjour"

    # Act
    # Should not raise an exception, but log a warning (handled in use case)
    card = await use_case.execute(sentence_text=sentence_text, include_audio=True)

    # Assert
    assert card is not None
    assert card.sentence.text == sentence_text
    assert card.translation.text == "Hello"
     # Audio should be None because saving failed
    assert card.audio is None
