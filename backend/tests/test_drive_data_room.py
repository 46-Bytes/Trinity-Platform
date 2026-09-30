"""
The Drive data room: folder mapping, upload, sync and the release boundary.

No test here talks to Google. DriveClient is replaced by a fake that records
what it was asked to do, which is the only way to assert the interesting
things - that a move is an update rather than a duplicate, that a delete
trashes rather than deletes, and that a buyer cannot reach an unreleased
document however the file arrived.

Skips wholesale until add_drive_data_room has been applied, the same way the
buyer suite does: without the media columns every query here errors and the
failures say nothing useful.
"""
import asyncio
import json
from datetime import datetime, timedelta
from uuid import uuid4
from io import BytesIO

import pytest
from sqlalchemy import text

from app.config import settings
from app.models.buyer import EngagementBuyer, EngagementReleasedFolder
from app.models.drive import DriveIntegration, EngagementDriveFolder
from app.models.engagement import Engagement
from app.models.media import Media
from app.models.sale_ready import EngagementDDItem
from app.models.user import UserRole
from app.services import sale_ready_rules as sr_rules
from app.services.data_room_service import DataRoomError, get_data_room_service
from app.services.drive_sync_service import get_drive_sync_service

_NEEDS_MIGRATION = (
    "Drive data room schema is missing. Migrate first:\n"
    "    cd backend && alembic upgrade head"
)


@pytest.fixture(autouse=True)
def drive_schema(db_session):
    try:
        db_session.execute(text("SELECT drive_file_id, dd_sub_item_code FROM media LIMIT 0"))
        db_session.execute(text("SELECT 1 FROM engagement_drive_folder LIMIT 0"))
        db_session.execute(text("SELECT 1 FROM drive_integration LIMIT 0"))
    except Exception:
        pytest.skip(_NEEDS_MIGRATION, allow_module_level=True)


# ----------------------------------------------------------------------
# A Drive that lives in a dict
# ----------------------------------------------------------------------
class FakeDrive:
    """Records calls and behaves like Drive enough to assert against."""

    def __init__(self):
        self.files = {}
        self.folders = {}
        self.trashed = []
        self.renamed = []
        self._next = 0

    def _id(self, prefix):
        self._next += 1
        return f"{prefix}-{self._next}"

    # folders
    def find_folder(self, name, parent_id):
        for fid, f in self.folders.items():
            if f["name"] == name and f["parent"] == parent_id:
                return {"id": fid, "name": name, "webViewLink": f"https://drive/{fid}"}
        return None

    def create_folder(self, name, parent_id):
        fid = self._id("folder")
        self.folders[fid] = {"name": name, "parent": parent_id}
        return {"id": fid, "name": name, "webViewLink": f"https://drive/{fid}"}

    def ensure_folder(self, name, parent_id):
        return self.find_folder(name, parent_id) or self.create_folder(name, parent_id)

    # files
    def upload(self, stream, name, mime_type, parent_id):
        fid = self._id("file")
        payload = {
            "id": fid, "name": name, "mimeType": mime_type or "application/pdf",
            "size": str(len(stream.read())), "parents": [parent_id],
            "modifiedTime": "2026-09-29T10:00:00.000Z",
            "webViewLink": f"https://drive/{fid}", "trashed": False,
        }
        self.files[fid] = payload
        return payload

    def download_stream(self, file_id, chunk_size=None):
        yield b"pretend-bytes"

    def get_metadata(self, file_id):
        return self.files[file_id]

    def rename(self, file_id, name):
        self.renamed.append((file_id, name))
        self.files[file_id]["name"] = name
        return self.files[file_id]

    def trash(self, file_id):
        self.trashed.append(file_id)
        self.files[file_id]["trashed"] = True

    def list_children(self, parent_id):
        return [f for f in self.files.values() if parent_id in f.get("parents", []) and not f["trashed"]]

    def start_page_token(self):
        return "token-1"

    def list_changes(self, page_token):
        return [], None, "token-2"


@pytest.fixture(autouse=True)
def _fresh_provision_backoff():
    """The backoff record lives in the process; no test may inherit another test's failures."""
    from app.services.drive_folder_service import reset_provision_backoff

    reset_provision_backoff()
    yield
    reset_provision_backoff()


@pytest.fixture
def fake_drive(monkeypatch):
    drive = FakeDrive()
    for module in ("drive_folder_service", "data_room_service", "drive_sync_service"):
        monkeypatch.setattr(f"app.services.{module}.get_drive_client", lambda db, d=drive: d,
                            raising=False)
    monkeypatch.setattr("app.services.drive_client.drive_enabled", lambda: True)
    monkeypatch.setattr("app.services.drive_folder_service.drive_enabled", lambda: True)
    return drive


@pytest.fixture
def advisor(make_user):
    return make_user(UserRole.ADVISOR)


@pytest.fixture
def engagement(db_session, advisor, make_user):
    owner = make_user(UserRole.CLIENT)
    eng = Engagement(engagement_name="Drive test", business_name="Hale Fabrication",
                     primary_advisor_id=advisor.id, client_id=owner.id, client_ids=[owner.id],
                     tool="sale_ready", status="active")
    db_session.add(eng)
    db_session.flush()
    db_session.add(DriveIntegration(status="connected", refresh_token="x",
                                    root_folder_id="root-clients",
                                    account_email=settings.GOOGLE_DRIVE_EXPECTED_ACCOUNT))
    db_session.flush()
    return eng


def _dd(db_session, engagement, cat="3", cat_name="Financial Documentation",
        sub="3.1", sub_name="Historical Financial Statements", key="DD-001", status=None):
    # template_item_id is NOT NULL and unique per engagement, so every DD item
    # needs its own template row. Created here rather than borrowed, so these
    # tests run on an empty database as well as a seeded one.
    #
    # The template's own item_key is made unique: program_dd_template is
    # unique on (program_type, item_key), and the seeded checklist already
    # owns DD-001 and friends on a real database.
    template_id = uuid4()
    db_session.execute(text(
        "INSERT INTO program_dd_template "
        "(id, program_type, item_key, stage_code, category_code, category, "
        " sub_item_code, sub_item, default_order) "
        "VALUES (:id, 'sale_ready', :template_key, 'M1', :cat, :cat_name, :sub, :sub_name, 0)"
    ), {"id": template_id, "template_key": f"TEST-{template_id}", "cat": cat,
        "cat_name": cat_name, "sub": sub, "sub_name": sub_name})
    db_session.flush()
    row = EngagementDDItem(
        engagement_id=engagement.id, template_item_id=template_id, item_key=key,
        stage_code="M1", category_code=cat, category=cat_name,
        sub_item_code=sub, sub_item=sub_name, status=status,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _upload(db_session, engagement, advisor, name="statements.pdf", cat="3", sub="3.1"):
    return get_data_room_service(db_session).upload(
        engagement, cat, sub, BytesIO(b"hello"), name, "application/pdf", advisor,
    )


# ======================================================================
# Folder structure
# ======================================================================
class TestFolderStructure:
    def test_the_path_is_business_name_then_data_room(
        self, db_session, fake_drive, engagement, advisor
    ):
        """Trinity/Clients/{business_name}/Data room, and no engagement level."""
        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor)

        names = {f["name"]: f for f in fake_drive.folders.values()}
        assert "Hale Fabrication" in names
        assert names["Hale Fabrication"]["parent"] == "root-clients"
        assert names["Data room"]["parent"] == \
            next(k for k, v in fake_drive.folders.items() if v["name"] == "Hale Fabrication")

    def test_folders_are_keyed_on_engagement_id(self, db_session, fake_drive, engagement, advisor):
        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor)
        rows = db_session.query(EngagementDriveFolder).filter(
            EngagementDriveFolder.engagement_id == engagement.id,
        ).all()
        assert {(r.category_code, r.sub_item_code) for r in rows} == {
            (None, None), ("3", None), ("3", "3.1"),
        }

    def test_folders_are_created_once_and_then_reused(
        self, db_session, fake_drive, engagement, advisor
    ):
        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor, name="a.pdf")
        after_first = len(fake_drive.folders)
        _upload(db_session, engagement, advisor, name="b.pdf")
        assert len(fake_drive.folders) == after_first

    def test_sub_item_folders_are_created_lazily(self, db_session, fake_drive, engagement, advisor):
        """Only the folder being written to appears; the other 200-odd do not."""
        _dd(db_session, engagement)
        _dd(db_session, engagement, cat="9", cat_name="Property & Assets",
            sub="9.1", sub_name="Real Estate", key="DD-002")
        _upload(db_session, engagement, advisor)
        assert not any(f["name"].startswith("9.1") for f in fake_drive.folders.values())


# ======================================================================
# Upload
# ======================================================================
class TestUpload:
    def test_trinity_keeps_no_bytes(self, db_session, fake_drive, engagement, advisor):
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        assert media.file_path is None
        assert media.drive_file_id in fake_drive.files
        assert media.source == "trinity"

    def test_the_file_is_filed_against_the_dd_folder(
        self, db_session, fake_drive, engagement, advisor
    ):
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        assert (media.dd_category_code, media.dd_sub_item_code) == ("3", "3.1")

    def test_upload_moves_the_dd_item_to_in_progress(
        self, db_session, fake_drive, engagement, advisor
    ):
        item = _dd(db_session, engagement)
        assert item.status is None
        _upload(db_session, engagement, advisor)
        db_session.refresh(item)
        assert item.status == sr_rules.DD_STATUS_IN_PROGRESS

    def test_upload_does_not_reopen_an_answered_item(
        self, db_session, fake_drive, engagement, advisor
    ):
        """A Yes was decided by an advisor; a file arriving does not undo it."""
        item = _dd(db_session, engagement, status=sr_rules.DD_STATUS_YES)
        _upload(db_session, engagement, advisor)
        db_session.refresh(item)
        assert item.status == sr_rules.DD_STATUS_YES

    def test_a_no_is_promoted(self, db_session, fake_drive, engagement, advisor):
        item = _dd(db_session, engagement, status=sr_rules.DD_STATUS_NO)
        _upload(db_session, engagement, advisor)
        db_session.refresh(item)
        assert item.status == sr_rules.DD_STATUS_IN_PROGRESS

    def test_an_unknown_folder_is_refused(self, db_session, fake_drive, engagement, advisor):
        _dd(db_session, engagement)
        with pytest.raises(DataRoomError):
            _upload(db_session, engagement, advisor, cat="99", sub="99.9")

    def test_the_ten_megabyte_limit_still_applies(self, db_session, fake_drive, engagement, advisor):
        _dd(db_session, engagement)
        service = get_data_room_service(db_session)
        with pytest.raises(DataRoomError, match="larger than"):
            service.upload(engagement, "3", "3.1", BytesIO(b"x"), "big.pdf",
                           "application/pdf", advisor, size=11 * 1024 * 1024)

    def test_a_disallowed_type_is_refused(self, db_session, fake_drive, engagement, advisor):
        _dd(db_session, engagement)
        with pytest.raises(DataRoomError, match="not allowed"):
            _upload(db_session, engagement, advisor, name="payload.exe")


# ======================================================================
# Rename and delete
# ======================================================================
class TestRenameAndDelete:
    def test_rename_reaches_drive(self, db_session, fake_drive, engagement, advisor):
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        get_data_room_service(db_session).rename(media, "FY24_statements.pdf")
        assert fake_drive.renamed == [(media.drive_file_id, "FY24_statements.pdf")]
        assert media.file_name == "FY24_statements.pdf"

    def test_delete_trashes_rather_than_destroying(
        self, db_session, fake_drive, engagement, advisor
    ):
        """buyer_access_log points at these rows; a hard delete would orphan it."""
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        drive_id = media.drive_file_id
        get_data_room_service(db_session).delete(media)
        assert fake_drive.trashed == [drive_id]
        assert media.deleted_at is not None
        assert db_session.query(Media).filter(Media.id == media.id).first() is not None

    def test_a_deleted_file_leaves_the_folder_listing(
        self, db_session, fake_drive, engagement, advisor
    ):
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        service = get_data_room_service(db_session)
        service.delete(media)
        assert service.files_in_folder(engagement.id, "3", "3.1") == []


