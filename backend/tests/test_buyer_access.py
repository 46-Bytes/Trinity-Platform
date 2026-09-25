"""
Buyer access: the permission foundation.

Most of these assert an absence. A buyer is an external party who may see one
engagement's released folders and nothing else, so the tests that matter are the
ones proving every other door is shut - including the routers that authenticate
without ever calling check_engagement_access.

Runs inside the rollback-only db_session; nothing is written to the database.
Inviting is patched where it would otherwise call Auth0.
"""
from datetime import date

import pytest
from sqlalchemy import text

from app.models.buyer import BuyerAccessLog, EngagementBuyer, EngagementReleasedFolder
from app.models.sale_ready import EngagementDDItem
from app.models.engagement import Engagement
from app.models.user import User, UserRole

ENG = "/api/engagements"
PORTAL = "/api/buyer"

_NEEDS_MIGRATION = (
    "Buyer tables are missing. Migrate first:\n"
    "    cd backend && alembic upgrade head"
)


@pytest.fixture(autouse=True)
def buyer_schema(db_session):
    for table in ("engagement_buyer", "engagement_released_folder", "buyer_access_log"):
        try:
            db_session.execute(text(f"SELECT 1 FROM {table} LIMIT 0"))
        except Exception:
            pytest.skip(_NEEDS_MIGRATION, allow_module_level=True)


def _with_valid_email(user, db_session):
    """
    Give a fixture user an address EmailStr will accept.

    conftest issues @example.test addresses and .test is an IANA reserved TLD,
    which email-validator refuses - so an invite carrying one would 422 before
    reaching the code under test. BuyerInvite.email stays EmailStr; only the
    fixture changes.
    """
    import uuid as _uuid
    user.email = f"buyer-test-{_uuid.uuid4()}@example.com"
    db_session.flush()
    return user


@pytest.fixture
def advisor(make_user):
    return make_user(UserRole.ADVISOR)


@pytest.fixture
def owner(make_user):
    return make_user(UserRole.CLIENT)


@pytest.fixture
def engagement(db_session, advisor, owner):
    eng = Engagement(engagement_name="Buyer test engagement", primary_advisor_id=advisor.id,
                     client_id=owner.id, client_ids=[owner.id], tool="sale_ready", status="active")
    db_session.add(eng)
    db_session.flush()
    return eng


@pytest.fixture
def other_engagement(db_session, make_user, owner):
    eng = Engagement(engagement_name="Someone else's engagement",
                     primary_advisor_id=make_user(UserRole.ADVISOR).id,
                     client_id=owner.id, client_ids=[owner.id], tool="sale_ready", status="active")
    db_session.add(eng)
    db_session.flush()
    return eng


def _buyer(db_session, make_user, engagement, status="active"):
    """A buyer already bound to the engagement, without going through Auth0."""
    user = _with_valid_email(make_user(UserRole.BUYER), db_session)
    row = EngagementBuyer(engagement_id=engagement.id, user_id=user.id, status=status)
    db_session.add(row)
    db_session.flush()
    return user, row


@pytest.fixture
def buyer(db_session, make_user, engagement):
    return _buyer(db_session, make_user, engagement)


def _release(db_session, engagement, category="3", sub="3.1"):
    row = EngagementReleasedFolder(engagement_id=engagement.id, category_code=category,
                                   sub_item_code=sub)
    db_session.add(row)
    db_session.flush()
    return row


# ======================================================================
# The role itself
# ======================================================================
class TestTheRole:
    def test_buyer_round_trips_through_the_column(self, db_session, make_user):
        user = make_user(UserRole.BUYER)
        db_session.flush()
        db_session.expire_all()
        assert db_session.query(User).filter(User.id == user.id).one().role == UserRole.BUYER

    def test_buyer_is_stored_lowercase_like_the_other_newer_roles(self, db_session, make_user):
        user = make_user(UserRole.BUYER)
        db_session.flush()
        raw = db_session.execute(
            text("SELECT role FROM users WHERE id = :i"), {"i": str(user.id)}
        ).scalar()
        assert raw == "buyer"


