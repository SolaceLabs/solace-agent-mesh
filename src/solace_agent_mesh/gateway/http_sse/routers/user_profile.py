"""
FastAPI router for managing user profiles and avatars.
"""

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dependencies import get_db_optional, get_user_id
from ..repository.models.user_profile_model import UserProfileModel
from ..shared import now_epoch_ms

log = logging.getLogger(__name__)

router = APIRouter()

# Configuration
AVATAR_MAX_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
AVATAR_STORAGE_DIR = Path("data/avatars")  # Local storage directory


class UserProfileResponse(BaseModel):
    """Response model for user profile."""
    userId: str
    displayName: str | None = None
    email: str | None = None
    avatarUrl: str | None = None
    createdAt: int
    updatedAt: int

    class Config:
        from_attributes = True
        populate_by_name = True
        
    @classmethod
    def from_orm(cls, obj):
        """Convert ORM model to response with camelCase."""
        return cls(
            userId=obj.user_id,
            displayName=obj.display_name,
            email=obj.email,
            avatarUrl=obj.avatar_url,
            createdAt=obj.created_at,
            updatedAt=obj.updated_at
        )


class AvatarUploadResponse(BaseModel):
    """Response model for avatar upload."""
    avatarUrl: str
    storageType: str
    message: str


def _get_or_create_profile(db: Session, user_id: str) -> UserProfileModel:
    """Get existing profile or create a new one."""
    stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
    profile = db.execute(stmt).scalar_one_or_none()
    
    if not profile:
        now = now_epoch_ms()
        profile = UserProfileModel(
            user_id=user_id,
            created_at=now,
            updated_at=now
        )
        db.add(profile)
        db.flush()
    
    return profile


def _save_avatar_locally(user_id: str, file_content: bytes, file_extension: str) -> str:
    """
    Save avatar to local filesystem.
    
    Returns:
        str: Relative path to the saved avatar
    """
    # Create storage directory if it doesn't exist
    AVATAR_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    filename = f"{user_id}_{uuid.uuid4().hex[:8]}{file_extension}"
    file_path = AVATAR_STORAGE_DIR / filename
    
    # Write file
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Return relative path for URL (router is mounted at /api/v1/user)
    return f"/api/v1/user/avatar/{filename}"


def _save_avatar_to_s3(user_id: str, file_content: bytes, file_extension: str, mime_type: str) -> str:
    """
    Save avatar to S3 storage.
    
    Returns:
        str: S3 URL to the saved avatar
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        # Get S3 configuration from environment
        bucket_name = os.getenv("AVATAR_S3_BUCKET")
        region = os.getenv("AVATAR_S3_REGION", "us-east-1")
        
        if not bucket_name:
            raise ValueError("AVATAR_S3_BUCKET environment variable not set")
        
        # Initialize S3 client
        s3_client = boto3.client('s3', region_name=region)
        
        # Generate unique key
        key = f"avatars/{user_id}/{uuid.uuid4().hex}{file_extension}"
        
        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=file_content,
            ContentType=mime_type,
            CacheControl='public, max-age=31536000',  # Cache for 1 year
        )
        
        # Return S3 URL
        return f"https://{bucket_name}.s3.{region}.amazonaws.com/{key}"
        
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="S3 storage not available. Install boto3: pip install boto3"
        )
    except ClientError as e:
        log.error(f"S3 upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload to S3: {str(e)}"
        )


@router.get(
    "/profile",
    response_model=UserProfileResponse,
    summary="Get User Profile",
    description="Retrieves the current user's profile information including avatar URL."
)
async def get_user_profile(
    user_id: str = Depends(get_user_id),
    db: Session | None = Depends(get_db_optional),
):
    """Get the current user's profile."""
    if not db:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Database not configured. User profiles require database support."
        )
    
    log.info(f"[GET /user/profile] Fetching profile for user: {user_id}")
    
    try:
        profile = _get_or_create_profile(db, user_id)
        db.commit()
        
        return UserProfileResponse.from_orm(profile)
    except Exception as e:
        db.rollback()
        log.error(f"Error fetching user profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user profile"
        )