# ======================================================================
# The release boundary
# ======================================================================
class TestReleaseBoundary:
    def _buyer(self, db_session, make_user, engagement):
        from app.services.buyer_service import get_buyer_service

        user = make_user(UserRole.BUYER)
        db_session.add(EngagementBuyer(engagement_id=engagement.id, user_id=user.id, status="active"))
        db_session.flush()
        return user, get_buyer_service(db_session)

    def test_an_unreleased_document_is_not_released(
        self, db_session, fake_drive, engagement, advisor, make_user
    ):
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        _, buyers = self._buyer(db_session, make_user, engagement)
        assert buyers.media_is_released(engagement.id, media.id) is False

    def test_releasing_the_folder_releases_its_documents(
        self, db_session, fake_drive, engagement, advisor, make_user
    ):
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        db_session.add(EngagementReleasedFolder(engagement_id=engagement.id,
                                                category_code="3", sub_item_code="3.1"))
        db_session.flush()
        _, buyers = self._buyer(db_session, make_user, engagement)
        assert buyers.media_is_released(engagement.id, media.id) is True
        assert [m.id for m in buyers.documents_in_folder(engagement.id, "3", "3.1")] == [media.id]

    def test_withdrawing_the_folder_takes_effect_at_once(
        self, db_session, fake_drive, engagement, advisor, make_user
    ):
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        row = EngagementReleasedFolder(engagement_id=engagement.id,
                                       category_code="3", sub_item_code="3.1")
        db_session.add(row)
        db_session.flush()
        _, buyers = self._buyer(db_session, make_user, engagement)
        assert buyers.media_is_released(engagement.id, media.id) is True
        row.is_deleted = True
        db_session.flush()
        assert buyers.media_is_released(engagement.id, media.id) is False

    def test_another_engagements_document_is_never_released(
        self, db_session, fake_drive, engagement, advisor, make_user
    ):
        """Even with the same folder released here, a foreign id must fail."""
        _dd(db_session, engagement)
        other = Engagement(engagement_name="Other", business_name="Other Co",
                           primary_advisor_id=advisor.id, client_id=advisor.id,
                           client_ids=[advisor.id], tool="sale_ready", status="active")
        db_session.add(other)
        db_session.flush()
        _dd(db_session, other, key="DD-OTHER")
        foreign = _upload(db_session, other, advisor, name="theirs.pdf")

        db_session.add(EngagementReleasedFolder(engagement_id=engagement.id,
                                                category_code="3", sub_item_code="3.1"))
        db_session.flush()
        _, buyers = self._buyer(db_session, make_user, engagement)
        assert buyers.media_is_released(engagement.id, foreign.id) is False

    def test_a_deleted_document_is_not_released(
        self, db_session, fake_drive, engagement, advisor, make_user
    ):
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        db_session.add(EngagementReleasedFolder(engagement_id=engagement.id,
                                                category_code="3", sub_item_code="3.1"))
        db_session.flush()
        get_data_room_service(db_session).delete(media)
        _, buyers = self._buyer(db_session, make_user, engagement)
        assert buyers.media_is_released(engagement.id, media.id) is False


# ======================================================================
# Drive -> Trinity sync
# ======================================================================
class TestSync:
    def _folder_row(self, db_session, engagement, fake_drive, advisor):
        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor)
        return db_session.query(EngagementDriveFolder).filter(
            EngagementDriveFolder.engagement_id == engagement.id,
            EngagementDriveFolder.sub_item_code == "3.1",
        ).first()

    def _change(self, file_id, name, parent, modified="2026-09-30T10:00:00.000Z", trashed=False):
        return {
            "fileId": file_id,
            "removed": False,
            "file": {
                "id": file_id, "name": name, "mimeType": "application/pdf", "size": "10",
                "parents": [parent], "modifiedTime": modified, "trashed": trashed,
                "webViewLink": f"https://drive/{file_id}",
            },
        }

    def test_a_file_added_in_drive_is_indexed(
        self, db_session, fake_drive, engagement, advisor
    ):
        folder = self._folder_row(db_session, engagement, fake_drive, advisor)
        sync = get_drive_sync_service(db_session)
        result = type("R", (), {"added": 0, "renamed": 0, "moved": 0, "deleted": 0, "skipped": 0})()
        sync._apply(self._change("drive-x", "dropped.pdf", folder.drive_folder_id), result)
        db_session.flush()
        found = db_session.query(Media).filter(Media.drive_file_id == "drive-x").first()
        assert found is not None
        assert found.source == "drive"
        assert found.dd_sub_item_code == "3.1"
        assert found.file_path is None

    def test_a_file_added_in_drive_also_promotes_the_dd_item(
        self, db_session, fake_drive, engagement, advisor
    ):
        item = _dd(db_session, engagement, sub="3.2", sub_name="Management Accounts", key="DD-2")
        folder = EngagementDriveFolder(engagement_id=engagement.id, category_code="3",
                                       sub_item_code="3.2", drive_folder_id="folder-3-2")
        db_session.add(folder)
        db_session.flush()
        sync = get_drive_sync_service(db_session)
        result = type("R", (), {"added": 0, "renamed": 0, "moved": 0, "deleted": 0, "skipped": 0})()
        sync._apply(self._change("drive-y", "mgmt.pdf", "folder-3-2"), result)
        db_session.flush()
        db_session.refresh(item)
        assert item.status == sr_rules.DD_STATUS_IN_PROGRESS

    def test_a_rename_in_drive_is_followed(self, db_session, fake_drive, engagement, advisor):
        folder = self._folder_row(db_session, engagement, fake_drive, advisor)
        media = db_session.query(Media).filter(Media.dd_sub_item_code == "3.1").first()
        media.drive_modified_time = datetime(2026, 9, 29, 10, 0)
        db_session.flush()
        sync = get_drive_sync_service(db_session)
        result = type("R", (), {"added": 0, "renamed": 0, "moved": 0, "deleted": 0, "skipped": 0})()
        sync._apply(self._change(media.drive_file_id, "renamed.pdf", folder.drive_folder_id), result)
        db_session.flush()
        assert media.file_name == "renamed.pdf"
        assert result.renamed == 1

    def test_a_move_updates_rather_than_duplicating(
        self, db_session, fake_drive, engagement, advisor
    ):
        """Identity is drive_file_id, so a move must not create a second row."""
        self._folder_row(db_session, engagement, fake_drive, advisor)
        media = db_session.query(Media).filter(Media.dd_sub_item_code == "3.1").first()
        media.drive_modified_time = datetime(2026, 9, 29, 10, 0)
        _dd(db_session, engagement, sub="3.2", sub_name="Management Accounts", key="DD-2")
        target = EngagementDriveFolder(engagement_id=engagement.id, category_code="3",
                                       sub_item_code="3.2", drive_folder_id="folder-3-2")
        db_session.add(target)
        db_session.flush()

        before = db_session.query(Media).filter(Media.engagement_id == engagement.id).count()
        sync = get_drive_sync_service(db_session)
        result = type("R", (), {"added": 0, "renamed": 0, "moved": 0, "deleted": 0, "skipped": 0})()
        sync._apply(self._change(media.drive_file_id, media.file_name, "folder-3-2"), result)
        db_session.flush()

        assert db_session.query(Media).filter(Media.engagement_id == engagement.id).count() == before
        assert media.dd_sub_item_code == "3.2"
        assert result.moved == 1

    def test_a_trashed_file_is_soft_deleted(self, db_session, fake_drive, engagement, advisor):
        folder = self._folder_row(db_session, engagement, fake_drive, advisor)
        media = db_session.query(Media).filter(Media.dd_sub_item_code == "3.1").first()
        sync = get_drive_sync_service(db_session)
        result = type("R", (), {"added": 0, "renamed": 0, "moved": 0, "deleted": 0, "skipped": 0})()
        sync._apply(
            self._change(media.drive_file_id, media.file_name, folder.drive_folder_id, trashed=True),
            result,
        )
        db_session.flush()
        assert media.deleted_at is not None
        assert db_session.query(Media).filter(Media.id == media.id).first() is not None

    def test_a_file_moved_out_of_the_data_room_disappears(
        self, db_session, fake_drive, engagement, advisor
    ):
        self._folder_row(db_session, engagement, fake_drive, advisor)
        media = db_session.query(Media).filter(Media.dd_sub_item_code == "3.1").first()
        sync = get_drive_sync_service(db_session)
        result = type("R", (), {"added": 0, "renamed": 0, "moved": 0, "deleted": 0, "skipped": 0})()
        sync._apply(self._change(media.drive_file_id, media.file_name, "somewhere-else"), result)
        db_session.flush()
        assert media.deleted_at is not None

    def test_an_echo_of_our_own_write_changes_nothing(
        self, db_session, fake_drive, engagement, advisor
    ):
        """Trinity wrote to Drive, so the change feed replays it. It must no-op."""
        folder = self._folder_row(db_session, engagement, fake_drive, advisor)
        media = db_session.query(Media).filter(Media.dd_sub_item_code == "3.1").first()
        media.drive_modified_time = datetime(2026, 9, 30, 10, 0)
        db_session.flush()
        sync = get_drive_sync_service(db_session)
        result = type("R", (), {"added": 0, "renamed": 0, "moved": 0, "deleted": 0, "skipped": 0})()
        # Same timestamp, different name: a real rename would be newer.
        sync._apply(
            self._change(media.drive_file_id, "should-not-apply.pdf", folder.drive_folder_id,
                         modified="2026-09-29T09:00:00.000Z"),
            result,
        )
        assert media.file_name != "should-not-apply.pdf"
        assert result.renamed == 0

    def test_a_file_in_an_unmapped_folder_is_ignored(
        self, db_session, fake_drive, engagement, advisor
    ):
        self._folder_row(db_session, engagement, fake_drive, advisor)
        sync = get_drive_sync_service(db_session)
        result = type("R", (), {"added": 0, "renamed": 0, "moved": 0, "deleted": 0, "skipped": 0})()
        sync._apply(self._change("stray", "elsewhere.pdf", "not-ours"), result)
        db_session.flush()
        assert db_session.query(Media).filter(Media.drive_file_id == "stray").first() is None


# ======================================================================
# Document register
# ======================================================================
class TestDocumentRegister:
    def test_the_register_is_generated_from_the_files(
        self, db_session, fake_drive, engagement, advisor
    ):
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        rows = get_data_room_service(db_session).register_for_stage(engagement.id, "M1")
        assert [r["media_id"] for r in rows] == [media.id]
        assert rows[0]["file_name"] == "statements.pdf"
        assert rows[0]["document_id"] is None

    def test_a_stage_with_no_files_has_an_empty_register(
        self, db_session, fake_drive, engagement, advisor
    ):
        _dd(db_session, engagement)
        assert get_data_room_service(db_session).register_for_stage(engagement.id, "M1") == []

    def test_typed_fields_are_saved_against_the_file(
        self, db_session, fake_drive, engagement, advisor
    ):
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        service = get_data_room_service(db_session)
        service.update_register_entry(engagement, "M1", media.id, {
            "document_id": "FIN-002", "notes": "FY24-FY26, exported from Xero",
        })
        row = service.register_for_stage(engagement.id, "M1")[0]
        assert row["document_id"] == "FIN-002"
        assert row["notes"] == "FY24-FY26, exported from Xero"

    def test_the_name_is_never_taken_from_the_advisor(
        self, db_session, fake_drive, engagement, advisor
    ):
        """The brief: name and date come from the file, so those columns stay NULL."""
        from app.models.sale_ready import EngagementDocumentRegisterEntry

        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        service = get_data_room_service(db_session)
        service.update_register_entry(engagement, "M1", media.id, {"document_id": "X"})
        row = db_session.query(EngagementDocumentRegisterEntry).filter(
            EngagementDocumentRegisterEntry.media_id == media.id,
        ).first()
        assert row.document_name is None and row.creation_date is None and row.file_link is None

    def test_a_foreign_file_cannot_be_annotated(
        self, db_session, fake_drive, engagement, advisor
    ):
        import uuid as _uuid

        with pytest.raises(DataRoomError):
            get_data_room_service(db_session).update_register_entry(
                engagement, "M1", _uuid.uuid4(), {"document_id": "X"},
            )