# ======================================================================
# Every other door is shut
# ======================================================================
class TestBuyersReachNothingElse:
    OTHER_ROUTES = [
        "/api/engagements", "/api/tasks", "/api/users", "/api/firms",
        "/api/dashboard/stats", "/api/advisor-client", "/api/advisor-client/my-clients",
    ]

    @pytest.mark.parametrize("path", OTHER_ROUTES)
    def test_a_buyer_is_refused(self, api, buyer, path):
        """Routers that authenticate without an engagement check must still refuse."""
        user, _ = buyer
        assert api.as_user(user).get(path).status_code == 403

    def test_a_buyer_cannot_read_their_own_engagement_through_the_normal_route(
        self, api, buyer, engagement
    ):
        user, _ = buyer
        assert api.as_user(user).get(f"{ENG}/{engagement.id}").status_code == 403

    def test_a_buyer_cannot_reach_sale_ready(self, api, buyer, engagement):
        user, _ = buyer
        for path in ("roadmap", "dd", "guide"):
            assert api.as_user(user).get(
                f"/api/sale-ready/engagements/{engagement.id}/{path}"
            ).status_code == 403

    def test_a_buyer_cannot_reach_diagnostics(self, api, buyer, engagement):
        user, _ = buyer
        assert api.as_user(user).get(
            f"/api/diagnostics/engagement/{engagement.id}"
        ).status_code == 403

    def test_a_buyer_cannot_reach_sale_ready_admin(self, api, buyer):
        user, _ = buyer
        assert api.as_user(user).get("/api/sale-ready/admin/guide").status_code == 403

    def test_a_buyer_cannot_manage_buyers(self, api, buyer, engagement):
        user, _ = buyer
        client = api.as_user(user)
        assert client.get(f"{ENG}/{engagement.id}/buyers").status_code == 403
        assert client.post(f"{ENG}/{engagement.id}/buyers",
                           json={"email": "x@example.com"}).status_code == 403
        assert client.put(f"{ENG}/{engagement.id}/released-folders",
                          json={"folders": []}).status_code == 403

    def test_check_engagement_access_still_denies_buyers(self, db_session, buyer, engagement):
        from app.services.role_check import check_engagement_access
        user, _ = buyer
        assert check_engagement_access(engagement, user, db=db_session) is False
        assert check_engagement_access(engagement, user, require_advisor=True, db=db_session) is False


# ======================================================================
# Engagement isolation
# ======================================================================
class TestEngagementIsolation:
    def test_the_engagement_comes_from_the_binding_not_the_request(
        self, api, buyer, engagement, other_engagement
    ):
        user, _ = buyer
        served = api.as_user(user).get(f"{PORTAL}/me/engagement").json()
        assert served["engagement_id"] == str(engagement.id)
        assert served["engagement_id"] != str(other_engagement.id)

    def test_a_buyer_sees_only_released_folders(self, api, db_session, buyer, engagement):
        user, _ = buyer
        assert api.as_user(user).get(f"{PORTAL}/me/folders").json() == []
        _release(db_session, engagement, "3", "3.1")
        folders = api.as_user(user).get(f"{PORTAL}/me/folders").json()
        assert [(f["category_code"], f["sub_item_code"]) for f in folders] == [("3", "3.1")]

    def test_an_unreleased_folder_is_a_404_not_an_empty_list(self, api, buyer):
        user, _ = buyer
        assert api.as_user(user).get(f"{PORTAL}/me/folders/9/9.9").status_code == 404

    def test_a_withdrawn_folder_disappears(self, api, db_session, advisor, buyer, engagement):
        user, _ = buyer
        _release(db_session, engagement, "3", "3.1")
        assert len(api.as_user(user).get(f"{PORTAL}/me/folders").json()) == 1
        api.as_user(advisor).put(f"{ENG}/{engagement.id}/released-folders", json={"folders": []})
        assert api.as_user(user).get(f"{PORTAL}/me/folders").json() == []
        assert api.as_user(user).get(f"{PORTAL}/me/folders/3/3.1").status_code == 404

    def test_another_engagements_release_is_not_visible(
        self, api, db_session, buyer, other_engagement
    ):
        user, _ = buyer
        _release(db_session, other_engagement, "3", "3.1")
        assert api.as_user(user).get(f"{PORTAL}/me/folders").json() == []

    def test_a_non_buyer_cannot_use_the_portal(self, api, advisor, owner):
        for user in (advisor, owner):
            assert api.as_user(user).get(f"{PORTAL}/me/engagement").status_code == 403

    def test_the_portal_has_no_write_route(self):
        from app.main import app
        writes = [
            r.path for r in app.routes
            if hasattr(r, "path") and r.path.startswith("/api/buyer/")
            and (r.methods - {"GET", "HEAD", "OPTIONS"})
        ]
        assert writes == []


