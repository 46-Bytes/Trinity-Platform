"""
Unit tests for derive_module_status().

Pure function, no database - every case is built by constructing
DeliverableState tuples directly.

Run with: pytest tests/test_program_deliverable_status.py -v
"""
from app.services.program_deliverable_service import (
    DeliverableState,
    derive_module_status,
    MODULE_STATUS_NOT_STARTED,
    MODULE_STATUS_IN_PROGRESS,
    MODULE_STATUS_COMPLETED,
)


def _s(mandatory: bool, in_scope: bool = True, complete: bool = False) -> DeliverableState:
    """Terse constructor - defaults are 'untouched': in scope, incomplete."""
    return DeliverableState(mandatory=mandatory, in_scope=in_scope, complete=complete)


def _mandatory(**kwargs) -> DeliverableState:
    return _s(True, **kwargs)


def _optional(**kwargs) -> DeliverableState:
    return _s(False, **kwargs)


# ==================== NOT STARTED ====================

class TestNotStarted:
    """Cases where no deliverable has been completed and nothing is finished."""

    def test_empty_module(self):
        assert derive_module_status([]) == MODULE_STATUS_NOT_STARTED

    def test_deliverables_exist_but_none_touched(self):
        states = [_mandatory(), _mandatory(), _optional()]
        assert derive_module_status(states) == MODULE_STATUS_NOT_STARTED

    def test_zero_mandatory_module_nothing_touched(self):
        """
        Regression test for the any_acted_on guard.

        outstanding_mandatory is 0 here because there are no mandatory items at
        all. Without the any_acted_on condition this module would vacuously
        report completed despite nobody having done anything.
        """
        states = [_optional(), _optional()]
        assert derive_module_status(states) == MODULE_STATUS_NOT_STARTED

    def test_scoping_out_an_optional_is_not_progress(self):
        """Mandatory work still outstanding and nothing completed."""
        states = [_mandatory(), _optional(in_scope=False)]
        assert derive_module_status(states) == MODULE_STATUS_NOT_STARTED

    def test_scoping_out_a_mandatory_is_not_progress(self):
        """
        The mandatory counterpart of the case above. The advisor has acted, but
        in_progress keys on any_complete rather than any_acted_on, so a module
        with outstanding mandatory work and nothing completed stays not_started.
        """
        states = [_mandatory(in_scope=False), _mandatory()]
        assert derive_module_status(states) == MODULE_STATUS_NOT_STARTED


# ==================== IN PROGRESS ====================

class TestInProgress:
    """Some work is done, but mandatory deliverables remain outstanding."""

    def test_one_mandatory_complete_another_outstanding(self):
        states = [_mandatory(complete=True), _mandatory()]
        assert derive_module_status(states) == MODULE_STATUS_IN_PROGRESS

    def test_optional_complete_mandatory_outstanding(self):
        states = [_optional(complete=True), _mandatory()]
        assert derive_module_status(states) == MODULE_STATUS_IN_PROGRESS

    def test_scoped_out_optional_plus_completed_optional_mandatory_outstanding(self):
        states = [_mandatory(), _optional(complete=True), _optional(in_scope=False)]
        assert derive_module_status(states) == MODULE_STATUS_IN_PROGRESS


# ==================== COMPLETED ====================

class TestCompleted:
    """Nothing mandatory outstanding, and at least one deliverable acted on."""

    def test_all_mandatory_complete_some_optionals_incomplete(self):
        """Incomplete optionals never block completion."""
        states = [_mandatory(complete=True), _mandatory(complete=True), _optional()]
        assert derive_module_status(states) == MODULE_STATUS_COMPLETED

    def test_everything_complete(self):
        states = [_mandatory(complete=True), _optional(complete=True)]
        assert derive_module_status(states) == MODULE_STATUS_COMPLETED

    def test_all_mandatory_scoped_out_one_optional_completed(self):
        states = [_mandatory(in_scope=False), _optional(complete=True)]
        assert derive_module_status(states) == MODULE_STATUS_COMPLETED

    def test_all_mandatory_scoped_out_nothing_completed(self):
        """
        Deliberate: the advisor judged that nothing mandatory applies to this
        client, so there is no outstanding work left for the module.
        """
        states = [_mandatory(in_scope=False), _mandatory(in_scope=False)]
        assert derive_module_status(states) == MODULE_STATUS_COMPLETED

    def test_zero_mandatory_module_one_optional_completed(self):
        """Documented edge: a module with no mandatory deliverables."""
        states = [_optional(complete=True), _optional()]
        assert derive_module_status(states) == MODULE_STATUS_COMPLETED

    def test_zero_mandatory_module_one_optional_scoped_out(self):
        """Documented edge: scoping out is activity, so this completes."""
        states = [_optional(in_scope=False)]
        assert derive_module_status(states) == MODULE_STATUS_COMPLETED


# ==================== SCOPE / COMPLETION INTERACTION ====================

class TestScopedOutAndComplete:
    """A deliverable can be complete and scoped out simultaneously."""

    def test_mandatory_complete_and_scoped_out_is_not_outstanding(self):
        states = [_mandatory(in_scope=False, complete=True)]
        assert derive_module_status(states) == MODULE_STATUS_COMPLETED

    def test_mandatory_complete_and_scoped_out_alongside_outstanding_mandatory(self):
        """The scoped-out item is not outstanding, but its completion counts."""
        states = [_mandatory(in_scope=False, complete=True), _mandatory()]
        assert derive_module_status(states) == MODULE_STATUS_IN_PROGRESS

    def test_incomplete_scoped_out_mandatory_does_not_block(self):
        states = [_mandatory(in_scope=False), _optional(complete=True)]
        assert derive_module_status(states) == MODULE_STATUS_COMPLETED
