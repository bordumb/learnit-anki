# adapters/audio/google_tts_adapter.py
from google.cloud import texttospeech_v1 as tts
from core.domain.interfaces import AudioService
from core.domain.models import AudioFile, AudioFormat
import hashlib

class GoogleTTSAdapter(AudioService):
    """Google Cloud Text-to-Speech"""
    
    def __init__(self, voice_name: str = "fr-FR-Neural2-A"):
        self.client = tts.TextToSpeechClient()
        self.voice_name = voice_name
    
    async def generate_audio(
        self,
        text: str,
        language: str,
        format: AudioFormat = AudioFormat.MP3
    ) -> AudioFile:
        
        synthesis_input = tts.SynthesisInput(text=text)
        
        voice = tts.VoiceSelectionParams(
            language_code=f"{language}-{language.upper()}",
            name=self.voice_name,
            ssml_gender=tts.SsmlVoiceGender.FEMALE
        )
        
        audio_config = tts.AudioConfig(
            audio_encoding=tts.AudioEncoding.MP3
        )
        
        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        # Generate filename from content hash
        text_hash = hashlib.md5(text.encode()).hexdigest()
        filename = f"{text_hash}.{format.value}"
        
        # Save audio data (would be handled by storage service)
        # For now, just return metadata
        
        return AudioFile(
            filename=filename,
            format=format,
            provider="google-tts"
        )