# ======================================================================
# Open folder in Drive
# ======================================================================
class TestDriveLinks:
    """
    Advisors and owners may open a folder in Drive; buyers never can.

    Trinity stays the working interface either way - the link is a
    convenience on top, not the route documents travel.
    """

    def test_the_folder_map_carries_a_link_for_the_advisor(
        self, db_session, fake_drive, engagement, advisor
    ):
        from app.services.drive_folder_service import get_drive_folder_service

        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor)
        links = get_drive_folder_service(db_session).mapped_web_links(engagement.id)
        assert links[(None, None)]                 # the Data room folder
        assert links[("3", "3.1")]                 # the sub-item folder
        assert all(v.startswith("https://") for v in links.values() if v)

    def test_an_uncreated_folder_simply_has_no_link(
        self, db_session, fake_drive, engagement, advisor
    ):
        """Folders are made on first upload, so most have no link yet."""
        from app.services.drive_folder_service import get_drive_folder_service

        _dd(db_session, engagement)
        _dd(db_session, engagement, cat="9", cat_name="Property & Assets",
            sub="9.1", sub_name="Real Estate", key="DD-009")
        _upload(db_session, engagement, advisor)
        links = get_drive_folder_service(db_session).mapped_web_links(engagement.id)
        assert ("9", "9.1") not in links

    def test_no_drive_link_reaches_a_buyer(
        self, db_session, fake_drive, engagement, advisor, make_user
    ):
        """
        The buyer payload must carry no Drive link and no Drive id, even for a
        folder that has both and has been released.
        """
        from app.services.buyer_service import get_buyer_service

        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        assert media.drive_web_link  # the advisor side does have one
        db_session.add(EngagementReleasedFolder(engagement_id=engagement.id,
                                                category_code="3", sub_item_code="3.1"))
        db_session.flush()

        buyers = get_buyer_service(db_session)
        for folder in buyers.buyer_folders(engagement):
            assert "drive_web_link" not in folder
            assert "drive_file_id" not in folder
            assert not any("drive" in str(k).lower() for k in folder)

    def test_the_buyer_folder_schema_has_no_link_field(self):
        """Belt and braces: the contract itself cannot express one."""
        from app.schemas.buyer import BuyerFolder, BuyerFolderView

        for model in (BuyerFolder, BuyerFolderView):
            assert not any("drive" in name for name in model.model_fields)

    def test_the_register_carries_a_file_link_for_the_advisor(
        self, db_session, fake_drive, engagement, advisor
    ):
        """The mockup's per-row arrow. Advisor-only endpoint, advisor-only field."""
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        row = get_data_room_service(db_session).register_for_stage(engagement.id, "M1")[0]
        assert row["drive_web_link"] == media.drive_web_link
        assert row["drive_web_link"].startswith("https://")

    def test_the_register_link_survives_an_edit(
        self, db_session, fake_drive, engagement, advisor
    ):
        """The update response feeds the same table, so it must match the list."""
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        updated = get_data_room_service(db_session).update_register_entry(
            engagement, "M1", media.id, {"document_id": "FIN-002"},
        )
        assert updated["drive_web_link"] == media.drive_web_link

    def test_the_buyer_document_schema_still_has_no_link(self):
        """Adding the advisor's link must not have opened one on the buyer side."""
        from app.schemas.buyer import BuyerDocument

        assert not any("drive" in name for name in BuyerDocument.model_fields)

    # -- the Files tab: per-file links for the advisor and the owner --------
    def _owner(self, db_session, engagement):
        from app.models.user import User
        return db_session.query(User).filter(User.id == engagement.client_ids[0]).one()

    def test_the_data_room_gives_the_advisor_a_link_per_file(
        self, api, db_session, fake_drive, engagement, advisor
    ):
        """The arrow beside each file on the Files tab, as in the mockup."""
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)

        body = api.as_user(advisor).get(
            f"/api/sale-ready/engagements/{engagement.id}/data-room").json()
        row = next(f for f in body["files"] if f["id"] == str(media.id))
        assert row["drive_web_link"] == media.drive_web_link
        assert row["drive_web_link"].startswith("https://")

    def test_the_data_room_gives_the_owner_the_same_link(
        self, api, db_session, fake_drive, engagement, advisor
    ):
        """
        The owner opens files in Drive too, not only folders.

        Their own documents: the brief gives them Files, and the mockup shows
        the same arrow. Read-only is enforced elsewhere - this is a link.
        """
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        owner = self._owner(db_session, engagement)

        resp = api.as_user(owner).get(
            f"/api/sale-ready/engagements/{engagement.id}/data-room")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        row = next(f for f in body["files"] if f["id"] == str(media.id))
        assert row["drive_web_link"] == media.drive_web_link
        # And the folder link the owner already had, unchanged.
        assert body["data_room_web_link"]

    def test_a_file_not_yet_in_drive_simply_has_no_link(
        self, api, db_session, fake_drive, engagement, advisor
    ):
        """Null is rendered as no arrow, never as a broken one."""
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        media.drive_web_link = None
        db_session.flush()

        body = api.as_user(advisor).get(
            f"/api/sale-ready/engagements/{engagement.id}/data-room").json()
        row = next(f for f in body["files"] if f["id"] == str(media.id))
        assert row["drive_web_link"] is None

    def test_the_file_link_never_reaches_a_buyer_through_the_portal(
        self, api, db_session, fake_drive, engagement, advisor, make_user
    ):
        """
        The regression guard for the change that added the link above.

        Checked through the buyer's own endpoint rather than the schema, so a
        payload built by hand could not slip one past the contract.
        """
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        assert media.drive_web_link  # the advisor and owner side does have one
        db_session.add(EngagementReleasedFolder(engagement_id=engagement.id,
                                                category_code="3", sub_item_code="3.1"))
        db_session.flush()
        buyer, _ = TestReleaseBoundary()._buyer(db_session, make_user, engagement)

        body = api.as_user(buyer).get("/api/buyer/me/folders/3/3.1").json()
        assert [d["id"] for d in body["documents"]] == [str(media.id)]
        for document in body["documents"]:
            assert not any("drive" in key.lower() for key in document)
        assert media.drive_web_link not in json.dumps(body)

    def test_a_buyer_cannot_reach_the_endpoint_that_carries_the_link(
        self, api, db_session, fake_drive, engagement, advisor, make_user
    ):
        """deny_buyers on the sale-ready router, not merely an absent field."""
        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor)
        buyer, _ = TestReleaseBoundary()._buyer(db_session, make_user, engagement)

        resp = api.as_user(buyer).get(
            f"/api/sale-ready/engagements/{engagement.id}/data-room")
        assert resp.status_code == 403, resp.text

# ======================================================================
# Backfill: files already in a folder (B1/B2)
# ======================================================================
class TestBackfill:
    """
    The change feed only reports what happens after the cursor is taken, so
    anything already in a folder has to be walked once. Without this the
    "pick up files added directly in Drive" requirement holds only for files
    added after Trinity first looked.
    """

    def _preexisting(self, fake_drive, parent_id, name="already_here.pdf"):
        """A file sitting in a Drive folder before Trinity ever mapped it."""
        fid = fake_drive._id("file")
        fake_drive.files[fid] = {
            "id": fid, "name": name, "mimeType": "application/pdf", "size": "99",
            "parents": [parent_id], "modifiedTime": "2026-09-01T10:00:00.000Z",
            "webViewLink": "https://drive/" + fid, "trashed": False,
        }
        return fid

    def _drive_tree(self, fake_drive, db_session, engagement):
        """
        The folder path as it would already exist in Drive, below a data room
        this engagement already owns. A data room is never adopted by name, so
        pre-existing folders are only picked up inside the engagement's own one.
        """
        client_folder = fake_drive.create_folder("Hale Fabrication", "root-clients")
        data_room = fake_drive.create_folder("Data room", client_folder["id"])
        db_session.add(EngagementDriveFolder(engagement_id=engagement.id,
                                             drive_folder_id=data_room["id"]))
        db_session.flush()
        category = fake_drive.create_folder("3. Financial Documentation", data_room["id"])
        return fake_drive.create_folder("3.1 Historical Financial Statements", category["id"])

    def test_mapping_a_folder_indexes_what_is_already_in_it(
        self, db_session, fake_drive, engagement, advisor
    ):
        """
        The folder exists in Drive with a document in it. The first upload
        adopts that folder, and what was already there must appear too.
        """
        _dd(db_session, engagement)
        sub = self._drive_tree(fake_drive, db_session, engagement)
        stray = self._preexisting(fake_drive, sub["id"])

        _upload(db_session, engagement, advisor, name="new_upload.pdf")

        names = {m.file_name for m in db_session.query(Media).filter(
            Media.engagement_id == engagement.id).all()}
        assert "already_here.pdf" in names, "the pre-existing file was never indexed"
        assert "new_upload.pdf" in names
        found = db_session.query(Media).filter(Media.drive_file_id == stray).first()
        assert found.source == "drive" and found.dd_sub_item_code == "3.1"

    def test_backfill_does_not_duplicate_on_a_second_pass(
        self, db_session, fake_drive, engagement, advisor
    ):
        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor)
        folder = db_session.query(EngagementDriveFolder).filter(
            EngagementDriveFolder.sub_item_code == "3.1").first()
        before = db_session.query(Media).filter(Media.engagement_id == engagement.id).count()
        assert get_drive_sync_service(db_session).backfill_folder(folder) == 0
        assert db_session.query(Media).filter(
            Media.engagement_id == engagement.id).count() == before

    def test_backfill_leaves_the_transaction_to_the_caller(
        self, db_session, fake_drive, engagement, advisor
    ):
        """It must not commit: it runs inside an upload's transaction."""
        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor)
        folder = db_session.query(EngagementDriveFolder).filter(
            EngagementDriveFolder.sub_item_code == "3.1").first()
        self._preexisting(fake_drive, folder.drive_folder_id, "late_arrival.pdf")
        assert get_drive_sync_service(db_session).backfill_folder(folder) == 1
        assert db_session.query(Media).filter(Media.file_name == "late_arrival.pdf").first()

    def test_the_first_sync_backfills_mapped_folders(
        self, db_session, fake_drive, engagement, advisor
    ):
        """
        A connection with no cursor walks every mapped folder before taking
        one, so files added while the sync was off are not lost forever.
        """
        from app.services.drive_folder_service import get_integration

        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor)
        folder = db_session.query(EngagementDriveFolder).filter(
            EngagementDriveFolder.sub_item_code == "3.1").first()
        self._preexisting(fake_drive, folder.drive_folder_id, "added_while_off.pdf")

        integration = get_integration(db_session)
        integration.changes_page_token = None
        db_session.flush()

        result = get_drive_sync_service(db_session).sync()
        assert result.added == 1
        assert db_session.query(Media).filter(Media.file_name == "added_while_off.pdf").first()
        assert get_integration(db_session).changes_page_token == "token-1"

    def test_backfill_promotes_the_dd_item_too(
        self, db_session, fake_drive, engagement, advisor
    ):
        from app.services.drive_folder_service import get_drive_folder_service

        item = _dd(db_session, engagement)
        sub = self._drive_tree(fake_drive, db_session, engagement)
        self._preexisting(fake_drive, sub["id"])

        get_drive_folder_service(db_session).ensure_sub_item(engagement, "3", "3.1")
        db_session.flush()
        db_session.refresh(item)
        assert item.status == sr_rules.DD_STATUS_IN_PROGRESS