# ======================================================================
# Grant, revoke, re-grant
# ======================================================================
class TestGrantRevokeRestore:
    def test_revoked_buyer_loses_access_immediately(self, api, db_session, advisor, buyer, engagement):
        user, row = buyer
        assert api.as_user(user).get(f"{PORTAL}/me/engagement").status_code == 200
        assert api.as_user(advisor).post(
            f"{ENG}/{engagement.id}/buyers/{row.id}/revoke"
        ).status_code == 200
        assert api.as_user(user).get(f"{PORTAL}/me/engagement").status_code == 403

    def test_revoke_is_a_soft_delete_and_leaves_the_account_active(
        self, api, db_session, advisor, buyer, engagement
    ):
        user, row = buyer
        api.as_user(advisor).post(f"{ENG}/{engagement.id}/buyers/{row.id}/revoke")
        db_session.expire_all()
        stored = db_session.query(EngagementBuyer).filter(EngagementBuyer.id == row.id).one()
        assert stored.status == "revoked" and stored.is_deleted is False
        assert db_session.query(User).filter(User.id == user.id).one().is_active is True

    def test_restore_re_grants_on_the_same_row(self, api, db_session, advisor, buyer, engagement):
        user, row = buyer
        api.as_user(advisor).post(f"{ENG}/{engagement.id}/buyers/{row.id}/revoke")
        restored = api.as_user(advisor).post(f"{ENG}/{engagement.id}/buyers/{row.id}/restore")
        assert restored.status_code == 200
        assert restored.json()["id"] == str(row.id)
        assert api.as_user(user).get(f"{PORTAL}/me/engagement").status_code == 200

    def test_one_live_engagement_per_buyer(self, db_session, make_user, engagement, other_engagement):
        user, _ = _buyer(db_session, make_user, engagement)
        db_session.add(EngagementBuyer(engagement_id=other_engagement.id, user_id=user.id,
                                       status="active"))
        with pytest.raises(Exception):
            db_session.flush()
        db_session.rollback()

    def test_nda_date_is_recorded_and_does_not_gate_access(
        self, api, advisor, buyer, engagement
    ):
        user, row = buyer
        # No NDA date: access already works.
        assert api.as_user(user).get(f"{PORTAL}/me/engagement").status_code == 200
        updated = api.as_user(advisor).patch(f"{ENG}/{engagement.id}/buyers/{row.id}",
                                             json={"nda_signed_date": "2026-09-01"})
        assert updated.status_code == 200 and updated.json()["nda_signed_date"] == "2026-09-01"
        assert api.as_user(user).get(f"{PORTAL}/me/engagement").status_code == 200

    def test_an_advisor_on_another_engagement_cannot_manage_these_buyers(
        self, api, make_user, engagement
    ):
        outsider = make_user(UserRole.ADVISOR)
        assert api.as_user(outsider).get(f"{ENG}/{engagement.id}/buyers").status_code == 403


