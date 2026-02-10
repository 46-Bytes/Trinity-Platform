"""
Note CRUD API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, text
from typing import List, Optional
from uuid import UUID

from ..database import get_db
from ..models.engagement import Engagement
from ..models.user import User, UserRole
from ..models.note import Note
from ..schemas.note import (
    NoteCreate,
    NoteUpdate,
    NoteResponse,
    NoteListItem,
)
from ..services.role_check import get_current_user_from_token, check_engagement_access

router = APIRouter(prefix="/api/notes", tags=["notes"])


def check_note_visibility(note: Note, user: User) -> bool:
    """
    Check if user can view a note based on visibility settings.
    
    Rules:
    - 'all': Everyone with engagement access can see
    - 'advisor_only': Only advisors and admins can see
    - 'client_only': Only clients and admins can see
    """
    if user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        return True
    
    if note.visibility == "all":
        return True
    elif note.visibility == "advisor_only":
        return user.role == UserRole.ADVISOR
    elif note.visibility == "client_only":
        return user.role == UserRole.CLIENT
    
    return False


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    note_data: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Create a new note.
    
    User must have access to the engagement.
    The author_id will be set to the current user.
    """
    # Verify engagement exists
    engagement = db.query(Engagement).filter(Engagement.id == note_data.engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    # Verify task exists if provided
    if note_data.task_id:
        from ..models.task import Task
        task = db.query(Task).filter(Task.id == note_data.task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found."
            )
        if task.engagement_id != note_data.engagement_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task does not belong to this engagement."
            )
    
    # Create note (use current_user.id as author_id, not from request)
    note = Note(
        engagement_id=note_data.engagement_id,
        author_id=current_user.id,
        diagnostic_id=note_data.diagnostic_id,
        task_id=note_data.task_id,
        title=note_data.title,
        content=note_data.content,
        note_type=note_data.note_type,
        is_pinned=note_data.is_pinned,
        visibility=note_data.visibility,
        tags=note_data.tags or [],
        attachments=note_data.attachments or [],
    )
    
    db.add(note)
    db.commit()
    db.refresh(note)
    
    return NoteResponse.model_validate(note)


@router.get("", response_model=List[NoteListItem])
async def list_notes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
    engagement_id: Optional[UUID] = Query(None, description="Filter by engagement ID"),
    task_id: Optional[UUID] = Query(None, description="Filter by task ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
):
    """
    List notes accessible to the current user.
    
    Returns notes based on:
    - User's access to engagements
    - Note visibility settings
    """
    # Build base query
    query = db.query(Note)
    
    # Filter by engagement if provided
    if engagement_id:
        # Verify engagement access
        engagement = db.query(Engagement).filter(Engagement.id == engagement_id).first()
        if not engagement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Engagement not found."
            )
        if not check_engagement_access(engagement, current_user, db=db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this engagement."
            )
        query = query.filter(Note.engagement_id == engagement_id)
    
    # Filter by task_id if provided
    if task_id:
        query = query.filter(Note.task_id == task_id)
    else:
        # Filter by accessible engagements
        if current_user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
            # Admins see all engagements
            pass
        elif current_user.role == UserRole.ADVISOR:
            # Advisors see notes from their engagements
            # Use PostgreSQL array contains operator (@>) to check if user ID is in secondary_advisor_ids array
            query = query.join(Engagement).filter(
                or_(
                    Engagement.primary_advisor_id == current_user.id,
                    text("secondary_advisor_ids @> ARRAY[:user_id]::uuid[]").bindparams(user_id=current_user.id)
                )
            )
        elif current_user.role == UserRole.CLIENT:
            # Clients see notes from their engagements
            query = query.join(Engagement).filter(Engagement.client_id == current_user.id)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid user role."
            )
    
    # Get all notes and filter by visibility
    notes = query.order_by(Note.is_pinned.desc(), Note.created_at.desc()).offset(skip).limit(limit * 2).all()
    
    # Filter by visibility and build response
    result = []
    for note in notes:
        if not check_note_visibility(note, current_user):
            continue
        
        # Get author name
        author = db.query(User).filter(User.id == note.author_id).first()
        author_name = author.name or author.email if author else None
        
        # Get engagement name
        engagement = db.query(Engagement).filter(Engagement.id == note.engagement_id).first()
        engagement_name = engagement.engagement_name if engagement else None
        
        note_dict = {
            **note.__dict__,
            "author_name": author_name,
            "engagement_name": engagement_name,
        }
        result.append(NoteListItem(**note_dict))
        
        if len(result) >= limit:
            break
    
    return result


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
):
    """
    Get a note by ID.
    
    User must have access to the engagement and note visibility.
    """
    note = db.query(Note).filter(Note.id == note_id).first()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found."
        )
    
    # Check engagement access
    engagement = db.query(Engagement).filter(Engagement.id == note.engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    if not check_engagement_access(engagement, current_user, db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this engagement."
        )
    
    # Check note visibility
    if not check_note_visibility(note, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this note."
        )
    
    return NoteResponse.model_validate(note)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: UUID,
    note_data: NoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
):
    """
    Update a note.
    
    Only the author, advisors, or admins can update notes.
    """
    note = db.query(Note).filter(Note.id == note_id).first()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found."
        )
    
    # Check engagement access
    engagement = db.query(Engagement).filter(Engagement.id == note.engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    if not check_engagement_access(engagement, current_user, db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this engagement."
        )
    
    # Check if user can update (author, advisor, or admin)
    # Author is the user who created the note (author_id == user_id)
    can_update = (
        current_user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN] or
        note.author_id == current_user.id or
        (current_user.role == UserRole.ADVISOR and (
            engagement.primary_advisor_id == current_user.id or
            (engagement.secondary_advisor_ids and current_user.id in engagement.secondary_advisor_ids)
        ))
    )
    
    if not can_update:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this note."
        )
    
    # Update fields
    update_data = note_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(note, field, value)
    
    db.commit()
    db.refresh(note)
    
    return NoteResponse.model_validate(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
):
    """
    Delete a note.
    
    Only the author, advisors, or admins can delete notes.
    """
    note = db.query(Note).filter(Note.id == note_id).first()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found."
        )
    
    # Check engagement access
    engagement = db.query(Engagement).filter(Engagement.id == note.engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    if not check_engagement_access(engagement, current_user, db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this engagement."
        )
    
    # Check if user can delete (author, advisor, or admin)
    # Author is the user who created the note (author_id == user_id)
    can_delete = (
        current_user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN] or
        note.author_id == current_user.id or
        (current_user.role == UserRole.ADVISOR and (
            engagement.primary_advisor_id == current_user.id or
            (engagement.secondary_advisor_ids and current_user.id in engagement.secondary_advisor_ids)
        ))
    )
    
    if not can_delete:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this note."
        )
    
    db.delete(note)
    db.commit()
    
    return None