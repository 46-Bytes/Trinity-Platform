"""
Diagnostic service - Main orchestrator for AI diagnostic workflow
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import datetime
import json
import logging

from app.models.diagnostic import Diagnostic
from app.models.task import Task
from app.models.engagement import Engagement
from app.services.openai_service import openai_service
from app.services.scoring_service import scoring_service
from app.utils.file_loader import (
    load_diagnostic_questions,
    load_scoring_map,
    load_task_library,
    load_prompt
)


class DiagnosticService:
    """
    Main service for handling diagnostic workflow.
    
    Workflow:
    1. Create diagnostic with questions
    2. User fills out responses (incremental saves)
    3. User submits → AI processing chain:
       a. Generate Q&A extract
       b. Generate summary
       c. Process scores with GPT
       d. Calculate module averages
       e. Generate roadmap
       f. Generate advisor report
       g. Auto-generate tasks
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    # ==================== PHASE 1: CREATE DIAGNOSTIC ====================
    
    async def create_diagnostic(
        self,
        engagement_id: UUID,
        created_by_user_id: UUID,
        diagnostic_type: str = "business_health_assessment",
        diagnostic_version: str = "1.0"
    ) -> Diagnostic:
        """
        Create a new diagnostic for an engagement.
        
        Args:
            engagement_id: UUID of the engagement
            created_by_user_id: UUID of the user creating the diagnostic
            diagnostic_type: Type of diagnostic
            diagnostic_version: Version of diagnostic
            
        Returns:
            Created Diagnostic model
        """
        self.logger.info(
            "Creating diagnostic",
            extra={
                "engagement_id": str(engagement_id),
                "created_by_user_id": str(created_by_user_id),
                "diagnostic_type": diagnostic_type,
                "diagnostic_version": diagnostic_version,
            },
        )
        # Verify engagement exists
        engagement = self.db.query(Engagement).filter(
            Engagement.id == engagement_id
        ).first()
        
        if not engagement:
            raise ValueError(f"Engagement {engagement_id} not found")
        
        # Load diagnostic questions
        questions = load_diagnostic_questions()
        
        # Create diagnostic
        diagnostic = Diagnostic(
            engagement_id=engagement_id,
            created_by_user_id=created_by_user_id,
            status="draft",
            diagnostic_type=diagnostic_type,
            diagnostic_version=diagnostic_version,
            questions=questions,
            user_responses={},
            tasks_generated_count=0
        )
        
        self.db.add(diagnostic)
        self.db.commit()
        self.db.refresh(diagnostic)
        self.logger.info(
            "Diagnostic created",
            extra={"diagnostic_id": str(diagnostic.id), "engagement_id": str(engagement_id)},
        )
        
        return diagnostic
    
    # ==================== PHASE 2: UPDATE RESPONSES ====================
    
    async def update_responses(
        self,
        diagnostic_id: UUID,
        user_responses: Dict[str, Any],
        status: Optional[str] = None
    ) -> Diagnostic:
        """
        Update diagnostic responses (incremental autosave).
        
        Args:
            diagnostic_id: UUID of the diagnostic
            user_responses: User's responses to questions
            status: Optional status update (e.g., "in_progress")
            
        Returns:
            Updated Diagnostic model
        """
        diagnostic = self.db.query(Diagnostic).filter(
            Diagnostic.id == diagnostic_id
        ).first()
        
        if not diagnostic:
            raise ValueError(f"Diagnostic {diagnostic_id} not found")
        
        self.logger.info(
            "Updating diagnostic responses",
            extra={
                "diagnostic_id": str(diagnostic_id),
                "status": status,
                "keys": list(user_responses.keys()) if user_responses else [],
            },
        )
        # Merge responses (preserve existing responses)
        # Create a new dict to ensure SQLAlchemy detects the change
        current_responses = dict(diagnostic.user_responses or {})
        current_responses.update(user_responses)
        
        # Remove any fields that are explicitly set to None (deletion marker)
        for key, value in list(current_responses.items()):
            if value is None:
                current_responses.pop(key, None)
        
        diagnostic.user_responses = current_responses
        
        # Explicitly flag the JSONB field as modified so SQLAlchemy detects the change
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(diagnostic, "user_responses")
        
        # Update status if provided
        if status:
            diagnostic.status = status
            
            # Set started_at if moving to in_progress
            if status == "in_progress" and not diagnostic.started_at:
                diagnostic.started_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(diagnostic)
        self.logger.info(
            "Diagnostic responses updated",
            extra={
                "diagnostic_id": str(diagnostic_id),
                "status": diagnostic.status,
                "response_keys_count": len(current_responses.keys()),
            },
        )
        
        return diagnostic
    
    # ==================== PHASE 3: SUBMIT & PROCESS ====================
    
    async def submit_diagnostic(
        self,
        diagnostic_id: UUID,
        completed_by_user_id: UUID
    ) -> Diagnostic:
        """
        Submit diagnostic and trigger AI processing pipeline.
        
        This is the main workflow that orchestrates all AI processing:
        1. Generate Q&A extract
        2. Generate summary
        3. Process scores with GPT
        4. Calculate module averages and rankings
        5. Generate advisor report
        6. Auto-generate tasks
        
        Args:
            diagnostic_id: UUID of the diagnostic
            completed_by_user_id: UUID of the user submitting
            
        Returns:
            Processed Diagnostic model with all AI data
        """
        diagnostic = self.db.query(Diagnostic).filter(
            Diagnostic.id == diagnostic_id
        ).first()
        
        if not diagnostic:
            raise ValueError(f"Diagnostic {diagnostic_id} not found")
        
        if not diagnostic.user_responses:
            raise ValueError("Cannot submit diagnostic without responses")
        
        # Update status to processing
        diagnostic.status = "processing"
        diagnostic.completed_by_user_id = completed_by_user_id
        self.db.commit()
        self.logger.info(
            "Diagnostic submission started",
            extra={
                "diagnostic_id": str(diagnostic_id),
                "completed_by_user_id": str(completed_by_user_id),
                "response_keys": list(diagnostic.user_responses.keys()),
            },
        )
        
        try:
            # Execute AI processing pipeline
            await self._process_diagnostic_pipeline(diagnostic)
            
            # Update status to completed
            diagnostic.status = "completed"
            diagnostic.completed_at = datetime.utcnow()
            self.logger.info(
                "Diagnostic submission completed",
                extra={"diagnostic_id": str(diagnostic_id)},
            )
            
        except Exception as e:
            # If processing fails, mark as failed
            diagnostic.status = "failed"
            self.logger.exception(
                "Diagnostic processing failed",
                extra={"diagnostic_id": str(diagnostic_id)},
            )
            raise Exception(f"Diagnostic processing failed: {str(e)}")
        
        finally:
            self.db.commit()
            self.db.refresh(diagnostic)
        
        return diagnostic
    
    async def _process_diagnostic_pipeline(self, diagnostic: Diagnostic):
        """
        Internal method to execute the complete AI processing pipeline.
        
        This method orchestrates all AI steps in sequence:
        1. Generate Q&A extract (for readability)
        2. Generate summary (client overview)
        3. Process scores with GPT (main scoring)
        4. Validate and calculate scores
        5. Generate advice (optional)
        6. Auto-generate tasks
        """
        user_responses = diagnostic.user_responses
        self.logger.info(
            "Pipeline started",
            extra={"diagnostic_id": str(diagnostic.id), "response_keys": list(user_responses.keys())},
        )
        
        # Load required data files
        diagnostic_questions = load_diagnostic_questions()
        scoring_map = load_scoring_map()
        task_library = load_task_library()
        self.logger.info(
            "Loaded auxiliary data",
            extra={
                "diagnostic_id": str(diagnostic.id),
                "questions_pages": len(diagnostic_questions.get("pages", [])) if isinstance(diagnostic_questions, dict) else "unknown",
            },
        )
        
        # ===== STEP 1: Generate Q&A Extract =====
        json_extract = self._generate_qa_extract(
            diagnostic_questions,
            user_responses
        )
        self.logger.info("Generated Q&A extract", extra={"diagnostic_id": str(diagnostic.id)})
        
        # ===== STEP 2: Generate Summary =====
        summary_prompt = load_prompt("diagnostic_summary")
        summary_result = await openai_service.generate_summary(
            system_prompt=summary_prompt,
            user_responses=user_responses
        )
        
        summary = summary_result["content"]
        self.logger.info(
            "Generated summary",
            extra={"diagnostic_id": str(diagnostic.id), "tokens_used": summary_result.get("tokens_used", 0)},
        )
        
        # ===== STEP 3: Process Scores with GPT =====
        scoring_prompt = load_prompt("scoring_prompt")
        scoring_result = await openai_service.process_scoring(
            scoring_prompt=scoring_prompt,
            scoring_map=scoring_map,
            task_library=task_library,
            diagnostic_questions=diagnostic_questions,
            user_responses=user_responses
        )
        
        # Extract scoring data
        scoring_data = scoring_result["parsed_content"]
        self.logger.info(
            "Processed scoring",
            extra={
                "diagnostic_id": str(diagnostic.id),
                "tokens_used": scoring_result.get("tokens_used", 0),
                "scored_rows": len(scoring_data.get("scored_rows", [])),
            },
        )
        
        # ===== STEP 4: Calculate and Validate Scores =====
        scored_rows = scoring_data.get("scored_rows", [])
        roadmap = scoring_data.get("roadmap", [])
        client_summary = scoring_data.get("clientSummary", "")
        advisor_report = scoring_data.get("advisorReport", "")
        
        # Calculate module scores
        module_scores = scoring_service.calculate_module_scores(scored_rows)
        
        # Rank modules
        ranked_modules = scoring_service.rank_modules(module_scores)
        
        # Calculate overall score
        overall_score = scoring_service.calculate_overall_score(module_scores)
        
        # Validate scoring data
        validation = scoring_service.validate_scoring_data(
            ai_scoring_data=scoring_data,
            user_responses=user_responses,
            scoring_map=scoring_map
        )
        self.logger.info(
            "Calculated scores",
            extra={
                "diagnostic_id": str(diagnostic.id),
                "modules_count": len(module_scores),
                "overall_score": str(overall_score),
            },
        )
        
        # ===== STEP 5: Generate Advice (Optional) =====
        advice = None
        try:
            advice_prompt = load_prompt("advice_prompt_diagnostic")
            advice_result = await openai_service.generate_advice(
                advice_prompt=advice_prompt,
                scoring_data=scoring_data
            )
            advice = advice_result["content"]
            self.logger.info(
                "Generated advice",
                extra={"diagnostic_id": str(diagnostic.id), "tokens_used": advice_result.get("tokens_used", 0)},
            )
        except Exception as e:
            # Advice generation is optional, don't fail the whole process
            self.logger.warning(
                "Could not generate advice",
                extra={"diagnostic_id": str(diagnostic.id), "error": str(e)},
            )
        
        # ===== STEP 6: Auto-Generate Tasks =====
        tasks_count = 0
        try:
            tasks_count = await self._generate_tasks(
                diagnostic=diagnostic,
                summary=summary,
                json_extract=json_extract,
                roadmap=roadmap
            )
            self.logger.info(
                "Tasks generated",
                extra={"diagnostic_id": str(diagnostic.id), "tasks_count": tasks_count},
            )
        except Exception as e:
            self.logger.warning(
                "Could not generate tasks",
                extra={"diagnostic_id": str(diagnostic.id), "error": str(e)},
            )
        
        # ===== Save All Data to Database =====
        # Store JSON extract
        if not hasattr(diagnostic, 'json_extract'):
            # Add as metadata if not a direct column
            pass
        
        # Store summary
        # Note: If you want to store summary separately, add a column
        # For now, it's included in ai_analysis
        
        # Import flag_modified for JSONB fields
        from sqlalchemy.orm.attributes import flag_modified
        
        # Store scoring data (ensure it's a dict, not a string)
        scoring_data_dict = {
            "scored_rows": scored_rows,
            "validation": validation,
            "tokens_used": scoring_result.get("tokens_used", 0)
        }
        diagnostic.scoring_data = scoring_data_dict
        flag_modified(diagnostic, "scoring_data")
        
        # Store module scores (ensure it's a dict, not a string)
        module_scores_dict = {
            "modules": {m["module"]: m for m in ranked_modules},
            "ranked": ranked_modules
        }
        diagnostic.module_scores = module_scores_dict
        flag_modified(diagnostic, "module_scores")
        
        # Store overall score
        diagnostic.overall_score = overall_score
        
        # Store AI analysis (roadmap, advisor report, summary, advice)
        # Ensure advisor_report is a string, not a dict
        advisor_report_str = advisor_report if isinstance(advisor_report, str) else str(advisor_report)
        
        ai_analysis_dict = {
            "clientSummary": client_summary,
            "summary": summary,
            "roadmap": roadmap,
            "advisorReport": advisor_report_str,
            "advice": advice,
            "validation": validation
        }
        diagnostic.ai_analysis = ai_analysis_dict
        flag_modified(diagnostic, "ai_analysis")
        
        # Store report HTML (ensure it's a string)
        report_html_str = advisor_report_str if isinstance(advisor_report_str, str) else str(advisor_report_str)
        diagnostic.report_html = report_html_str
        
        # Store AI metadata
        diagnostic.ai_model_used = scoring_result.get("model", "gpt-4o")
        diagnostic.ai_tokens_used = (
            scoring_result.get("tokens_used", 0) +
            summary_result.get("tokens_used", 0) +
            (advice_result.get("tokens_used", 0) if advice else 0)
        )
        
        # Store tasks count
        diagnostic.tasks_generated_count = tasks_count
        
        self.db.commit()
        self.logger.info(
            "Pipeline data persisted",
            extra={
                "diagnostic_id": str(diagnostic.id),
                "overall_score": str(overall_score),
                "tasks_count": tasks_count,
            },
        )
    
    def _generate_qa_extract(
        self,
        diagnostic_questions: Dict[str, Any],
        user_responses: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate Q&A extract (question text → answer pairs).
        This makes responses more readable.
        
        Args:
            diagnostic_questions: Diagnostic survey structure
            user_responses: User's responses (key → value)
            
        Returns:
            Dictionary mapping question text to answers
        """
        qa_extract = {}
        
        # Build question key → question text mapping
        question_text_map = {}
        for page in diagnostic_questions.get("pages", []):
            for element in page.get("elements", []):
                question_text_map[element["name"]] = element.get("title", element["name"])
        
        # Map responses to question text
        for key, value in user_responses.items():
            question_text = question_text_map.get(key, key)
            qa_extract[question_text] = value
        
        return qa_extract
    
    async def _generate_tasks(
        self,
        diagnostic: Diagnostic,
        summary: str,
        json_extract: Dict[str, Any],
        roadmap: List[Dict[str, Any]]
    ) -> int:
        """
        Auto-generate tasks based on diagnostic results.
        
        Args:
            diagnostic: Diagnostic model
            summary: Diagnostic summary
            json_extract: Q&A extract (question text → answer pairs)
            roadmap: Priority roadmap with module rankings
            
        Returns:
            Number of tasks created
        """
        # Load task generation prompt
        task_prompt = load_prompt("initial_task_prompt")
        
        # Generate tasks with GPT
        task_result = await openai_service.generate_tasks(
            task_prompt=task_prompt,
            diagnostic_summary=summary,
            json_extract=json_extract,
            roadmap=roadmap
        )
        tasks_raw = task_result.get("parsed_content")
        self.logger.info(
            f"Generated tasks from AI | diagnostic_id={diagnostic.id} | tokens_used={task_result.get('tokens_used', 0)} | tasks_raw={tasks_raw}"
        )
        
        # Parse tasks
        tasks_data = task_result["parsed_content"]
        
        # Handle both array and object with tasks key
        if isinstance(tasks_data, dict):
            tasks_list = tasks_data.get("tasks", [])
        else:
            tasks_list = tasks_data
        
        if not tasks_list:
            self.logger.warning(
                f"No tasks parsed from AI response | diagnostic_id={diagnostic.id} | tasks_data={tasks_data}"
            )
            return 0
        
        self.logger.info(
            f"Parsed tasks list | diagnostic_id={diagnostic.id} | count={len(tasks_list)}"
        )
        
        # Create Task records
        tasks_created = 0
        for task_data in tasks_list:
            try:
                task = Task(
                    engagement_id=diagnostic.engagement_id,
                    diagnostic_id=diagnostic.id,
                    created_by_user_id=diagnostic.created_by_user_id,
                    title=task_data.get("title"),
                    description=task_data.get("description"),
                    task_type="diagnostic_generated",
                    status="pending",
                    priority=task_data.get("priority", "medium"),
                    # Map category to module if possible
                    module_reference=self._map_category_to_module(
                        task_data.get("category", "")
                    )
                )
                
                self.db.add(task)
                tasks_created += 1
                self.logger.info(
                    f"Task created | diagnostic_id={diagnostic.id} | engagement_id={diagnostic.engagement_id} | "
                    f"title={task_data.get('title')} | priority={task_data.get('priority', 'medium')} | "
                    f"module={task_data.get('category', '')} | description={task_data.get('description')}"
                )
                
            except Exception as e:
                self.logger.warning(
                    f"Could not create task | diagnostic_id={diagnostic.id} | error={str(e)}"
                )
                continue
        
        self.db.commit()
        self.logger.info(
            f"Tasks committed | diagnostic_id={diagnostic.id} | tasks_created={tasks_created}"
        )
        
        return tasks_created
    
    def _map_category_to_module(self, category: str) -> Optional[str]:
        """Map task category to module reference."""
        category_to_module = {
            "financial": "M1",
            "legal": "M2",
            "legal-licensing": "M2",
            "operations": "M3",
            "human-resources": "M4",
            "customers": "M5",
            "sales-marketing": "M5",
            "products-or-services": "M5",
            "technology": "M6",
            "tax": "M7",
            "general": "M8"
        }
        
        return category_to_module.get(category.lower())
    
    # ==================== PHASE 4: RETRIEVE DIAGNOSTIC ====================
    
    def get_diagnostic(self, diagnostic_id: UUID) -> Optional[Diagnostic]:
        """Get diagnostic by ID."""
        return self.db.query(Diagnostic).filter(
            Diagnostic.id == diagnostic_id
        ).first()
    
    def get_engagement_diagnostics(self, engagement_id: UUID) -> list:
        """Get all diagnostics for an engagement."""
        return self.db.query(Diagnostic).filter(
            Diagnostic.engagement_id == engagement_id
        ).order_by(Diagnostic.created_at.desc()).all()
    
    # ==================== PHASE 5: HELPER METHODS ====================
    
    async def regenerate_report(self, diagnostic_id: UUID) -> Diagnostic:
        """
        Regenerate the advisor report for a completed diagnostic.
        Useful if you want to refresh the report without reprocessing scores.
        
        Args:
            diagnostic_id: UUID of the diagnostic
            
        Returns:
            Updated Diagnostic model
        """
        diagnostic = self.db.query(Diagnostic).filter(
            Diagnostic.id == diagnostic_id
        ).first()
        
        if not diagnostic:
            raise ValueError(f"Diagnostic {diagnostic_id} not found")
        
        if diagnostic.status != "completed":
            raise ValueError("Can only regenerate reports for completed diagnostics")
        
        # Use existing scoring data to regenerate report
        scoring_data = diagnostic.ai_analysis
        
        advice_prompt = load_prompt("advice_prompt_diagnostic")
        advice_result = await openai_service.generate_advice(
            advice_prompt=advice_prompt,
            scoring_data=scoring_data
        )
        
        # Update report
        diagnostic.ai_analysis["advice"] = advice_result["content"]
        diagnostic.report_html = scoring_data.get("advisorReport", "")
        
        self.db.commit()
        self.db.refresh(diagnostic)
        
        return diagnostic


def get_diagnostic_service(db: Session) -> DiagnosticService:
    """Factory function to create DiagnosticService with DB session."""
    return DiagnosticService(db)