# ======================================================================
# Invite refuses to touch other accounts
# ======================================================================
class TestInviteNeverConvertsAnAccount:
    @pytest.mark.parametrize("role", [UserRole.ADVISOR, UserRole.CLIENT, UserRole.ADMIN,
                                      UserRole.SUPER_ADMIN, UserRole.FIRM_ADMIN])
    def test_existing_non_buyer_email_is_refused_and_untouched(
        self, api, db_session, advisor, engagement, make_user, role
    ):
        victim = _with_valid_email(make_user(role), db_session)
        before_role, before_active = victim.role, victim.is_active

        resp = api.as_user(advisor).post(f"{ENG}/{engagement.id}/buyers",
                                         json={"email": victim.email})
        assert resp.status_code == 400
        assert "never converted" in resp.json()["detail"]

        db_session.expire_all()
        after = db_session.query(User).filter(User.id == victim.id).one()
        assert after.role == before_role and after.is_active == before_active

    def test_inviting_an_existing_buyer_on_this_engagement_is_refused(
        self, api, advisor, buyer, engagement, db_session
    ):
        user, _ = buyer
        resp = api.as_user(advisor).post(f"{ENG}/{engagement.id}/buyers",
                                         json={"email": user.email})
        assert resp.status_code == 400
        assert "already has access" in resp.json()["detail"]

    def test_generic_user_creation_refuses_the_buyer_role(self, api, make_user):
        """
        POST /api/users validates against UserRole, so adding BUYER to that enum
        would otherwise have opened this path. Buyers belong to an engagement;
        one created here would be an account that can sign in and reach nothing.
        """
        admin = make_user(UserRole.ADMIN)
        resp = api.as_user(admin).post("/api/users", json={
            "email": "loose-buyer@example.com", "name": "Loose Buyer", "role": "buyer",
        })
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "engagements" in detail and "buyers" in detail

    @pytest.mark.parametrize("role", ["client", "advisor", "admin", "super_admin",
                                      "firm_admin", "firm_advisor"])
    def test_generic_user_creation_is_unchanged_for_every_other_role(
        self, api, make_user, role
    ):
        """
        The other roles still get past role validation untouched. They stop at
        the Auth0 call, which has no network here - the point is that they are
        not refused by the new buyer guard.
        """
        admin = make_user(UserRole.ADMIN)
        resp = api.as_user(admin).post("/api/users", json={
            "email": f"new-{role}@example.com", "name": f"New {role}", "role": role,
        })
        assert resp.status_code != 403
        if resp.status_code == 400:
            detail = resp.json()["detail"]
            assert "Invalid role" not in detail
            assert "not created here" not in detail

    def test_the_engagement_invite_still_creates_a_buyer(
        self, api, db_session, advisor, engagement, monkeypatch
    ):
        """The supported path still works, with Auth0 stubbed out."""
        from app.models.user import User as UserModel
        from app.services import buyer_service as svc

        def fake_invite(db, email, role, first_name=None, last_name=None, business_name=None):
            user = UserModel(email=email, role=role)
            db.add(user)
            db.flush()
            return user

        monkeypatch.setattr(svc.AuthService, "create_invited_user", staticmethod(fake_invite))

        resp = api.as_user(advisor).post(f"{ENG}/{engagement.id}/buyers",
                                         json={"email": "invited@example.com"})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["email"] == "invited@example.com" and body["status"] == "active"

        db_session.expire_all()
        created = db_session.query(UserModel).filter(
            UserModel.email == "invited@example.com").one()
        assert created.role == UserRole.BUYER
        assert db_session.query(EngagementBuyer).filter(
            EngagementBuyer.user_id == created.id,
            EngagementBuyer.engagement_id == engagement.id,
        ).count() == 1

    def test_a_buyer_with_no_binding_reaches_nothing(self, api, db_session, make_user):
        """
        The safety net under an orphan buyer account.

        POST /api/users validates its role against UserRole, so adding BUYER to
        that enum made it accept role="buyer" - an admin can now create a buyer
        there without any engagement binding. That is not a hole, because access
        is resolved forward from the binding and there is none, but it is a way
        to make an account that can sign in and see nothing. This test pins the
        harmlessness; whether the endpoint should refuse the role outright is a
        separate decision.
        """
        orphan = _with_valid_email(make_user(UserRole.BUYER), db_session)
        client = api.as_user(orphan)
        assert client.get(f"{PORTAL}/me/engagement").status_code == 403
        assert client.get(f"{PORTAL}/me/folders").status_code == 403
        for path in ("/api/engagements", "/api/tasks", "/api/users"):
            assert client.get(path).status_code == 403


