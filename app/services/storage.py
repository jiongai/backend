
import os
import boto3
from botocore.exceptions import ClientError

class R2Storage:
    def __init__(self):
        self.endpoint_url = os.getenv("R2_ENDPOINT_URL")
        self.access_key_id = os.getenv("R2_ACCESS_KEY_ID")
        self.secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY")
        self.bucket_name = os.getenv("R2_BUCKET_NAME")
        
        if not all([self.endpoint_url, self.access_key_id, self.secret_access_key, self.bucket_name]):
            print("⚠️ R2 Storage initialized but missing configuration")
            self.s3_client = None
            return

        try:
            self.s3_client = boto3.client(
                service_name='s3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                # R2 specific config often helps
                config=boto3.session.Config(signature_version='s3v4')
            )
        except Exception as e:
            print(f"❌ Failed to initialize R2 client: {e}")
            self.s3_client = None

    def upload_file(self, file_path: str, project_id: str, chapter_id: str, content_type: str = 'audio/mpeg') -> str:
        """
        Uploads a file to Cloudflare R2 with best practices.
        
        Args:
            file_path: Absolute path to the local file.
            project_id: Project identifier for folder structure.
            chapter_id: Chapter identifier (filename without extension).
            content_type: MIME type of the file.
            
        Returns:
            str: The object key (path) in the bucket.
        """
        if not self.s3_client:
            raise RuntimeError("R2 Client is not configured")

        # Determine extension from input file path
        if file_path.lower().endswith('.srt'):
            ext = ".srt"
        else:
            ext = ".mp3"

        # 1. Key Naming (Folder Structure)
        # projects/{project_id}/{chapter_id}.{ext}
        object_key = f"projects/{project_id}/{chapter_id}{ext}"
        
        try:
            print(f"🚀 Uploading to R2: {object_key}...")
            
            # 2. Content-Type & 3. Cache-Control
            extra_args = {
                'ContentType': content_type,
                'CacheControl': 'max-age=31536000' # 1 Year Cache
            }
            
            self.s3_client.upload_file(
                Filename=file_path,
                Bucket=self.bucket_name,
                Key=object_key,
                ExtraArgs=extra_args
            )
            
            print(f"✅ Upload successful: {object_key}")
            return object_key
            
        except ClientError as e:
            print(f"❌ R2 Upload Failed: {e}")
            raise e
        except Exception as e:
            print(f"❌ An unexpected error occurred during upload: {e}")
            raise e

# Singleton instance
r2_storage = R2Storage()
