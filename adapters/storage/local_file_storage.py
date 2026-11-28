# adapters/storage/local_file_storage.py
import os
import errno
from pathlib import Path
from typing import Optional
from core.domain.interfaces import StorageService
from core.domain.models import AudioFile
import logging

logger = logging.getLogger(__name__)

class LocalFileStorage(StorageService):
    """
    Stores audio files locally on the filesystem.
    Suitable for development or single-user desktop use.
    """

    def __init__(self, base_path: str = "./storage"):
        """
        Initializes the local storage service.

        Args:
            base_path: The root directory for storing files. Defaults to './storage'.
        """
        try:
            # Resolve the base path relative to the current working directory
            # Use resolve() to get an absolute path
            self.base_path = Path(base_path).resolve()
            self.audio_path = self.base_path / "audio"
            # Create directories if they don't exist
            self.audio_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Local storage initialized at: {self.audio_path}")
        except OSError as e:
            logger.error(f"Failed to create storage directory {self.audio_path}: {e}")
            raise # Re-raise after logging, initialization failed

    async def save_audio(self, audio: AudioFile, data: bytes) -> Optional[str]:
        """
        Saves audio data to a local file.

        Args:
            audio: The AudioFile model containing metadata (like filename).
            data: The raw audio data (bytes).

        Returns:
            The absolute path (str) to the saved file if successful, otherwise None.
        """
        if not audio or not audio.filename:
            logger.error("Attempted to save audio with invalid AudioFile model (missing filename).")
            return None
        if not data:
             logger.error(f"Attempted to save empty audio data for filename: {audio.filename}.")
             return None

        # Use only the filename part to prevent path traversal issues
        filename = Path(audio.filename).name
        filepath = self.audio_path / filename

        try:
            with open(filepath, 'wb') as f:
                f.write(data)
            logger.info(f"Audio file saved successfully: {filepath}")
            # Return the absolute path as a string
            return str(filepath)
        except IOError as e:
            logger.error(f"Failed to write audio file {filepath}: {e}")
            # Attempt to clean up potentially partially written file
            try:
                if filepath.exists():
                    filepath.unlink()
            except OSError:
                 logger.warning(f"Could not clean up partially written file {filepath}.")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred saving audio file {filepath}: {e}")
            return None

    async def get_audio(self, filename: str) -> Optional[bytes]:
        """
        Retrieves audio data from a local file.

        Args:
            filename: The name of the audio file to retrieve.

        Returns:
            The audio data as bytes if the file exists, otherwise None.
        """
        if not filename:
            logger.warning("Attempted to get audio with empty filename.")
            return None

        # Sanitize filename
        base_filename = Path(filename).name
        filepath = self.audio_path / base_filename

        try:
            if filepath.is_file(): # Check if it exists and is a file
                with open(filepath, 'rb') as f:
                    data = f.read()
                logger.debug(f"Audio file retrieved successfully: {filepath}")
                return data
            else:
                logger.warning(f"Audio file not found or is not a file: {filepath}")
                return None
        except IOError as e:
            logger.error(f"Failed to read audio file {filepath}: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred getting audio file {filepath}: {e}")
            return None

    async def delete_audio(self, filename: str) -> bool:
        """
        Deletes an audio file from local storage.

        Args:
            filename: The name of the audio file to delete.

        Returns:
            True if the file was deleted successfully or didn't exist, False otherwise.
        """
        if not filename:
            logger.warning("Attempted to delete audio with empty filename.")
            return False # Indicate failure for invalid input

        # Sanitize filename
        base_filename = Path(filename).name
        filepath = self.audio_path / base_filename

        try:
            # Use missing_ok=True to avoid error if file doesn't exist
            # unlink raises FileNotFoundError if it doesn't exist and missing_ok=False
            filepath.unlink(missing_ok=True)
            logger.info(f"Audio file deleted (or did not exist): {filepath}")
            return True
        except IsADirectoryError:
             logger.error(f"Deletion failed: Path is a directory, not a file: {filepath}")
             return False
        except OSError as e:
            # Catch permissions errors etc.
            logger.error(f"Failed to delete audio file {filepath}: {e}")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred deleting audio file {filepath}: {e}")
            return False
