"""
Integration tests for ProgramDeliverableService mutations.

These hit a real Postgres because the behaviour under test IS database
behaviour: lazy materialization, the unique constraint that stops duplicate
preset instances, and boolean server defaults that SQLite gets wrong. Nothing
is ever committed - see the db_session fixture in conftest.py.

Run with: pytest tests/test_program_deliverable_mutations.py -v
"""
import uuid

import pytest

from app.models.program_deliverable import EngagementModuleDeliverable, ProgramModuleDeliverable
from app.services.program_deliverable_service import (
    MODULE_STATUS_COMPLETED,
    MODULE_STATUS_NOT_STARTED,
    get_program_deliverable_service,
)


@pytest.fixture
def service(db_session):
    return get_program_deliverable_service(db_session)


@pytest.fixture
def make_preset(db_session):
    """Create a library preset. Defaults to the engagement's own program type."""
    def _make(module_code="V1", key=None, is_mandatory=True, is_active=True, program_type="value_builder"):
        preset = ProgramModuleDeliverable(
            program_type=program_type,
            module_code=module_code,
            deliverable_key=key or f"key-{uuid.uuid4()}",
            title="Preset deliverable",
            is_mandatory=is_mandatory,
            display_order=1,
            is_active=is_active,
        )
        db_session.add(preset)
        db_session.flush()
        return preset
    return _make


def _instances(db_session, engagement, include_deleted=False):
    q = db_session.query(EngagementModuleDeliverable).filter(
        EngagementModuleDeliverable.engagement_id == engagement.id
    )
    if not include_deleted:
        q = q.filter(EngagementModuleDeliverable.is_deleted == False)  # noqa: E712
    return q.all()


# ==================== LAZY MATERIALIZATION ====================

class TestMaterialization:

    def test_completing_a_preset_creates_an_instance(self, service, db_session, test_engagement, test_user, make_preset):
        preset = make_preset()
        assert _instances(db_session, test_engagement) == []

        row = service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)

        assert row is not None
        assert row.library_deliverable_id == preset.id
        assert row.is_complete is True
        assert len(_instances(db_session, test_engagement)) == 1

    def test_materialized_row_leaves_advisor_fields_null(self, service, test_engagement, test_user, make_preset):
        """Presets read title/description/is_mandatory live from the library."""
        preset = make_preset()
        row = service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)

        assert row.title is None
        assert row.description is None
        assert row.is_mandatory is None

    def test_materialized_module_code_comes_from_the_library(self, service, test_engagement, test_user, make_preset):
        preset = make_preset(module_code="V7")
        row = service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)
        assert row.module_code == "V7"

    def test_second_mutation_updates_rather_than_duplicating(self, service, db_session, test_engagement, test_user, make_preset):
        preset = make_preset()
        first = service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)
        second = service.set_deliverable_scope(test_engagement, preset.id, False, test_user.id)

        assert second.id == first.id
        assert len(_instances(db_session, test_engagement)) == 1

    def test_uncompleting_an_unmaterialized_preset_is_a_noop(self, service, db_session, test_engagement, test_user, make_preset):
        """An absent row already means incomplete, so nothing is recorded."""
        preset = make_preset()
        result = service.set_deliverable_complete(test_engagement, preset.id, False, test_user.id)

        assert result is None
        assert _instances(db_session, test_engagement) == []

    def test_scoping_in_an_unmaterialized_preset_is_a_noop(self, service, db_session, test_engagement, test_user, make_preset):
        preset = make_preset()
        result = service.set_deliverable_scope(test_engagement, preset.id, True, test_user.id)

        assert result is None
        assert _instances(db_session, test_engagement) == []


# ==================== SCOPE / COMPLETION ORTHOGONALITY ====================

