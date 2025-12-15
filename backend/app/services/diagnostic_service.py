"""
Diagnostic service - Main orchestrator for AI diagnostic workflow
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import datetime
import json

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
        
        # Merge responses (preserve existing responses)
        current_responses = diagnostic.user_responses or {}
        current_responses.update(user_responses)
        diagnostic.user_responses = current_responses
        
        # Update status if provided
        if status:
            diagnostic.status = status
            
            # Set started_at if moving to in_progress
            if status == "in_progress" and not diagnostic.started_at:
                diagnostic.started_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(diagnostic)
        
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
        
        try:
            # Execute AI processing pipeline
            await self._process_diagnostic_pipeline(diagnostic)
            
            # Update status to completed
            diagnostic.status = "completed"
            diagnostic.completed_at = datetime.utcnow()
            
        except Exception as e:
            # If processing fails, mark as failed
            diagnostic.status = "failed"
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
        
        # Load required data files
        diagnostic_questions = load_diagnostic_questions()
        scoring_map = load_scoring_map()
        task_library = load_task_library()
        
        # ===== STEP 1: Generate Q&A Extract =====
        json_extract = self._generate_qa_extract(
            diagnostic_questions,
            user_responses
        )
        
        # ===== STEP 2: Generate Summary =====
        summary_prompt = load_prompt("diagnostic_summary")
        summary_result = await openai_service.generate_summary(
            system_prompt=summary_prompt,
            user_responses=user_responses
        )
        
        summary = summary_result["content"]
        
        # ===== STEP 3: Process Scores with GPT (including uploaded files) =====
        # Get files attached to this diagnostic
        attached_files = list(diagnostic.media)
        file_context = self._build_file_context(attached_files)
        
        # Extract OpenAI file IDs (only files that have been uploaded to OpenAI)
        file_ids = [
            file.openai_file_id 
            for file in attached_files 
            if file.openai_file_id
        ]
        
        print(f"📎 Found {len(attached_files)} attached files for scoring")
        print(f"📤 {len(file_ids)} files uploaded to OpenAI and ready for AI analysis")
        
        scoring_prompt = load_prompt("scoring_prompt")
        scoring_result = await openai_service.process_scoring(
            scoring_prompt=scoring_prompt,
            scoring_map=scoring_map,
            task_library=task_library,
            diagnostic_questions=diagnostic_questions,
            user_responses=user_responses,
            file_context=file_context,  # Context about files (text description)
            file_ids=file_ids if file_ids else None  # Actual file IDs for GPT to read
        )
        
        # Extract scoring data
        scoring_data = scoring_result["parsed_content"]
        
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
        
        # ===== STEP 5: Generate Advice (Optional) =====
        advice = None
        try:
            advice_prompt = load_prompt("advice_prompt_diagnostic")
            advice_result = await openai_service.generate_advice(
                advice_prompt=advice_prompt,
                scoring_data=scoring_data
            )
            advice = advice_result["content"]
        except Exception as e:
            # Advice generation is optional, don't fail the whole process
            print(f"Warning: Could not generate advice: {str(e)}")
        
        # ===== STEP 6: Auto-Generate Tasks =====
        tasks_count = 0
        try:
            tasks_count = await self._generate_tasks(
                diagnostic=diagnostic,
                summary=summary,
                json_extract=json_extract,
                roadmap=roadmap
            )
        except Exception as e:
            print(f"Warning: Could not generate tasks: {str(e)}")
        
        # ===== Save All Data to Database =====
        # Store JSON extract
        if not hasattr(diagnostic, 'json_extract'):
            # Add as metadata if not a direct column
            pass
        
        # Store summary
        # Note: If you want to store summary separately, add a column
        # For now, it's included in ai_analysis
        
        # Store scoring data
        diagnostic.scoring_data = {
            "scored_rows": scored_rows,
            "validation": validation,
            "tokens_used": scoring_result.get("tokens_used", 0)
        }
        
        # Store module scores
        diagnostic.module_scores = {
            "modules": {m["module"]: m for m in ranked_modules},
            "ranked": ranked_modules
        }
        
        # Store overall score
        diagnostic.overall_score = overall_score
        
        # Store AI analysis (roadmap, advisor report, summary, advice)
        diagnostic.ai_analysis = {
            "clientSummary": client_summary,
            "summary": summary,
            "roadmap": roadmap,
            "advisorReport": advisor_report,
            "advice": advice,
            "validation": validation
        }
        
        # Store report HTML
        diagnostic.report_html = advisor_report
        
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
    
    def _build_file_context(self, files: list) -> Optional[str]:
        """
        Build file context string for GPT analysis.
        Includes information about uploaded files (Balance Sheets, P&L, etc.)
        
        Args:
            files: List of Media objects
            
        Returns:
            Formatted string with file information for GPT context
        """
        if not files:
            return None
        
        file_info_list = []
        files_with_ids = 0
        
        for file in files:
            file_info = {
                "filename": file.file_name,
                "type": file.file_type or file.file_extension,
                "question": file.question_field_name or "general",
                "openai_file_id": file.openai_file_id
            }
            file_info_list.append(file_info)
            if file.openai_file_id:
                files_with_ids += 1
        
        # Build context string
        context = "\n\n=== UPLOADED DOCUMENTS ===\n"
        context += f"The user has uploaded {len(files)} document(s) for this diagnostic.\n"
        
        if files_with_ids > 0:
            context += f"✅ {files_with_ids} document(s) are attached to this request and available for you to read directly.\n\n"
        
        context += "Documents uploaded:\n\n"
        
        for idx, file_info in enumerate(file_info_list, 1):
            context += f"{idx}. {file_info['filename']}\n"
            context += f"   Type: {file_info['type']}\n"
            context += f"   Question: {file_info['question']}\n"
            if file_info['openai_file_id']:
                context += f"   Status: ✅ Attached for analysis\n"
            else:
                context += f"   Status: ⚠️ Metadata only (not attached)\n"
            context += "\n"
        
        if files_with_ids > 0:
            context += "IMPORTANT INSTRUCTIONS:\n"
            context += "- The attached documents (financial statements, reports, etc.) are available for you to read.\n"
            context += "- When scoring, analyze the actual data from these documents.\n"
            context += "- For financial questions (M1), review P&L statements, balance sheets, and financial reports.\n"
            context += "- Use document data to validate and enrich scores beyond just survey responses.\n"
            context += "- Extract key metrics, trends, and insights from the documents.\n"
        
        context += "=== END UPLOADED DOCUMENTS ===\n\n"
        
        return context
    
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
        
        # Parse tasks
        tasks_data = task_result["parsed_content"]
        
        # Handle both array and object with tasks key
        if isinstance(tasks_data, dict):
            tasks_list = tasks_data.get("tasks", [])
        else:
            tasks_list = tasks_data
        
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
                
            except Exception as e:
                print(f"Warning: Could not create task: {str(e)}")
                continue
        
        self.db.commit()
        
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

