"""
Diagnostic API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.schemas.diagnostic import (
    DiagnosticCreate,
    DiagnosticResponse,
    DiagnosticDetail,
    DiagnosticResults,
    DiagnosticResponseUpdate,
    DiagnosticSubmit,
    DiagnosticListItem
)
from app.services.diagnostic_service import get_diagnostic_service
from app.api.auth import get_current_user
from app.models.user import User


router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


# ==================== CREATE DIAGNOSTIC ====================

@router.post("/create", response_model=DiagnosticResponse, status_code=status.HTTP_201_CREATED)
async def create_diagnostic(
    diagnostic_data: DiagnosticCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new diagnostic for an engagement.
    
    **Workflow Step 1**: Create diagnostic with questions loaded from JSON.
    
    Args:
        diagnostic_data: Diagnostic creation data
        
    Returns:
        Created diagnostic with questions structure
        
    Example:
        ```json
        {
            "engagement_id": "uuid",
            "created_by_user_id": "uuid",
            "diagnostic_type": "business_health_assessment",
            "diagnostic_version": "1.0"
        }
        ```
    """
    service = get_diagnostic_service(db)
    
    try:
        diagnostic = await service.create_diagnostic(
            engagement_id=diagnostic_data.engagement_id,
            created_by_user_id=diagnostic_data.created_by_user_id,
            diagnostic_type=diagnostic_data.diagnostic_type,
            diagnostic_version=diagnostic_data.diagnostic_version
        )
        
        return diagnostic
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create diagnostic: {str(e)}"
        )


# ==================== UPDATE RESPONSES ====================

@router.patch("/{diagnostic_id}/responses", response_model=DiagnosticResponse)
async def update_diagnostic_responses(
    diagnostic_id: UUID,
    update_data: DiagnosticResponseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update diagnostic responses (incremental autosave).
    
    **Workflow Step 2**: User fills out questions, responses saved incrementally.
    
    Args:
        diagnostic_id: UUID of the diagnostic
        update_data: Response updates
        
    Returns:
        Updated diagnostic
        
    Example:
        ```json
        {
            "user_responses": {
                "financial_performance_since_acquisition": "Better",
                "key_reports_review_frequency": "Weekly"
            },
            "status": "in_progress"
        }
        ```
    """
    service = get_diagnostic_service(db)
    
    try:
        diagnostic = await service.update_responses(
            diagnostic_id=diagnostic_id,
            user_responses=update_data.user_responses,
            status=update_data.status
        )
        
        return diagnostic
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update responses: {str(e)}"
        )


# ==================== SUBMIT DIAGNOSTIC ====================

@router.post("/{diagnostic_id}/submit", response_model=DiagnosticResponse)
async def submit_diagnostic(
    diagnostic_id: UUID,
    submit_data: DiagnosticSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit diagnostic and trigger AI processing pipeline.
    
    **Workflow Step 3**: Main AI processing workflow:
    1. Generate Q&A extract
    2. Generate summary
    3. Process scores with GPT
    4. Calculate module averages and rankings
    5. Determine RAG status
    6. Generate roadmap
    7. Generate advisor report
    8. Auto-generate tasks
    
    This endpoint may take 30-60 seconds to complete.
    
    Args:
        diagnostic_id: UUID of the diagnostic
        submit_data: Submission data
        
    Returns:
        Processed diagnostic with AI analysis
        
    Example:
        ```json
        {
            "completed_by_user_id": "uuid"
        }
        ```
    """
    service = get_diagnostic_service(db)
    
    try:
        diagnostic = await service.submit_diagnostic(
            diagnostic_id=diagnostic_id,
            completed_by_user_id=submit_data.completed_by_user_id
        )
        
        return diagnostic
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Diagnostic processing failed: {str(e)}"
        )


# ==================== GET DIAGNOSTIC ====================

@router.get("/{diagnostic_id}", response_model=DiagnosticDetail)
async def get_diagnostic(
    diagnostic_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed diagnostic information.
    
    Returns complete diagnostic with questions, responses, scores, and AI analysis.
    
    Args:
        diagnostic_id: UUID of the diagnostic
        
    Returns:
        Detailed diagnostic data
    """
    service = get_diagnostic_service(db)
    
    diagnostic = service.get_diagnostic(diagnostic_id)
    
    if not diagnostic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic {diagnostic_id} not found"
        )
    
    return diagnostic


# ==================== GET DIAGNOSTIC RESULTS ====================

@router.get("/{diagnostic_id}/results", response_model=DiagnosticResults)
async def get_diagnostic_results(
    diagnostic_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get diagnostic results (scores, roadmap, report).
    
    Lightweight endpoint for displaying results without full questions/responses.
    
    Args:
        diagnostic_id: UUID of the diagnostic
        
    Returns:
        Diagnostic results with scores and AI analysis
    """
    service = get_diagnostic_service(db)
    
    diagnostic = service.get_diagnostic(diagnostic_id)
    
    if not diagnostic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic {diagnostic_id} not found"
        )
    
    if diagnostic.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Diagnostic is not yet completed"
        )
    
    return diagnostic


# ==================== LIST DIAGNOSTICS ====================

@router.get("/engagement/{engagement_id}", response_model=List[DiagnosticListItem])
async def list_engagement_diagnostics(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all diagnostics for an engagement.
    
    Args:
        engagement_id: UUID of the engagement
        
    Returns:
        List of diagnostics for the engagement
    """
    service = get_diagnostic_service(db)
    
    diagnostics = service.get_engagement_diagnostics(engagement_id)
    
    return diagnostics


# ==================== REGENERATE REPORT ====================

@router.post("/{diagnostic_id}/regenerate-report", response_model=DiagnosticResponse)
async def regenerate_diagnostic_report(
    diagnostic_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Regenerate advisor report for a completed diagnostic.
    
    Useful for refreshing the report without reprocessing all scores.
    
    Args:
        diagnostic_id: UUID of the diagnostic
        
    Returns:
        Updated diagnostic with new report
    """
    service = get_diagnostic_service(db)
    
    try:
        diagnostic = await service.regenerate_report(diagnostic_id)
        
        return diagnostic
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate report: {str(e)}"
        )

