"""
Files uploaded straight to an engagement, outside any diagnostic.

Until now a document could only reach an engagement through a diagnostic
questionnaire. These cover the four operations and, above all, who may perform
them: everyone on the engagement may upload, list and download - clients
included, because they already attach files through the diagnostic - but only
the uploader, an advisor or an admin may delete.

Run with: pytest tests/test_engagement_files.py -v
"""
import io
import uuid

import pytest

from app.models.engagement import Engagement
from app.models.media import Media
from app.models.user import UserRole

BASE = "/api/engagements"


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------
@pytest.fixture
def advisor(db_session, test_engagement, make_user):
    user = make_user(UserRole.ADVISOR)
    test_engagement.primary_advisor_id = user.id
    db_session.flush()
    return user


@pytest.fixture
def client_user(db_session, test_engagement, make_user):
    user = make_user(UserRole.CLIENT)
    test_engagement.client_ids = [user.id]
    db_session.flush()
    return user


@pytest.fixture
def other_client(db_session, test_engagement, make_user):
    """A second client on the same engagement."""
    user = make_user(UserRole.CLIENT)
    test_engagement.client_ids = list(test_engagement.client_ids or []) + [user.id]
    db_session.flush()
    return user


@pytest.fixture
def outsider(make_user):
    return make_user(UserRole.ADVISOR)


def _file(name="notes.pdf", content=b"hello world"):
    return {"files": (name, io.BytesIO(content), "application/pdf")}


def _upload(api, user, engagement, name="notes.pdf", content=b"hello world"):
    return api.as_user(user).post(f"{BASE}/{engagement.id}/files", files=_file(name, content))


def _list(api, user, engagement):
    return api.as_user(user).get(f"{BASE}/{engagement.id}/files")


