"""
Buyer access: invite, revoke, re-grant, folder release and the access log.

Buyers authenticate exactly like everyone else. Inviting one reuses
AuthService.create_invited_user, which creates the Auth0 account and sends the
password-setup ticket through Resend, so there is no second authentication
system and no second activation experience.

Two rules are enforced here rather than left to the caller:

  - an email that already belongs to a non-buyer account is refused, and that
    account is never touched. Downgrading an advisor or a client to a buyer
    would silently destroy their access, so it is not offered at all;
  - a buyer account holds one live engagement. The partial unique index on
    engagement_buyer backs this up, but the check happens here first so the
    caller gets a sentence rather than an integrity error.

Nothing in this module widens check_engagement_access. A buyer's engagement is
resolved forward from their binding, never from a path parameter they supply.
"""
import logging
from datetime import date, datetime
from typing import Any, Dict, List, NamedTuple, Optional
from uuid import UUID

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.buyer import BuyerAccessLog, EngagementBuyer, EngagementReleasedFolder
from app.models.engagement import Engagement
from app.models.media import Media
from app.models.sale_ready import EngagementDDItem
from app.models.user import User, UserRole
from app.services import buyer_rules as rules
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


class BuyerNotFound(LookupError):
    pass


class BuyerConflict(ValueError):
    """The request is valid but cannot be applied to this email or engagement."""


class DataRoomNotConnected(NotImplementedError):
    """
    Document storage is not wired up yet, so no document can be placed in a
    folder and none can be authorised for release.

    Raised rather than returning an empty list on purpose. An empty list looks
    like a completed check that found nothing, which is how a placeholder turns
    into an authorisation bypass the day someone fills the folders in. Every
    caller has to decide what to do about this exception, and the compiler of
    last resort - a 500 - is still safer than a silent allow.
    """


# An "open" is a document being opened; a folder listing is not one.
OPEN_ACTIONS = (rules.ACTION_VIEW, rules.ACTION_DOWNLOAD)


class Activity(NamedTuple):
    """What the access log says about one buyer on one engagement."""
    last_access_at: Optional[datetime]
    open_count: int


def _display_name(user: Optional[User]) -> Optional[str]:
    if not user:
        return None
    full = " ".join(p for p in (user.first_name, user.last_name) if p)
    return user.name or full or user.email


