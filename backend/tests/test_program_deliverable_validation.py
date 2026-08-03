"""
Unit tests for the deliverable invariant validators.

Pure functions, no database - these are the rules that keep malformed rows out
of engagement_module_deliverable, and they can all be exercised by passing
plain values.

Run with: pytest tests/test_program_deliverable_validation.py -v
"""
import uuid

import pytest

from app.services.program_deliverable_service import (
    assert_advisor_added,
    normalize_advisor_title,
    normalize_module_code,
    validate_advisor_mandatory,
)


class TestNormalizeAdvisorTitle:
    """Advisor-added deliverables must carry a title."""

    def test_returns_title_unchanged(self):
        assert normalize_advisor_title("Financial Health Summary") == "Financial Health Summary"

    def test_strips_surrounding_whitespace(self):
        assert normalize_advisor_title("  Pricing Review  ") == "Pricing Review"

    def test_none_raises(self):
        with pytest.raises(ValueError, match="require a title"):
            normalize_advisor_title(None)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="require a title"):
            normalize_advisor_title("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="require a title"):
            normalize_advisor_title("   \t\n  ")


class TestValidateAdvisorMandatory:
    """
    Advisor-added rows have no library row to inherit is_mandatory from, so a
    NULL here is exactly what the status query has to COALESCE around.
    """

    def test_true_passes(self):
        assert validate_advisor_mandatory(True) is True

    def test_false_passes(self):
        assert validate_advisor_mandatory(False) is False

    def test_none_raises(self):
        with pytest.raises(ValueError, match="require is_mandatory"):
            validate_advisor_mandatory(None)


class TestNormalizeModuleCode:
    def test_returns_code_unchanged(self):
        assert normalize_module_code("V1") == "V1"

    def test_strips_surrounding_whitespace(self):
        assert normalize_module_code("  M12 ") == "M12"

    def test_none_raises(self):
        with pytest.raises(ValueError, match="require a module_code"):
            normalize_module_code(None)

    def test_blank_raises(self):
        with pytest.raises(ValueError, match="require a module_code"):
            normalize_module_code("  ")


class TestAssertAdvisorAdded:
    """The guard that makes presets undeletable and uneditable per engagement."""

    def test_null_library_id_is_advisor_added_and_passes(self):
        assert assert_advisor_added(None, "delete") is None

    def test_preset_raises_on_delete(self):
        with pytest.raises(ValueError, match="Cannot delete a preset deliverable"):
            assert_advisor_added(uuid.uuid4(), "delete")

    def test_preset_raises_on_edit(self):
        with pytest.raises(ValueError, match="Cannot edit a preset deliverable"):
            assert_advisor_added(uuid.uuid4(), "edit")

    def test_error_points_at_scoping_out_instead(self):
        with pytest.raises(ValueError, match="scope it out instead"):
            assert_advisor_added(uuid.uuid4(), "delete")
