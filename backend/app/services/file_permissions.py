"""
File permissions for media/file access control.
Handles permissions for firm accounts and solo advisors.
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, text
from typing import Optional
from uuid import UUID

from ..models.user import User, UserRole
from ..models.media import Media
from ..models.diagnostic import Diagnostic
from ..models.engagement import Engagement
from ..services.role_check import check_engagement_access


def can_access_file(user: User, media: Media, db: Session) -> bool:
    """
    Check if user can access a specific file/media.
    
    Rules:
    - Super Admin/Admin: Access to all files
    - Firm Admin: Access to files in their firm's engagements
    - Firm Advisor: Access to files in assigned engagements (same firm)
    - Solo Advisor: Access to files in their engagements
    - Client: Access to files in their own engagements
    
    Args:
        user: Current user
        media: Media/file to check
        db: Database session
        
    Returns:
        bool: True if user has access
    """
    # Super Admin and Admin have full access
    if user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        return True
    
    # Get the diagnostic(s) associated with this media
    # Media can be linked to diagnostics via diagnostic_media association table
    diagnostics = db.query(Diagnostic).join(
        Diagnostic.media
    ).filter(
        Media.id == media.id
    ).all()
    
    if not diagnostics:
        # If no diagnostic association, check if user owns the file
        return media.user_id == user.id
    
    # Check access through engagements
    for diagnostic in diagnostics:
        engagement = db.query(Engagement).filter(
            Engagement.id == diagnostic.engagement_id
        ).first()
        
        if engagement:
            # Use existing engagement access check
            if check_engagement_access(engagement, user):
                return True
    
    # If file is directly owned by user
    if media.user_id == user.id:
        return True
    
    return False


def can_upload_file_to_diagnostic(
    user: User,
    diagnostic_id: UUID,
    db: Session
) -> bool:
    """
    Check if user can upload files to a diagnostic.
    
    Args:
        user: Current user
        diagnostic_id: Diagnostic ID
        db: Database session
        
    Returns:
        bool: True if user can upload
    """
    # Super Admin and Admin can upload anywhere
    if user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        return True
    
    # Get diagnostic and its engagement
    diagnostic = db.query(Diagnostic).filter(Diagnostic.id == diagnostic_id).first()
    if not diagnostic:
        return False
    
    engagement = db.query(Engagement).filter(
        Engagement.id == diagnostic.engagement_id
    ).first()
    
    if not engagement:
        return False
    
    # Check engagement access (requires advisor access for uploads)
    return check_engagement_access(engagement, user, require_advisor=True)


def can_delete_file(user: User, media: Media, db: Session) -> bool:
    """
    Check if user can delete a file.
    
    Rules:
    - Super Admin/Admin: Can delete any file
    - Firm Admin: Can delete files in their firm's engagements
    - Firm Advisor/Solo Advisor: Can delete files they uploaded or in their engagements
    - Client: Can delete files in their engagements
    
    Args:
        user: Current user
        media: Media/file to check
        db: Database session
        
    Returns:
        bool: True if user can delete
    """
    # Super Admin and Admin can delete any file
    if user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        return True
    
    # User can always delete their own files
    if media.user_id == user.id:
        return True
    
    # Firm Admin can delete files in their firm
    if user.role == UserRole.FIRM_ADMIN and user.firm_id:
        diagnostics = db.query(Diagnostic).join(
            Diagnostic.media
        ).filter(
            Media.id == media.id
        ).all()
        
        for diagnostic in diagnostics:
            engagement = db.query(Engagement).filter(
                Engagement.id == diagnostic.engagement_id
            ).first()
            
            if engagement and engagement.firm_id == user.firm_id:
                return True
    
    # Check through engagement access
    return can_access_file(user, media, db)


def get_accessible_files(
    user: User,
    db: Session,
    diagnostic_id: Optional[UUID] = None,
    engagement_id: Optional[UUID] = None
) -> list[Media]:
    """
    Get list of files accessible to the user.
    
    Args:
        user: Current user
        db: Database session
        diagnostic_id: Optional filter by diagnostic
        engagement_id: Optional filter by engagement
        
    Returns:
        List of Media objects
    """
    # Super Admin and Admin see all files
    if user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        query = db.query(Media).filter(Media.is_active == True)
    else:
        # Build query based on role
        if user.role == UserRole.FIRM_ADMIN:
            # Firm Admin sees all files in their firm's engagements
            query = db.query(Media).join(
                Diagnostic.media
            ).join(
                Engagement
            ).filter(
                Engagement.firm_id == user.firm_id,
                Media.is_active == True
            )
        elif user.role == UserRole.FIRM_ADVISOR:
            # Firm Advisor sees files in assigned engagements
            query = db.query(Media).join(
                Diagnostic.media
            ).join(
                Engagement
            ).filter(
                Engagement.firm_id == user.firm_id,
                Engagement.primary_advisor_id == user.id,
                Media.is_active == True
            )
        elif user.role == UserRole.ADVISOR:
            # Solo Advisor sees files in their engagements
            query = db.query(Media).join(
                Diagnostic.media
            ).join(
                Engagement
            ).filter(
                or_(
                    Engagement.primary_advisor_id == user.id,
                    text("secondary_advisor_ids @> ARRAY[:user_id]::uuid[]").bindparams(user_id=user.id)
                ),
                Media.is_active == True
            )
        elif user.role == UserRole.CLIENT:
            # Client sees files in their engagements
            query = db.query(Media).join(
                Diagnostic.media
            ).join(
                Engagement
            ).filter(
                Engagement.client_id == user.id,
                Media.is_active == True
            )
        else:
            # Default: only own files
            query = db.query(Media).filter(
                Media.user_id == user.id,
                Media.is_active == True
            )
    
    # Apply filters
    if diagnostic_id:
        query = query.join(Diagnostic.media).filter(Diagnostic.id == diagnostic_id)
    
    if engagement_id:
        query = query.join(Diagnostic).filter(Diagnostic.engagement_id == engagement_id)
    
    return query.distinct().all()