@router.post(
    "/avatar",
    response_model=AvatarUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload User Avatar",
    description="Uploads a new avatar image for the current user. Supports local and S3 storage."
)
async def upload_avatar(
    file: UploadFile = File(..., description="Avatar image file (JPEG, PNG, GIF, or WebP)"),
    storage_type: str = "local",  # 'local' or 's3'
    user_id: str = Depends(get_user_id),
    db: Session | None = Depends(get_db_optional),
):
    """
    Upload a new avatar image for the current user.
    
    The avatar will be stored either locally or in S3 based on the storage_type parameter.
    """
    if not db:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Database not configured. Avatar upload requires database support."
        )
    
    log.info(f"[POST /user/avatar] User {user_id} uploading avatar, storage: {storage_type}")
    
    # Validate file type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
        )
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Validate file size
        if len(file_content) > AVATAR_MAX_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {AVATAR_MAX_SIZE / (1024*1024):.1f}MB"
            )
        
        # Get file extension
        file_extension = Path(file.filename).suffix.lower()
        if not file_extension:
            # Default based on mime type
            ext_map = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
                "image/webp": ".webp"
            }
            file_extension = ext_map.get(file.content_type, ".jpg")
        
        # Save avatar based on storage type
        if storage_type == "s3":
            avatar_url = _save_avatar_to_s3(user_id, file_content, file_extension, file.content_type)
        else:
            avatar_url = _save_avatar_locally(user_id, file_content, file_extension)
        
        # Update user profile
        profile = _get_or_create_profile(db, user_id)
        
        # Delete old avatar if it exists and is local
        if profile.avatar_url and profile.avatar_storage_type == "local":
            try:
                old_filename = profile.avatar_url.split("/")[-1]
                old_path = AVATAR_STORAGE_DIR / old_filename
                if old_path.exists():
                    old_path.unlink()
                    log.info(f"Deleted old avatar: {old_path}")
            except Exception as e:
                log.warning(f"Failed to delete old avatar: {e}")
        
        profile.avatar_url = avatar_url
        profile.avatar_storage_type = storage_type
        profile.updated_at = now_epoch_ms()
        
        db.commit()
        
        log.info(f"Avatar uploaded successfully for user {user_id}: {avatar_url}")
        
        return AvatarUploadResponse(
            avatarUrl=avatar_url,
            storageType=storage_type,
            message="Avatar uploaded successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error(f"Error uploading avatar: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar"
        )
    finally:
        await file.close()


@router.delete(
    "/avatar",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete User Avatar",
    description="Deletes the current user's avatar image."
)
async def delete_avatar(
    user_id: str = Depends(get_user_id),
    db: Session | None = Depends(get_db_optional),
):
    """Delete the current user's avatar."""
    if not db:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Database not configured."
        )
    
    log.info(f"[DELETE /user/avatar] User {user_id} deleting avatar")
    
    try:
        stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
        profile = db.execute(stmt).scalar_one_or_none()
        
        if not profile or not profile.avatar_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No avatar found"
            )
        
        # Delete file if stored locally
        if profile.avatar_storage_type == "local":
            try:
                filename = profile.avatar_url.split("/")[-1]
                file_path = AVATAR_STORAGE_DIR / filename
                if file_path.exists():
                    file_path.unlink()
                    log.info(f"Deleted avatar file: {file_path}")
            except Exception as e:
                log.warning(f"Failed to delete avatar file: {e}")
        
        # Update profile
        profile.avatar_url = None
        profile.avatar_storage_type = None
        profile.updated_at = now_epoch_ms()
        
        db.commit()
        
        log.info(f"Avatar deleted successfully for user {user_id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error(f"Error deleting avatar: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete avatar"
        )


@router.get(
    "/avatar/{filename}",
    summary="Get Avatar Image",
    description="Retrieves an avatar image file from local storage."
)
async def get_avatar(filename: str):
    """Serve avatar image from local storage."""
    file_path = AVATAR_STORAGE_DIR / filename
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found"
        )
    
    # Security check: ensure file is within avatar directory
    try:
        file_path.resolve().relative_to(AVATAR_STORAGE_DIR.resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return FileResponse(
        path=file_path,
        media_type="image/jpeg",  # Will be auto-detected by FastAPI
        headers={"Cache-Control": "public, max-age=31536000"}  # Cache for 1 year
    )