# ======================================================================
# Rate limiting is not a broken connection (B4)
# ======================================================================
class TestRateLimitIsNotRevocation:
    def _http_error(self, status_code, reason):
        from googleapiclient.errors import HttpError

        body = {"error": {"code": status_code, "errors": [{"reason": reason, "message": "x"}]}}
        resp = type("R", (), {"status": status_code, "reason": "x"})()
        return HttpError(resp, json.dumps(body).encode())

    def _raise_through_call(self, exc):
        from app.services.drive_client import DriveClient

        class Failing:
            def execute(self):
                raise exc

        return DriveClient._call(Failing())

    def test_a_403_rate_limit_is_its_own_error(self):
        from app.services.drive_client import DriveRateLimited

        for reason in ("rateLimitExceeded", "userRateLimitExceeded", "dailyLimitExceeded"):
            with pytest.raises(DriveRateLimited):
                self._raise_through_call(self._http_error(403, reason))

    def test_a_403_permission_failure_is_still_treated_as_revoked(self):
        from app.services.drive_client import DriveRateLimited, DriveUnavailable

        with pytest.raises(DriveUnavailable) as caught:
            self._raise_through_call(self._http_error(403, "insufficientPermissions"))
        assert not isinstance(caught.value, DriveRateLimited)
        assert "revoked" in str(caught.value)

    def test_a_401_is_always_revocation(self):
        from app.services.drive_client import DriveRateLimited, DriveUnavailable

        with pytest.raises(DriveUnavailable) as caught:
            self._raise_through_call(self._http_error(401, "authError"))
        assert not isinstance(caught.value, DriveRateLimited)

    def test_rate_limiting_still_reads_as_unavailable_to_ordinary_callers(self):
        """Subclassing matters: every existing `except DriveUnavailable` must hold."""
        from app.services.drive_client import DriveRateLimited, DriveUnavailable

        assert issubclass(DriveRateLimited, DriveUnavailable)

    def test_an_unparseable_403_is_not_assumed_to_be_throttling(self):
        """Guessing would hide a revoked token behind "try again shortly"."""
        from googleapiclient.errors import HttpError

        from app.services.drive_client import DriveRateLimited, DriveUnavailable

        resp = type("R", (), {"status": 403, "reason": "x"})()
        with pytest.raises(DriveUnavailable) as caught:
            self._raise_through_call(HttpError(resp, b"not json at all"))
        assert not isinstance(caught.value, DriveRateLimited)

    def test_check_does_not_disconnect_on_a_rate_limit(
        self, db_session, engagement, monkeypatch
    ):
        """
        The defect this fix exists for: throttling used to mark a healthy
        connection disconnected and send an admin off to re-authorise.
        """
        import app.api.drive_admin as admin
        from app.services.drive_client import DriveRateLimited
        from app.services.drive_folder_service import get_integration

        integration = get_integration(db_session)
        integration.status = "connected"
        db_session.flush()

        class Throttled:
            def start_page_token(self):
                raise DriveRateLimited("slow down")

        monkeypatch.setattr(admin, "get_drive_client", lambda db: Throttled())
        asyncio.run(admin.check(db=db_session))

        assert get_integration(db_session).status == "connected"
        assert "slow down" in get_integration(db_session).last_error

    def test_check_does_disconnect_on_a_real_refusal(
        self, db_session, engagement, monkeypatch
    ):
        import app.api.drive_admin as admin
        from app.services.drive_client import DriveUnavailable
        from app.services.drive_folder_service import get_integration

        integration = get_integration(db_session)
        integration.status = "connected"
        db_session.flush()

        class Revoked:
            def start_page_token(self):
                raise DriveUnavailable("revoked")

        monkeypatch.setattr(admin, "get_drive_client", lambda db: Revoked())
        asyncio.run(admin.check(db=db_session))

        assert get_integration(db_session).status == "disconnected"


# ======================================================================
# OAuth state survives a restart (B5)
# ======================================================================
class TestOAuthState:
    """
    The state is signed rather than remembered, so a reload between Connect
    and Google's redirect - constant under --reload - no longer rejects a
    legitimate callback.
    """

    def test_a_state_is_valid_without_any_stored_record(self):
        """Nothing is held in memory: validity comes from the signature alone."""
        from app.api.drive_admin import _issue_state, _state_is_valid

        assert _state_is_valid(_issue_state()) is True

    def test_each_state_is_distinct(self):
        from app.api.drive_admin import _issue_state

        assert _issue_state() != _issue_state()

    def test_a_forged_state_is_refused(self):
        from app.api.drive_admin import _state_is_valid

        assert _state_is_valid("not-a-real-state") is False
        assert _state_is_valid("") is False

    def test_a_state_signed_with_another_key_is_refused(self):
        from itsdangerous import URLSafeTimedSerializer

        from app.api.drive_admin import _STATE_SALT, _state_is_valid

        forged = URLSafeTimedSerializer(
            "someone-elses-secret", salt=_STATE_SALT).dumps({"nonce": "x"})
        assert _state_is_valid(forged) is False

    def test_an_expired_state_is_refused(self, monkeypatch):
        import app.api.drive_admin as admin

        state = admin._issue_state()
        monkeypatch.setattr(admin, "_STATE_MAX_AGE_SECONDS", -1)
        assert admin._state_is_valid(state) is False

# ======================================================================
# Retry and backoff (B3)
# ======================================================================
class TestRetry:
    """
    Transient failures are retried; failures that will never succeed are not.
    Sleep is injected so the suite does not actually wait.
    """

    class _Flaky:
        """Fails `failures` times, then succeeds."""

        def __init__(self, exc, failures):
            self.exc = exc
            self.remaining = failures
            self.calls = 0

        def execute(self):
            self.calls += 1
            if self.remaining > 0:
                self.remaining -= 1
                raise self.exc
            return {"ok": True}

    def _http(self, status_code, reason):
        from googleapiclient.errors import HttpError

        body = {"error": {"code": status_code, "errors": [{"reason": reason, "message": "x"}]}}
        resp = type("R", (), {"status": status_code, "reason": "x"})()
        return HttpError(resp, json.dumps(body).encode())

    def test_a_rate_limit_is_retried_and_can_succeed(self):
        from app.services.drive_client import DriveClient

        slept = []
        request = self._Flaky(self._http(403, "rateLimitExceeded"), failures=2)
        assert DriveClient._call(request, _sleep=slept.append) == {"ok": True}
        assert request.calls == 3
        assert len(slept) == 2

    def test_a_5xx_is_retried(self):
        from app.services.drive_client import DriveClient

        slept = []
        request = self._Flaky(self._http(503, "backendError"), failures=1)
        assert DriveClient._call(request, _sleep=slept.append) == {"ok": True}
        assert request.calls == 2

    def test_a_network_error_is_retried(self):
        from app.services.drive_client import DriveClient

        request = self._Flaky(ConnectionError("dns went away"), failures=1)
        assert DriveClient._call(request, _sleep=lambda _: None) == {"ok": True}
        assert request.calls == 2

    def test_retries_are_bounded(self):
        from app.services.drive_client import DriveClient, DriveRateLimited, RETRY_ATTEMPTS

        request = self._Flaky(self._http(403, "rateLimitExceeded"), failures=99)
        with pytest.raises(DriveRateLimited):
            DriveClient._call(request, _sleep=lambda _: None)
        assert request.calls == RETRY_ATTEMPTS

    def test_an_auth_failure_is_never_retried(self):
        """Retrying an expired token just makes the user wait for the same answer."""
        from app.services.drive_client import DriveClient, DriveUnavailable

        request = self._Flaky(self._http(401, "authError"), failures=99)
        with pytest.raises(DriveUnavailable):
            DriveClient._call(request, _sleep=lambda _: None)
        assert request.calls == 1

    def test_a_permission_failure_is_never_retried(self):
        from app.services.drive_client import DriveClient, DriveUnavailable

        request = self._Flaky(self._http(403, "insufficientPermissions"), failures=99)
        with pytest.raises(DriveUnavailable):
            DriveClient._call(request, _sleep=lambda _: None)
        assert request.calls == 1

    def test_a_404_is_never_retried(self):
        from app.services.drive_client import DriveClient, DriveUnavailable

        request = self._Flaky(self._http(404, "notFound"), failures=99)
        with pytest.raises(DriveUnavailable):
            DriveClient._call(request, _sleep=lambda _: None)
        assert request.calls == 1

    def test_the_backoff_grows_and_is_jittered(self):
        from app.services.drive_client import DriveClient, RETRY_BASE_DELAY

        slept = []
        request = self._Flaky(self._http(503, "backendError"), failures=2)
        DriveClient._call(request, _sleep=slept.append)
        assert slept[1] > slept[0], "backoff should grow"
        # Jitter multiplies by 1..2, so each delay sits in a known band.
        assert RETRY_BASE_DELAY <= slept[0] <= RETRY_BASE_DELAY * 2


# ======================================================================
# Buyers cannot reach the Drive admin router (C1)
# ======================================================================
class TestDriveRouterDeniesBuyers:
    def test_every_admin_endpoint_carries_both_guards(self):
        """
        admin_required already excludes buyers; deny_buyers is the belt to
        its braces, and keeps this router consistent with the other twenty.
        """
        from app.api.drive_admin import router
        from app.utils.auth import deny_buyers

        for route in router.routes:
            if route.path.endswith("/callback"):
                continue
            names = {getattr(d.dependency, "__name__", "") for d in route.dependencies}
            assert deny_buyers.__name__ in names, f"{route.path} is missing deny_buyers"

    def test_the_callback_stays_open(self):
        """
        Google calls it, not a signed-in browser. deny_buyers resolves
        get_current_user, so guarding it would break the OAuth flow outright.
        """
        from app.api.drive_admin import router

        callback = next(r for r in router.routes if r.path.endswith("/callback"))
        assert callback.dependencies == []

    def test_a_buyer_is_refused_by_the_api(self, api, db_session, make_user, engagement):
        user = make_user(UserRole.BUYER)
        db_session.add(EngagementBuyer(engagement_id=engagement.id, user_id=user.id,
                                       status="active"))
        db_session.flush()
        client = api.as_user(user)
        for path in ("/api/drive/status", "/api/drive/connect"):
            assert client.get(path).status_code == 403, path
        assert client.post("/api/drive/check").status_code == 403


# ======================================================================
# The size limit cannot be skipped (C2)
# ======================================================================
class TestUploadSizeGuard:
    def test_the_limit_holds_when_the_reported_size_is_missing(
        self, db_session, fake_drive, engagement, advisor
    ):
        """
        UploadFile.size is what the declared check uses, and it is not part of
        any contract we control. With it absent, the byte count has to catch
        an oversized file on its own.
        """
        from app.services.data_room_service import MAX_FILE_SIZE, get_data_room_service

        _dd(db_session, engagement)
        oversized = BytesIO(b"x" * (MAX_FILE_SIZE + 1024))
        with pytest.raises(DataRoomError, match="larger than"):
            get_data_room_service(db_session).upload(
                engagement, "3", "3.1", oversized, "huge.pdf", "application/pdf",
                advisor, size=None,
            )

    def test_nothing_is_recorded_when_the_guard_trips(
        self, db_session, fake_drive, engagement, advisor
    ):
        from app.services.data_room_service import MAX_FILE_SIZE, get_data_room_service

        _dd(db_session, engagement)
        with pytest.raises(DataRoomError):
            get_data_room_service(db_session).upload(
                engagement, "3", "3.1", BytesIO(b"x" * (MAX_FILE_SIZE + 1)),
                "huge.pdf", "application/pdf", advisor, size=None,
            )
        assert db_session.query(Media).filter(Media.file_name == "huge.pdf").first() is None

    def test_a_file_at_the_limit_is_accepted(
        self, db_session, fake_drive, engagement, advisor
    ):
        """The limit is unchanged: exactly 10MB still goes through."""
        from app.services.data_room_service import MAX_FILE_SIZE, get_data_room_service

        _dd(db_session, engagement)
        media = get_data_room_service(db_session).upload(
            engagement, "3", "3.1", BytesIO(b"x" * MAX_FILE_SIZE),
            "exactly_at_limit.pdf", "application/pdf", advisor, size=None,
        )
        assert media.id is not None

    def test_the_declared_size_still_refuses_before_any_bytes_move(
        self, db_session, fake_drive, engagement, advisor
    ):
        """The cheap check stays: an oversized declared size never reaches Drive."""
        from app.services.data_room_service import MAX_FILE_SIZE, get_data_room_service

        _dd(db_session, engagement)
        before = len(fake_drive.files)
        with pytest.raises(DataRoomError, match="larger than"):
            get_data_room_service(db_session).upload(
                engagement, "3", "3.1", BytesIO(b"tiny"), "claimed_huge.pdf",
                "application/pdf", advisor, size=MAX_FILE_SIZE + 1,
            )
        assert len(fake_drive.files) == before


