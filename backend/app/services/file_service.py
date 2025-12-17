"""
File upload and management service
"""
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import uuid
import os
import shutil
from pathlib import Path

from app.models.media import Media
from app.models.user import User
from app.services.openai_service import OpenAIService
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
        self.openai_service = OpenAIService()
        self.upload_dir = Path(settings.UPLOAD_DIR if hasattr(settings, 'UPLOAD_DIR') else "uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
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
        upload_to_openai: bool = True
    ) -> Media:
        """
        Upload a file, store it locally, and optionally upload to OpenAI
        
        Args:
            file: The uploaded file
            user_id: ID of the user uploading the file
            question_field_name: Which diagnostic question this file answers
            description: Optional description
            upload_to_openai: Whether to upload to OpenAI for analysis
            
        Returns:
            Media object representing the uploaded file
        """
        # Validate file
        self._validate_file(file)
        
        # Create user-specific directory
        user_dir = self.upload_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        ext = self._get_file_extension(file.filename)
        unique_filename = f"{uuid.uuid4()}.{ext}"
        file_path = user_dir / unique_filename
        
        # Save file locally
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Create media record
        media = Media(
            user_id=user_id,
            file_name=file.filename,
            file_path=str(file_path),
            file_size=file_size,
            file_type=file.content_type,
            file_extension=ext,
            question_field_name=question_field_name,
            description=description
        )
        
        self.db.add(media)
        self.db.flush()  # Get the media ID
        
        # Upload to OpenAI if requested
        if upload_to_openai:
            try:
                openai_file = await self.openai_service.upload_file(
                    file_path=str(file_path),
                    purpose="assistants"  # For file analysis
                )
                
                if openai_file:
                    media.openai_file_id = openai_file.get('id')
                    media.openai_purpose = "assistants"
                    from datetime import datetime
                    media.openai_uploaded_at = datetime.utcnow()
                    print(f"✅ File uploaded to OpenAI: {media.openai_file_id}")
            except Exception as e:
                print(f"⚠️ Failed to upload file to OpenAI: {str(e)}")
                # Continue even if OpenAI upload fails
        
        self.db.commit()
        self.db.refresh(media)
        
        return media
    
    async def upload_files(
        self,
        files: List[UploadFile],
        user_id: UUID,
        question_field_name: Optional[str] = None,
        upload_to_openai: bool = True
    ) -> List[Media]:
        """
        Upload multiple files
        
        Args:
            files: List of uploaded files
            user_id: ID of the user uploading the files
            question_field_name: Which diagnostic question these files answer
            upload_to_openai: Whether to upload to OpenAI
            
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
                    upload_to_openai=upload_to_openai
                )
                media_list.append(media)
            except Exception as e:
                print(f"⚠️ Failed to upload file {file.filename}: {str(e)}")
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
            Diagnostic.id == diagnostic_id
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
        diagnostic = self.db.query(Diagnostic).filter(Diagnostic.id == diagnostic_id).first()
        
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
            # Delete physical file
            try:
                if os.path.exists(media.file_path):
                    os.remove(media.file_path)
            except Exception as e:
                print(f"⚠️ Failed to delete physical file: {str(e)}")
            
            # Delete from database
            self.db.delete(media)
        else:
            # Soft delete
            from datetime import datetime
            media.is_active = False
            media.deleted_at = datetime.utcnow()
        
        self.db.commit()
        return True


    """Dependency injection for FileService"""
def get_file_service(db: Session) -> FileService:
    return FileService(db)