# ======================================================================
# Access log
# ======================================================================
class TestAccessLog:
    def _rows(self, db_session, engagement):
        return db_session.query(BuyerAccessLog).filter(
            BuyerAccessLog.engagement_id == engagement.id
        ).all()

    def test_every_buyer_read_is_logged(self, api, db_session, buyer, engagement):
        user, _ = buyer
        _release(db_session, engagement, "3", "3.1")
        client = api.as_user(user)
        client.get(f"{PORTAL}/me/engagement")
        client.get(f"{PORTAL}/me/folders")
        client.get(f"{PORTAL}/me/folders/3/3.1")
        db_session.expire_all()
        actions = [r.action for r in self._rows(db_session, engagement)]
        assert actions.count("list") == 2 and actions.count("view") == 1

    def test_a_refused_read_is_not_logged(self, api, db_session, buyer, engagement):
        user, _ = buyer
        api.as_user(user).get(f"{PORTAL}/me/folders/9/9.9")
        db_session.expire_all()
        assert self._rows(db_session, engagement) == []

    def test_the_log_survives_revocation(self, api, db_session, advisor, buyer, engagement):
        user, row = buyer
        api.as_user(user).get(f"{PORTAL}/me/engagement")
        api.as_user(advisor).post(f"{ENG}/{engagement.id}/buyers/{row.id}/revoke")
        db_session.expire_all()
        assert len(self._rows(db_session, engagement)) >= 1

    def test_the_advisor_can_read_the_log(self, api, db_session, advisor, buyer, engagement):
        user, _ = buyer
        api.as_user(user).get(f"{PORTAL}/me/engagement")
        entries = api.as_user(advisor).get(f"{ENG}/{engagement.id}/buyer-access-log").json()
        assert len(entries) >= 1 and entries[0]["action"] == "list"


# ======================================================================
# Documents are served by Trinity, never linked
# ======================================================================
class TestDocumentsAreServedNotLinked:
    def test_download_refuses_explicitly_before_drive(self, api, db_session, buyer, engagement):
        """
        503, not 404: the release check cannot be answered yet, and saying so is
        what stops it being mistaken for a check that ran and found nothing.
        """
        import uuid as _uuid
        user, _ = buyer
        _release(db_session, engagement, "3", "3.1")
        resp = api.as_user(user).get(f"{PORTAL}/me/documents/{_uuid.uuid4()}/download")
        assert resp.status_code == 503
        assert "not connected" in resp.json()["detail"]

    def test_the_release_check_raises_rather_than_returning_a_default(self, db_session):
        """
        The guard against this becoming an authorisation bypass later.

        Neither stub may return a value: an empty list or a False reads as a
        completed check, and whoever wires up Drive would have no reason to
        look at it again.
        """
        from app.services.buyer_service import DataRoomNotConnected, get_buyer_service
        import uuid as _uuid
        service = get_buyer_service(db_session)
        with pytest.raises(DataRoomNotConnected):
            service.media_is_released(_uuid.uuid4(), _uuid.uuid4())
        with pytest.raises(DataRoomNotConnected):
            service.documents_in_folder(_uuid.uuid4(), "3", "3.1")

    def test_a_real_media_row_is_still_refused(self, api, db_session, buyer, engagement, advisor):
        """Even a document that genuinely belongs to the engagement is refused."""
        from app.models.media import Media
        user, _ = buyer
        media = Media(engagement_id=engagement.id, user_id=advisor.id, file_name="x.pdf",
                      file_path="/tmp/x.pdf", is_active=True)
        db_session.add(media)
        db_session.flush()
        resp = api.as_user(user).get(f"{PORTAL}/me/documents/{media.id}/download")
        assert resp.status_code == 503

    def test_a_released_folder_returns_the_shape_with_no_contents(
        self, api, db_session, buyer, engagement
    ):
        user, _ = buyer
        _release(db_session, engagement, "3", "3.1")
        body = api.as_user(user).get(f"{PORTAL}/me/folders/3/3.1").json()
        assert body["category_code"] == "3" and body["documents"] == []

    def test_no_buyer_response_contains_a_storage_path(self, api, db_session, buyer, engagement):
        user, _ = buyer
        _release(db_session, engagement, "3", "3.1")
        client = api.as_user(user)
        for path in ("/me/engagement", "/me/folders", "/me/folders/3/3.1"):
            body = client.get(f"{PORTAL}{path}").text
            assert "/files/" not in body
            assert "drive.google" not in body
            assert "file_path" not in body