# ======================================================================
# One client per operation (E1)
# ======================================================================
class TestClientReuse:
    def test_an_upload_builds_one_client_not_four(
        self, db_session, fake_drive, engagement, advisor, monkeypatch
    ):
        """
        A first upload walks three folder levels. Each get_drive_client is a
        query, a token decrypt and a service build, and repeating it four
        times buys nothing.
        """
        import app.services.data_room_service as drs
        import app.services.drive_folder_service as dfs

        calls = {"n": 0}

        def counting(db):
            calls["n"] += 1
            return fake_drive

        monkeypatch.setattr(drs, "get_drive_client", counting)
        monkeypatch.setattr(dfs, "get_drive_client", counting)

        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor)
        assert calls["n"] == 1, f"expected one client for the whole upload, got {calls['n']}"

    def test_the_folder_service_still_works_without_a_supplied_client(
        self, db_session, fake_drive, engagement
    ):
        """The parameter is optional; existing callers are unaffected."""
        from app.services.drive_folder_service import get_drive_folder_service

        _dd(db_session, engagement)
        folder_id = get_drive_folder_service(db_session).ensure_sub_item(engagement, "3", "3.1")
        assert folder_id


# ======================================================================
# A failed change is not lost (E2)
# ======================================================================
class TestFailedChangesAreNotLost:
    def _change(self, file_id, name, parent):
        return {
            "fileId": file_id, "removed": False,
            "file": {
                "id": file_id, "name": name, "mimeType": "application/pdf", "size": "10",
                "parents": [parent], "modifiedTime": "2026-10-01T10:00:00.000Z",
                "trashed": False, "webViewLink": "https://drive/" + file_id,
            },
        }

    def _prepared(self, db_session, fake_drive, engagement, advisor):
        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor)
        folder = db_session.query(EngagementDriveFolder).filter(
            EngagementDriveFolder.sub_item_code == "3.1").first()
        from app.services.drive_folder_service import get_integration
        integration = get_integration(db_session)
        integration.changes_page_token = "cursor-before"
        # Committed, not flushed: a failing change rolls the session back, and
        # an uncommitted cursor would be undone with it. The real sync task
        # starts from a committed row, so this matches production.
        db_session.commit()
        return folder, integration

    def test_the_cursor_is_held_when_a_change_cannot_be_applied(
        self, db_session, fake_drive, engagement, advisor, monkeypatch
    ):
        """
        Advancing past an unapplied change loses it for good: the feed reports
        each change once, so nothing would ever mention that file again.
        """
        folder, integration = self._prepared(db_session, fake_drive, engagement, advisor)
        monkeypatch.setattr(
            fake_drive, "list_changes",
            lambda token: ([self._change("boom", "x.pdf", folder.drive_folder_id)], None, "cursor-after"),
            raising=False,
        )
        sync = get_drive_sync_service(db_session)
        monkeypatch.setattr(sync, "_apply", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("nope")))

        result = sync.sync()
        assert result.held is True
        assert result.skipped == 1
        from app.services.drive_folder_service import get_integration
        assert get_integration(db_session).changes_page_token == "cursor-before"

    def test_the_failure_is_visible_to_an_admin(
        self, db_session, fake_drive, engagement, advisor, monkeypatch
    ):
        """Silent loss was the defect; a named, visible stall is the fix."""
        folder, _ = self._prepared(db_session, fake_drive, engagement, advisor)
        monkeypatch.setattr(
            fake_drive, "list_changes",
            lambda token: ([self._change("boom", "x.pdf", folder.drive_folder_id)], None, "cursor-after"),
            raising=False,
        )
        sync = get_drive_sync_service(db_session)
        monkeypatch.setattr(sync, "_apply", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("nope")))
        sync.sync()

        from app.services.drive_folder_service import get_integration
        assert "could not be applied" in get_integration(db_session).last_error
        assert "boom" in get_integration(db_session).last_error

    def test_a_change_that_fails_once_is_retried_and_succeeds(
        self, db_session, fake_drive, engagement, advisor, monkeypatch
    ):
        folder, _ = self._prepared(db_session, fake_drive, engagement, advisor)
        monkeypatch.setattr(
            fake_drive, "list_changes",
            lambda token: ([self._change("flaky", "y.pdf", folder.drive_folder_id)], None, "cursor-after"),
            raising=False,
        )
        sync = get_drive_sync_service(db_session)
        real_apply = sync._apply
        state = {"first": True}

        def flaky(change, result):
            if state["first"]:
                state["first"] = False
                raise RuntimeError("transient")
            return real_apply(change, result)

        monkeypatch.setattr(sync, "_apply", flaky)
        result = sync.sync()

        assert result.held is False
        from app.services.drive_folder_service import get_integration
        assert get_integration(db_session).changes_page_token == "cursor-after"
        assert db_session.query(Media).filter(Media.drive_file_id == "flaky").first()

    def test_the_cursor_advances_normally_when_everything_applies(
        self, db_session, fake_drive, engagement, advisor, monkeypatch
    ):
        folder, _ = self._prepared(db_session, fake_drive, engagement, advisor)
        monkeypatch.setattr(
            fake_drive, "list_changes",
            lambda token: ([self._change("fine", "z.pdf", folder.drive_folder_id)], None, "cursor-after"),
            raising=False,
        )
        result = get_drive_sync_service(db_session).sync()

        assert result.held is False and result.added == 1
        from app.services.drive_folder_service import get_integration
        assert get_integration(db_session).changes_page_token == "cursor-after"
        assert get_integration(db_session).last_error is None


# ======================================================================
# Engagement isolation: a business name is never a folder's identity
# ======================================================================
def _folder_ids(db_session, engagement):
    rows = db_session.query(EngagementDriveFolder).filter(
        EngagementDriveFolder.engagement_id == engagement.id,
    ).all()
    return {(r.category_code, r.sub_item_code): r.drive_folder_id for r in rows}


def _sibling(db_session, advisor, business_name="Hale Fabrication", primary_advisor=True):
    eng = Engagement(engagement_name="Second engagement", business_name=business_name,
                     primary_advisor_id=advisor.id if primary_advisor else None,
                     client_ids=[advisor.id], tool="sale_ready", status="active")
    db_session.add(eng)
    db_session.flush()
    return eng


def _no_result():
    return type("R", (), {"added": 0, "renamed": 0, "moved": 0, "deleted": 0, "skipped": 0})()


class TestEngagementIsolation:
    def _both_uploaded(self, db_session, engagement, other, advisor):
        _dd(db_session, engagement, key="DD-A")
        _dd(db_session, other, key="DD-B")
        _upload(db_session, engagement, advisor, name="a.pdf")
        _upload(db_session, other, advisor, name="b.pdf")

    def test_a_different_business_names_get_different_folders(
        self, db_session, fake_drive, engagement, advisor
    ):
        other = _sibling(db_session, advisor, business_name="XYZ Pty Ltd")
        self._both_uploaded(db_session, engagement, other, advisor)
        a, b = _folder_ids(db_session, engagement), _folder_ids(db_session, other)
        assert not set(a.values()) & set(b.values())

    def test_b_same_business_name_gets_separate_folders_at_every_level(
        self, db_session, fake_drive, engagement, advisor
    ):
        other = _sibling(db_session, advisor)  # same "Hale Fabrication"
        assert other.id != engagement.id
        self._both_uploaded(db_session, engagement, other, advisor)
        a, b = _folder_ids(db_session, engagement), _folder_ids(db_session, other)
        for scope in [(None, None), ("3", None), ("3", "3.1")]:
            assert a[scope] != b[scope], scope
        # Two client-level folders under the root, both named for the business.
        client_folders = [f for f in fake_drive.folders.values()
                          if f["name"] == "Hale Fabrication" and f["parent"] == "root-clients"]
        assert len(client_folders) == 2

    def test_c_every_category_folder_sits_under_its_own_engagement(
        self, db_session, fake_drive, engagement, advisor
    ):
        _dd(db_session, engagement, cat="3", sub="3.1", key="DD-C1")
        _dd(db_session, engagement, cat="2", cat_name="Legal", sub="2.1", sub_name="Company", key="DD-C2")
        _dd(db_session, engagement, cat="4", cat_name="Tax", sub="4.1", sub_name="Returns", key="DD-C3")
        for cat, sub in [("3", "3.1"), ("2", "2.1"), ("4", "4.1")]:
            _upload(db_session, engagement, advisor, cat=cat, sub=sub)
        ids = _folder_ids(db_session, engagement)
        for cat in ("3", "2", "4"):
            assert fake_drive.folders[ids[(cat, None)]]["parent"] == ids[(None, None)]
            assert db_session.query(EngagementDriveFolder).filter(
                EngagementDriveFolder.drive_folder_id == ids[(cat, None)]
            ).count() == 1

    def test_d_same_category_in_same_named_engagements_is_two_folders(
        self, db_session, fake_drive, engagement, advisor
    ):
        other = _sibling(db_session, advisor)
        self._both_uploaded(db_session, engagement, other, advisor)
        a, b = _folder_ids(db_session, engagement), _folder_ids(db_session, other)
        assert a[("3", None)] != b[("3", None)]
        assert fake_drive.folders[a[("3", None)]]["parent"] == a[(None, None)]
        assert fake_drive.folders[b[("3", None)]]["parent"] == b[(None, None)]

    def test_e_a_file_dropped_in_drive_belongs_to_that_engagement_only(
        self, db_session, fake_drive, engagement, advisor
    ):
        other = _sibling(db_session, advisor)
        self._both_uploaded(db_session, engagement, other, advisor)
        folder_a = _folder_ids(db_session, engagement)[("3", "3.1")]
        get_drive_sync_service(db_session)._apply(
            TestSync()._change("dropped-in-a", "lease.pdf", folder_a), _no_result())
        db_session.flush()
        media = db_session.query(Media).filter(Media.drive_file_id == "dropped-in-a").one()
        assert media.engagement_id == engagement.id
        other_files = get_data_room_service(db_session).files_for_engagement(other.id)
        assert "dropped-in-a" not in {m.drive_file_id for m in other_files}

    def test_e_a_file_moved_to_another_engagement_follows_the_folder(
        self, db_session, fake_drive, engagement, advisor
    ):
        other = _sibling(db_session, advisor)
        self._both_uploaded(db_session, engagement, other, advisor)
        media = db_session.query(Media).filter(Media.engagement_id == engagement.id).first()
        media.drive_modified_time = datetime(2026, 9, 29, 10, 0)
        db_session.flush()
        folder_b = _folder_ids(db_session, other)[("3", "3.1")]
        get_drive_sync_service(db_session)._apply(
            TestSync()._change(media.drive_file_id, media.file_name, folder_b), _no_result())
        db_session.flush()
        assert media.engagement_id == other.id

    def test_f_a_release_on_one_engagement_never_reaches_the_other(
        self, db_session, fake_drive, engagement, advisor, make_user
    ):
        other = _sibling(db_session, advisor)
        self._both_uploaded(db_session, engagement, other, advisor)
        a_file = db_session.query(Media).filter(Media.engagement_id == engagement.id).first()
        db_session.add(EngagementReleasedFolder(engagement_id=engagement.id,
                                                category_code="3", sub_item_code="3.1"))
        db_session.flush()
        _, buyers = TestReleaseBoundary()._buyer(db_session, make_user, engagement)
        assert buyers.media_is_released(engagement.id, a_file.id) is True
        # Engagement B's buyers are resolved to B, and A's file is not B's.
        assert buyers.media_is_released(other.id, a_file.id) is False
        assert all(m.engagement_id == other.id
                   for m in buyers.documents_in_folder(other.id, "3", "3.1"))

    def test_a_folder_already_mapped_elsewhere_is_never_shared(
        self, db_session, fake_drive, engagement, advisor
    ):
        """A legacy shared mapping fails closed instead of filing into the wrong engagement."""
        from app.services.drive_folder_service import SharedDriveFolder, get_drive_folder_service

        other = _sibling(db_session, advisor)
        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor)
        shared = _folder_ids(db_session, engagement)[("3", "3.1")]
        with pytest.raises(SharedDriveFolder):
            get_drive_folder_service(db_session)._record(other.id, "3", "3.1", {"id": shared})

        db_session.add(EngagementDriveFolder(engagement_id=other.id, category_code="3",
                                             sub_item_code="3.1", drive_folder_id=shared))
        db_session.flush()
        with pytest.raises(SharedDriveFolder):
            get_drive_folder_service(db_session).folder_by_drive_id(shared)