class TestScopeAndCompletionAreIndependent:
    """The whole reason is_in_scope and is_complete are separate columns."""

    def test_scoping_out_preserves_completion(self, service, test_engagement, test_user, make_preset):
        preset = make_preset()
        service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)

        row = service.set_deliverable_scope(test_engagement, preset.id, False, test_user.id)

        assert row.is_in_scope is False
        assert row.is_complete is True
        assert row.completed_at is not None

    def test_scoping_back_in_still_preserves_completion(self, service, test_engagement, test_user, make_preset):
        preset = make_preset()
        service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)
        service.set_deliverable_scope(test_engagement, preset.id, False, test_user.id)

        row = service.set_deliverable_scope(test_engagement, preset.id, True, test_user.id)

        assert row.is_in_scope is True
        assert row.is_complete is True
        assert row.completed_by_user_id == test_user.id

    def test_scoping_back_in_clears_the_scope_stamps(self, service, test_engagement, test_user, make_preset):
        preset = make_preset()
        service.set_deliverable_scope(test_engagement, preset.id, False, test_user.id)
        row = service.set_deliverable_scope(test_engagement, preset.id, True, test_user.id)

        assert row.scoped_out_by_user_id is None
        assert row.scoped_out_at is None

    def test_uncompleting_clears_both_completion_stamps(self, service, test_engagement, test_user, make_preset):
        preset = make_preset()
        service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)

        row = service.set_deliverable_complete(test_engagement, preset.id, False, test_user.id)

        assert row.is_complete is False
        assert row.completed_by_user_id is None
        assert row.completed_at is None

    def test_completing_does_not_touch_scope(self, service, test_engagement, test_user, make_preset):
        preset = make_preset()
        service.set_deliverable_scope(test_engagement, preset.id, False, test_user.id)

        row = service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)

        assert row.is_in_scope is False
        assert row.scoped_out_by_user_id == test_user.id


# ==================== RESOLUTION ====================

class TestResolution:

    def test_unknown_id_raises(self, service, test_engagement, test_user):
        with pytest.raises(ValueError, match="not found"):
            service.set_deliverable_complete(test_engagement, uuid.uuid4(), True, test_user.id)

    def test_retired_preset_is_not_resolvable(self, service, test_engagement, test_user, make_preset):
        """A retired preset is invisible to the status query, so state written against it is unreadable."""
        preset = make_preset(is_active=False)
        with pytest.raises(ValueError, match="not found"):
            service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)

    def test_preset_from_another_program_is_not_resolvable(self, service, test_engagement, test_user, make_preset):
        preset = make_preset(program_type="sale_ready")
        with pytest.raises(ValueError, match="not found"):
            service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)

    def test_materialized_preset_is_addressable_by_instance_id(self, service, test_engagement, test_user, make_preset):
        preset = make_preset()
        row = service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)

        same = service.set_deliverable_scope(test_engagement, row.id, False, test_user.id)
        assert same.id == row.id


# ==================== ADVISOR-ADDED ====================

class TestAddAdvisorDeliverable:

    def test_creates_an_advisor_row(self, service, test_engagement, test_user):
        row = service.add_advisor_deliverable(
            test_engagement, module_code="V2", title="Custom deliverable",
            is_mandatory=True, user_id=test_user.id,
        )
        assert row.library_deliverable_id is None
        assert row.title == "Custom deliverable"
        assert row.is_mandatory is True
        assert row.created_by_user_id == test_user.id
        assert row.is_complete is False
        assert row.is_in_scope is True
        assert row.is_deleted is False

    def test_missing_title_raises(self, service, test_engagement, test_user):
        with pytest.raises(ValueError, match="require a title"):
            service.add_advisor_deliverable(
                test_engagement, module_code="V2", title=None,
                is_mandatory=True, user_id=test_user.id,
            )

    def test_blank_title_raises(self, service, test_engagement, test_user):
        with pytest.raises(ValueError, match="require a title"):
            service.add_advisor_deliverable(
                test_engagement, module_code="V2", title="   ",
                is_mandatory=True, user_id=test_user.id,
            )

    def test_missing_is_mandatory_raises(self, service, test_engagement, test_user):
        with pytest.raises(ValueError, match="require is_mandatory"):
            service.add_advisor_deliverable(
                test_engagement, module_code="V2", title="Custom",
                is_mandatory=None, user_id=test_user.id,
            )

    def test_multiple_advisor_rows_allowed_on_same_module(self, service, db_session, test_engagement, test_user):
        """The unique constraint only binds preset instances - NULLs are distinct."""
        for n in range(3):
            service.add_advisor_deliverable(
                test_engagement, module_code="V2", title=f"Custom {n}",
                is_mandatory=False, user_id=test_user.id,
            )
        assert len(_instances(db_session, test_engagement)) == 3