# ======================================================================
# Activity shown to the advisor
# ======================================================================
class TestBuyerActivity:
    """
    Last access, opens and the "invited" label are derived from the access log
    on read. Nothing about them is stored, so `status` must stay two-valued.
    """

    def _row(self, api, advisor, engagement, user):
        body = api.as_user(advisor).get(f"{ENG}/{engagement.id}/buyers").json()
        return next(b for b in body if b["user_id"] == str(user.id))

    def test_a_buyer_who_has_never_looked_reads_as_invited(self, api, advisor, buyer, engagement):
        user, _ = buyer
        row = self._row(api, advisor, engagement, user)
        assert row["status"] == "active"
        assert row["display_status"] == "invited"
        assert row["last_access_at"] is None and row["open_count"] == 0

    def test_a_visit_makes_them_active_and_sets_last_access(
        self, api, db_session, advisor, buyer, engagement
    ):
        user, _ = buyer
        api.as_user(user).get(f"{PORTAL}/me/engagement")
        db_session.expire_all()
        row = self._row(api, advisor, engagement, user)
        assert row["display_status"] == "active"
        assert row["last_access_at"] is not None

    def test_listing_is_a_visit_but_not_an_open(
        self, api, db_session, advisor, buyer, engagement
    ):
        """A folder listing counts as access; only a view or download is an open."""
        user, _ = buyer
        client = api.as_user(user)
        client.get(f"{PORTAL}/me/engagement")
        client.get(f"{PORTAL}/me/folders")
        db_session.expire_all()
        row = self._row(api, advisor, engagement, user)
        assert row["last_access_at"] is not None
        assert row["open_count"] == 0

    def test_opening_a_folder_counts_as_an_open(
        self, api, db_session, advisor, buyer, engagement
    ):
        user, _ = buyer
        _release(db_session, engagement, "3", "3.1")
        client = api.as_user(user)
        client.get(f"{PORTAL}/me/folders/3/3.1")
        client.get(f"{PORTAL}/me/folders/3/3.1")
        db_session.expire_all()
        row = self._row(api, advisor, engagement, user)
        assert row["open_count"] == 2

    def test_revoked_keeps_its_own_label(self, api, db_session, advisor, buyer, engagement):
        user, row = buyer
        api.as_user(user).get(f"{PORTAL}/me/engagement")
        api.as_user(advisor).post(f"{ENG}/{engagement.id}/buyers/{row.id}/revoke")
        db_session.expire_all()
        got = self._row(api, advisor, engagement, user)
        assert got["status"] == "revoked" and got["display_status"] == "revoked"

    def test_a_revoked_buyer_keeps_the_activity_they_had(
        self, api, db_session, advisor, buyer, engagement
    ):
        """Revoking is a soft delete; the log survives, so the counts must too."""
        user, row = buyer
        _release(db_session, engagement, "3", "3.1")
        api.as_user(user).get(f"{PORTAL}/me/folders/3/3.1")
        api.as_user(advisor).post(f"{ENG}/{engagement.id}/buyers/{row.id}/revoke")
        db_session.expire_all()
        got = self._row(api, advisor, engagement, user)
        assert got["open_count"] == 1 and got["last_access_at"] is not None

    def test_a_mutation_response_carries_the_same_activity_as_the_list(
        self, api, db_session, advisor, buyer, engagement
    ):
        """The panel upserts this row into its list, so the shapes have to agree."""
        user, row = buyer
        _release(db_session, engagement, "3", "3.1")
        api.as_user(user).get(f"{PORTAL}/me/folders/3/3.1")
        db_session.expire_all()
        patched = api.as_user(advisor).patch(
            f"{ENG}/{engagement.id}/buyers/{row.id}", json={"nda_signed_date": "2026-09-01"}
        ).json()
        listed = self._row(api, advisor, engagement, user)
        assert patched["open_count"] == listed["open_count"] == 1
        assert patched["display_status"] == listed["display_status"] == "active"

    def test_another_engagements_activity_is_not_counted(
        self, api, db_session, advisor, buyer, engagement, make_user
    ):
        """A log row on a different engagement must never inflate this one."""
        user, _ = buyer
        other = Engagement(engagement_name="other", primary_advisor_id=advisor.id,
                           client_id=advisor.id, client_ids=[advisor.id],
                           tool="sale_ready", status="active")
        db_session.add(other)
        db_session.flush()
        db_session.add(BuyerAccessLog(engagement_id=other.id, user_id=user.id, action="view"))
        db_session.flush()
        row = self._row(api, advisor, engagement, user)
        assert row["open_count"] == 0 and row["display_status"] == "invited"


