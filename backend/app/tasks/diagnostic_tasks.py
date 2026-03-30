"""
Celery tasks for diagnostic processing.

Runs the AI diagnostic pipeline out-of-process via a Celery worker.
The pipeline is async (uses await for Claude API calls), so each task
bridges into an event loop with asyncio.run().
"""
import asyncio
import logging
import time
from uuid import UUID
from datetime import datetime, timezone

from celery import states
from celery.exceptions import SoftTimeLimitExceeded
from celery.signals import worker_ready

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.diagnostic import Diagnostic
from app.models.engagement import Engagement
from app.models.user import User
from app.services.diagnostic_service import get_diagnostic_service
from app.services.report_service import ReportService
from app.services.claude_service import ClaudeService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker lifecycle: reset stale diagnostics on startup
# ---------------------------------------------------------------------------

@worker_ready.connect
def cleanup_stale_tasks(sender, **kwargs):
    """Reset diagnostics stuck in 'processing' from a previous unclean shutdown."""
    db = SessionLocal()
    try:
        stale = db.query(Diagnostic).filter(Diagnostic.status == "processing").all()
        for d in stale:
            d.status = "draft"
            logger.warning(f"Reset stale diagnostic {d.id} from 'processing' to 'draft'")
        if stale:
            db.commit()
            logger.info(f"Reset {len(stale)} stale diagnostic(s) to 'draft'")
    except Exception as e:
        logger.error(f"Failed to clean up stale diagnostics: {e}")
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Main Celery task
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="process_diagnostic", max_retries=0)
def process_diagnostic_task(self, diagnostic_id_str: str):
    """
    Celery task that runs the full diagnostic AI pipeline.

    Uses asyncio.run() to bridge into the async pipeline.
    max_retries=0 because the pipeline is NOT idempotent (Claude API calls,
    PDF generation produce different results each time).
    """
    asyncio.run(_run_pipeline(diagnostic_id_str))


# ---------------------------------------------------------------------------
# Async pipeline runner (moved from diagnostics.py endpoint)
# ---------------------------------------------------------------------------