# ======================================================================
# Sync: one bad file does not stall the feed
# ======================================================================
class TestSyncCursor:
    def _integration(self, db_session):
        row = db_session.query(DriveIntegration).filter(
            DriveIntegration.is_deleted == False,  # noqa: E712
        ).first()
        row.changes_page_token = "token-1"
        db_session.commit()  # the sync rolls back between retries; the cursor must survive that
        return row

    def test_an_unindexable_file_is_recorded_and_the_rest_still_sync(
        self, db_session, fake_drive, engagement, advisor
    ):
        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor)
        good_folder = _folder_ids(db_session, engagement)[("3", "3.1")]
        orphan = _sibling(db_session, advisor, business_name="No advisor", primary_advisor=False)
        db_session.add(EngagementDriveFolder(engagement_id=orphan.id, category_code="3",
                                             sub_item_code="3.1", drive_folder_id="folder-orphan"))
        db_session.flush()
        integration = self._integration(db_session)

        changes = [
            TestSync()._change("good-1", "first.pdf", good_folder),
            TestSync()._change("bad-1", "cannot attribute.pdf", "folder-orphan"),
            TestSync()._change("good-2", "second.pdf", good_folder),
        ]
        fake_drive.list_changes = lambda token: (changes, None, "token-2")
        result = get_drive_sync_service(db_session).sync()

        indexed = {m.drive_file_id for m in db_session.query(Media).filter(
            Media.drive_file_id.in_(["good-1", "bad-1", "good-2"]))}
        assert indexed == {"good-1", "good-2"}
        assert result.held is False
        assert integration.changes_page_token == "token-2"
        assert "bad-1" in integration.last_error

    def test_a_transient_failure_still_holds_the_cursor(
        self, db_session, fake_drive, engagement, advisor, monkeypatch
    ):
        from app.services import drive_sync_service as sync_module

        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor)
        integration = self._integration(db_session)
        folder = _folder_ids(db_session, engagement)[("3", "3.1")]
        fake_drive.list_changes = lambda token: (
            [TestSync()._change("flaky", "x.pdf", folder)], None, "token-2")

        def boom(self, change, result):
            raise RuntimeError("database is locked")
        monkeypatch.setattr(sync_module.DriveSyncService, "_apply", boom)

        result = get_drive_sync_service(db_session).sync()
        assert result.held is True
        assert integration.changes_page_token == "token-1"

    @pytest.mark.parametrize("name", [
        "Lease v2.final signed by both parties",  # "extension" longer than the column
        ("x" * 300) + ".pdf",                     # longer than media.file_name
    ])
    def test_awkward_drive_names_are_indexed(self, db_session, fake_drive, engagement, advisor, name):
        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor)
        folder = _folder_ids(db_session, engagement)[("3", "3.1")]
        get_drive_sync_service(db_session)._apply(
            TestSync()._change("awkward", name, folder), _no_result())
        db_session.flush()
        media = db_session.query(Media).filter(Media.drive_file_id == "awkward").one()
        assert len(media.file_name) <= 255
        assert media.file_extension is None or len(media.file_extension) <= 20

    def test_a_file_over_two_gigabytes_is_indexed_without_a_size(
        self, db_session, fake_drive, engagement, advisor
    ):
        _dd(db_session, engagement)
        _upload(db_session, engagement, advisor)
        folder = _folder_ids(db_session, engagement)[("3", "3.1")]
        change = TestSync()._change("huge", "video.mp4", folder)
        change["file"]["size"] = str(5 * 1024 ** 3)
        get_drive_sync_service(db_session)._apply(change, _no_result())
        db_session.flush()
        assert db_session.query(Media).filter(Media.drive_file_id == "huge").one().file_size is None


# ======================================================================
# Download file names survive the Content-Disposition header
# ======================================================================
AWKWARD_NAMES = [
    "Balance sheet FY26.pdf",               # English with spaces
    "مالیاتی گوشوارہ.pdf",                  # Urdu
    "财务报表 2026.pdf",                     # Chinese
    "決算書_最終版.pdf",                      # Japanese
    'Lease "final" copy.pdf',               # quotes
    "Q&A; notes, v2 (draft) #3 100%.pdf",   # special characters
    ("Very long name " * 16).strip() + ".pdf",  # ~250 characters
]


def _filename_from(header: str) -> str:
    from urllib.parse import unquote
    return unquote(header.split("filename*=UTF-8''", 1)[1])


@pytest.mark.parametrize("name", AWKWARD_NAMES)
def test_the_header_carries_the_exact_name(name):
    from app.utils.content_disposition import attachment

    header = attachment(name)
    header.encode("latin-1")  # what the server does; must not raise
    assert _filename_from(header) == name
    fallback = header.split('filename="', 1)[1].split('"', 1)[0]
    assert fallback and '"' not in fallback


@pytest.mark.parametrize("name", AWKWARD_NAMES)
def test_advisor_and_buyer_downloads_keep_the_name(
    api, db_session, fake_drive, engagement, advisor, make_user, name
):
    _dd(db_session, engagement)
    media = _upload(db_session, engagement, advisor)
    media.file_name = name
    db_session.add(EngagementReleasedFolder(engagement_id=engagement.id,
                                            category_code="3", sub_item_code="3.1"))
    db_session.flush()
    buyer, _ = TestReleaseBoundary()._buyer(db_session, make_user, engagement)

    for user, url in [
        (advisor, f"/api/sale-ready/engagements/{engagement.id}/data-room/files/{media.id}/download"),
        (buyer, f"/api/buyer/me/documents/{media.id}/download"),
    ]:
        resp = api.as_user(user).get(url)
        assert resp.status_code == 200, (url, resp.text)
        assert _filename_from(resp.headers["content-disposition"]) == name
        assert resp.content == b"pretend-bytes"


# ======================================================================
# Data room files never break the generic Media features
# ======================================================================
class TestGenericFilesAreUnaffected:
    def _local_file(self, db_session, engagement, user, tmp_path):
        path = tmp_path / "board_minutes.pdf"
        path.write_bytes(b"local-bytes")
        media = Media(user_id=user.id, engagement_id=engagement.id, file_name="board_minutes.pdf",
                      file_path=str(path), file_type="application/pdf", file_extension="pdf")
        db_session.add(media)
        db_session.flush()
        return media

    def test_engagement_files_stay_local_and_keep_working(
        self, api, db_session, fake_drive, engagement, advisor, tmp_path
    ):
        _dd(db_session, engagement)
        drive_file = _upload(db_session, engagement, advisor)
        local = self._local_file(db_session, engagement, advisor, tmp_path)
        client = api.as_user(advisor)
        base = f"/api/engagements/{engagement.id}/files"

        assert [f["id"] for f in client.get(base).json()] == [str(local.id)]
        resp = client.get(f"{base}/{local.id}/download")
        assert resp.status_code == 200 and resp.content == b"local-bytes"

        # A data room file is not the generic tab's to serve or delete.
        assert client.get(f"{base}/{drive_file.id}/download").status_code == 404
        assert client.delete(f"{base}/{drive_file.id}").status_code == 404
        db_session.refresh(drive_file)
        assert drive_file.deleted_at is None and fake_drive.trashed == []

        listed = client.get("/api/engagements").json()
        assert next(e for e in listed if e["id"] == str(engagement.id))["documents_count"] == 1

    def test_generic_file_delete_refuses_a_data_room_file(
        self, api, db_session, fake_drive, engagement, advisor
    ):
        _dd(db_session, engagement)
        drive_file = _upload(db_session, engagement, advisor)
        for hard in ("false", "true"):
            resp = api.as_user(advisor).delete(f"/api/files/{drive_file.id}?hard_delete={hard}")
            assert resp.status_code == 400
        db_session.refresh(drive_file)
        assert drive_file.deleted_at is None and fake_drive.trashed == []

    def test_super_admin_download_streams_a_data_room_file(
        self, api, db_session, fake_drive, engagement, advisor, make_user, tmp_path
    ):
        _dd(db_session, engagement)
        drive_file = _upload(db_session, engagement, advisor)
        local = self._local_file(db_session, engagement, advisor, tmp_path)
        client = api.as_user(make_user(UserRole.SUPER_ADMIN))
        resp = client.get(f"/api/users/{advisor.id}/files/{drive_file.id}/download")
        assert resp.status_code == 200 and resp.content == b"pretend-bytes"
        resp = client.get(f"/api/users/{advisor.id}/files/{local.id}/download")
        assert resp.status_code == 200 and resp.content == b"local-bytes"

    def test_offboarding_the_uploader_keeps_the_data_room_file(
        self, api, db_session, fake_drive, engagement, make_user, tmp_path
    ):
        uploader = make_user(UserRole.ADVISOR)  # not the primary, so the engagement survives
        _dd(db_session, engagement)
        drive_file = _upload(db_session, engagement, uploader)
        local = self._local_file(db_session, engagement, uploader, tmp_path)

        resp = api.as_user(make_user(UserRole.SUPER_ADMIN)).delete(f"/api/users/{uploader.id}")
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        assert db_session.query(Media).get(drive_file.id).deleted_at is None
        assert db_session.query(Media).get(local.id).deleted_at is not None