# ======================================================================
# What the buyer's folder list actually contains
# ======================================================================
def _dd_item(db_session, engagement, cat="3", cat_name="Financial Documentation",
             sub="3.1", sub_name="Historical Financial Statements", key="DD-001"):
    """A DD item on this engagement. template_item_id is NOT NULL, so borrow any template."""
    template_id = db_session.execute(
        text("SELECT id FROM program_dd_template LIMIT 1")
    ).scalar()
    if template_id is None:
        pytest.skip("program_dd_template is not seeded")
    row = EngagementDDItem(
        engagement_id=engagement.id, template_item_id=template_id, item_key=key,
        stage_code="M1", category_code=cat, category=cat_name,
        sub_item_code=sub, sub_item=sub_name,
    )
    db_session.add(row)
    db_session.flush()
    return row


class TestTheBuyerFolderPayload:
    """
    A buyer gets folder names and none of the advisor's release metadata. The
    names come from the engagement's own DD items, which is where the folder
    structure comes from, so the two can never disagree.
    """

    def test_folders_are_named_not_bare_codes(self, api, db_session, buyer, engagement):
        user, _ = buyer
        _dd_item(db_session, engagement)
        _release(db_session, engagement, "3", "3.1")
        folder = api.as_user(user).get(f"{PORTAL}/me/folders").json()[0]
        assert folder["sub_item"] == "Historical Financial Statements"
        assert folder["category"] == "Financial Documentation"

    def test_advisor_metadata_is_not_sent_to_the_buyer(self, api, db_session, buyer, engagement):
        user, _ = buyer
        _dd_item(db_session, engagement)
        _release(db_session, engagement, "3", "3.1")
        folder = api.as_user(user).get(f"{PORTAL}/me/folders").json()[0]
        assert "released_by_user_id" not in folder
        assert "released_at" not in folder

    def test_the_advisor_still_gets_the_release_metadata(
        self, api, db_session, advisor, engagement
    ):
        """Slimming the buyer payload must not slim the advisor's."""
        _release(db_session, engagement, "3", "3.1")
        folder = api.as_user(advisor).get(f"{ENG}/{engagement.id}/released-folders").json()[0]
        assert "released_at" in folder and "released_by_user_id" in folder

    def test_a_folder_with_no_dd_item_still_lists(self, api, db_session, buyer, engagement):
        """Names are a courtesy; a released folder is never hidden for want of one."""
        user, _ = buyer
        _release(db_session, engagement, "9", "9.9")
        folder = api.as_user(user).get(f"{PORTAL}/me/folders").json()[0]
        assert folder["sub_item_code"] == "9.9" and folder["sub_item"] is None

    def test_the_folder_detail_is_named_too(self, api, db_session, buyer, engagement):
        user, _ = buyer
        _dd_item(db_session, engagement)
        _release(db_session, engagement, "3", "3.1")
        body = api.as_user(user).get(f"{PORTAL}/me/folders/3/3.1").json()
        assert body["sub_item"] == "Historical Financial Statements"
        assert body["documents"] == []

    def test_names_come_from_this_engagement_only(
        self, api, db_session, buyer, engagement, other_engagement
    ):
        """Another engagement's DD item must not name this engagement's folder."""
        user, _ = buyer
        _dd_item(db_session, other_engagement, sub_name="Someone else's label")
        _release(db_session, engagement, "3", "3.1")
        folder = api.as_user(user).get(f"{PORTAL}/me/folders").json()[0]
        assert folder["sub_item"] is None

    def test_an_unreleased_folder_is_still_invisible_however_it_is_named(
        self, api, db_session, buyer, engagement
    ):
        """Naming must not widen what is listed."""
        user, _ = buyer
        _dd_item(db_session, engagement)
        assert api.as_user(user).get(f"{PORTAL}/me/folders").json() == []
        assert api.as_user(user).get(f"{PORTAL}/me/folders/3/3.1").status_code == 404
