"""
Strategy Workbook service for document analysis and data extraction
"""
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from uuid import UUID
from pathlib import Path
import json
import logging

from app.models.strategy_workbook import StrategyWorkbook
from app.models.diagnostic import Diagnostic
from app.models.media import Media
# from app.services.openai_service import openai_service  # Preserved for rollback
from app.services.claude_service import claude_service
from app.services.file_service import get_file_service
from app.config import settings
from app.utils.file_loader import load_prompt

logger = logging.getLogger(__name__)


class StrategyWorkbookService:
    """Service for handling strategy workbook operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.claude_service = claude_service
        self.file_service = get_file_service(db)
        # Prompts
        self.extraction_prompt = load_prompt("strategy-workbook/extraction_prompt")
        self.formatting_prompt = load_prompt("strategy-workbook/formatting_prompt")
        self.precheck_prompt = load_prompt("strategy-workbook/precheck_prompt")
    
    def create_workbook(self, user_id: Optional[UUID] = None, engagement_id: Optional[UUID] = None) -> StrategyWorkbook:
        """
        Create a new strategy workbook session.

        Args:
            user_id: Optional creator user ID
            engagement_id: Optional engagement ID to link to

        Returns:
            Created StrategyWorkbook model
        """
        workbook = StrategyWorkbook(
            status="draft",
            created_by_user_id=user_id,
            engagement_id=engagement_id,
        )

        self.db.add(workbook)
        self.db.commit()
        self.db.refresh(workbook)

        logger.info(f"Created strategy workbook {workbook.id}")
        return workbook

    def create_from_diagnostic(self, diagnostic_id: UUID, user_id: UUID, force_new: bool = False) -> StrategyWorkbook:
        """
        Create a strategy workbook from a completed diagnostic. Idempotent:
        if a workbook already exists for this diagnostic_id and force_new is False,
        returns that workbook unchanged. If force_new is True, resets it to draft state.
        """
        diagnostic = self.db.query(Diagnostic).filter(Diagnostic.id == diagnostic_id).first()
        if not diagnostic:
            raise ValueError(f"Diagnostic {diagnostic_id} not found")
        if diagnostic.status != "completed":
            raise ValueError(f"Diagnostic must be completed (current status: {diagnostic.status})")

        diagnostic_context = {}
        if diagnostic.report_html:
            diagnostic_context["report_html"] = diagnostic.report_html
        if diagnostic.ai_analysis:
            diagnostic_context["ai_analysis"] = diagnostic.ai_analysis

        existing = self.db.query(StrategyWorkbook).filter(
            StrategyWorkbook.diagnostic_id == diagnostic_id
        ).first()
        if existing:
            if not force_new:
                logger.info(f"Returning existing strategy workbook {existing.id} for diagnostic {diagnostic_id}")
                return existing
            logger.info(f"Resetting existing strategy workbook {existing.id} for diagnostic {diagnostic_id} (force_new=True)")
            # Delete old generated file from disk if it exists
            if existing.generated_workbook_path:
                old_path = Path(existing.generated_workbook_path)
                if old_path.exists():
                    try:
                        old_path.unlink()
                    except OSError:
                        logger.warning(f"Failed to delete old workbook file: {old_path}")
            # Reset to draft state
            existing.status = "draft"
            existing.extracted_data = None
            existing.uploaded_media_ids = None
            existing.generated_workbook_path = None
            existing.completed_at = None
            existing.notes = None
            existing.template_path = None
            existing.diagnostic_context = diagnostic_context or None
            existing.created_by_user_id = user_id
            self.db.commit()
            self.db.refresh(existing)
            return existing

        workbook = StrategyWorkbook(
            engagement_id=diagnostic.engagement_id,
            diagnostic_id=diagnostic_id,
            created_by_user_id=user_id,
            diagnostic_context=diagnostic_context or None,
            status="draft",
        )
        self.db.add(workbook)
        self.db.commit()
        self.db.refresh(workbook)
        logger.info(f"Created strategy workbook {workbook.id} from diagnostic {diagnostic_id} for user {user_id}")
        return workbook
    
    def attach_files(self, workbook_id: UUID, media_ids: List[UUID]) -> StrategyWorkbook:
        """
        Attach uploaded files to a workbook.
        
        Args:
            workbook_id: ID of the workbook
            media_ids: List of Media IDs to attach
            
        Returns:
            Updated StrategyWorkbook model
        """
        workbook = self.db.query(StrategyWorkbook).filter(
            StrategyWorkbook.id == workbook_id
        ).first()
        
        if not workbook:
            raise ValueError(f"Workbook {workbook_id} not found")
        
        # Update uploaded_media_ids
        existing_ids = set(workbook.uploaded_media_ids or [])
        new_ids = set(media_ids)
        workbook.uploaded_media_ids = list(existing_ids | new_ids)
        
        self.db.commit()
        self.db.refresh(workbook)
        
        logger.info(f"Attached {len(media_ids)} files to workbook {workbook_id}")
        return workbook
    
    async def extract_data(self, workbook_id: UUID, clarification_notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract strategic data from uploaded documents using AI.
        
        Args:
            workbook_id: ID of the workbook to extract data for
            
        Returns:
            Extracted data dictionary
        """
        workbook = self.db.query(StrategyWorkbook).filter(
            StrategyWorkbook.id == workbook_id
        ).first()
        
        if not workbook:
            raise ValueError(f"Workbook {workbook_id} not found")
        
        if not workbook.uploaded_media_ids:
            raise ValueError(f"No files uploaded for workbook {workbook_id}")
        
        # Update status to extracting
        workbook.status = "extracting"
        self.db.commit()
        
        try:
            # Get file IDs from Media records
            media_records = self.db.query(Media).filter(
                Media.id.in_(workbook.uploaded_media_ids),
                Media.is_active == True
            ).all()
            
            if not media_records:
                raise ValueError(f"No active media files found for workbook {workbook_id}")
            
            image_or_archive_ext = {"png", "jpg", "jpeg", "gif", "webp", "zip"}
            pdf_ext = {"pdf"}
            ci_ext = {"csv", "txt", "text", "md", "markdown", "json", "xml", "yaml", "yml", "xlsx", "xls"}

            pdf_file_ids: List[str] = []
            ci_file_ids: List[str] = []
            filtered_files: List[str] = []

            for media in media_records:
                file_id = media.llm_file_id or media.openai_file_id
                if not file_id:
                    logger.warning(f"Media {media.id} has no LLM file ID (file_name={media.file_name})")
                    continue

                ext = (media.file_extension or "").lower()
                if ext in pdf_ext:
                    pdf_file_ids.append(file_id)
                elif ext in ci_ext:
                    ci_file_ids.append(file_id)
                elif ext in image_or_archive_ext:
                    filtered_files.append(f"{media.file_name} ({ext or 'no ext'})")
                else:
                    # Unknown extension - default to Code Interpreter so it can be opened/read
                    logger.warning(
                        f"Unknown file extension '{ext}' for {media.file_name}; treating as Code Interpreter file"
                    )
                    ci_file_ids.append(file_id)

            if filtered_files:
                logger.info(
                    f"Filtered out {len(filtered_files)} unsupported attachment(s) (images/zip): {filtered_files}"
                )

            if not pdf_file_ids and not ci_file_ids:
                raise ValueError(f"No usable file IDs found for workbook {workbook_id}")
            
            # ===== STEP 1: Raw extraction from documents =====
            step1_user_message = (
                "Analyse all uploaded documents and extract every piece of strategic information "
                "relevant to the Strategy Workbook. Follow the extraction structure provided in the "
                "system prompt. Focus on capturing all facts and details. Do not worry about perfect "
                "JSON formatting in this step; focus on completeness and clarity of content.\n\n"
                "IMPORTANT: You MUST produce your final extracted content as a text response message. "
                "If you use code interpreter to read files, always write your final findings as text output, "
                "not just as code interpreter print statements."
            )

            step1_messages = [
                {"role": "system", "content": self.extraction_prompt},
                {"role": "user", "content": step1_user_message},
            ]

            # If the advisor has provided clarification notes about uncertainties,
            # include them as additional context for the model to resolve ambiguities
            if clarification_notes:
                step1_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "The advisor has provided the following clarifications, context, or notes "
                            "about the uploaded documents. Use these only to resolve ambiguities or "
                            "interpret unclear references, and NEVER to override explicit facts in the "
                            "documents themselves:\n\n"
                            f"{clarification_notes}"
                        ),
                    }
                )
            
            logger.info(
                f"[StrategyWorkbook] STEP 1: Extracting raw data for workbook {workbook_id}: "
                f"{len(pdf_file_ids)} PDF(s) as input_file, {len(ci_file_ids)} file(s) via Code Interpreter"
            )

            step1_tools = (
                [{"type": "code_interpreter", "container": {"type": "auto", "file_ids": ci_file_ids}}]
                if ci_file_ids
                else None
            )

            step1_response = await self.claude_service.generate_completion(
                messages=step1_messages,
                file_ids=pdf_file_ids if pdf_file_ids else None,
                tools=step1_tools,
                reasoning_effort="medium",
                model=settings.ANTHROPIC_MODEL,
                max_output_tokens=128000,
            )

            raw_content = step1_response.get("content", "")
            if not raw_content:
                raise ValueError(
                    "No content returned from OpenAI in extraction step "
                    f"(finish_reason={step1_response.get('finish_reason')}, "
                    f"tokens_used={step1_response.get('tokens_used')}, "
                    f"response_id={step1_response.get('response_id')}, "
                    f"output_summary={step1_response.get('output_summary')})"
                )

            # ===== STEP 2: JSON validation & normalisation =====
            logger.info(f"[StrategyWorkbook] STEP 2: Normalising JSON for workbook {workbook_id}")

            step2_messages = [
                {"role": "system", "content": self.formatting_prompt},
                {
                    "role": "user",
                    "content": (
                        "Here is the raw extracted content from the documents. "
                        "Clean, validate, and normalise it into the exact JSON schema described "
                        "in the system prompt. Respond with ONLY the final JSON object.\n\n"
                        "---- RAW EXTRACTED CONTENT START ----\n"
                        f"{raw_content}\n"
                        "---- RAW EXTRACTED CONTENT END ----"
                    ),
                },
            ]

            step2_response = await self.claude_service.generate_json_completion(
                messages=step2_messages,
                reasoning_effort="medium",
                model=settings.ANTHROPIC_MODEL,
                max_output_tokens=128000,
            )

            extracted_data = step2_response.get("parsed_content")
            if not extracted_data:
                raise ValueError(
                    "No content returned from OpenAI in formatting step "
                    f"(finish_reason={step2_response.get('finish_reason')}, "
                    f"tokens_used={step2_response.get('tokens_used')}, "
                    f"response_id={step2_response.get('response_id')}, "
                    f"output_summary={step2_response.get('output_summary')})"
                )
            
            # Validate and normalize extracted data
            extracted_data = self._normalize_extracted_data(extracted_data)
            
            # Store extracted data
            workbook.extracted_data = extracted_data
            workbook.status = "ready"
            self.db.commit()
            self.db.refresh(workbook)
            
            logger.info(f"Successfully extracted data for workbook {workbook_id}")
            return extracted_data
            
        except Exception as e:
            logger.error(f"Failed to extract data for workbook {workbook_id}: {str(e)}")
            workbook.status = "failed"
            self.db.commit()
            raise

    async def precheck_workbook(self, workbook_id: UUID) -> Dict[str, Any]:
        """
        Run a lightweight LLM precheck to see if uploaded documents are suitable for
        extraction, and surface any ambiguities or issues that should be clarified.
        """
        workbook = self.db.query(StrategyWorkbook).filter(
            StrategyWorkbook.id == workbook_id
        ).first()

        if not workbook:
            raise ValueError(f"Workbook {workbook_id} not found")

        if not workbook.uploaded_media_ids:
            raise ValueError(f"No files uploaded for workbook {workbook_id}")

        # Reuse the same media selection logic as extraction, but without changing status
        media_records = self.db.query(Media).filter(
            Media.id.in_(workbook.uploaded_media_ids),
            Media.is_active == True
        ).all()

        if not media_records:
            raise ValueError(f"No active media files found for workbook {workbook_id}")

        image_or_archive_ext = {"png", "jpg", "jpeg", "gif", "webp", "zip"}
        pdf_ext = {"pdf"}
        ci_ext = {"csv", "txt", "text", "md", "markdown", "json", "xml", "yaml", "yml", "xlsx", "xls"}

        pdf_file_ids: List[str] = []
        ci_file_ids: List[str] = []
        filtered_files: List[str] = []

        for media in media_records:
            file_id = media.llm_file_id or media.openai_file_id
            if not file_id:
                logger.warning(f"[Precheck] Media {media.id} has no LLM file ID (file_name={media.file_name})")
                continue

            ext = (media.file_extension or "").lower()
            if ext in pdf_ext:
                pdf_file_ids.append(file_id)
            elif ext in ci_ext:
                ci_file_ids.append(file_id)
            elif ext in image_or_archive_ext:
                filtered_files.append(f"{media.file_name} ({ext or 'no ext'})")
            else:
                logger.warning(
                    f"[Precheck] Unknown file extension '{ext}' for {media.file_name}; treating as Code Interpreter file"
                )
                ci_file_ids.append(file_id)

        if filtered_files:
            logger.info(
                f"[Precheck] Filtered out {len(filtered_files)} unsupported attachment(s) (images/zip): {filtered_files}"
            )

        if not pdf_file_ids and not ci_file_ids:
            raise ValueError(f"No usable OpenAI file IDs found for workbook {workbook_id}")

        logger.info(
            f"[StrategyWorkbook] PRECHECK: Checking suitability for workbook {workbook_id}: "
            f"{len(pdf_file_ids)} PDF(s) as input_file, {len(ci_file_ids)} file(s) via Code Interpreter"
        )

        messages = [
            {"role": "system", "content": self.precheck_prompt},
            {
                "role": "user",
                "content": (
                    "Review all uploaded documents and determine whether they are suitable inputs "
                    "for creating a prefilled Strategy Workshop Excel Workbook. Identify any major "
                    "issues or ambiguities that might affect the extraction, and propose concise "
                    "clarification questions for the advisor where needed. Respond ONLY with the "
                    "JSON object described in the system prompt."
                ),
            },
        ]

        tools = (
            [{"type": "code_interpreter", "container": {"type": "auto", "file_ids": ci_file_ids}}]
            if ci_file_ids
            else None
        )

        response = await self.claude_service.generate_json_completion(
            messages=messages,
            file_ids=pdf_file_ids if pdf_file_ids else None,
            tools=tools,
            reasoning_effort="low",
            model=settings.ANTHROPIC_MODEL,
            max_output_tokens=2000,
        )

        parsed = response.get("parsed_content")
        if not parsed:
            raise ValueError(
                "No content returned from OpenAI in precheck step "
                f"(finish_reason={response.get('finish_reason')}, "
                f"tokens_used={response.get('tokens_used')}, "
                f"response_id={response.get('response_id')}, "
                f"output_summary={response.get('output_summary')})"
            )

        clarification_questions = parsed.get("clarification_questions") or []
        status = parsed.get("status") or ("needs_clarification" if clarification_questions else "ok")
        issues = parsed.get("issues") or []

        return {
            "status": status,
            "clarification_questions": clarification_questions,
            "issues": issues,
            "message": parsed.get("message", "Precheck completed"),
        }
    
    def _normalize_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and validate extracted data structure.
        
        Args:
            data: Raw extracted data from AI
            
        Returns:
            Normalized data dictionary
        """
        # Ensure all required top-level keys exist
        normalized = {
            "visioning": data.get("visioning", {}),
            "business_model": data.get("business_model", {}),
            "market_segmentation": data.get("market_segmentation", []),
            "porters_5_forces": data.get("porters_5_forces", []),
            "pestel": data.get("pestel", []),
            "swot": data.get("swot", {}),
            "customer_analysis": data.get("customer_analysis", []),
            "product_analysis": data.get("product_analysis", []),
            "competitor_analysis": data.get("competitor_analysis", []),
            "growth_opportunities": data.get("growth_opportunities", []),
            "financial_targets": data.get("financial_targets", {}),
            "risks": data.get("risks", {}),
            "strategic_priorities": data.get("strategic_priorities", []),
            "key_actions": data.get("key_actions", []),
            # Optional helper key: list of follow-up questions the AI suggests for the advisor
            "clarification_questions": data.get("clarification_questions", []),
        }
        
        # Ensure SWOT has all keys
        if "swot" in normalized:
            normalized["swot"] = {
                "strengths": normalized["swot"].get("strengths", []),
                "weaknesses": normalized["swot"].get("weaknesses", []),
                "opportunities": normalized["swot"].get("opportunities", []),
                "threats": normalized["swot"].get("threats", [])
            }
        
        # Ensure risks has all categories
        if "risks" in normalized:
            normalized["risks"] = {
                "legal": normalized["risks"].get("legal", []),
                "financial": normalized["risks"].get("financial", []),
                "operations": normalized["risks"].get("operations", []),
                "people": normalized["risks"].get("people", []),
                "sm": normalized["risks"].get("sm", []),
                "product": normalized["risks"].get("product", []),
                "other": normalized["risks"].get("other", [])
            }
        
        # Ensure financial_targets structure
        if "financial_targets" in normalized:
            normalized["financial_targets"] = {
                "current_fy": normalized["financial_targets"].get("current_fy", {}),
                "next_fy": normalized["financial_targets"].get("next_fy", {})
            }
        
        return normalized
    
    def get_workbooks_by_engagement(self, engagement_id: UUID, user_id: UUID) -> List[StrategyWorkbook]:
        """
        Return all strategy workbooks for a given engagement, ordered most-recent first.
        """
        return (
            self.db.query(StrategyWorkbook)
            .filter(
                StrategyWorkbook.engagement_id == engagement_id,
                StrategyWorkbook.created_by_user_id == user_id,
            )
            .order_by(StrategyWorkbook.updated_at.desc())
            .all()
        )

    def get_workbook(self, workbook_id: UUID) -> Optional[StrategyWorkbook]:
        """
        Get a workbook by ID.
        
        Args:
            workbook_id: ID of the workbook
            
        Returns:
            StrategyWorkbook model or None if not found
        """
        workbook = self.db.query(StrategyWorkbook).filter(
            StrategyWorkbook.id == workbook_id
        ).first()
        
        return workbook


def get_strategy_workbook_service(db: Session) -> StrategyWorkbookService:
    """Dependency injection for StrategyWorkbookService"""
    return StrategyWorkbookService(db)