# ======================================================================
# Buyer: viewing a released document in the browser
# ======================================================================
class TestBuyerView:
    def _released(self, db_session, engagement, advisor, make_user, name="statements.pdf"):
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        media.file_name = name
        db_session.add(EngagementReleasedFolder(engagement_id=engagement.id,
                                                category_code="3", sub_item_code="3.1"))
        db_session.flush()
        buyer, _ = TestReleaseBoundary()._buyer(db_session, make_user, engagement)
        return media, buyer

    def test_a_released_pdf_opens_inline_through_trinity(
        self, api, db_session, fake_drive, engagement, advisor, make_user
    ):
        from app.models.buyer import BuyerAccessLog

        media, buyer = self._released(db_session, engagement, advisor, make_user)
        resp = api.as_user(buyer).get(f"/api/buyer/me/documents/{media.id}/view")
        assert resp.status_code == 200, resp.text
        assert resp.content == b"pretend-bytes"
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.headers["content-disposition"].startswith("inline;")
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["cache-control"] == "no-store"
        assert "drive" not in " ".join(resp.headers.values()).lower()

        logged = db_session.query(BuyerAccessLog).filter(
            BuyerAccessLog.media_id == media.id, BuyerAccessLog.user_id == buyer.id).all()
        assert [row.action for row in logged] == ["view"]

    @pytest.mark.parametrize("name,expected", [
        ("scan.png", "image/png"), ("photo.JPG", "image/jpeg"),
        ("notes.txt", "text/plain; charset=utf-8"), ("ledger.csv", "text/plain; charset=utf-8"),
    ])
    def test_images_and_text_open_inline(
        self, api, db_session, fake_drive, engagement, advisor, make_user, name, expected
    ):
        media, buyer = self._released(db_session, engagement, advisor, make_user, name=name)
        resp = api.as_user(buyer).get(f"/api/buyer/me/documents/{media.id}/view")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == expected

    @pytest.mark.parametrize("name", ["contract.docx", "model.xlsx", "bundle.zip", "page.html", "logo.svg"])
    def test_other_types_stay_download_only_and_are_not_logged(
        self, api, db_session, fake_drive, engagement, advisor, make_user, name
    ):
        from app.models.buyer import BuyerAccessLog

        media, buyer = self._released(db_session, engagement, advisor, make_user, name=name)
        assert api.as_user(buyer).get(f"/api/buyer/me/documents/{media.id}/view").status_code == 415
        assert db_session.query(BuyerAccessLog).filter(BuyerAccessLog.media_id == media.id).count() == 0
        assert api.as_user(buyer).get(f"/api/buyer/me/documents/{media.id}/download").status_code == 200

    def test_the_content_type_comes_from_the_extension_not_the_upload(
        self, api, db_session, fake_drive, engagement, advisor, make_user
    ):
        media, buyer = self._released(db_session, engagement, advisor, make_user)
        media.file_type = "text/html"
        db_session.flush()
        resp = api.as_user(buyer).get(f"/api/buyer/me/documents/{media.id}/view")
        assert resp.headers["content-type"] == "application/pdf"

    def test_the_folder_listing_says_what_can_be_viewed(
        self, api, db_session, fake_drive, engagement, advisor, make_user
    ):
        pdf, buyer = self._released(db_session, engagement, advisor, make_user)
        docx = _upload(db_session, engagement, advisor, name="contract.docx")
        docs = api.as_user(buyer).get("/api/buyer/me/folders/3/3.1").json()["documents"]
        viewable = {d["id"]: d["viewable"] for d in docs}
        assert viewable == {str(pdf.id): True, str(docx.id): False}

    def test_the_release_boundary_still_applies(
        self, api, db_session, fake_drive, engagement, advisor, make_user
    ):
        _dd(db_session, engagement)
        unreleased = _upload(db_session, engagement, advisor)
        buyer, _ = TestReleaseBoundary()._buyer(db_session, make_user, engagement)
        client = api.as_user(buyer)
        assert client.get(f"/api/buyer/me/documents/{unreleased.id}/view").status_code == 404

        other = _sibling(db_session, advisor)
        _dd(db_session, other, key="DD-OTHER")
        foreign = _upload(db_session, other, advisor, name="theirs.pdf")
        db_session.add(EngagementReleasedFolder(engagement_id=other.id,
                                                category_code="3", sub_item_code="3.1"))
        db_session.flush()
        assert client.get(f"/api/buyer/me/documents/{foreign.id}/view").status_code == 404

        # Soft-deleting the engagement closes viewing like every other portal route.
        db_session.add(EngagementReleasedFolder(engagement_id=engagement.id,
                                                category_code="3", sub_item_code="3.1"))
        engagement.is_deleted = True
        db_session.flush()
        assert client.get(f"/api/buyer/me/documents/{unreleased.id}/view").status_code == 403

    def test_only_a_buyer_can_use_the_view_route(
        self, api, db_session, fake_drive, engagement, advisor, make_user
    ):
        media, _ = self._released(db_session, engagement, advisor, make_user)
        assert api.as_user(advisor).get(f"/api/buyer/me/documents/{media.id}/view").status_code == 403


# ======================================================================
# Owner: the Sale Ready Files tab
# ======================================================================
class TestOwnerFiles:
    def _owner(self, db_session, engagement):
        from app.models.user import User
        return db_session.query(User).filter(User.id == engagement.client_ids[0]).one()

    def test_the_owner_reads_the_data_room_with_release_flags(
        self, api, db_session, fake_drive, engagement, advisor
    ):
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        db_session.add(EngagementReleasedFolder(engagement_id=engagement.id,
                                                category_code="3", sub_item_code="3.1"))
        db_session.flush()
        owner = self._owner(db_session, engagement)
        base = f"/api/sale-ready/engagements/{engagement.id}/data-room"

        resp = api.as_user(owner).get(base)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert [f["id"] for f in body["files"]] == [str(media.id)]
        folder = next(f for f in body["folders"] if f["sub_item_code"] == "3.1")
        assert folder["released_to_buyers"] is True and folder["file_count"] == 1

        download = api.as_user(owner).get(f"{base}/files/{media.id}/download")
        assert download.status_code == 200 and download.content == b"pretend-bytes"

    def test_the_owner_stays_read_only(self, api, db_session, fake_drive, engagement, advisor):
        _dd(db_session, engagement)
        media = _upload(db_session, engagement, advisor)
        owner = self._owner(db_session, engagement)
        client = api.as_user(owner)
        base = f"/api/sale-ready/engagements/{engagement.id}/data-room"

        # The advisor-only release list the tab no longer calls for owners.
        assert client.get(f"/api/engagements/{engagement.id}/released-folders").status_code == 403
        assert client.put(f"/api/engagements/{engagement.id}/released-folders",
                          json={"folders": []}).status_code == 403
        assert client.post(f"{base}/3/3.1/files",
                           files={"file": ("x.pdf", b"x", "application/pdf")}).status_code == 403
        assert client.patch(f"{base}/files/{media.id}", json={"file_name": "y.pdf"}).status_code == 403
        assert client.delete(f"{base}/files/{media.id}").status_code == 403
        assert fake_drive.trashed == [] and fake_drive.renamed == []

    def test_an_owner_of_another_engagement_is_refused(
        self, api, db_session, fake_drive, engagement, advisor, make_user
    ):
        stranger = make_user(UserRole.CLIENT)
        resp = api.as_user(stranger).get(f"/api/sale-ready/engagements/{engagement.id}/data-room")
        assert resp.status_code == 403


# ======================================================================
# Folder tree provisioning (H2/H5)
# ======================================================================
def _mapped(db_session, engagement):
    rows = db_session.query(EngagementDriveFolder).filter(
        EngagementDriveFolder.engagement_id == engagement.id,
    ).all()
    return {
        "root": sum(1 for r in rows if r.category_code is None),
        "categories": sum(1 for r in rows if r.category_code and r.sub_item_code is None),
        "sub_items": sum(1 for r in rows if r.sub_item_code),
    }


def _small_tree(db_session, engagement):
    _dd(db_session, engagement, cat="3", sub="3.1", key="DD-1")
    _dd(db_session, engagement, cat="3", sub="3.2", sub_name="Management Accounts", key="DD-2")
    _dd(db_session, engagement, cat="9", cat_name="Property", sub="9.1", sub_name="Leases", key="DD-3")


class TestProvisioning:
    def _service(self, db_session):
        from app.services.drive_folder_service import get_drive_folder_service
        return get_drive_folder_service(db_session)

    def test_the_full_tree_is_created_once(self, db_session, fake_drive, engagement):
        from app.models.sale_ready import ProgramStage
        from app.services.sale_ready_service import get_sale_ready_service

        if db_session.query(ProgramStage).filter_by(program_type="sale_ready").count() != 15:
            pytest.skip("Sale Ready templates are not seeded")
        get_sale_ready_service(db_session).ensure_initialized(engagement)

        created = self._service(db_session).provision_tree(engagement)

        assert _mapped(db_session, engagement) == {"root": 1, "categories": 16, "sub_items": 73}
        # Client folder + Data room + 16 categories + 73 sub-items.
        assert len(fake_drive.folders) == 91
        # The root counts once: its client-folder parent is not a mapped row.
        assert created == 90
        assert self._service(db_session).provision_tree(engagement) == 0
        assert len(fake_drive.folders) == 91

    def test_rerunning_creates_no_duplicates(self, db_session, fake_drive, engagement):
        _small_tree(db_session, engagement)
        service = self._service(db_session)
        service.provision_tree(engagement)
        before = dict(fake_drive.folders)
        assert service.provision_tree(engagement) == 0
        assert fake_drive.folders == before
        assert _mapped(db_session, engagement) == {"root": 1, "categories": 2, "sub_items": 3}

    def test_a_lost_category_row_is_adopted_not_duplicated(self, db_session, fake_drive, engagement):
        """An interrupted pass loses its uncommitted rows; the next adopts the folders by name."""
        _small_tree(db_session, engagement)
        service = self._service(db_session)
        service.provision_tree(engagement)
        before = len(fake_drive.folders)
        db_session.query(EngagementDriveFolder).filter(
            EngagementDriveFolder.engagement_id == engagement.id,
            EngagementDriveFolder.category_code == "3",
        ).delete()
        db_session.flush()

        service.provision_tree(engagement)
        assert len(fake_drive.folders) == before
        assert _mapped(db_session, engagement) == {"root": 1, "categories": 2, "sub_items": 3}

    def test_a_file_dropped_into_a_never_uploaded_folder_is_picked_up(
        self, db_session, fake_drive, engagement, monkeypatch
    ):
        from app.services.drive_folder_service import get_integration

        _small_tree(db_session, engagement)
        self._service(db_session).provision_tree(engagement)
        folder = db_session.query(EngagementDriveFolder).filter_by(
            engagement_id=engagement.id, sub_item_code="9.1").one()
        assert db_session.query(Media).filter(Media.engagement_id == engagement.id).count() == 0

        get_integration(db_session).changes_page_token = "cursor"
        db_session.flush()
        change = TestSync()._change("dropped-1", "lease.pdf", folder.drive_folder_id)
        monkeypatch.setattr(fake_drive, "list_changes", lambda token: ([change], None, "cursor-2"))
        result = get_drive_sync_service(db_session).sync()

        assert result.added == 1
        media = db_session.query(Media).filter(Media.drive_file_id == "dropped-1").one()
        assert (media.engagement_id, media.dd_sub_item_code, media.source) == (engagement.id, "9.1", "drive")

    def test_pending_lists_incomplete_trees_only(self, db_session, fake_drive, engagement):
        from app.services.drive_folder_service import pending_engagements

        _small_tree(db_session, engagement)
        assert engagement.id in {e.id for e in pending_engagements(db_session)}
        self._service(db_session).provision_tree(engagement)
        assert engagement.id not in {e.id for e in pending_engagements(db_session)}

    def test_a_pass_provisions_at_most_the_batch(
        self, db_session, fake_drive, engagement, advisor, monkeypatch
    ):
        from app.services import drive_folder_service

        engagements = []
        for i in range(7):
            eng = Engagement(engagement_name=f"Batch {i}", business_name=f"Batch {i}",
                             primary_advisor_id=advisor.id, tool="sale_ready", status="active")
            db_session.add(eng)
            db_session.flush()
            _dd(db_session, eng, key=f"DD-B{i}")
            engagements.append(eng)
        monkeypatch.setattr(drive_folder_service, "pending_engagements", lambda db: engagements)

        result = drive_folder_service.provision_pending(db_session, limit=5)

        # Per engagement: data room root, one category, one sub-item.
        assert result == {"provisioned": 5, "pending": 7, "folders_created": 5 * 3,
                          "failed": [], "backing_off": 0}
        assert [_mapped(db_session, e)["sub_items"] for e in engagements] == [1, 1, 1, 1, 1, 0, 0]

    def test_throttling_ends_the_pass_and_is_raised(
        self, db_session, fake_drive, engagement, monkeypatch
    ):
        from app.services import drive_folder_service
        from app.services.drive_client import DriveRateLimited

        _small_tree(db_session, engagement)
        monkeypatch.setattr(drive_folder_service, "pending_engagements", lambda db: [engagement])

        def throttled(name, parent_id):
            raise DriveRateLimited("slow down")
        monkeypatch.setattr(fake_drive, "create_folder", throttled)

        with pytest.raises(DriveRateLimited):
            drive_folder_service.provision_pending(db_session)

    def test_one_broken_engagement_does_not_stop_the_rest(
        self, db_session, fake_drive, engagement, advisor, monkeypatch
    ):
        from app.services import drive_folder_service

        other = Engagement(engagement_name="Other", business_name="Other",
                           primary_advisor_id=advisor.id, tool="sale_ready", status="active")
        db_session.add(other)
        db_session.flush()
        _dd(db_session, other, key="DD-O")
        _small_tree(db_session, engagement)
        monkeypatch.setattr(drive_folder_service, "pending_engagements",
                            lambda db: [engagement, other])
        real = drive_folder_service.DriveFolderService.provision_tree

        def flaky(self, eng, client=None):
            if eng.id == engagement.id:
                raise ValueError("boom")
            return real(self, eng, client=client)
        monkeypatch.setattr(drive_folder_service.DriveFolderService, "provision_tree", flaky)
        # The failure path rolls back; commit the setup so only the failed work is lost.
        db_session.commit()

        result = drive_folder_service.provision_pending(db_session)
        assert result["provisioned"] == 1
        assert _mapped(db_session, other)["sub_items"] == 1


