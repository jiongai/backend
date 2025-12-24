
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

    def upload_file(self, file_path: str, project_id: str, chapter_id: str, content_type: str = 'audio/mpeg', subfolder: str = "") -> str:
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
        # projects/{project_id}/{subfolder}/{chapter_id}.{ext}
        # Clean subfolder
        subfolder_path = f"{subfolder}/" if subfolder else ""
        object_key = f"projects/{project_id}/{subfolder_path}{chapter_id}{ext}"
        
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

    def save_file_as_new(self, source_url: str) -> str:
        """
        Copies a file (from temp or saved) to a NEW 'saved' location with a NEW UUID.
        Returns the new public URL.
        """
        if not self.s3_client:
             raise RuntimeError("R2 Client is not configured")
        
        from uuid import uuid4

        # 1. Parse Key from URL
        r2_domain = os.getenv("R2_PUBLIC_DOMAIN", "")
        clean_domain = r2_domain.replace("https://", "").replace("http://", "").rstrip("/")
        
        # Remove protocol from input
        clean_source = source_url.replace("https://", "").replace("http://", "")
        
        if clean_domain and clean_source.startswith(clean_domain):
            source_key = clean_source[len(clean_domain):].lstrip("/")
        else:
            # Fallback
            if "projects/" in clean_source:
                source_key = clean_source[clean_source.find("projects/"):]
            else:
                 raise ValueError("Invalid URL format: Could not extract object key")

        # 2. Extract Project ID and Extension
        # Key format assumption: projects/{project_id}/{subfolder}/{filename}
        # OR projects/{project_id}/{filename} (legacy)
        
        parts = source_key.split("/")
        # parts[0] = "projects"
        # parts[1] = project_id
        
        if len(parts) < 3 or parts[0] != "projects":
             raise ValueError(f"Unexpected key format: {source_key}")
             
        project_id = parts[1]
        
        # Get extension
        _, ext = os.path.splitext(source_key)
        if not ext:
            ext = ".mp3" # default fallback?

        # 3. Generate NEW Destination Key
        # Format: projects/{project_id}/saved/{NEW_UUID}{ext}
        new_uuid = str(uuid4())
        dest_key = f"projects/{project_id}/saved/{new_uuid}{ext}"

        print(f"👯 Copying R2 Object: {source_key} -> {dest_key}")

        try:
            # COPY
            self.s3_client.copy_object(
                Bucket=self.bucket_name,
                CopySource={'Bucket': self.bucket_name, 'Key': source_key},
                Key=dest_key,
                ACL='public-read'
            )
            
            # Conditional Delete (Move if temp, Copy if saved)
            if "/temp/" in source_key:
                try:
                    self.s3_client.delete_object(
                        Bucket=self.bucket_name,
                        Key=source_key
                    )
                    print(f"🗑️ Deleted temp source: {source_key}")
                except Exception as del_err:
                     print(f"⚠️ Failed to delete temp source: {del_err}")
            
            # Return new URL
            new_url = f"{os.getenv('R2_PUBLIC_DOMAIN')}/{dest_key}"
            return new_url
            
        except ClientError as e:
            print(f"❌ R2 Copy Failed: {e}")
            raise e

    def delete_file(self, file_url: str) -> bool:
        """
        Deletes a file from R2 based on its public URL.
        Returns True if successful, False otherwise.
        """
        if not self.s3_client:
             raise RuntimeError("R2 Client is not configured")

        try:
            # 1. Parse Key from URL (Same logic as save_file_as_new)
            r2_domain = os.getenv("R2_PUBLIC_DOMAIN", "")
            clean_domain = r2_domain.replace("https://", "").replace("http://", "").rstrip("/")
            clean_source = file_url.replace("https://", "").replace("http://", "")
            
            if clean_domain and clean_source.startswith(clean_domain):
                source_key = clean_source[len(clean_domain):].lstrip("/")
            else:
                if "projects/" in clean_source:
                    source_key = clean_source[clean_source.find("projects/"):]
                else:
                     logger.warn("Delete failed: Invalid URL", url=file_url)
                     return False
            
            print(f"🗑️ Deleting R2 Object: {source_key}")
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=source_key
            )
            return True
            
        except Exception as e:
            print(f"❌ R2 Delete Failed: {e}")
            return False

    def move_file_to_temp(self, source_url: str) -> str:
        """
        Moves a file from 'saved' folder back to 'temp' folder.
        Actually performs Copy (to new temp key) + Delete (source).
        Returns new public URL.
        """
        if not self.s3_client:
             raise RuntimeError("R2 Client is not configured")
        
        from uuid import uuid4

        # 1. Parse Key from URL
        r2_domain = os.getenv("R2_PUBLIC_DOMAIN", "")
        clean_domain = r2_domain.replace("https://", "").replace("http://", "").rstrip("/")
        clean_source = source_url.replace("https://", "").replace("http://", "")
        
        if clean_domain and clean_source.startswith(clean_domain):
            source_key = clean_source[len(clean_domain):].lstrip("/")
        else:
            if "projects/" in clean_source:
                source_key = clean_source[clean_source.find("projects/"):]
            else:
                 raise ValueError("Invalid URL format: Could not extract object key")

        # 2. Validation: Must be in 'saved' folder
        if "/saved/" not in source_key:
             raise ValueError("Source file is not in 'saved' folder")

        # 3. Generate NEW Destination Key in 'temp'
        # Current: projects/{project_id}/saved/{filename}
        # Target: projects/{project_id}/temp/{NEW_UUID}{ext}
        
        parts = source_key.split("/")
        # We assume standard structure: projects/{project_id}/...
        if len(parts) < 3 or parts[0] != "projects":
             # Try to start from 'projects' if path is deeper or different, but strictly we need project_id
             # Let's rely on finding "projects/" and taking the next token as project_id
             try:
                 idx = parts.index("projects")
                 project_id = parts[idx+1]
             except (ValueError, IndexError):
                 raise ValueError("Could not determine project_id from key")
        else:
             project_id = parts[1]

        _, ext = os.path.splitext(source_key)
        if not ext:
            ext = ".mp3"

        new_uuid = str(uuid4())
        dest_key = f"projects/{project_id}/temp/{new_uuid}{ext}"

        print(f"🔄 Moving to Temp: {source_key} -> {dest_key}")

        try:
            # COPY
            self.s3_client.copy_object(
                Bucket=self.bucket_name,
                CopySource={'Bucket': self.bucket_name, 'Key': source_key},
                Key=dest_key,
                ACL='public-read'
            )
            
            # DELETE Source
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=source_key
            )
            print(f"🗑️ Deleted source from saved: {source_key}")
            
            # Return new URL
            new_url = f"{os.getenv('R2_PUBLIC_DOMAIN')}/{dest_key}"
            return new_url
            
        except ClientError as e:
            print(f"❌ R2 Move Failed: {e}")
            raise e

# Singleton instance
r2_storage = R2Storage()
