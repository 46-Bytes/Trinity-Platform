"""
File upload and management service
"""
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import uuid
import os
from pathlib import Path

import logging

logger = logging.getLogger(__name__)

from app.models.media import Media
from app.models.user import User
# from app.services.openai_service import openai_service  # Preserved for rollback
from app.services.claude_service import claude_service
from app.services.storage_service import get_storage_service
from app.config import settings


class FileService:
    """Service for handling file uploads and management"""
    
    # Allowed file extensions for diagnostics
    ALLOWED_EXTENSIONS = {
        # Documents
        'pdf', 'doc', 'docx', 'txt', 'rtf',
        # Spreadsheets
        'xls', 'xlsx', 'csv',
        # Images
        'jpg', 'jpeg', 'png', 'gif', 'webp',
        # Other
        'zip'
    }
    
    # Max file size: 10MB
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    def __init__(self, db: Session):
        self.db = db
        # Use the singleton openai_service instance
        self.claude_service = claude_service
        self.storage = get_storage_service()
        # Storage keys for diagnostic/user files are rooted at "uploads/"
        # (relative to the files root, e.g. backend/files/uploads on disk,
        # or the "uploads/" prefix inside the Azure Blob container).
        self.upload_dir = Path("uploads")
    
    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename"""
        return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    def _validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file"""
        # Check extension
        ext = self._get_file_extension(file.filename)
        if ext not in self.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type .{ext} not allowed. Allowed types: {', '.join(self.ALLOWED_EXTENSIONS)}"
            )
        
        # Check file size (if available)
        if hasattr(file, 'size') and file.size and file.size > self.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size of {self.MAX_FILE_SIZE / (1024*1024)}MB"
            )
    
    async def upload_file(
        self,
        file: UploadFile,
        user_id: UUID,
        question_field_name: Optional[str] = None,
        description: Optional[str] = None,
        upload_to_openai: bool = True,
        diagnostic_id: Optional[UUID] = None
    ) -> Media:
        """
        Upload a file, store it locally, and optionally upload to OpenAI
        
        Args:
            file: The uploaded file
            user_id: ID of the user uploading the file
            question_field_name: Which diagnostic question this file answers
            description: Optional description
            upload_to_openai: Whether to upload to OpenAI for analysis
            diagnostic_id: Optional diagnostic ID. If provided, files are stored in 
                          files/uploads/diagnostic/{diagnostic_id}/, otherwise files/uploads/users/{user_id}/
            
        Returns:
            Media object representing the uploaded file
        """
        # Validate file
        self._validate_file(file)

        # Storage key based on whether diagnostic_id is provided
        if diagnostic_id:
            # Store diagnostic files under uploads/diagnostic/{diagnostic_id}/
            storage_prefix = self.upload_dir / "diagnostic" / str(diagnostic_id)
        else:
            # Store user files (profile pictures, etc.) under uploads/users/{user_id}/
            storage_prefix = self.upload_dir / "users" / str(user_id)

        # Generate unique filename
        ext = self._get_file_extension(file.filename)
        unique_filename = f"{uuid.uuid4()}.{ext}"
        storage_key = (storage_prefix / unique_filename).as_posix()

        # Read the upload into memory and persist via the storage backend
        try:
            content = file.file.read()
            self.storage.write_bytes(storage_key, content)
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            raise HTTPException(status_code=500, detail="Failed to save file. Please try again or contact support.")

        file_size = len(content)

        # Create media record
        media = Media(
            user_id=user_id,
            file_name=file.filename,
            file_path=storage_key,
            file_size=file_size,
            file_type=file.content_type,
            file_extension=ext,
            question_field_name=question_field_name,
            description=description
        )

        self.db.add(media)
        self.db.flush()  # Get the media ID

        # Upload to LLM provider if requested
        if upload_to_openai:  # param name kept for interface compat
            local_path = self.storage.local_path(storage_key)
            temp_path = None
            try:
                if local_path is not None:
                    claude_path = str(local_path)
                else:
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                        tmp.write(content)
                        temp_path = tmp.name
                    claude_path = temp_path

                print(f"Uploading file to Claude from path: {claude_path}")
                llm_file = await self.claude_service.upload_file(
                    file_path=claude_path,
                    purpose="user_data",
                )

                if llm_file:
                    # Set generic LLM fields
                    from datetime import datetime, timezone
                    media.llm_file_id = llm_file.get("id")
                    media.llm_provider = "claude"
                    media.llm_uploaded_at = datetime.now(timezone.utc)
                    # Also populate legacy OpenAI fields for backward compatibility
                    media.openai_file_id = llm_file.get("id")
                    media.openai_purpose = llm_file.get("purpose") or "user_data"
                    media.openai_uploaded_at = media.llm_uploaded_at
                    print(f"  File uploaded to Claude: {media.llm_file_id}")
            except Exception as e:
                print(f"  Failed to upload file to LLM provider: {str(e)}")
                # Continue even if LLM upload fails
            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass

        self.db.commit()
        self.db.refresh(media)

        return media
    
    async def upload_files(
        self,
        files: List[UploadFile],
        user_id: UUID,
        question_field_name: Optional[str] = None,
        upload_to_openai: bool = True,
        diagnostic_id: Optional[UUID] = None
    ) -> List[Media]:
        """
        Upload multiple files
        
        Args:
            files: List of uploaded files
            user_id: ID of the user uploading the files
            question_field_name: Which diagnostic question these files answer
            upload_to_openai: Whether to upload to OpenAI
            diagnostic_id: Optional diagnostic ID. If provided, files are stored in 
                          files/uploads/diagnostic/{diagnostic_id}/, otherwise files/uploads/users/{user_id}/
            
        Returns:
            List of Media objects
        """
        media_list = []
        
        for file in files:
            try:
                media = await self.upload_file(
                    file=file,
                    user_id=user_id,
                    question_field_name=question_field_name,
                    upload_to_openai=upload_to_openai,
                    diagnostic_id=diagnostic_id
                )
                media_list.append(media)
            except Exception as e:
                print(f"  Failed to upload file {file.filename}: {str(e)}")
                # Continue with other files
        
        return media_list
    
    def get_user_files(self, user_id: UUID) -> List[Media]:
        """Get all files for a user"""
        return self.db.query(Media).filter(
            Media.user_id == user_id,
            Media.is_active == True
        ).order_by(Media.created_at.desc()).all()
    
    def get_diagnostic_files(self, diagnostic_id: UUID) -> List[Media]:
        """Get all files attached to a diagnostic"""
        from app.models.diagnostic import Diagnostic
        
        diagnostic = self.db.query(Diagnostic).filter(
            Diagnostic.id == diagnostic_id,
            Diagnostic.is_deleted == False
        ).first()

        if not diagnostic:
            return []

        return list(diagnostic.media)
    
    def attach_file_to_diagnostic(
        self,
        media_id: UUID,
        diagnostic_id: UUID
    ) -> bool:
        """Attach a file to a diagnostic"""
        from app.models.diagnostic import Diagnostic
        
        media = self.db.query(Media).filter(Media.id == media_id).first()
        diagnostic = self.db.query(Diagnostic).filter(
            Diagnostic.id == diagnostic_id,
            Diagnostic.is_deleted == False
        ).first()

        if not media or not diagnostic:
            return False
        
        if media not in diagnostic.media:
            diagnostic.media.append(media)
            self.db.commit()
        
        return True
    
    def delete_file(self, media_id: UUID, hard_delete: bool = False) -> bool:
        """
        Delete a file (soft delete by default)
        
        Args:
            media_id: ID of the media to delete
            hard_delete: If True, permanently delete; if False, soft delete
            
        Returns:
            True if successful
        """
        media = self.db.query(Media).filter(Media.id == media_id).first()
        
        if not media:
            return False
        
        if hard_delete:
            # Delete stored file
            try:
                self.storage.delete(media.file_path)
            except Exception as e:
                print(f"  Failed to delete physical file: {str(e)}")
            
            # Delete from database
            self.db.delete(media)
        else:
            # Soft delete
            from datetime import datetime, timezone
            media.is_active = False
            media.deleted_at = datetime.now(timezone.utc)
        
        self.db.commit()
        return True


    """Dependency injection for FileService"""
def get_file_service(db: Session) -> FileService:
    return FileService(db)

