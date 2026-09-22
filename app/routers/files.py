from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from app.auth.deps import get_current_active_user
from app.models.user import User
from app.services.storage import ALLOWED_MIME_PREFIXES, get_storage_service

router = APIRouter(prefix="/api/files", tags=["Files"])


class FileUploadResponse(BaseModel):
    file_url: str
    file_name: str
    file_size: int
    content_type: str


@router.post(
    "/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload media or file attachment",
    description="Uploads an image, video, audio/voice message, or document. Supports Local or S3/Cloudflare R2 storage.",
)
async def upload_file(
    file: UploadFile = File(...),
    subfolder: str = Form("media", description="Subfolder category: 'media', 'avatars', 'voice', or 'docs'"),
    current_user: User = Depends(get_current_active_user),
):
    # Validate MIME type
    content_type = file.content_type or "application/octet-stream"
    is_allowed = any(content_type.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES)
    if not is_allowed and content_type != "application/octet-stream":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{content_type}' is not supported.",
        )

    # Sanitize subfolder
    clean_subfolder = "".join(c for c in subfolder if c.isalnum() or c in ("-", "_")) or "media"

    storage = get_storage_service()
    url, filename, size = await storage.upload_file(file=file, subfolder=clean_subfolder)

    return FileUploadResponse(
        file_url=url,
        file_name=filename,
        file_size=size,
        content_type=content_type,
    )