async def _run_pipeline(diagnostic_id_str: str):
    """
    Async function that runs inside asyncio.run() in the Celery worker.

    Creates a fresh event loop, DB session, and Claude client per invocation.
    """
    diagnostic_id = UUID(diagnostic_id_str)
    pipeline_start_time = time.time()

    # Force re-create the AsyncAnthropic client on THIS event loop.
    # The class-level _client may be stale from a previous event loop.
    ClaudeService._client = None
    ClaudeService.initialize_client()

    background_db = SessionLocal()
    try:
        logger.info(f"[Celery Task] Starting background processing for diagnostic {diagnostic_id}")
        logger.info(f"[Celery Task] Started at {time.strftime('%Y-%m-%d %H:%M:%S')}")

        background_service = get_diagnostic_service(background_db)
        diagnostic_obj = background_service.get_diagnostic(diagnostic_id)

        if not diagnostic_obj:
            logger.error(f"[Celery Task] Diagnostic {diagnostic_id} not found")
            return

        logger.info(f"[Celery Task] Diagnostic status: {diagnostic_obj.status}")
        logger.info(f"[Celery Task] Diagnostic engagement_id: {diagnostic_obj.engagement_id}")

        # Run the AI pipeline (timeout is handled by Celery's task_soft_time_limit)
        await background_service._process_diagnostic_pipeline(
            diagnostic_obj, check_shutdown=True
        )

        pipeline_elapsed = time.time() - pipeline_start_time
        logger.info(
            f"[Celery Task] Diagnostic pipeline completed in "
            f"{pipeline_elapsed:.2f}s ({pipeline_elapsed / 60:.2f} min)"
        )

        # ---- Generate PDF report ----
        try:
            logger.info(f"[Celery Task] Generating PDF report for diagnostic {diagnostic_id}")

            report_user_id = diagnostic_obj.completed_by_user_id or diagnostic_obj.created_by_user_id
            report_user = background_db.query(User).filter(User.id == report_user_id).first()

            if report_user:
                question_text_map = {}
                structured_question_map = {}
                diagnostic_questions = diagnostic_obj.questions or {}

                for page in diagnostic_questions.get("pages", []):
                    for element in page.get("elements", []):
                        element_name = element.get("name")
                        element_title = element.get("title", element_name)
                        el_type = element.get("type", "")

                        if el_type == "file":
                            continue
                        if element_name:
                            question_text_map[element_name] = element_title
                        if element_name and el_type == "matrixdynamic":
                            structured_question_map[element_name] = {
                                "type": "matrixdynamic",
                                "fields": {
                                    col.get("name"): col.get("title", col.get("name", ""))
                                    for col in element.get("columns", []) if col.get("name")
                                },
                            }
                        elif element_name and el_type == "multipletext":
                            structured_question_map[element_name] = {
                                "type": "multipletext",
                                "fields": {
                                    item.get("name"): item.get("title", item.get("name", ""))
                                    for item in element.get("items", []) if item.get("name")
                                },
                            }

                # Look up lead advisor name for cover page
                advisor_name = ""
                try:
                    engagement_obj = background_db.query(Engagement).filter(
                        Engagement.id == diagnostic_obj.engagement_id
                    ).first()
                    if engagement_obj and engagement_obj.primary_advisor_id:
                        advisor_user = background_db.query(User).filter(
                            User.id == engagement_obj.primary_advisor_id
                        ).first()
                        if advisor_user:
                            advisor_name = advisor_user.name or advisor_user.email or ""
                except Exception:
                    advisor_name = ""

                pdf_bytes = ReportService.generate_pdf_report(
                    diagnostic=diagnostic_obj,
                    user=report_user,
                    question_text_map=question_text_map,
                    structured_question_map=structured_question_map,
                    advisor_name=advisor_name,
                )
                logger.info(f"[Celery Task] PDF report generated ({len(pdf_bytes)} bytes)")
            else:
                logger.warning(f"[Celery Task] Could not find user for PDF generation")

        except Exception as pdf_error:
            logger.error(f"[Celery Task] PDF generation failed (non-critical): {pdf_error}", exc_info=True)

        # ---- Mark completed ----
        diagnostic_obj.status = "completed"
        diagnostic_obj.completed_at = datetime.now(timezone.utc)

        # Link diagnostic to conversation for chat
        try:
            from app.services.chat_service import get_chat_service
            chat_service = get_chat_service(background_db)
            conversation = chat_service.get_or_create_conversation(
                user_id=diagnostic_obj.created_by_user_id,
                category="diagnostic",
                diagnostic_id=diagnostic_obj.id,
            )
            diagnostic_obj.conversation_id = conversation.id
            logger.info(f"[Celery Task] Linked diagnostic {diagnostic_obj.id} to conversation {conversation.id}")
        except Exception as chat_err:
            logger.error(f"[Celery Task] Failed to link conversation (non-critical): {chat_err}")

        # Update engagement status
        engagement = background_db.query(Engagement).filter(
            Engagement.id == diagnostic_obj.engagement_id
        ).first()
        if engagement and engagement.status != "completed":
            engagement.status = "completed"
            if not engagement.completed_at:
                engagement.completed_at = datetime.now(timezone.utc)
            logger.info(f"[Celery Task] Updated engagement {engagement.id} status to 'completed'")

        background_db.commit()

        total_elapsed = time.time() - pipeline_start_time
        logger.info(
            f"[Celery Task] Background processing completed for diagnostic {diagnostic_id} "
            f"in {total_elapsed:.2f}s ({total_elapsed / 60:.2f} min)"
        )

    except SoftTimeLimitExceeded:
        logger.error(
            f"[Celery Task] Pipeline timed out for diagnostic {diagnostic_id} "
            f"(soft time limit exceeded)"
        )
        try:
            diagnostic_obj = background_db.query(Diagnostic).filter(
                Diagnostic.id == diagnostic_id
            ).first()
            if diagnostic_obj:
                diagnostic_obj.status = "failed"
                background_db.commit()
        except Exception as update_err:
            logger.error(f"[Celery Task] Failed to update status after timeout: {update_err}")

    except asyncio.CancelledError:
        elapsed = time.time() - pipeline_start_time
        logger.warning(
            f"[Celery Task] Processing cancelled for diagnostic {diagnostic_id} "
            f"after {elapsed:.2f}s"
        )
        try:
            diagnostic_obj = background_db.query(Diagnostic).filter(
                Diagnostic.id == diagnostic_id
            ).first()
            if diagnostic_obj:
                diagnostic_obj.status = "draft"
                background_db.commit()
        except Exception as update_err:
            logger.error(f"[Celery Task] Failed to update status after cancellation: {update_err}")

    except Exception as e:
        elapsed = time.time() - pipeline_start_time
        logger.error(
            f"[Celery Task] Processing FAILED for diagnostic {diagnostic_id} "
            f"after {elapsed:.2f}s: {type(e).__name__}: {e}",
            exc_info=True,
        )
        try:
            diagnostic_obj = background_db.query(Diagnostic).filter(
                Diagnostic.id == diagnostic_id
            ).first()
            if diagnostic_obj:
                diagnostic_obj.status = "failed"
                background_db.commit()
        except Exception as update_err:
            logger.error(f"[Celery Task] Failed to update status after error: {update_err}")

    finally:
        background_db.close()
