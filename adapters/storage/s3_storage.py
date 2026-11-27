# adapters/storage/s3_storage.py
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from typing import Optional
from core.domain.interfaces import StorageService
from core.domain.models import AudioFile, AudioFormat
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class S3StorageAdapter(StorageService):
    """
    Stores audio files in an AWS S3 bucket.
    Suitable for production environments or cloud deployments.
    Assumes AWS credentials are configured (e.g., via environment variables, IAM role).
    """

    def __init__(self, bucket_name: str, region: str = "us-east-1", base_prefix: str = "audio"):
        """
        Initializes the S3 storage adapter.

        Args:
            bucket_name: The name of the S3 bucket to use.
            region: The AWS region where the bucket is located. Defaults to 'us-east-1'.
            base_prefix: The prefix (folder path) within the bucket for audio files. Defaults to 'audio'.
        """
        if not bucket_name:
            logger.error("S3 bucket name is required but was not provided.")
            raise ValueError("S3 bucket name cannot be empty.")

        self.bucket_name = bucket_name
        self.region = region
        # Ensure the prefix doesn't start or end with / but does end with one if not empty
        self.base_prefix = base_prefix.strip('/')
        try:
            # Initialize S3 client
            # Credentials should be configured externally (env vars, instance profile, etc.)
            self.s3 = boto3.client('s3', region_name=self.region)
            # Optional: Add a check here to ensure the bucket exists or is accessible
            # self.s3.head_bucket(Bucket=self.bucket_name) # This can add startup latency
            logger.info(f"S3 storage adapter initialized for bucket '{self.bucket_name}' in region '{self.region}' using prefix '{self.base_prefix}'.")
        except (NoCredentialsError, PartialCredentialsError) as e:
             logger.error(f"AWS credentials not found or incomplete. S3 adapter failed to initialize. Error: {e}")
             raise ValueError(f"AWS credentials issue: {e}")
        except ClientError as e:
             # Handle potential errors like invalid region or access denied during initialization (if head_bucket is used)
             logger.error(f"Failed to initialize S3 client or access bucket '{self.bucket_name}'. Error: {e}")
             raise ValueError(f"S3 client/bucket error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during S3 adapter initialization: {e}")
            raise # Re-raise unexpected errors

    def _get_s3_key(self, filename: str) -> str:
        """Constructs the full S3 object key including the prefix."""
        # Sanitize filename to prevent issues
        safe_filename = Path(filename).name
        if self.base_prefix:
            return f"{self.base_prefix}/{safe_filename}"
        else:
            return safe_filename

    async def save_audio(self, audio: AudioFile, data: bytes) -> Optional[str]:
        """
        Saves audio data to an S3 bucket object.

        Args:
            audio: The AudioFile model containing metadata (filename, format).
            data: The raw audio data (bytes).

        Returns:
            The public URL (https://...) to the saved S3 object if successful, otherwise None.
        """
        if not audio or not audio.filename:
            logger.error("Attempted to save audio with invalid AudioFile model (missing filename).")
            return None
        if not data:
             logger.error(f"Attempted to save empty audio data for filename: {audio.filename}.")
             return None

        key = self._get_s3_key(audio.filename)
        content_type = f"audio/{audio.format.value}" if audio.format else 'application/octet-stream'

        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type
                # Consider adding ACL='public-read' if files need to be directly accessible via URL
                # ACL='public-read'
            )

            # Construct the object URL (assumes standard S3 URL format, may vary with settings)
            # Note: This URL might not be publicly accessible unless bucket/object ACLs allow it.
            # For private buckets, consider using presigned URLs.
            url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{key}"
            logger.info(f"Audio file saved successfully to S3: s3://{self.bucket_name}/{key} (URL: {url})")
            return url
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            logger.error(f"Failed to save audio to S3 (s3://{self.bucket_name}/{key}). Error Code: {error_code}. Message: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred saving audio to S3 (s3://{self.bucket_name}/{key}): {e}")
            return None

    async def get_audio(self, filename: str) -> Optional[bytes]:
        """
        Retrieves audio data from an S3 object.

        Args:
            filename: The name of the audio file to retrieve.

        Returns:
            The audio data as bytes if the object exists, otherwise None.
        """
        if not filename:
            logger.warning("Attempted to get audio with empty filename.")
            return None

        key = self._get_s3_key(filename)

        try:
            response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
            data = response['Body'].read()
            logger.debug(f"Audio file retrieved successfully from S3: s3://{self.bucket_name}/{key}")
            return data
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'NoSuchKey':
                logger.warning(f"Audio file not found in S3: s3://{self.bucket_name}/{key}")
            else:
                logger.error(f"Failed to retrieve audio from S3 (s3://{self.bucket_name}/{key}). Error Code: {error_code}. Message: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred getting audio from S3 (s3://{self.bucket_name}/{key}): {e}")
            return None

    async def delete_audio(self, filename: str) -> bool:
        """
        Deletes an audio object from the S3 bucket.

        Args:
            filename: The name of the audio file to delete.

        Returns:
            True if deletion was successful (or object didn't exist), False otherwise.
        """
        if not filename:
            logger.warning("Attempted to delete audio with empty filename.")
            return False

        key = self._get_s3_key(filename)

        try:
            # delete_object doesn't error if the key doesn't exist, it just succeeds.
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Audio file deleted (or did not exist) from S3: s3://{self.bucket_name}/{key}")
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            logger.error(f"Failed to delete audio from S3 (s3://{self.bucket_name}/{key}). Error Code: {error_code}. Message: {e}")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred deleting audio from S3 (s3://{self.bucket_name}/{key}): {e}")
            return False
