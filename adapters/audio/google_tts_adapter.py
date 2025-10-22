# adapters/audio/google_tts_adapter.py
from google.cloud import texttospeech_v1 as tts
from core.domain.interfaces import AudioService
from core.domain.models import AudioFile, AudioFormat
import hashlib
from typing import Tuple, Dict, Optional

class GoogleTTSAdapter(AudioService):
    """Google Cloud Text-to-Speech adapter supporting multiple languages."""

    def __init__(self, voice_map: Dict[str, str]):
        """
        Initializes the adapter.

        Args:
            voice_map: A dictionary mapping language codes (e.g., 'fr', 'de')
                       to specific Google TTS voice names (e.g., 'fr-FR-Neural2-A').
        """
        self.client = tts.TextToSpeechClient()
        self.voice_map = voice_map
        # Define a fallback voice if a language is not found in the map
        self.fallback_voice = "en-US-Standard-C" # Example fallback
        self.fallback_language_code = "en-US" # Example fallback


    async def generate_audio(
        self,
        text: str,
        language: str, # e.g., 'fr', 'de', 'es'
        format: AudioFormat = AudioFormat.MP3
    ) -> Tuple[Optional[AudioFile], Optional[bytes]]:
        """
        Generates audio for the given text in the specified language.

        Args:
            text: The text to synthesize.
            language: The language code (e.g., 'fr', 'de') for synthesis.
            format: The desired audio format.

        Returns:
            A tuple containing the AudioFile model and the audio data bytes,
            or (None, None) if audio generation fails or is skipped.
        """
        try:
            # --- Select Voice and Language Code ---
            selected_voice_name = self.voice_map.get(language)
            language_code_for_api = None

            if selected_voice_name:
                # Extract language code like 'fr-FR' from voice name 'fr-FR-Neural2-A'
                parts = selected_voice_name.split('-')
                if len(parts) >= 2:
                    language_code_for_api = f"{parts[0]}-{parts[1]}"
                else: # Fallback if voice name format is unexpected
                     print(f"⚠️ Warning: Could not parse language code from voice '{selected_voice_name}'. Falling back.")
                     selected_voice_name = self.fallback_voice
                     language_code_for_api = self.fallback_language_code
            else:
                print(f"⚠️ Warning: No voice configured for language '{language}'. Falling back to default English voice.")
                selected_voice_name = self.fallback_voice
                language_code_for_api = self.fallback_language_code
            # --- End Voice Selection ---

            synthesis_input = tts.SynthesisInput(text=text)

            voice = tts.VoiceSelectionParams(
                language_code=language_code_for_api,
                name=selected_voice_name
            )

            audio_config = tts.AudioConfig(
                audio_encoding=tts.AudioEncoding.MP3 if format == AudioFormat.MP3 else tts.AudioEncoding.LINEAR16
            )

            response = self.client.synthesize_speech(
                request = tts.SynthesizeSpeechRequest(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
            )

            # Generate filename from content hash + language
            text_hash = hashlib.md5(f"{language}-{text}".encode()).hexdigest()
            filename = f"{text_hash}.{format.value}"

            audio_file_model = AudioFile(
                filename=filename,
                format=format,
                provider="google-tts",
                # Store language with the audio file for reference
                # language=language # Optional: Add language field to AudioFile model if needed
            )

            # Return both the model and the raw audio data
            return audio_file_model, response.audio_content

        except Exception as e:
            print(f"❌ Error generating Google TTS audio for language '{language}': {e}")
            return None, None # Indicate failure
