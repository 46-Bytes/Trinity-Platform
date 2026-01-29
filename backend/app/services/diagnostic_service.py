"""
Diagnostic service - Main orchestrator for AI diagnostic workflow
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import datetime
import json
import re
import asyncio
import logging
import time
import os

from app.models.diagnostic import Diagnostic
from app.models.task import Task
from app.models.engagement import Engagement
from app.services.openai_service import openai_service
from app.services.scoring_service import scoring_service
from app.utils.background_task_manager import background_task_manager
from app.utils.file_loader import (
    load_diagnostic_questions,
    load_scoring_map,
    load_task_library,
    load_prompt
)


def convert_numbered_list_to_bullets(text: str) -> str:
    """
    Convert numbered lists (1., 2., Step 1, step1), etc.) to bullet points.
    
    Examples:
        "1. First step" -> "- First step"
        "Step 1) Do this" -> "- Do this"
        "step1) Action" -> "- Action"
        "1. Step one\n2. Step two" -> "- Step one\n- Step two"
    
    Args:
        text: Text that may contain numbered lists
        
    Returns:
        Text with numbered lists converted to bullet points
    """
    if not text:
        return text
    
    # Pattern to match various numbered list formats:
    # - "1. " or "1) " (number followed by period or parenthesis)
    # - "Step 1. " or "step 1) " (case-insensitive "step" followed by number)
    # - "step1) " or "Step1. " (no space between step and number)
    # - Handles multi-digit numbers (10., 11), etc.)
    # - Can appear at start of line or after newline
    
    # Split text into lines to process each line individually
    lines = text.split('\n')
    converted_lines = []
    
    for line in lines:
        # Pattern to match numbered list items at the start of a line
        # Matches: "1. ", "1) ", "Step 1. ", "step 1) ", "step1) ", "Step1. ", etc.
        pattern = r'^(?:[Ss]tep\s*)?\d+[.)]\s*'
        
        if re.match(pattern, line):
            # Replace the numbered prefix with a bullet point
            converted_line = re.sub(pattern, '- ', line, count=1)
            converted_lines.append(converted_line)
        else:
            # Keep the line as-is if it doesn't match the pattern
            converted_lines.append(line)
    
    # Join lines back together
    converted_text = '\n'.join(converted_lines)
    
    # Clean up: remove extra spaces after bullet points
    converted_text = re.sub(r'^- \s+', '- ', converted_text, flags=re.MULTILINE)
    
    return converted_text


import logging
logger = logging.getLogger(__name__)

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
            
            # Link diagnostic to conversation for chat
            from app.services.chat_service import get_chat_service
            chat_service = get_chat_service(self.db)
            conversation = chat_service.get_or_create_conversation(
                user_id=diagnostic.created_by_user_id,
                category="diagnostic",
                diagnostic_id=diagnostic.id
            )
            diagnostic.conversation_id = conversation.id
            logger.info(f"Linked diagnostic {diagnostic.id} to conversation {conversation.id}")
            # Update engagement status to completed if diagnostic is completed
            engagement = self.db.query(Engagement).filter(
                Engagement.id == diagnostic.engagement_id
            ).first()
            
            if engagement and engagement.status != "completed":
                engagement.status = "completed"
                if not engagement.completed_at:
                    engagement.completed_at = datetime.utcnow()
                logger.info(f"Updated engagement {engagement.id} status to 'completed' because diagnostic {diagnostic.id} is completed")
            
        except Exception as e:
            # If processing fails, mark as failed
            diagnostic.status = "failed"
            raise Exception(f"Diagnostic processing failed: {str(e)}")
        
        finally:
            self.db.commit()
            self.db.refresh(diagnostic)
        
        return diagnostic
    
    async def _process_diagnostic_pipeline(self, diagnostic: Diagnostic, check_shutdown: bool = False):
        """
        Internal method to execute the complete AI processing pipeline.
        
        This method orchestrates all AI steps in sequence:
        1. Generate Q&A extract (for readability)
        2. Generate summary (client overview)
        3. Process scores with GPT (main scoring)
        4. Validate and calculate scores
        5. Generate advice (optional)
        6. Auto-generate tasks
        
        Args:
            diagnostic: Diagnostic model to process
            check_shutdown: If True, check for shutdown signals between steps
        """
        # Use time_module alias to avoid any scoping issues
        import time as time_module
        
        try:
            pipeline_start = time_module.time()
            start_time_str = time_module.strftime('%Y-%m-%d %H:%M:%S')
        except (NameError, UnboundLocalError, AttributeError) as time_err:
            # Fallback if time module has issues
            logger.warning(f"[Pipeline] Could not get start time: {time_err}")
            pipeline_start = 0
            start_time_str = "unknown"
        
        logger.info(f"[Pipeline] ========== Starting diagnostic pipeline for {diagnostic.id} ==========")
        logger.info(f"[Pipeline] Started at {start_time_str}")
        
        user_responses = diagnostic.user_responses
        
        # Check for shutdown before starting
        if check_shutdown and background_task_manager.is_shutting_down():
            logger.warning(f"[Pipeline] Shutdown detected before starting diagnostic pipeline for {diagnostic.id}")
            raise asyncio.CancelledError("Shutdown detected")
        
        # Load required data files
        logger.info(f"[Pipeline] Loading required data files...")
        diagnostic_questions = load_diagnostic_questions()
        scoring_map = load_scoring_map()
        task_library = load_task_library()
        logger.info(f"[Pipeline] Data files loaded successfully")
        
        # ===== STEP 1: Generate Q&A Extract =====
        step1_start = time_module.time()
        logger.info(f"[Pipeline] ========== STEP 1: JSON Extract Started ==========")
        logger.info(f"[Pipeline] Step 1 started at {time_module.strftime('%Y-%m-%d %H:%M:%S')}")

        json_extract = self._generate_qa_extract(
            diagnostic_questions,
            user_responses
        )
        step1_elapsed = time_module.time() - step1_start
        logger.info(f"[Pipeline] ✅ STEP 1 completed in {step1_elapsed:.2f} seconds")
        logger.info(f"[Pipeline] JSON Extract: {len(json_extract)} items extracted")
        
        # Check for shutdown after step 1
        if check_shutdown and background_task_manager.is_shutting_down():
            logger.warning(f"[Pipeline] Shutdown detected after Q&A extract for diagnostic {diagnostic.id}")
            raise asyncio.CancelledError("Shutdown detected")
        
        # ===== STEP 2: Generate Summary =====
        step2_start = time_module.time()
        logger.info(f"[Pipeline] ========== STEP 2: Generate Summary Started ==========")
        logger.info(f"[Pipeline] Step 2 started at {time_module.strftime('%Y-%m-%d %H:%M:%S')}")
        
        summary_prompt = load_prompt("diagnostic_summary")
        summary_result = await openai_service.generate_summary(
            system_prompt=summary_prompt,
            user_responses=user_responses
        )
        step2_elapsed = time_module.time() - step2_start
        logger.info(f"[Pipeline] ✅ STEP 2 completed in {step2_elapsed:.2f} seconds")
        
        summary = summary_result["content"]
        
        # Check for shutdown after step 2
        if check_shutdown and background_task_manager.is_shutting_down():
            logger.warning(f"  Shutdown detected after summary generation for diagnostic {diagnostic.id}")
            raise asyncio.CancelledError("Shutdown detected")
        
        # ===== STEP 3: Process Scores with GPT (including uploaded files) =====
        step3_start = time_module.time()
        logger.info("=" * 60)
        logger.info("[Pipeline] ========== STEP 3: Starting Scoring Process with GPT ==========")
        logger.info(f"[Pipeline] Step 3 started at {time_module.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        # Get files that are CURRENTLY in user_responses (not stale files)
        # Only use files that the user has explicitly included in their current responses
        attached_files = self._get_current_files_from_responses(diagnostic)
        logger.info(f"[Scoring] Found {len(attached_files)} current files from user_responses for diagnostic {diagnostic.id}")
        
        # Log which files are being used
        if attached_files:
            logger.info(f"[Scoring] Files being used for scoring:")
            for f in attached_files:
                logger.info(f"[Scoring]   - {f.file_name} (media_id: {f.id}, openai_file_id: {f.openai_file_id})")
        else:
            logger.info(f"[Scoring] No files found in user_responses - scoring will proceed without file attachments")
        
        file_context = self._build_file_context(attached_files)
        logger.info(f"[Scoring] File context built: {len(file_context) if file_context else 0} characters")
        
        # Attach files correctly for the Responses API:
        # - PDFs can be attached as message content items: {"type":"input_file","file_id": ...}
        # - CSV/TXT/XLSX/etc. must NOT be attached as message content; they must be provided to
        #   Code Interpreter via tools[].container.file_ids (per OpenAI docs).
        image_or_archive_ext = {"png", "jpg", "jpeg", "gif", "webp", "zip"}
        pdf_ext = {"pdf"}
        ci_ext = {"csv", "txt", "text", "md", "markdown", "json", "xml", "yaml", "yml", "xlsx", "xls"}

        pdf_files = [
            f for f in attached_files
            if f.openai_file_id and f.file_extension and f.file_extension.lower() in pdf_ext
        ]
        ci_files = [
            f for f in attached_files
            if (
                f.openai_file_id
                and f.file_extension
                and f.file_extension.lower() in ci_ext
            )
        ]
        filtered_files = [
            f for f in attached_files
            if f.openai_file_id and f.file_extension and f.file_extension.lower() in image_or_archive_ext
        ]

        pdf_file_ids = [f.openai_file_id for f in pdf_files if f.openai_file_id]
        ci_file_ids = [f.openai_file_id for f in ci_files if f.openai_file_id]

        if filtered_files:
            logger.info(
                f"[Scoring] Filtered out {len(filtered_files)} unsupported attachment(s) (images/zip): "
                f"{[x.file_name + ' (' + (x.file_extension or 'no ext') + ')' for x in filtered_files]}"
            )
        
        # Load scoring prompt
        scoring_prompt = load_prompt("scoring_prompt")

        
        # Call OpenAI API for scoring with file re-upload retry on file-not-found errors
        logger.info("[Scoring] Calling OpenAI API for scoring (this may take several minutes)...")
        
        scoring_start_time = time_module.time()
        
        # Build mapping of file_id -> Media object for retry logic
        file_id_to_media = {}
        for media in pdf_files + ci_files:
            if media.openai_file_id:
                file_id_to_media[media.openai_file_id] = media
        
        max_retries = 1  # Retry once after re-uploading files
        retry_count = 0
        scoring_result = None
        
        while retry_count <= max_retries:
            try:
                # Rebuild file_ids in case they were updated during retry
                pdf_file_ids = [f.openai_file_id for f in pdf_files if f.openai_file_id]
                ci_file_ids = [f.openai_file_id for f in ci_files if f.openai_file_id]
                
                scoring_result = await openai_service.process_scoring(
                    scoring_prompt=scoring_prompt,
                    scoring_map=scoring_map,
                    task_library=task_library,
                    diagnostic_questions=diagnostic_questions,
                    user_responses=user_responses,
                    file_context=file_context,
                    file_ids=pdf_file_ids if pdf_file_ids else None,
                    tools=(
                        [{"type": "code_interpreter", "container": {"type": "auto", "file_ids": ci_file_ids}}]
                        if ci_file_ids
                        else None
                    )
                )
                
                scoring_elapsed = time_module.time() - scoring_start_time
                logger.info(f"[Scoring] ✅ OpenAI scoring completed successfully in {scoring_elapsed:.2f} seconds ({scoring_elapsed/60:.2f} minutes)")
                break  # Success, exit retry loop
                
            except Exception as e:
                error_msg = str(e).lower()
                error_type = type(e).__name__
                
                is_file_error = (
                    "file" in error_msg and ("not found" in error_msg or "invalid" in error_msg or "deleted" in error_msg or "does not exist" in error_msg)
                ) or (
                    "404" in error_msg and "file" in error_msg
                ) or (
                    hasattr(e, 'status_code') and e.status_code == 404 and "file" in error_msg
                )
                
                if is_file_error and retry_count < max_retries:
                    logger.warning(f"[Scoring] ⚠️ File-not-found error detected (attempt {retry_count + 1}/{max_retries + 1}): {error_type}: {error_msg[:200]}")
                    logger.info(f"[Scoring] 🔄 Re-uploading files and retrying...")
                    
                    # Re-upload all files that were used
                    files_to_reupload = pdf_files + ci_files
                    reuploaded_count = 0
                    
                    for media in files_to_reupload:
                        file_path_str = str(media.file_path) if media.file_path else None
                        if not file_path_str or not os.path.exists(file_path_str):
                            logger.warning(f"[Scoring] ⚠️ Cannot re-upload {media.file_name}: file not found at {file_path_str}")
                            continue
                        
                        try:
                            logger.info(f"[Scoring] 🔄 Re-uploading {media.file_name}...")
                            openai_file = await openai_service.upload_file(
                                file_path=file_path_str,
                                purpose="user_data"
                            )
                            
                            if openai_file and openai_file.get("id"):
                                old_file_id = media.openai_file_id
                                media.openai_file_id = openai_file["id"]
                                media.openai_purpose = openai_file.get("purpose", "user_data")
                                media.openai_uploaded_at = datetime.utcnow()
                                
                                # Update file_id_to_media mapping
                                if old_file_id in file_id_to_media:
                                    del file_id_to_media[old_file_id]
                                file_id_to_media[openai_file["id"]] = media
                                
                                self.db.commit()
                                reuploaded_count += 1
                                logger.info(f"[Scoring] Re-uploaded {media.file_name}: new file_id={openai_file['id']}")
                            else:
                                logger.error(f"[Scoring] Failed to re-upload {media.file_name}: OpenAI returned no file ID")
                        except Exception as reupload_error:
                            logger.error(f"[Scoring] Failed to re-upload {media.file_name}: {str(reupload_error)}")
                            # Continue with other files
                    
                    if reuploaded_count > 0:
                        logger.info(f"[Scoring] Re-uploaded {reuploaded_count}/{len(files_to_reupload)} files. Retrying scoring call...")
                        retry_count += 1
                        # Rebuild file lists with updated IDs
                        pdf_files = [f for f in attached_files if f.openai_file_id and f.file_extension and f.file_extension.lower() in pdf_ext]
                        ci_files = [f for f in attached_files if f.openai_file_id and f.file_extension and f.file_extension.lower() in ci_ext]
                        continue  # Retry the scoring call
                    else:
                        logger.error(f"[Scoring] Could not re-upload any files. Failing.")
                        raise
                else:
                    # Not a file error, or max retries reached
                    scoring_elapsed = time_module.time() - scoring_start_time
                    logger.error(f"[Scoring] Error type: {error_type}, Message: {error_msg[:500]}")
                    raise
        
        if scoring_result is None:
            raise Exception("Scoring failed after all retries")
        
        # Extract scoring data
        scoring_data = scoring_result["parsed_content"]
        
        step3_elapsed = time_module.time() - step3_start
        logger.info(f"[Pipeline] ✅ STEP 3 (Scoring) completed in {step3_elapsed:.2f} seconds ({step3_elapsed/60:.2f} minutes)")
        
        # ===== STEP 4: Calculate and Validate Scores =====
        step4_start = time_module.time()
        # Check for shutdown after step 3 (scoring)
        if check_shutdown and background_task_manager.is_shutting_down():
            logger.warning(f"[Pipeline] Shutdown detected after scoring for diagnostic {diagnostic.id}")
            raise asyncio.CancelledError("Shutdown detected")
        
        logger.info("=" * 60)
        logger.info("[Pipeline] ========== STEP 4: Processing Scoring Data ==========")
        logger.info(f"[Pipeline] Step 4 started at {time_module.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        scored_rows = scoring_data.get("scored_rows", [])
        roadmap = scoring_data.get("roadmap", [])
        client_summary = scoring_data.get("clientSummary", "")
        advisor_report = scoring_data.get("advisorReport", "")
        
        
        # Calculate module scores
        logger.info("[Scoring Data] Calculating module scores...")
        module_scores = scoring_service.calculate_module_scores(scored_rows)
        
        # Rank modules
        logger.info("[Scoring Data] Ranking modules...")
        ranked_modules = scoring_service.rank_modules(module_scores)

        # Calculate overall score
        logger.info("[Scoring Data] Calculating overall score...")
        overall_score = scoring_service.calculate_overall_score(module_scores)
        
        # Validate scoring data
        logger.info("[Scoring Data] Validating scoring data...")
        validation = scoring_service.validate_scoring_data(
            ai_scoring_data=scoring_data,
            user_responses=user_responses,
            scoring_map=scoring_map
        )

        step4_elapsed = time_module.time() - step4_start
        logger.info(f"[Pipeline] ✅ STEP 4 completed in {step4_elapsed:.2f} seconds")
        logger.info(f"[Pipeline] ✅ STEP 4 completed in {step4_elapsed:.2f} seconds")

        logger.info("=" * 60)
        logger.info("[Pipeline] STEP 4: Scoring Data Processing Completed")
        logger.info("=" * 60)
        
        # Check for shutdown after step 4
        if check_shutdown and background_task_manager.is_shutting_down():
            logger.warning(f"[Pipeline] Shutdown detected after scoring data processing for diagnostic {diagnostic.id}")
            raise asyncio.CancelledError("Shutdown detected")
        
        # ===== STEP 5: Generate Advice (Optional) =====
        step5_start = time_module.time()
        logger.info(f"[Pipeline] ========== STEP 5: Generate Advice (Optional) Started ==========")
        logger.info(f"[Pipeline] Step 5 started at {time_module.strftime('%Y-%m-%d %H:%M:%S')}")
        
        advice = None
        try:
            advice_prompt = load_prompt("advice_prompt_diagnostic")
            advice_result = await openai_service.generate_advice(
                advice_prompt=advice_prompt,
                scoring_data=scoring_data
            )
            advice = advice_result["content"]
            step5_elapsed = time_module.time() - step5_start
            logger.info(f"[Pipeline] ✅ STEP 5 completed in {step5_elapsed:.2f} seconds")
        except Exception as e:
            step5_elapsed = time_module.time() - step5_start
            # Advice generation is optional, don't fail the whole process
            logger.warning(f"[Pipeline] ⚠️ STEP 5 (Advice) failed after {step5_elapsed:.2f} seconds (non-critical): {str(e)}")
        
        # ===== STEP 6: Auto-Generate Tasks =====
        step6_start = time_module.time()
        tasks_count = 0
        try:
            logger.info(f"[Pipeline] ========== STEP 6: Tasks Generation Started ==========")
            logger.info(f"[Pipeline] Step 6 started at {time_module.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"==========================Tasks Generation Started==========================:")
            tasks_count = await self._generate_tasks(
                diagnostic=diagnostic,
                summary=summary,
                json_extract=json_extract,
                roadmap=roadmap
            )
            step6_elapsed = time_module.time() - step6_start
            logger.info(f"[Pipeline] ✅ STEP 6 completed in {step6_elapsed:.2f} seconds")
            logger.info(f"[Pipeline] Generated {tasks_count} tasks")
            logger.info(f"==========================Tasks Generation Completed Successfully==========================:")
            
            # Check for shutdown after step 6
            if check_shutdown and background_task_manager.is_shutting_down():
                logger.warning(f"  Shutdown detected after task generation for diagnostic {diagnostic.id}")
                raise asyncio.CancelledError("Shutdown detected")
        except Exception as e:
            logger.warning(f"Warning: Could not generate tasks: {str(e)}", exc_info=True)
        
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
        
        # ===== STEP 7: Save All Data to Database =====
        save_start = time_module.time()
        logger.info(f"[Pipeline] ========== STEP 7: Saving Results to Database ==========")
        logger.info(f"[Pipeline] Step 7 started at {time_module.strftime('%Y-%m-%d %H:%M:%S')}")
        
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
        
        save_elapsed = time_module.time() - save_start
        total_elapsed = time_module.time() - pipeline_start
        
        logger.info(f"[Pipeline] ✅ STEP 7 completed in {save_elapsed:.2f} seconds")
        logger.info("=" * 60)
        logger.info(f"[Pipeline] ========== PIPELINE COMPLETED SUCCESSFULLY ==========")
        logger.info(f"[Pipeline] Total pipeline time: {total_elapsed:.2f} seconds ({total_elapsed/60:.2f} minutes)")
        logger.info(f"[Pipeline] Completed at {time_module.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"[Pipeline] Steps breakdown:")
        logger.info(f"[Pipeline]   - Step 1 (JSON Extract): {step1_elapsed:.2f}s")
        logger.info(f"[Pipeline]   - Step 2 (Summary): {step2_elapsed:.2f}s")
        logger.info(f"[Pipeline]   - Step 3 (Scoring): {step3_elapsed:.2f}s ({step3_elapsed/60:.2f} min)")
        logger.info(f"[Pipeline]   - Step 4 (Processing): {step4_elapsed:.2f}s")
        logger.info(f"[Pipeline]   - Step 5 (Advice): {step5_elapsed:.2f}s")
        logger.info(f"[Pipeline]   - Step 6 (Tasks): {step6_elapsed:.2f}s")
        logger.info(f"[Pipeline]   - Step 7 (Save): {save_elapsed:.2f}s")
        logger.info("=" * 60)
    
    def _get_current_files_from_responses(self, diagnostic: Diagnostic) -> List:
        """
        Get only the files that are currently referenced in user_responses.
        This ensures we don't use stale/old files that were previously attached.
        
        Args:
            diagnostic: Diagnostic model with user_responses
            
        Returns:
            List of Media objects that are currently in user_responses
        """
        from app.models.media import Media
        
        user_responses = diagnostic.user_responses or {}
        
        # Collect all media_ids from user_responses
        # Files can be stored as:
        # - Single object: {"file_name": "...", "media_id": "uuid", ...}
        # - Array: [{"file_name": "...", "media_id": "uuid", ...}, ...]
        current_media_ids = set()
        files_without_id = []  # For fallback matching
        
        for field_name, field_value in user_responses.items():
            if not field_value:
                continue
            
            # Handle both array and single file metadata
            file_metadatas = field_value if isinstance(field_value, list) else [field_value]
            
            for file_meta in file_metadatas:
                if isinstance(file_meta, dict):
                    # Try to get media_id (preferred identifier)
                    media_id = file_meta.get("media_id")
                    if media_id:
                        try:
                            current_media_ids.add(UUID(media_id))
                        except (ValueError, TypeError):
                            logger.warning(f"[File Sync] Invalid media_id format: {media_id} in field {field_name}")
                            # Store for fallback matching
                            files_without_id.append({
                                "file_name": file_meta.get("file_name"),
                                "relative_path": file_meta.get("relative_path"),
                                "field": field_name
                            })
                    else:
                        # No media_id - store for fallback matching
                        file_name = file_meta.get("file_name")
                        relative_path = file_meta.get("relative_path")
                        if file_name:
                            files_without_id.append({
                                "file_name": file_name,
                                "relative_path": relative_path,
                                "field": field_name
                            })
                            logger.info(f"[File Sync] File {file_name} in field {field_name} has no media_id, will try fallback matching")
        
        # Query Media objects by IDs (primary method)
        valid_media = []
        if current_media_ids:
            media_objects = self.db.query(Media).filter(
                Media.id.in_(current_media_ids),
                Media.is_active == True
            ).all()
            
            # Verify files are actually attached to this diagnostic
            attached_media_ids = {m.id for m in diagnostic.media}
            valid_media = [
                m for m in media_objects 
                if m.id in attached_media_ids
            ]
            
            logger.info(f"[File Sync] Found {len(valid_media)}/{len(current_media_ids)} files by media_id")
        
        # Fallback: Try to match files without media_id by file_name + relative_path
        if files_without_id:
            logger.info(f"[File Sync] Attempting fallback matching for {len(files_without_id)} files without media_id")
            for file_info in files_without_id:
                file_name = file_info["file_name"]
                relative_path = file_info.get("relative_path")
                
                # Try to find matching Media object
                query = self.db.query(Media).filter(
                    Media.file_name == file_name,
                    Media.is_active == True
                )
                
                # If relative_path is available, use it for more precise matching
                if relative_path:
                    # Extract diagnostic_id from relative_path: diagnostic/{id}/filename
                    if "diagnostic/" in relative_path:
                        try:
                            path_parts = relative_path.split("/")
                            if len(path_parts) >= 2:
                                diagnostic_id_from_path = path_parts[1]
                                # Verify this matches current diagnostic
                                if str(diagnostic.id) == diagnostic_id_from_path:
                                    query = query.filter(Media.file_path.like(f"%{diagnostic_id_from_path}%"))
                        except Exception as e:
                            logger.warning(f"[File Sync] Error parsing relative_path {relative_path}: {e}")
                
                matched_media = query.first()
                if matched_media and matched_media.id not in {m.id for m in valid_media}:
                    # Check if it's attached to this diagnostic
                    if matched_media in diagnostic.media:
                        valid_media.append(matched_media)
                        logger.info(f"[File Sync] Matched file {file_name} by name/path (media_id: {matched_media.id})")
                    else:
                        logger.warning(f"[File Sync] File {file_name} found but not attached to diagnostic")
        
        logger.info(f"[File Sync] Total valid files: {len(valid_media)}")
        if valid_media:
            logger.info(f"[File Sync] Files being used: {[f.file_name + ' (id: ' + str(f.id) + ')' for f in valid_media]}")
        
        return valid_media
    
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
            context += f"  {files_with_ids} document(s) are attached to this request and available for you to read directly.\n\n"
        
        context += "Documents uploaded:\n\n"
        
        for idx, file_info in enumerate(file_info_list, 1):
            context += f"{idx}. {file_info['filename']}\n"
            context += f"   Type: {file_info['type']}\n"
            context += f"   Question: {file_info['question']}\n"
            if file_info['openai_file_id']:
                context += f"   Status:   Attached for analysis\n"
            else:
                context += f"   Status:   Metadata only (not attached)\n"
            context += "\n"
        
        if files_with_ids > 0:
            context += "IMPORTANT INSTRUCTIONS:\n"
            context += "- The attached documents (financial statements, reports, etc.) are available for you to read.\n"
            context += "- When scoring, analyze the actual data from these documents.\n"
            context += "- For financial questions (M1), review P&L statements, balance sheets, and financial reports.\n"
            context += "- Use document data to validate and enrich scores beyond just survey responses.\n"
            context += "- Extract key metrics, trends, and insights from the documents.\n"
        
        context += "=== END UPLOADED DOCUMENTS ===\n\n"
        logger.info(f"==========================File Context==========================: {context}")
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
        # Step 1: Delete existing diagnostic_generated tasks for this engagement/diagnostic
        # This prevents duplicate tasks when diagnostic is resubmitted
        try:
            existing_tasks = self.db.query(Task).filter(
                Task.engagement_id == diagnostic.engagement_id,
                Task.diagnostic_id == diagnostic.id,
                Task.task_type == "diagnostic_generated"
            ).all()
            
            if existing_tasks:
                deleted_count = len(existing_tasks)
                logger.info(f"Deleting {deleted_count} existing diagnostic_generated tasks for engagement {diagnostic.engagement_id} and diagnostic {diagnostic.id}")
                
                for task in existing_tasks:
                    self.db.delete(task)
                
                self.db.commit()
                logger.info(f"Successfully deleted {deleted_count} existing diagnostic_generated tasks")
        except Exception as e:
            logger.warning(f"Failed to delete existing diagnostic_generated tasks: {str(e)}")
            # Continue with task generation even if deletion fails
            self.db.rollback()
        
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
        tasks_data = task_result.get("parsed_content", {})
        logger.info(f"Raw tasks_data type: {type(tasks_data)}, content: {str(tasks_data)[:500]}")
        
        # Handle different response formats
        if isinstance(tasks_data, list):
            # Already a list of tasks
            tasks_list = tasks_data
            logger.info(f"Tasks data is a list: {len(tasks_list)} tasks")
        elif isinstance(tasks_data, dict):
            # Check if it has a "tasks" key (wrapped format)
            if "tasks" in tasks_data:
                tasks_list = tasks_data.get("tasks", [])
                logger.info(f"Extracted tasks from dict with 'tasks' key: {len(tasks_list)} tasks")
            # Check if it's a single task object (has task-like fields)
            elif "title" in tasks_data or "name" in tasks_data:
                # Single task object - wrap it in a list
                tasks_list = [tasks_data]
                logger.info(f"Single task object detected, wrapped in list: 1 task")
            else:
                # Unknown dict format
                tasks_list = []
                logger.warning(f"Dict format not recognized. Keys: {list(tasks_data.keys())}")
        else:
            tasks_list = []
            logger.warning(f"Tasks data is not dict or list: {type(tasks_data)}")
        
        # Ensure tasks_list is a list and not None
        if not isinstance(tasks_list, list):
            logger.warning(f"Tasks data is not in expected format: {type(tasks_list)}")
            tasks_list = []
        
        # Log sample task structure for debugging
        if tasks_list and len(tasks_list) > 0:
            logger.info(f"Sample task structure (first task): {tasks_list[0]}")
        
        # Create Task records
        tasks_created = 0
        created_tasks = []  # Track successfully created tasks
        
        logger.info(f"Attempting to create {len(tasks_list)} tasks from AI response")
        
        for idx, task_data in enumerate(tasks_list):
            try:
                # Validate required fields
                title = task_data.get("title") or task_data.get("name")
                if not title or not title.strip():
                    logger.warning(f"Task {idx + 1}: Missing or empty title, skipping. Task data: {task_data}")
                    continue
                
                # Ensure title is not too long (max 255 chars)
                title = str(title).strip()[:255]
                
                # Get full category name (store as-is, don't map to module code)
                category = task_data.get("category") or task_data.get("module_reference") or ""
                # Ensure category is not too long (max 50 chars to match database)
                category = str(category).strip()[:50] if category else ""
                
                # Get description and convert numbered lists to bullet points
                raw_description = task_data.get("description") or task_data.get("details") or ""
                description = convert_numbered_list_to_bullets(raw_description)
                
                task = Task(
                    engagement_id=diagnostic.engagement_id,
                    diagnostic_id=diagnostic.id,
                    created_by_user_id=diagnostic.created_by_user_id,
                    title=title,
                    description=description,
                    task_type="diagnostic_generated",
                    status="pending",
                    priority=task_data.get("priority", "medium"),
                    # Store full category name (e.g., "products-or-services", not just "M5")
                    module_reference=category
                )
                
                self.db.add(task)
                created_tasks.append(task)  # Track this task
                tasks_created += 1
                logger.info(f"Task {idx + 1} added to session: '{title[:50]}...'")
                
            except Exception as e:
                logger.error(f"Could not create task {idx + 1}: {str(e)}", exc_info=True)
                logger.error(f"Task data that failed: {task_data}")
                continue
        
        # Only commit and refresh if we created at least one task
        if tasks_created > 0:
            try:
                self.db.commit()
                logger.info(f"Successfully committed {tasks_created} tasks to database")
                
                # Refresh all created tasks
                for task in created_tasks:
                    try:
                        self.db.refresh(task)
                    except Exception as e:
                        logger.warning(f"Could not refresh task {task.id}: {str(e)}")
                
                logger.info(f"==========================Tasks stored in DB: {tasks_created} tasks created==========================")
            except Exception as e:
                logger.error(f"Failed to commit tasks to database: {str(e)}", exc_info=True)
                self.db.rollback()
                logger.error("Database transaction rolled back due to error")
                return 0
        else:
            logger.warning(f"No tasks were created from the generated task list (received {len(tasks_list)} tasks from AI)")
            if tasks_list:
                logger.warning(f"Sample task data structure: {tasks_list[0] if tasks_list else 'N/A'}")
        
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

