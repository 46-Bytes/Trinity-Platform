"""
Connecting Trinity to Benchmark's Google Drive.

A one-time admin action, not something a user does. An admin starts the
consent flow, Google calls back, and the refresh token that comes out is
encrypted and stored. Everything after that runs server-side with no user
present.

Locked to admins and super admins. Nothing here returns the token, the
authorisation code, or any part of either - the status endpoint reports
whether the connection works and who made it, and that is all.
"""
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.drive import DriveIntegration
from app.models.user import User, UserRole
from app.services.drive_client import (
    DriveRateLimited, DriveUnavailable, authorization_url, drive_enabled, encrypt_token,
    exchange_code,
)
from app.services.drive_folder_service import account_matches, get_drive_client, get_integration
from app.utils.auth import deny_buyers, get_current_user, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drive", tags=["drive"])

admin_required = require_role([UserRole.SUPER_ADMIN, UserRole.ADMIN])

# Applied per endpoint rather than on the router, because /callback has to
# stay unauthenticated - Google calls it, not a signed-in browser - and
# deny_buyers resolves get_current_user. admin_required already excludes
# buyers; this is the belt to its braces, and keeps the Drive router
# consistent with every other router in the app.
ADMIN_ONLY = [Depends(admin_required), Depends(deny_buyers)]

# The OAuth `state` is a signed, expiring token rather than a value held in
# memory. Nothing is stored: the signature proves Trinity issued it and the
# timestamp bounds how long it is good for. An in-process set would have been
# simpler but breaks in the two cases that matter - a reload between Connect
# and Google's redirect, which happens constantly under --reload, and more
# than one worker, where the callback rarely lands on the process that issued
# the state.
_STATE_SALT = "drive-oauth-state"
_STATE_MAX_AGE_SECONDS = 600


def _state_serializer():
    from itsdangerous import URLSafeTimedSerializer

    return URLSafeTimedSerializer(settings.SECRET_KEY, salt=_STATE_SALT)


def _issue_state() -> str:
    """A one-use value proving the callback belongs to a flow Trinity started."""
    return _state_serializer().dumps({"nonce": secrets.token_urlsafe(16)})


def _state_is_valid(state: str) -> bool:
    from itsdangerous import BadSignature, SignatureExpired

    try:
        _state_serializer().loads(state, max_age=_STATE_MAX_AGE_SECONDS)
        return True
    except SignatureExpired:
        logger.info("Drive OAuth state expired; the admin took too long to consent")
        return False
    except BadSignature:
        logger.warning("Drive OAuth callback carried a state Trinity did not issue")
        return False


class DriveStatus(BaseModel):
    enabled: bool = Field(..., description="Whether the integration is switched on at all")
    connected: bool
    account_email: Optional[str] = None
    expected_account: Optional[str] = Field(None, description="The account the data room must live in")
    account_mismatch: bool = Field(False, description="Connected as another account; uploads and sync are paused")
    root_folder_id: Optional[str] = None
    root_folder_configured: bool = False
    last_synced_at: Optional[str] = None
    last_error: Optional[str] = None
    configuration_missing: list[str] = Field(default_factory=list)


class RootFolderUpdate(BaseModel):
    root_folder_id: str = Field(..., min_length=1, max_length=255,
                                description="Drive id of Trinity/Clients")


def _missing_configuration() -> list[str]:
    return [
        name for name in (
            "GOOGLE_DRIVE_CLIENT_ID", "GOOGLE_DRIVE_CLIENT_SECRET",
            "GOOGLE_DRIVE_REDIRECT_URI", "GOOGLE_DRIVE_TOKEN_KEY",
        ) if not getattr(settings, name, None)
    ]


@router.get("/status", response_model=DriveStatus, dependencies=ADMIN_ONLY)
async def drive_status(db: Session = Depends(get_db)):
    """Whether the data room is usable, and what is missing if it is not."""
    integration = get_integration(db)
    return DriveStatus(
        enabled=drive_enabled(),
        connected=bool(integration and integration.status == "connected"),
        account_email=integration.account_email if integration else None,
        expected_account=settings.GOOGLE_DRIVE_EXPECTED_ACCOUNT or None,
        account_mismatch=bool(integration and integration.status == "connected"
                              and not account_matches(integration.account_email)),
        root_folder_id=integration.root_folder_id if integration else None,
        root_folder_configured=bool(integration and integration.root_folder_id),
        last_synced_at=integration.last_synced_at.isoformat() if integration and integration.last_synced_at else None,
        last_error=integration.last_error if integration else None,
        configuration_missing=_missing_configuration(),
    )


@router.get("/connect", dependencies=ADMIN_ONLY)
async def connect(db: Session = Depends(get_db)):
    """Start the Google consent flow. Returns the URL to send the admin to."""
    missing = _missing_configuration()
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Drive is not configured. Missing: " + ", ".join(missing),
        )
    try:
        return {"authorization_url": authorization_url(_issue_state())}
    except DriveUnavailable as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.get("/callback")
