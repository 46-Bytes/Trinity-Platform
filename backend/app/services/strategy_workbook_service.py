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
from app.models.media import Media
from app.services.openai_service import openai_service
from app.services.file_service import get_file_service
from app.config import settings
from app.utils.file_loader import load_prompt

logger = logging.getLogger(__name__)


class StrategyWorkbookService:
    """Service for handling strategy workbook operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.openai_service = openai_service
        self.file_service = get_file_service(db)
        # Prompts
        self.extraction_prompt = load_prompt("strategy-workbook/extraction_prompt")
        self.formatting_prompt = load_prompt("strategy-workbook/formatting_prompt")
        self.precheck_prompt = load_prompt("strategy-workbook/precheck_prompt")
    
    def create_workbook(self) -> StrategyWorkbook:
        """
        Create a new strategy workbook session.
        
        Returns:
            Created StrategyWorkbook model
        """
        workbook = StrategyWorkbook(
            status="draft"
        )
        
        self.db.add(workbook)
        self.db.commit()
        self.db.refresh(workbook)
        
        logger.info(f"Created strategy workbook {workbook.id}")
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
                if not media.openai_file_id:
                    logger.warning(f"Media {media.id} does not have OpenAI file ID (file_name={media.file_name})")
                    continue

                ext = (media.file_extension or "").lower()
                if ext in pdf_ext:
                    pdf_file_ids.append(media.openai_file_id)
                elif ext in ci_ext:
                    ci_file_ids.append(media.openai_file_id)
                elif ext in image_or_archive_ext:
                    filtered_files.append(f"{media.file_name} ({ext or 'no ext'})")
                else:
                    # Unknown extension - default to Code Interpreter so it can be opened/read
                    logger.warning(
                        f"Unknown file extension '{ext}' for {media.file_name}; treating as Code Interpreter file"
                    )
                    ci_file_ids.append(media.openai_file_id)

            if filtered_files:
                logger.info(
                    f"Filtered out {len(filtered_files)} unsupported attachment(s) (images/zip): {filtered_files}"
                )

            if not pdf_file_ids and not ci_file_ids:
                raise ValueError(f"No usable OpenAI file IDs found for workbook {workbook_id}")
            
            # ===== STEP 1: Raw extraction from documents =====
            step1_user_message = (
                "Analyse all uploaded documents and extract every piece of strategic information "
                "relevant to the Strategy Workbook. Follow the extraction structure provided in the "
                "system prompt. Focus on capturing all facts and details. Do not worry about perfect "
                "JSON formatting in this step; focus on completeness and clarity of content."
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

            step1_response = await self.openai_service.generate_completion(
                messages=step1_messages,
                file_ids=pdf_file_ids if pdf_file_ids else None,
                tools=step1_tools,
                reasoning_effort="medium",
                model=settings.OPENAI_MODEL,
                max_output_tokens=8000,
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

            step2_response = await self.openai_service.generate_json_completion(
                messages=step2_messages,
                reasoning_effort="medium",
                model=settings.OPENAI_MODEL,
                max_output_tokens=8000,
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
            if not media.openai_file_id:
                logger.warning(f"[Precheck] Media {media.id} does not have OpenAI file ID (file_name={media.file_name})")
                continue

            ext = (media.file_extension or "").lower()
            if ext in pdf_ext:
                pdf_file_ids.append(media.openai_file_id)
            elif ext in ci_ext:
                ci_file_ids.append(media.openai_file_id)
            elif ext in image_or_archive_ext:
                filtered_files.append(f"{media.file_name} ({ext or 'no ext'})")
            else:
                logger.warning(
                    f"[Precheck] Unknown file extension '{ext}' for {media.file_name}; treating as Code Interpreter file"
                )
                ci_file_ids.append(media.openai_file_id)

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

        response = await self.openai_service.generate_json_completion(
            messages=messages,
            file_ids=pdf_file_ids if pdf_file_ids else None,
            tools=tools,
            reasoning_effort="low",
            model=settings.OPENAI_MODEL,
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