# ----------------------------------------------------------------------
# Upload
# ----------------------------------------------------------------------
class TestUpload:

    def test_an_advisor_can_upload(self, api, advisor, test_engagement):
        resp = _upload(api, advisor, test_engagement)
        assert resp.status_code == 201, resp.text

        body = resp.json()
        assert len(body) == 1
        assert body[0]["file_name"] == "notes.pdf"
        assert body[0]["uploaded_by_user_id"] == str(advisor.id)

    def test_a_client_on_the_engagement_can_upload(self, api, client_user, test_engagement):
        """Clients already attach files through the diagnostic."""
        assert _upload(api, client_user, test_engagement).status_code == 201

    def test_the_file_is_linked_to_the_engagement(self, api, advisor, db_session, test_engagement):
        media_id = _upload(api, advisor, test_engagement).json()[0]["id"]
        media = db_session.query(Media).filter(Media.id == uuid.UUID(media_id)).one()
        assert media.engagement_id == test_engagement.id

    def test_it_is_not_attached_to_any_diagnostic(self, api, advisor, db_session, test_engagement):
        """Engagement uploads must not appear as diagnostic attachments."""
        media_id = _upload(api, advisor, test_engagement).json()[0]["id"]
        media = db_session.query(Media).filter(Media.id == uuid.UUID(media_id)).one()
        assert media.diagnostics == []

    def test_several_files_in_one_request(self, api, advisor, test_engagement):
        resp = api.as_user(advisor).post(
            f"{BASE}/{test_engagement.id}/files",
            files=[
                ("files", ("a.pdf", io.BytesIO(b"a"), "application/pdf")),
                ("files", ("b.docx", io.BytesIO(b"b"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ],
        )
        assert resp.status_code == 201
        assert {f["file_name"] for f in resp.json()} == {"a.pdf", "b.docx"}

    def test_a_disallowed_extension_is_rejected(self, api, advisor, test_engagement):
        """FileService validates the extension; the error must surface as 400."""
        resp = api.as_user(advisor).post(
            f"{BASE}/{test_engagement.id}/files",
            files={"files": ("payload.exe", io.BytesIO(b"x"), "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "not allowed" in resp.text

    def test_a_rejected_upload_stores_nothing(self, api, advisor, db_session, test_engagement):
        api.as_user(advisor).post(
            f"{BASE}/{test_engagement.id}/files",
            files={"files": ("payload.exe", io.BytesIO(b"x"), "application/octet-stream")},
        )
        assert db_session.query(Media).filter(Media.engagement_id == test_engagement.id).count() == 0


# ----------------------------------------------------------------------
# List
# ----------------------------------------------------------------------
class TestList:

    def test_an_empty_engagement_lists_nothing(self, api, advisor, test_engagement):
        resp = _list(api, advisor, test_engagement)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_uploads_are_listed(self, api, advisor, test_engagement):
        _upload(api, advisor, test_engagement, name="one.pdf")
        _upload(api, advisor, test_engagement, name="two.pdf")

        assert {f["file_name"] for f in _list(api, advisor, test_engagement).json()} == {"one.pdf", "two.pdf"}

    def test_a_client_sees_advisor_uploads(self, api, advisor, client_user, test_engagement):
        _upload(api, advisor, test_engagement)
        assert len(_list(api, client_user, test_engagement).json()) == 1

    def test_another_engagements_files_are_not_listed(self, api, advisor, db_session, test_engagement):
        other = Engagement(
            engagement_name=f"Other {uuid.uuid4()}",
            primary_advisor_id=advisor.id,
            tool="value_builder",
        )
        db_session.add(other)
        db_session.flush()
        _upload(api, advisor, other)

        assert _list(api, advisor, test_engagement).json() == []

    def test_the_uploader_is_reported(self, api, advisor, test_engagement):
        _upload(api, advisor, test_engagement)
        item = _list(api, advisor, test_engagement).json()[0]
        assert item["uploaded_by_user_id"] == str(advisor.id)
        assert item["uploaded_by_role"] == UserRole.ADVISOR.value


# ----------------------------------------------------------------------
# Access control
# ----------------------------------------------------------------------
class TestAccessControl:

    def test_an_outsider_cannot_upload(self, api, outsider, test_engagement):
        assert _upload(api, outsider, test_engagement).status_code == 403

    def test_an_outsider_cannot_list(self, api, outsider, test_engagement):
        assert _list(api, outsider, test_engagement).status_code == 403

    def test_an_outsider_cannot_download(self, api, advisor, outsider, test_engagement):
        media_id = _upload(api, advisor, test_engagement).json()[0]["id"]
        resp = api.as_user(outsider).get(f"{BASE}/{test_engagement.id}/files/{media_id}/download")
        assert resp.status_code == 403

    def test_an_outsider_cannot_delete(self, api, advisor, outsider, test_engagement):
        media_id = _upload(api, advisor, test_engagement).json()[0]["id"]
        resp = api.as_user(outsider).delete(f"{BASE}/{test_engagement.id}/files/{media_id}")
        assert resp.status_code == 403

    def test_a_refused_upload_writes_nothing(self, api, outsider, db_session, test_engagement):
        _upload(api, outsider, test_engagement)
        assert db_session.query(Media).filter(Media.engagement_id == test_engagement.id).count() == 0

    def test_an_unknown_engagement_is_404(self, api, advisor):
        assert api.as_user(advisor).get(f"{BASE}/{uuid.uuid4()}/files").status_code == 404

    def test_a_file_from_another_engagement_is_404(self, api, advisor, db_session, test_engagement):
        """The id must be scoped to the engagement in the URL."""
        other = Engagement(
            engagement_name=f"Other {uuid.uuid4()}",
            primary_advisor_id=advisor.id,
            tool="value_builder",
        )
        db_session.add(other)
        db_session.flush()
        media_id = _upload(api, advisor, other).json()[0]["id"]

        resp = api.as_user(advisor).get(f"{BASE}/{test_engagement.id}/files/{media_id}/download")
        assert resp.status_code == 404


# ----------------------------------------------------------------------
# Download
# ----------------------------------------------------------------------
class TestDownload:

    def test_the_bytes_come_back(self, api, advisor, test_engagement):
        media_id = _upload(api, advisor, test_engagement, content=b"trinity report").json()[0]["id"]
        resp = api.as_user(advisor).get(f"{BASE}/{test_engagement.id}/files/{media_id}/download")

        assert resp.status_code == 200
        assert resp.content == b"trinity report"

    def test_a_client_can_download(self, api, advisor, client_user, test_engagement):
        media_id = _upload(api, advisor, test_engagement).json()[0]["id"]
        resp = api.as_user(client_user).get(f"{BASE}/{test_engagement.id}/files/{media_id}/download")
        assert resp.status_code == 200

    def test_an_unknown_file_is_404(self, api, advisor, test_engagement):
        resp = api.as_user(advisor).get(f"{BASE}/{test_engagement.id}/files/{uuid.uuid4()}/download")
        assert resp.status_code == 404


# ----------------------------------------------------------------------
# Delete
# ----------------------------------------------------------------------
class TestDelete:

    def test_the_uploader_can_delete_their_own(self, api, client_user, test_engagement):
        media_id = _upload(api, client_user, test_engagement).json()[0]["id"]
        resp = api.as_user(client_user).delete(f"{BASE}/{test_engagement.id}/files/{media_id}")
        assert resp.status_code == 204

    def test_an_advisor_can_delete_someone_elses(self, api, advisor, client_user, test_engagement):
        media_id = _upload(api, client_user, test_engagement).json()[0]["id"]
        resp = api.as_user(advisor).delete(f"{BASE}/{test_engagement.id}/files/{media_id}")
        assert resp.status_code == 204

    def test_a_client_cannot_delete_another_users_file(
        self, api, advisor, other_client, test_engagement
    ):
        """The one place the rule is narrower than engagement access."""
        media_id = _upload(api, advisor, test_engagement).json()[0]["id"]
        resp = api.as_user(other_client).delete(f"{BASE}/{test_engagement.id}/files/{media_id}")
        assert resp.status_code == 403

    def test_a_refused_delete_leaves_the_file(self, api, advisor, other_client, db_session, test_engagement):
        media_id = _upload(api, advisor, test_engagement).json()[0]["id"]
        api.as_user(other_client).delete(f"{BASE}/{test_engagement.id}/files/{media_id}")

        media = db_session.query(Media).filter(Media.id == uuid.UUID(media_id)).one()
        db_session.refresh(media)
        assert media.is_active is True

    def test_can_delete_is_reported_per_caller(self, api, advisor, other_client, test_engagement):
        _upload(api, advisor, test_engagement)
        assert _list(api, advisor, test_engagement).json()[0]["can_delete"] is True
        assert _list(api, other_client, test_engagement).json()[0]["can_delete"] is False

    def test_delete_is_soft(self, api, advisor, db_session, test_engagement):
        """The row and the bytes stay, so a mistake is recoverable."""
        media_id = _upload(api, advisor, test_engagement).json()[0]["id"]
        api.as_user(advisor).delete(f"{BASE}/{test_engagement.id}/files/{media_id}")

        media = db_session.query(Media).filter(Media.id == uuid.UUID(media_id)).one()
        db_session.refresh(media)
        assert media.is_active is False
        assert media.deleted_at is not None

    def test_a_deleted_file_is_not_listed(self, api, advisor, test_engagement):
        media_id = _upload(api, advisor, test_engagement).json()[0]["id"]
        api.as_user(advisor).delete(f"{BASE}/{test_engagement.id}/files/{media_id}")
        assert _list(api, advisor, test_engagement).json() == []

    def test_a_deleted_file_cannot_be_downloaded(self, api, advisor, test_engagement):
        media_id = _upload(api, advisor, test_engagement).json()[0]["id"]
        api.as_user(advisor).delete(f"{BASE}/{test_engagement.id}/files/{media_id}")

        resp = api.as_user(advisor).get(f"{BASE}/{test_engagement.id}/files/{media_id}/download")
        assert resp.status_code == 404

    def test_deleting_twice_is_404(self, api, advisor, test_engagement):
        media_id = _upload(api, advisor, test_engagement).json()[0]["id"]
        api.as_user(advisor).delete(f"{BASE}/{test_engagement.id}/files/{media_id}")
        resp = api.as_user(advisor).delete(f"{BASE}/{test_engagement.id}/files/{media_id}")
        assert resp.status_code == 404


# ----------------------------------------------------------------------
# documents_count on the engagements list
# ----------------------------------------------------------------------
class TestDocumentsCount:

    def _count(self, api, user, engagement):
        rows = api.as_user(user).get(BASE).json()
        row = next((e for e in rows if e["id"] == str(engagement.id)), None)
        assert row is not None
        return row["documents_count"]

    def test_engagement_uploads_are_counted(self, api, advisor, test_engagement):
        assert self._count(api, advisor, test_engagement) == 0
        _upload(api, advisor, test_engagement)
        assert self._count(api, advisor, test_engagement) == 1

    def test_a_deleted_file_is_not_counted(self, api, advisor, test_engagement):
        media_id = _upload(api, advisor, test_engagement).json()[0]["id"]
        api.as_user(advisor).delete(f"{BASE}/{test_engagement.id}/files/{media_id}")
        assert self._count(api, advisor, test_engagement) == 0