class TestUpdateAdvisorDeliverable:

    def test_updates_only_provided_fields(self, service, test_engagement, test_user):
        row = service.add_advisor_deliverable(
            test_engagement, module_code="V2", title="Original",
            is_mandatory=True, user_id=test_user.id, description="desc",
        )
        updated = service.update_advisor_deliverable(test_engagement, row.id, title="Renamed")

        assert updated.title == "Renamed"
        assert updated.description == "desc"
        assert updated.is_mandatory is True

    def test_updating_a_preset_raises(self, service, test_engagement, test_user, make_preset):
        preset = make_preset()
        row = service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)

        with pytest.raises(ValueError, match="Cannot edit a preset deliverable"):
            service.update_advisor_deliverable(test_engagement, row.id, title="Nope")

    def test_explicit_none_title_raises(self, service, test_engagement, test_user):
        row = service.add_advisor_deliverable(
            test_engagement, module_code="V2", title="Original",
            is_mandatory=True, user_id=test_user.id,
        )
        with pytest.raises(ValueError, match="require a title"):
            service.update_advisor_deliverable(test_engagement, row.id, title=None)

    def test_unknown_field_raises(self, service, test_engagement, test_user):
        row = service.add_advisor_deliverable(
            test_engagement, module_code="V2", title="Original",
            is_mandatory=True, user_id=test_user.id,
        )
        with pytest.raises(ValueError, match="Cannot update"):
            service.update_advisor_deliverable(test_engagement, row.id, is_complete=True)

    def test_updating_a_soft_deleted_row_raises(self, service, test_engagement, test_user):
        row = service.add_advisor_deliverable(
            test_engagement, module_code="V2", title="Original",
            is_mandatory=True, user_id=test_user.id,
        )
        service.remove_advisor_deliverable(test_engagement, row.id)

        with pytest.raises(ValueError, match="not found"):
            service.update_advisor_deliverable(test_engagement, row.id, title="Nope")


class TestRemoveAdvisorDeliverable:

    def test_soft_deletes_an_advisor_row(self, service, db_session, test_engagement, test_user):
        row = service.add_advisor_deliverable(
            test_engagement, module_code="V2", title="Custom",
            is_mandatory=True, user_id=test_user.id,
        )
        removed = service.remove_advisor_deliverable(test_engagement, row.id)

        assert removed.is_deleted is True
        assert _instances(db_session, test_engagement) == []
        assert len(_instances(db_session, test_engagement, include_deleted=True)) == 1

    def test_deleting_a_preset_raises(self, service, test_engagement, test_user, make_preset):
        preset = make_preset()
        row = service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)

        with pytest.raises(ValueError, match="Cannot delete a preset deliverable"):
            service.remove_advisor_deliverable(test_engagement, row.id)

    def test_preset_survives_a_failed_delete(self, service, db_session, test_engagement, test_user, make_preset):
        preset = make_preset()
        row = service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)

        with pytest.raises(ValueError):
            service.remove_advisor_deliverable(test_engagement, row.id)

        db_session.refresh(row)
        assert row.is_deleted is False
        assert row.is_complete is True

    def test_deleting_twice_raises(self, service, test_engagement, test_user):
        row = service.add_advisor_deliverable(
            test_engagement, module_code="V2", title="Custom",
            is_mandatory=True, user_id=test_user.id,
        )
        service.remove_advisor_deliverable(test_engagement, row.id)

        with pytest.raises(ValueError, match="not found"):
            service.remove_advisor_deliverable(test_engagement, row.id)


# ==================== END TO END ====================

class TestStatusReflectsMutations:
    """The mutations and the prior layer's status query agree."""

    def test_completing_the_only_mandatory_completes_the_module(self, service, test_engagement, test_user, make_preset):
        preset = make_preset(module_code="V9")
        assert service.get_module_statuses(test_engagement)["V9"] == MODULE_STATUS_NOT_STARTED

        service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)

        assert service.get_module_statuses(test_engagement)["V9"] == MODULE_STATUS_COMPLETED

    def test_scoping_out_the_only_mandatory_completes_the_module(self, service, test_engagement, test_user, make_preset):
        preset = make_preset(module_code="V10")
        service.set_deliverable_scope(test_engagement, preset.id, False, test_user.id)

        assert service.get_module_statuses(test_engagement)["V10"] == MODULE_STATUS_COMPLETED

    def test_removed_advisor_deliverable_leaves_the_status_calculation(self, service, test_engagement, test_user):
        row = service.add_advisor_deliverable(
            test_engagement, module_code="V11", title="Custom",
            is_mandatory=True, user_id=test_user.id,
        )
        assert service.get_module_statuses(test_engagement)["V11"] == MODULE_STATUS_NOT_STARTED

        service.remove_advisor_deliverable(test_engagement, row.id)

        assert "V11" not in service.get_module_statuses(test_engagement)
