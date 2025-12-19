"""
Task CRUD API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, text
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from ..database import get_db
from ..models.engagement import Engagement
from ..models.user import User, UserRole
from ..models.task import Task
from ..schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskListItem,
    TaskCreateFromDiagnostic,
    BulkTaskCreate,
)
from ..services.role_check import get_current_user_from_token, check_engagement_access

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Create a new task.
    
    User must have access to the engagement.
    The created_by_user_id will be set to the current user.
    """
    # Verify engagement exists
    engagement = db.query(Engagement).filter(Engagement.id == task_data.engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    # Check engagement access
    if not check_engagement_access(engagement, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this engagement."
        )
    
    # Verify assigned user exists if provided
    if task_data.assigned_to_user_id:
        assigned_user = db.query(User).filter(User.id == task_data.assigned_to_user_id).first()
        if not assigned_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assigned user not found."
            )
        if not assigned_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned user is inactive."
            )
    
    # Verify diagnostic exists if provided
    if task_data.diagnostic_id:
        from ..models.diagnostic import Diagnostic
        diagnostic = db.query(Diagnostic).filter(Diagnostic.id == task_data.diagnostic_id).first()
        if not diagnostic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diagnostic not found."
            )
        if diagnostic.engagement_id != task_data.engagement_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Diagnostic does not belong to this engagement."
            )
    
    # Create task (use current_user.id as created_by_user_id, ignore from request for security)
    task = Task(
        engagement_id=task_data.engagement_id,
        created_by_user_id=current_user.id,  # Always use current user, ignore request value
        assigned_to_user_id=task_data.assigned_to_user_id,
        diagnostic_id=task_data.diagnostic_id,
        title=task_data.title,
        description=task_data.description,
        task_type=task_data.task_type,
        status=task_data.status,
        priority=task_data.priority,
        priority_rank=task_data.priority_rank,
        module_reference=task_data.module_reference,
        impact_level=task_data.impact_level,
        effort_level=task_data.effort_level,
        due_date=task_data.due_date,
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return TaskResponse.model_validate(task)


@router.post("/from-diagnostic", response_model=List[TaskResponse], status_code=status.HTTP_201_CREATED)
async def create_tasks_from_diagnostic(
    bulk_data: BulkTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Create multiple tasks from diagnostic AI recommendations.
    
    User must have access to the engagement.
    """
    if not bulk_data.tasks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tasks provided."
        )
    
    # Verify all tasks belong to the same engagement
    engagement_ids = {task.engagement_id for task in bulk_data.tasks}
    if len(engagement_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All tasks must belong to the same engagement."
        )
    
    engagement_id = list(engagement_ids)[0]
    
    # Verify engagement exists and user has access
    engagement = db.query(Engagement).filter(Engagement.id == engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    if not check_engagement_access(engagement, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this engagement."
        )
    
    # Verify diagnostic exists and belongs to engagement
    diagnostic_ids = {task.diagnostic_id for task in bulk_data.tasks if task.diagnostic_id}
    if len(diagnostic_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All tasks must belong to the same diagnostic."
        )
    
    if diagnostic_ids:
        from ..models.diagnostic import Diagnostic
        diagnostic_id = list(diagnostic_ids)[0]
        diagnostic = db.query(Diagnostic).filter(Diagnostic.id == diagnostic_id).first()
        if not diagnostic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diagnostic not found."
            )
        if diagnostic.engagement_id != engagement_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Diagnostic does not belong to this engagement."
            )
    
    # Create all tasks
    created_tasks = []
    for task_data in bulk_data.tasks:
        # Verify assigned user exists if provided
        if task_data.assigned_to_user_id:
            assigned_user = db.query(User).filter(User.id == task_data.assigned_to_user_id).first()
            if not assigned_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assigned user not found for task: {task_data.title}"
                )
        
        task = Task(
            engagement_id=task_data.engagement_id,
            created_by_user_id=current_user.id,
            assigned_to_user_id=task_data.assigned_to_user_id,
            diagnostic_id=task_data.diagnostic_id,
            title=task_data.title,
            description=task_data.description,
            task_type=task_data.task_type,
            status="pending",  # New tasks start as pending
            priority=task_data.priority,
            priority_rank=task_data.priority_rank,
            module_reference=task_data.module_reference,
            impact_level=task_data.impact_level,
            effort_level=task_data.effort_level,
            due_date=task_data.due_date,
        )
        db.add(task)
        created_tasks.append(task)
    
    db.commit()
    
    # Refresh all tasks
    for task in created_tasks:
        db.refresh(task)
    
    return [TaskResponse.model_validate(task) for task in created_tasks]


@router.get("", response_model=List[TaskListItem])
async def list_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
    engagement_id: Optional[UUID] = Query(None, description="Filter by engagement ID"),
    assigned_to_user_id: Optional[UUID] = Query(None, description="Filter by assigned user ID"),
    status_filter: Optional[str] = Query(None, description="Filter by status (pending, in_progress, completed, cancelled)"),
    priority_filter: Optional[str] = Query(None, description="Filter by priority (low, medium, high, urgent)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
):
    """
    List tasks accessible to the current user.
    
    Returns tasks based on user's access to engagements.
    """
    # Build base query
    query = db.query(Task)
    
    # Filter by engagement if provided
    if engagement_id:
        # Verify engagement access
        engagement = db.query(Engagement).filter(Engagement.id == engagement_id).first()
        if not engagement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Engagement not found."
            )
        if not check_engagement_access(engagement, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this engagement."
            )
        query = query.filter(Task.engagement_id == engagement_id)
    else:
        # Filter by accessible engagements and user's tasks
        if current_user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
            # Admins see all tasks
            pass
        elif current_user.role == UserRole.FIRM_ADMIN:
            # Firm Admin sees all tasks in their firm's engagements
            query = query.join(Engagement).filter(
                Engagement.firm_id == current_user.firm_id
            )
        elif current_user.role == UserRole.FIRM_ADVISOR:
            # Firm Advisor sees:
            # 1. Tasks they created (created_by_user_id = advisor)
            # 2. Tasks assigned to them (assigned_to_user_id = advisor)
            # 3. Tasks from their assigned engagements (same firm, primary or secondary advisor)
            query = query.join(Engagement).filter(
                Engagement.firm_id == current_user.firm_id
            ).filter(
                or_(
                    Task.created_by_user_id == current_user.id,
                    Task.assigned_to_user_id == current_user.id,
                    Engagement.primary_advisor_id == current_user.id,
                    text("secondary_advisor_ids @> ARRAY[:user_id]::uuid[]").bindparams(user_id=current_user.id)
                )
            )
        elif current_user.role == UserRole.ADVISOR:
            # Solo Advisors see:
            # 1. Tasks they created (created_by_user_id = advisor)
            # 2. Tasks assigned to them (assigned_to_user_id = advisor)
            # 3. Tasks from their engagements (primary or secondary advisor)
            query = query.join(Engagement).filter(
                or_(
                    Task.created_by_user_id == current_user.id,
                    Task.assigned_to_user_id == current_user.id,
                    Engagement.primary_advisor_id == current_user.id,
                    text("secondary_advisor_ids @> ARRAY[:user_id]::uuid[]").bindparams(user_id=current_user.id)
                )
            )
        elif current_user.role == UserRole.CLIENT:
            # Clients see:
            # 1. Tasks they created (created_by_user_id = client)
            # 2. Tasks assigned to them (assigned_to_user_id = client)
            query = query.filter(
                or_(
                    Task.created_by_user_id == current_user.id,
                    Task.assigned_to_user_id == current_user.id
                )
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid user role."
            )
    
    # Filter by assigned user
    if assigned_to_user_id:
        query = query.filter(Task.assigned_to_user_id == assigned_to_user_id)
    
    # Filter by status
    if status_filter:
        query = query.filter(Task.status == status_filter)
    
    # Filter by priority
    if priority_filter:
        query = query.filter(Task.priority == priority_filter)
    
    # Get tasks ordered by priority and due date
    tasks = query.order_by(
        Task.priority.desc(),
        Task.due_date.asc().nulls_last(),
        Task.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    # Build response with user names
    result = []
    for task in tasks:
        # Get engagement name
        engagement = db.query(Engagement).filter(Engagement.id == task.engagement_id).first()
        engagement_name = engagement.engagement_name if engagement else None
        
        # Get assigned user name
        assigned_to_name = None
        if task.assigned_to_user_id:
            assigned_user = db.query(User).filter(User.id == task.assigned_to_user_id).first()
            assigned_to_name = assigned_user.name or assigned_user.email if assigned_user else None
        
        # Get creator name
        creator = db.query(User).filter(User.id == task.created_by_user_id).first()
        created_by_name = creator.name or creator.email if creator else None
        
        task_dict = {
            **task.__dict__,
            "engagement_name": engagement_name,
            "assigned_to_name": assigned_to_name,
            "created_by_name": created_by_name,
        }
        result.append(TaskListItem(**task_dict))
    
    return result


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
):
    """
    Get a task by ID.
    
    User must have access to the engagement.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found."
        )
    
    # Check engagement access
    engagement = db.query(Engagement).filter(Engagement.id == task.engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    if not check_engagement_access(engagement, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this engagement."
        )
    
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    task_data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
):
    """
    Update a task.
    
    User must have access to the engagement.
    Only the creator, assigned user, advisors, or admins can update tasks.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found."
        )
    
    # Check engagement access
    engagement = db.query(Engagement).filter(Engagement.id == task.engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    if not check_engagement_access(engagement, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this engagement."
        )
    
    # Check if user can update (creator, assigned user, advisor, or admin)
    can_update = False
    if current_user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        can_update = True
    elif task.created_by_user_id == current_user.id:
        can_update = True
    elif task.assigned_to_user_id == current_user.id:
        can_update = True
    elif current_user.role == UserRole.FIRM_ADMIN:
        # Firm Admin can update tasks in their firm
        if engagement.firm_id == current_user.firm_id:
            can_update = True
    elif current_user.role == UserRole.FIRM_ADVISOR:
        # Firm Advisor can update tasks in their assigned engagements (same firm)
        if engagement.firm_id == current_user.firm_id:
            if engagement.primary_advisor_id == current_user.id:
                can_update = True
            elif engagement.secondary_advisor_ids and current_user.id in engagement.secondary_advisor_ids:
                can_update = True
    elif current_user.role == UserRole.ADVISOR:
        # Solo Advisor can update tasks in their engagements
        if engagement.primary_advisor_id == current_user.id:
            can_update = True
        elif engagement.secondary_advisor_ids and current_user.id in engagement.secondary_advisor_ids:
            can_update = True
    
    if not can_update:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this task."
        )
    
    # Verify assigned user exists if being updated
    if task_data.assigned_to_user_id is not None and task_data.assigned_to_user_id != task.assigned_to_user_id:
        assigned_user = db.query(User).filter(User.id == task_data.assigned_to_user_id).first()
        if not assigned_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assigned user not found."
            )
        if not assigned_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned user is inactive."
            )
    
    # Update fields
    update_data = task_data.model_dump(exclude_unset=True)
    
    # Handle status change to completed
    if update_data.get("status") == "completed" and task.status != "completed":
        update_data["completed_at"] = datetime.utcnow()
    elif update_data.get("status") != "completed" and task.status == "completed":
        # If uncompleting, clear completed_at
        update_data["completed_at"] = None
    
    for field, value in update_data.items():
        setattr(task, field, value)
    
    db.commit()
    db.refresh(task)
    
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token),
):
    """
    Delete a task.
    
    Only the creator, advisors, or admins can delete tasks.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found."
        )
    
    # Check engagement access
    engagement = db.query(Engagement).filter(Engagement.id == task.engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found."
        )
    
    if not check_engagement_access(engagement, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this engagement."
        )
    
    # Check if user can delete (creator, advisor, or admin)
    can_delete = False
    if current_user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        can_delete = True
    elif task.created_by_user_id == current_user.id:
        can_delete = True
    elif current_user.role == UserRole.FIRM_ADMIN:
        # Firm Admin can delete tasks in their firm
        if engagement.firm_id == current_user.firm_id:
            can_delete = True
    elif current_user.role == UserRole.FIRM_ADVISOR:
        # Firm Advisor can delete tasks in their assigned engagements (same firm)
        if engagement.firm_id == current_user.firm_id:
            if engagement.primary_advisor_id == current_user.id:
                can_delete = True
            elif engagement.secondary_advisor_ids and current_user.id in engagement.secondary_advisor_ids:
                can_delete = True
    elif current_user.role == UserRole.ADVISOR:
        # Solo Advisor can delete tasks in their engagements
        if engagement.primary_advisor_id == current_user.id:
            can_delete = True
        elif engagement.secondary_advisor_ids and current_user.id in engagement.secondary_advisor_ids:
            can_delete = True
    
    if not can_delete:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this task."
        )
    
    db.delete(task)
    db.commit()
    
    return None