async def callback(
    state: str = Query(...),
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Google's redirect target.

    Unauthenticated by necessity - Google calls it, not a signed-in browser -
    so the signed `state` is what proves the request came from a consent flow
    Trinity started. A state Trinity did not sign, or one older than ten
    minutes, is refused outright.
    """
    if not _state_is_valid(state):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="This authorisation link is not valid or has expired. "
                                   "Start again from Sale Ready Admin.")

    if error or not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Google did not authorise Trinity: {error or 'no code returned'}")

    try:
        refresh_token, account_email = exchange_code(code)
    except DriveUnavailable as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))

    # Checked before anything is stored: the wrong account never becomes the data room.
    if not account_matches(account_email):
        logger.warning("Drive connection refused: authorised as %s, expected %s",
                       account_email or "an unknown account", settings.GOOGLE_DRIVE_EXPECTED_ACCOUNT)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trinity must be connected as {settings.GOOGLE_DRIVE_EXPECTED_ACCOUNT}, "
                   f"but Google authorised {account_email or 'an account whose email could not be read'}. "
                   "Nothing was saved. Start again from Sale Ready Admin and choose the right account.",
        )

    try:
        encrypted = encrypt_token(refresh_token)
    except DriveUnavailable as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))

    integration = get_integration(db)
    if integration is None:
        integration = DriveIntegration()
        db.add(integration)
    integration.account_email = account_email
    integration.refresh_token = encrypted
    integration.status = "connected"
    integration.last_error = None
    integration.connected_at = _utcnow()
    integration.is_deleted = False
    if not integration.root_folder_id and settings.GOOGLE_DRIVE_ROOT_FOLDER_ID:
        integration.root_folder_id = settings.GOOGLE_DRIVE_ROOT_FOLDER_ID
    # A fresh connection starts a fresh change feed.
    integration.changes_page_token = None
    db.commit()

    logger.info("Google Drive connected as %s", account_email)
    # Absolute, via FRONTEND_URL: Google returns the browser to the backend, and
    # a relative path would resolve there rather than on the app.
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/dashboard/sale-ready-management?drive=connected"
    )


@router.put("/root-folder", response_model=DriveStatus, dependencies=ADMIN_ONLY)
async def set_root_folder(
    payload: RootFolderUpdate,
    db: Session = Depends(get_db),
):
    """Point Trinity at Trinity/Clients. Everything is created beneath it."""
    integration = get_integration(db)
    if integration is None:
        integration = DriveIntegration(status="disconnected")
        db.add(integration)
    integration.root_folder_id = payload.root_folder_id.strip()
    db.commit()
    return await drive_status(db)


@router.post("/disconnect", response_model=DriveStatus, dependencies=ADMIN_ONLY)
async def disconnect(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Forget the token.

    The folder map and every indexed file stay: the documents still exist in
    Drive and the record of what a buyer was shown must survive. Reconnecting
    the same account picks up exactly where this left off.
    """
    integration = get_integration(db)
    if integration is not None:
        integration.refresh_token = None
        integration.status = "disconnected"
        integration.changes_page_token = None
        db.commit()
        logger.info("Google Drive disconnected by %s", current_user.id)
    return await drive_status(db)


@router.post("/check", response_model=DriveStatus, dependencies=ADMIN_ONLY)
async def check(db: Session = Depends(get_db)):
    """Prove the stored token still works, and record the answer."""
    integration = get_integration(db)
    if integration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Trinity has never been connected to Google Drive.")
    try:
        get_drive_client(db).start_page_token()
        integration.last_error = None
        integration.status = "connected"
    except DriveRateLimited as e:
        # Throttling says nothing about whether the connection is good, so the
        # status is left alone. Marking it disconnected here would send an
        # admin off to re-authorise an integration that is working fine.
        integration.last_error = str(e)
    except DriveUnavailable as e:
        integration.last_error = str(e)
        integration.status = "disconnected"
    db.commit()
    return await drive_status(db)


@router.post("/sync", dependencies=ADMIN_ONLY)
async def sync_now():
    """
    Run one Drive sync immediately, instead of waiting for the scheduler.

    The periodic pass runs every few minutes, which makes testing tedious:
    drop a file in Drive, then wait. This runs the same code path the
    scheduler runs, through the same advisory lock, so it cannot collide with
    a pass already in flight - it simply reports that one is running.

    Blocking work, so it goes to a thread like the scheduler's own pass does;
    holding the event loop here would stall every other request.
    """
    import asyncio

    from app.services import drive_scheduler

    if not drive_scheduler.should_run():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The Drive sync is switched off. Check GOOGLE_DRIVE_ENABLED "
                   "and GOOGLE_DRIVE_SYNC_ENABLED.",
        )
    result = await asyncio.to_thread(drive_scheduler.run_one_pass)
    if result is None:
        return {"ran": False, "detail": "A sync is already running, or Drive is not connected."}
    return {"ran": True, "result": result}


def _utcnow():
    from datetime import datetime

    return datetime.utcnow()