# ======================================================================
# The provisioning queue: failures back off instead of blocking (audit C1)
# ======================================================================
def _queue(db_session, advisor, n, created=None):
    """n Sale Ready engagements with one DD folder each, oldest first."""
    base = created or datetime(2001, 1, 1)
    out = []
    for i in range(n):
        eng = Engagement(engagement_name=f"Queue {i}", business_name=f"Queue {i}",
                         primary_advisor_id=advisor.id, tool="sale_ready", status="active",
                         created_at=base + timedelta(days=i))
        db_session.add(eng)
        db_session.flush()
        _dd(db_session, eng, key=f"DD-Q{i}")
        out.append(eng)
    db_session.commit()  # failures roll back to here, not to an empty session
    return out


class TestProvisioningQueue:
    T0 = datetime(2026, 10, 1, 9, 0, 0)

    @pytest.fixture
    def queue(self, db_session, fake_drive, engagement, advisor, monkeypatch):
        from app.services import drive_folder_service

        engagements = _queue(db_session, advisor, 6)
        monkeypatch.setattr(
            drive_folder_service, "pending_engagements",
            lambda db: [e for e in engagements if _mapped(db_session, e)["sub_items"] == 0],
        )
        return engagements

    def _failing_for(self, monkeypatch, bad_ids, exc_factory):
        from app.services import drive_folder_service

        real = drive_folder_service.DriveFolderService.provision_tree
        attempts = []

        def provision(self, eng, client=None):
            attempts.append(eng.id)
            if eng.id in bad_ids:
                raise exc_factory()
            return real(self, eng, client=client)
        monkeypatch.setattr(drive_folder_service.DriveFolderService, "provision_tree", provision)
        return attempts

    def test_a_failing_old_engagement_does_not_block_newer_ones(self, db_session, queue, monkeypatch):
        from app.services.drive_folder_service import provision_pending

        oldest = queue[0]
        attempts = self._failing_for(monkeypatch, {oldest.id}, lambda: ValueError("broken"))

        first = provision_pending(db_session, limit=5, now=self.T0)
        assert first["provisioned"] == 4 and first["failed"] == [str(oldest.id)]

        # Next pass: the failing engagement is backing off and takes no slot.
        attempts.clear()
        second = provision_pending(db_session, limit=5, now=self.T0 + timedelta(seconds=1))
        assert attempts == [queue[5].id]
        assert second["provisioned"] == 1 and second["backing_off"] == 1
        assert _mapped(db_session, queue[5])["sub_items"] == 1

    def test_backoff_expires_and_the_engagement_is_retried(self, db_session, queue, monkeypatch):
        from app.services.drive_folder_service import provision_backoff_seconds, provision_pending

        oldest = queue[0]
        attempts = self._failing_for(monkeypatch, {oldest.id}, lambda: ValueError("broken"))
        provision_pending(db_session, limit=1, now=self.T0)
        wait = provision_backoff_seconds(1)

        attempts.clear()
        provision_pending(db_session, limit=1, now=self.T0 + timedelta(seconds=wait - 1))
        assert oldest.id not in attempts

        attempts.clear()
        provision_pending(db_session, limit=1, now=self.T0 + timedelta(seconds=wait + 1))
        assert attempts == [oldest.id]

    def test_a_success_clears_the_failure_record(self, db_session, queue, monkeypatch):
        from app.services import drive_folder_service as dfs

        oldest = queue[0]
        bad = {oldest.id}
        attempts = self._failing_for(monkeypatch, bad, lambda: ValueError("broken"))
        dfs.provision_pending(db_session, limit=1, now=self.T0)
        assert dfs._is_backing_off(oldest.id, self.T0)

        bad.clear()  # fixed; retried once the wait is over
        later = self.T0 + timedelta(seconds=dfs.provision_backoff_seconds(1) + 1)
        result = dfs.provision_pending(db_session, limit=1, now=later)
        assert result["provisioned"] == 1 and attempts[-1] == oldest.id
        assert oldest.id not in dfs._provision_failures

    def test_a_missing_folder_skips_one_engagement_not_the_pass(self, db_session, queue, monkeypatch):
        from app.services.drive_client import DriveNotFound
        from app.services.drive_folder_service import provision_pending

        oldest = queue[0]
        self._failing_for(monkeypatch, {oldest.id},
                          lambda: DriveNotFound("That file or folder no longer exists in Drive."))
        result = provision_pending(db_session, limit=3, now=self.T0)
        assert result["failed"] == [str(oldest.id)] and result["provisioned"] == 2

    @pytest.mark.parametrize("error", ["unavailable", "transient", "rate_limited"])
    def test_a_connection_failure_still_ends_the_pass(self, db_session, queue, monkeypatch, error):
        from app.services import drive_folder_service as dfs
        from app.services.drive_client import DriveRateLimited, DriveTransient, DriveUnavailable

        exc = {"unavailable": DriveUnavailable, "transient": DriveTransient,
               "rate_limited": DriveRateLimited}[error]
        oldest = queue[0]
        attempts = self._failing_for(monkeypatch, {oldest.id}, lambda: exc("connection trouble"))

        with pytest.raises(DriveUnavailable):
            dfs.provision_pending(db_session, limit=5, now=self.T0)
        assert attempts == [oldest.id]
        # Not the engagement's fault, so it is not backed off.
        assert not dfs._is_backing_off(oldest.id, self.T0)

    def test_an_unexpected_error_is_logged_with_its_traceback(self, db_session, queue, monkeypatch, caplog):
        import logging

        from app.services.drive_folder_service import provision_pending

        oldest = queue[0]
        self._failing_for(monkeypatch, {oldest.id}, lambda: RuntimeError("kaboom"))
        with caplog.at_level(logging.ERROR, logger="app.services.drive_folder_service"):
            provision_pending(db_session, limit=1, now=self.T0)
        record = next(r for r in caplog.records if str(oldest.id) in r.getMessage())
        assert record.levelno == logging.ERROR and record.exc_info is not None
        assert "kaboom" in str(record.exc_info[1])

    def test_the_backoff_doubles_and_is_capped(self, monkeypatch):
        from app.services import drive_folder_service as dfs

        monkeypatch.setattr(dfs.settings, "GOOGLE_DRIVE_SYNC_INTERVAL_SECONDS", 300)
        assert [dfs.provision_backoff_seconds(n) for n in (1, 2, 3)] == [300, 600, 1200]
        assert dfs.provision_backoff_seconds(50) == dfs.PROVISION_BACKOFF_MAX_SECONDS

    def test_a_404_from_drive_is_classified_as_not_found(self):
        from googleapiclient.errors import HttpError

        from app.services.drive_client import DriveClient, DriveNotFound

        resp = type("R", (), {"status": 404, "reason": "x"})()

        class Failing:
            def execute(self):
                raise HttpError(resp, b"{}")

        with pytest.raises(DriveNotFound):
            DriveClient._call(Failing())

    def test_pending_is_oldest_first_by_creation_not_insertion(self, db_session, fake_drive, advisor):
        from app.services.drive_folder_service import pending_engagements

        # Inserted newest first, so insertion order and creation order disagree.
        made = []
        for year in (2003, 2001, 2002):
            made += _queue(db_session, advisor, 1, created=datetime(year, 1, 1))
        ours = {e.id for e in made}
        order = [e.id for e in pending_engagements(db_session) if e.id in ours]
        assert order == [e.id for e in sorted(made, key=lambda e: e.created_at)]


# ======================================================================
# The data room is pinned to one Google account (H1)
# ======================================================================
class TestDriveAccountPin:
    EXPECTED = "benchmark@example.test"

    @pytest.fixture(autouse=True)
    def _pin(self, monkeypatch):
        monkeypatch.setattr(settings, "GOOGLE_DRIVE_EXPECTED_ACCOUNT", self.EXPECTED)

    def _callback(self, api, admin, monkeypatch, account_email):
        import app.api.drive_admin as drive_admin

        monkeypatch.setattr(drive_admin, "exchange_code", lambda code: ("refresh-token", account_email))
        monkeypatch.setattr(drive_admin, "encrypt_token", lambda raw: f"enc:{raw}")
        return api.as_user(admin).get(
            "/api/drive/callback",
            params={"state": drive_admin._issue_state(), "code": "abc"},
            follow_redirects=False,
        )

    def test_the_wrong_account_is_refused_and_nothing_is_stored(
        self, api, db_session, make_user, monkeypatch
    ):
        from app.services.drive_folder_service import get_integration

        before = get_integration(db_session)
        snapshot = (before.account_email, before.refresh_token) if before else None

        resp = self._callback(api, make_user(UserRole.ADMIN), monkeypatch, "someone@else.test")

        assert resp.status_code == 400
        assert self.EXPECTED in resp.json()["detail"] and "someone@else.test" in resp.json()["detail"]
        after = get_integration(db_session)
        assert (after.account_email, after.refresh_token) == snapshot if after else snapshot is None

    def test_an_unreadable_account_email_is_refused(self, api, db_session, make_user, monkeypatch):
        resp = self._callback(api, make_user(UserRole.ADMIN), monkeypatch, None)
        assert resp.status_code == 400

    def test_the_expected_account_connects_whatever_its_case(self, api, db_session, make_user, monkeypatch):
        from app.services.drive_folder_service import get_integration

        resp = self._callback(api, make_user(UserRole.ADMIN), monkeypatch, "Benchmark@Example.TEST")

        assert resp.status_code in (302, 307), resp.text
        integration = get_integration(db_session)
        assert integration.status == "connected" and integration.refresh_token == "enc:refresh-token"

    def test_no_pin_accepts_any_account(self, api, db_session, make_user, monkeypatch):
        monkeypatch.setattr(settings, "GOOGLE_DRIVE_EXPECTED_ACCOUNT", "")
        resp = self._callback(api, make_user(UserRole.ADMIN), monkeypatch, "dev@localhost.test")
        assert resp.status_code in (302, 307)

    def test_an_existing_wrong_connection_pauses_writes_but_not_downloads(
        self, api, db_session, fake_drive, engagement, advisor, make_user
    ):
        from app.services.drive_folder_service import get_integration

        _dd(db_session, engagement)
        get_integration(db_session).account_email = self.EXPECTED
        media = _upload(db_session, engagement, advisor)
        get_integration(db_session).account_email = "someone@else.test"
        db_session.flush()
        base = f"/api/sale-ready/engagements/{engagement.id}/data-room"
        client = api.as_user(advisor)
        files_before = dict(fake_drive.files)

        upload = client.post(f"{base}/3/3.1/files", files={"file": ("x.pdf", b"x", "application/pdf")})
        assert upload.status_code == 503 and "someone@else.test" in upload.json()["detail"]
        assert client.patch(f"{base}/files/{media.id}", json={"file_name": "y.pdf"}).status_code == 503
        assert client.delete(f"{base}/files/{media.id}").status_code == 503
        assert fake_drive.files == files_before and fake_drive.trashed == [] and fake_drive.renamed == []

        download = client.get(f"{base}/files/{media.id}/download")
        assert download.status_code == 200

        status = api.as_user(make_user(UserRole.ADMIN)).get("/api/drive/status").json()
        assert status["account_mismatch"] is True and status["expected_account"] == self.EXPECTED

    def test_provisioning_refuses_the_wrong_account(self, db_session, fake_drive, engagement, monkeypatch):
        from app.services import drive_folder_service

        _small_tree(db_session, engagement)
        drive_folder_service.get_integration(db_session).account_email = "someone@else.test"
        db_session.flush()
        monkeypatch.setattr(drive_folder_service, "pending_engagements", lambda db: [engagement])

        with pytest.raises(drive_folder_service.DriveAccountMismatch):
            drive_folder_service.provision_pending(db_session)
        assert fake_drive.folders == {}
