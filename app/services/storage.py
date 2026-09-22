import os
import shutil
import uuid
from abc import ABC, abstractmethod
from typing import Optional, Tuple
import aiofiles
from fastapi import HTTPException, UploadFile, status
from app.config import settings

# Allowed file MIME categories
ALLOWED_MIME_PREFIXES = (
    "image/",
    "video/",
    "audio/",
    "application/pdf",
    "application/zip",
    "application/x-zip-compressed",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument",
)


class StorageService(ABC):
    """
    Abstract storage interface allowing seamless swapping between
    local filesystem (development) and Cloud Object Storage (S3 / Cloudflare R2 / MinIO).
    """

    @abstractmethod
    async def upload_file(
        self, file: UploadFile, subfolder: str = "media"
    ) -> Tuple[str, str, int]:
        """
        Uploads an incoming file.
        Returns (file_url, original_filename, file_size_bytes).
        """
        pass

    @abstractmethod
    async def delete_file(self, file_path_or_url: str) -> bool:
        """Deletes a file from storage."""
        pass


class LocalStorageService(StorageService):
    def __init__(self, base_dir: str = settings.LOCAL_UPLOAD_DIR):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    async def upload_file(
        self, file: UploadFile, subfolder: str = "media"
    ) -> Tuple[str, str, int]:
        target_dir = os.path.join(self.base_dir, subfolder)
        os.makedirs(target_dir, exist_ok=True)

        original_filename = file.filename or "file"
        _, ext = os.path.splitext(original_filename)
        unique_name = f"{uuid.uuid4().hex}{ext.lower()}"
        file_path = os.path.join(target_dir, unique_name)

        size = 0
        async with aiofiles.open(file_path, "wb") as out_file:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                size += len(chunk)
                if size > settings.MAX_FILE_SIZE_BYTES:
                    # Clean up file on size exceed
                    await out_file.close()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_BYTES // (1024*1024)}MB",
                    )
                await out_file.write(chunk)

        # Build accessible URL
        # Mounted as static directory in FastAPI under /uploads
        url = f"/uploads/{subfolder}/{unique_name}"
        return url, original_filename, size

    async def delete_file(self, file_path_or_url: str) -> bool:
        # Extract relative path from URL like /uploads/media/xyz.jpg
        rel = file_path_or_url.lstrip("/")
        if rel.startswith("uploads/"):
            rel = rel[len("uploads/") :]
        full_path = os.path.join(self.base_dir, rel)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
                return True
            except OSError:
                return False
        return False


class S3StorageService(StorageService):
    def __init__(self):
        import boto3
        from botocore.config import Config

        boto_config = Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        )

        client_kwargs = {
            "service_name": "s3",
            "region_name": settings.STORAGE_REGION if settings.STORAGE_REGION != "auto" else None,
            "aws_access_key_id": settings.STORAGE_ACCESS_KEY,
            "aws_secret_access_key": settings.STORAGE_SECRET_KEY,
            "config": boto_config,
        }
        if settings.STORAGE_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = settings.STORAGE_ENDPOINT_URL

        self.s3_client = boto3.client(**client_kwargs)
        self.bucket = settings.STORAGE_BUCKET

    async def upload_file(
        self, file: UploadFile, subfolder: str = "media"
    ) -> Tuple[str, str, int]:
        original_filename = file.filename or "file"
        _, ext = os.path.splitext(original_filename)
        unique_name = f"{subfolder}/{uuid.uuid4().hex}{ext.lower()}"

        content_type = file.content_type or "application/octet-stream"
        content = await file.read()
        size = len(content)

        if size > settings.MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_BYTES // (1024*1024)}MB",
            )

        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=unique_name,
                Body=content,
                ContentType=content_type,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload media to cloud storage: {str(e)}",
            )

        if settings.STORAGE_PUBLIC_URL_PREFIX:
            url = f"{settings.STORAGE_PUBLIC_URL_PREFIX.rstrip('/')}/{unique_name}"
        elif settings.STORAGE_ENDPOINT_URL:
            url = f"{settings.STORAGE_ENDPOINT_URL.rstrip('/')}/{self.bucket}/{unique_name}"
        else:
            url = f"https://{self.bucket}.s3.amazonaws.com/{unique_name}"

        return url, original_filename, size

    async def delete_file(self, file_path_or_url: str) -> bool:
        try:
            key = file_path_or_url.split("/")[-1]
            self.s3_client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False


def get_storage_service() -> StorageService:
    """Factory creating the configured storage provider."""
    if settings.STORAGE_PROVIDER.lower() == "s3" and settings.STORAGE_BUCKET:
        return S3StorageService()
    return LocalStorageService()