class BuyerService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------
    def _binding_or_404(self, engagement_id: UUID, binding_id: UUID) -> EngagementBuyer:
        row = self.db.query(EngagementBuyer).filter(
            EngagementBuyer.id == binding_id,
            EngagementBuyer.engagement_id == engagement_id,
            EngagementBuyer.is_deleted == False,  # noqa: E712
        ).first()
        if not row:
            raise BuyerNotFound("Buyer not found on this engagement")
        return row

    def live_binding_for_user(self, user_id: UUID) -> Optional[EngagementBuyer]:
        """
        The engagement this buyer may see, or None.

        This is the only way a buyer's engagement is determined. Nothing reads an
        engagement id from the request.
        """
        return self.db.query(EngagementBuyer).filter(
            EngagementBuyer.user_id == user_id,
            EngagementBuyer.status == rules.BUYER_STATUS_ACTIVE,
            EngagementBuyer.is_deleted == False,  # noqa: E712
        ).first()

    def _activity(self, engagement_id: UUID, user_ids: List[UUID]) -> Dict[UUID, "Activity"]:
        """
        Last access and open count per buyer, from the access log.

        Last access counts any action, so listing the data room reads as a
        visit. Opens counts only 'view' and 'download', because an open means a
        document was opened, not that the folder list loaded. Scoped to the
        engagement, so a buyer invited elsewhere later never carries another
        sale's activity onto this one.
        """
        if not user_ids:
            return {}
        rows = self.db.query(
            BuyerAccessLog.user_id,
            func.max(BuyerAccessLog.created_at),
            func.count(case((BuyerAccessLog.action.in_(OPEN_ACTIONS), 1))),
        ).filter(
            BuyerAccessLog.engagement_id == engagement_id,
            BuyerAccessLog.user_id.in_(user_ids),
        ).group_by(BuyerAccessLog.user_id).all()
        return {r[0]: Activity(r[1], int(r[2] or 0)) for r in rows}

    def _as_dict(self, row: EngagementBuyer, user: Optional[User],
                 activity: Optional["Activity"] = None) -> Dict[str, Any]:
        seen = activity.last_access_at if activity else None
        return {
            "id": row.id,
            "engagement_id": row.engagement_id,
            "user_id": row.user_id,
            "email": user.email if user else None,
            "name": _display_name(user),
            "status": row.status,
            # Presentation only. `status` stays the stored two-state value, so
            # the partial unique index and every access rule are untouched: a
            # buyer granted access who has never opened it reads as "invited".
            "display_status": (
                rules.DISPLAY_STATUS_INVITED
                if row.status == rules.BUYER_STATUS_ACTIVE and seen is None
                else row.status
            ),
            "last_access_at": seen,
            "open_count": activity.open_count if activity else 0,
            "nda_signed_date": row.nda_signed_date,
            "invited_by_user_id": row.invited_by_user_id,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def _one(self, row: EngagementBuyer, user: Optional[User]) -> Dict[str, Any]:
        """One buyer with its activity, so a mutation response matches the list rows."""
        found = self._activity(row.engagement_id, [row.user_id])
        return self._as_dict(row, user, found.get(row.user_id))

    def list_buyers(self, engagement: Engagement) -> List[Dict[str, Any]]:
        rows = self.db.query(EngagementBuyer).filter(
            EngagementBuyer.engagement_id == engagement.id,
            EngagementBuyer.is_deleted == False,  # noqa: E712
        ).order_by(EngagementBuyer.created_at.asc()).all()
        if not rows:
            return []
        users = {
            u.id: u for u in self.db.query(User).filter(User.id.in_([r.user_id for r in rows])).all()
        }
        activity = self._activity(engagement.id, [r.user_id for r in rows])
        return [self._as_dict(r, users.get(r.user_id), activity.get(r.user_id)) for r in rows]

    # ------------------------------------------------------------------
    # Invite
    # ------------------------------------------------------------------
    def invite(self, engagement: Engagement, email: str, inviter: User,
               first_name: Optional[str] = None, last_name: Optional[str] = None,
               nda_signed_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Invite a buyer to this engagement.

        Reuses an existing buyer account when the email already has one and it is
        free. Refuses outright when the email belongs to any other role - the
        other account is never modified.
        """
        email = (email or "").strip().lower()
        if not email:
            raise BuyerConflict("An email address is required")

        existing = self.db.query(User).filter(
            User.email == email, User.is_deleted == False,  # noqa: E712
        ).first()

        if existing is not None and existing.role != UserRole.BUYER:
            raise BuyerConflict(
                f"{email} already belongs to a {existing.role.value} account. "
                "Invite the buyer using a different email address; an existing "
                "account is never converted to a buyer."
            )

        if existing is not None:
            prior = self.db.query(EngagementBuyer).filter(
                EngagementBuyer.engagement_id == engagement.id,
                EngagementBuyer.user_id == existing.id,
                EngagementBuyer.is_deleted == False,  # noqa: E712
            ).first()
            if prior is not None:
                if rules.is_live(prior.status, prior.is_deleted):
                    raise BuyerConflict(f"{email} already has access to this engagement")
                # Previously revoked here: re-granting is the restore path.
                raise BuyerConflict(
                    f"{email} was revoked on this engagement. Restore the existing "
                    "buyer instead of inviting them again."
                )
            live = self.live_binding_for_user(existing.id)
            if live is not None:
                raise BuyerConflict(
                    f"{email} already has access to another engagement. A buyer "
                    "account holds one engagement at a time."
                )
            user = existing
        else:
            # Same Auth0 + Resend path every other invited user takes.
            user = AuthService.create_invited_user(
                db=self.db, email=email, role=UserRole.BUYER,
                first_name=first_name, last_name=last_name,
            )

        row = EngagementBuyer(
            engagement_id=engagement.id,
            user_id=user.id,
            status=rules.BUYER_STATUS_ACTIVE,
            invited_by_user_id=inviter.id,
            nda_signed_date=nda_signed_date,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        logger.info("Buyer %s invited to engagement %s by %s", user.id, engagement.id, inviter.id)
        return self._one(row, user)

    # ------------------------------------------------------------------
    # Revoke / restore
    # ------------------------------------------------------------------
    def revoke(self, engagement: Engagement, binding_id: UUID) -> Dict[str, Any]:
        """
        End a buyer's access. A soft delete: the row and the log survive.

        The user account is deliberately left active - revoking access to one
        engagement is not a reason to disable someone's login.
        """
        row = self._binding_or_404(engagement.id, binding_id)
        row.status = rules.BUYER_STATUS_REVOKED
        self.db.commit()
        self.db.refresh(row)
        logger.info("Buyer %s revoked on engagement %s", row.user_id, engagement.id)
        return self._one(row, self.db.query(User).filter(User.id == row.user_id).first())

    def restore(self, engagement: Engagement, binding_id: UUID) -> Dict[str, Any]:
        """Re-grant a revoked buyer. Same row, so the history stays attached."""
        row = self._binding_or_404(engagement.id, binding_id)
        if rules.is_live(row.status, row.is_deleted):
            return self._one(row, self.db.query(User).filter(User.id == row.user_id).first())
        clash = self.live_binding_for_user(row.user_id)
        if clash is not None:
            raise BuyerConflict(
                "This buyer now has access to another engagement. Revoke that "
                "first; a buyer account holds one engagement at a time."
            )
        row.status = rules.BUYER_STATUS_ACTIVE
        self.db.commit()
        self.db.refresh(row)
        logger.info("Buyer %s restored on engagement %s", row.user_id, engagement.id)
        return self._one(row, self.db.query(User).filter(User.id == row.user_id).first())

    def update(self, engagement: Engagement, binding_id: UUID, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Record-only fields. The NDA date does not gate access."""
        row = self._binding_or_404(engagement.id, binding_id)
        if "nda_signed_date" in fields:
            row.nda_signed_date = fields["nda_signed_date"]
        self.db.commit()
        self.db.refresh(row)
        return self._one(row, self.db.query(User).filter(User.id == row.user_id).first())

    # ------------------------------------------------------------------
    # Released folders
    # ------------------------------------------------------------------
    def list_released_folders(self, engagement: Engagement) -> List[Dict[str, Any]]:
        rows = self.db.query(EngagementReleasedFolder).filter(
            EngagementReleasedFolder.engagement_id == engagement.id,
            EngagementReleasedFolder.is_deleted == False,  # noqa: E712
        ).order_by(EngagementReleasedFolder.category_code.asc(),
                   EngagementReleasedFolder.sub_item_code.asc()).all()
        return [
            {"category_code": r.category_code, "sub_item_code": r.sub_item_code,
             "released_at": r.released_at, "released_by_user_id": r.released_by_user_id}
            for r in rows
        ]

    def _folder_names(self, engagement_id: UUID) -> Dict[tuple, Dict[str, Optional[str]]]:
        """
        Folder names keyed by (category_code, sub_item_code).

        Taken from the engagement's own due diligence items, which is where the
        folder structure comes from in the first place. One name per code pair.
        """
        rows = self.db.query(
            EngagementDDItem.category_code,
            EngagementDDItem.category,
            EngagementDDItem.sub_item_code,
            EngagementDDItem.sub_item,
        ).filter(EngagementDDItem.engagement_id == engagement_id).distinct().all()
        return {
            (r.category_code, r.sub_item_code): {"category": r.category, "sub_item": r.sub_item}
            for r in rows
        }

    def buyer_folders(self, engagement: Engagement) -> List[Dict[str, Any]]:
        """
        The released folders as a buyer sees them: named, and without the
        advisor metadata.

        Built on list_released_folders rather than repeating its filter, so
        there is exactly one rule for what "released" means and the advisor's
        view and the buyer's can never drift apart.
        """
        names = self._folder_names(engagement.id)
        return [
            {
                "category_code": f["category_code"],
                "sub_item_code": f["sub_item_code"],
                **names.get((f["category_code"], f["sub_item_code"]),
                            {"category": None, "sub_item": None}),
            }
            for f in self.list_released_folders(engagement)
        ]

    def folder_name(self, engagement_id: UUID, category_code: str,
                    sub_item_code: str) -> Dict[str, Optional[str]]:
        """One folder's names, or empty ones when the engagement has no DD items."""
        return self._folder_names(engagement_id).get(
            (category_code, sub_item_code), {"category": None, "sub_item": None}
        )

    def set_released_folders(self, engagement: Engagement, folders: List[Dict[str, str]],
                             actor: User) -> List[Dict[str, Any]]:
        """
        Replace the released set. Folders not listed are un-released.

        Un-releasing soft-deletes so a folder released, withdrawn and released
        again keeps one row and one history.
        """
        wanted = {(f["category_code"], f["sub_item_code"]) for f in folders}
        existing = self.db.query(EngagementReleasedFolder).filter(
            EngagementReleasedFolder.engagement_id == engagement.id,
        ).all()
        by_key = {(r.category_code, r.sub_item_code): r for r in existing}

        for key in wanted:
            row = by_key.get(key)
            if row is None:
                self.db.add(EngagementReleasedFolder(
                    engagement_id=engagement.id, category_code=key[0], sub_item_code=key[1],
                    released_by_user_id=actor.id,
                ))
            elif row.is_deleted:
                row.is_deleted = False
                row.released_by_user_id = actor.id
        for key, row in by_key.items():
            if key not in wanted and not row.is_deleted:
                row.is_deleted = True

        self.db.commit()
        return self.list_released_folders(engagement)

    def is_released(self, engagement_id: UUID, category_code: str, sub_item_code: str) -> bool:
        return self.db.query(EngagementReleasedFolder).filter(
            EngagementReleasedFolder.engagement_id == engagement_id,
            EngagementReleasedFolder.category_code == category_code,
            EngagementReleasedFolder.sub_item_code == sub_item_code,
            EngagementReleasedFolder.is_deleted == False,  # noqa: E712
        ).first() is not None

    # ------------------------------------------------------------------
    # Access log
    # ------------------------------------------------------------------
    def log(self, engagement_id: UUID, user: User, action: str,
            media_id: Optional[UUID] = None, detail: Optional[str] = None) -> None:
        """
        Append-only. Written before the response is returned, never batched.

        A failure here is recorded and swallowed. The log exists to say what a
        buyer saw; it must never be the reason they are refused something they
        are entitled to see. The rollback matters as much as the except: without
        it a failed insert would poison the session and take the read down
        anyway, which is the exact failure this guard is here to prevent.
        """
        try:
            self.db.add(BuyerAccessLog(
                engagement_id=engagement_id,
                user_id=user.id,
                media_id=media_id,
                action=rules.validate_action(action),
                detail=detail,
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception(
                "Buyer access log write failed for user %s on engagement %s (%s); "
                "the read was still served", user.id, engagement_id, action,
            )

    def access_log(self, engagement: Engagement, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self.db.query(BuyerAccessLog).filter(
            BuyerAccessLog.engagement_id == engagement.id,
        ).order_by(BuyerAccessLog.created_at.desc()).limit(limit).all()
        return [
            {"id": r.id, "user_id": r.user_id, "media_id": r.media_id, "action": r.action,
             "detail": r.detail, "created_at": r.created_at}
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Buyer-facing reads
    # ------------------------------------------------------------------
    def documents_in_folder(self, engagement_id: UUID, category_code: str,
                            sub_item_code: str) -> List[Media]:
        """
        Documents in a released folder.

        Not implemented: nothing files a Media row against a DD sub-item yet, so
        there is no honest answer to give. Implementing this is the moment the
        release rule becomes real, and every caller below has been written to
        expect the exception until then.
        """
        raise DataRoomNotConnected(
            "The data room is not connected yet, so documents cannot be listed "
            "or released."
        )

    def media_is_released(self, engagement_id: UUID, media_id: UUID) -> bool:
        """
        Whether this document sits in a folder released to buyers.

        The real check, and the one a download must pass. It cannot be answered
        until a document knows which folder it is in, so it raises rather than
        guessing. Anyone wiring up Drive has to implement this deliberately -
        there is no default that quietly returns True, and none that quietly
        returns False and looks like a working check either.
        """
        raise DataRoomNotConnected(
            "The data room is not connected yet, so document release cannot be "
            "checked."
        )


def get_buyer_service(db: Session) -> BuyerService:
    return BuyerService(db)
