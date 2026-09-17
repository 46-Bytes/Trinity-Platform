"""
Endpoint tests for the deliverables API.

The role-boundary matrix is the point of this file. Enforcement is quarantined
in app/services/deliverable_permissions.py, and a guard that is never exercised
is indistinguishable from one that was deleted - these tests are what prove it
actually holds.

Run with: pytest tests/test_program_deliverable_api.py -v
"""
import uuid

import pytest

from app.models.program_deliverable import ProgramModuleDeliverable
from app.models.user import UserRole

BASE = "/api/deliverables/engagements"


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------
@pytest.fixture
def advisor(db_session, test_engagement, make_user):
    """The engagement's primary advisor."""
    user = make_user(UserRole.ADVISOR)
    test_engagement.primary_advisor_id = user.id
    db_session.flush()
    return user


@pytest.fixture
def owner(db_session, test_engagement, make_user):
    """A client on the engagement - the 'owner' the spec denies mutations to."""
    user = make_user(UserRole.CLIENT)
    test_engagement.client_ids = [user.id]
    db_session.flush()
    return user


@pytest.fixture
def admin(make_user):
    return make_user(UserRole.ADMIN)


@pytest.fixture
def outsider(make_user):
    """An advisor with no relationship to this engagement at all."""
    return make_user(UserRole.ADVISOR)


@pytest.fixture
def preset(db_session, test_engagement):
    row = ProgramModuleDeliverable(
        program_type="value_builder",
        module_code="V1",
        deliverable_key=f"key-{uuid.uuid4()}",
        title="Financial Health Summary",
        is_mandatory=True,
        display_order=1,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _advisor_item(api, user, engagement, module_code="V2", title="Custom"):
    resp = api.as_user(user).post(
        f"{BASE}/{engagement.id}/items",
        json={"module_code": module_code, "title": title, "is_mandatory": True},
    )
    assert resp.status_code == 201, resp.text
    module = next(m for m in resp.json()["modules"] if m["module_code"] == module_code)
    return module["deliverables"][0]["deliverable_id"]


# ----------------------------------------------------------------------
# Role boundary - the tests that matter
# ----------------------------------------------------------------------
class TestReadAccess:

    def test_advisor_can_read(self, api, advisor, test_engagement):
        assert api.as_user(advisor).get(f"{BASE}/{test_engagement.id}").status_code == 200

    def test_admin_can_read(self, api, admin, test_engagement):
        assert api.as_user(admin).get(f"{BASE}/{test_engagement.id}").status_code == 200

    def test_owner_is_denied(self, api, owner, test_engagement):
        """
        Part A puts module card contents, preset deliverables and advisor-added
        deliverables in the owner's No column - all of which this read returns.
        Their dashboard is a separate, narrower read that does not come from
        this endpoint.
        """
        assert api.as_user(owner).get(f"{BASE}/{test_engagement.id}").status_code == 403

    def test_outsider_is_rejected(self, api, outsider, test_engagement):
        assert api.as_user(outsider).get(f"{BASE}/{test_engagement.id}").status_code == 403

    def test_unknown_engagement_is_404(self, api, advisor):
        assert api.as_user(advisor).get(f"{BASE}/{uuid.uuid4()}").status_code == 404


class TestMutationRoleBoundary:
    """
    Every mutation, against every class of caller.

    Owners and outsiders must be refused server-side on all five, regardless of
    what the client sends.
    """

    def _requests(self, engagement, preset_id, instance_id):
        e = engagement.id
        return {
            "complete": ("put", f"{BASE}/{e}/items/{preset_id}/complete", {"is_complete": True}),
            "scope": ("put", f"{BASE}/{e}/items/{preset_id}/scope", {"is_in_scope": False}),
            "add": ("post", f"{BASE}/{e}/items", {"module_code": "V3", "title": "X", "is_mandatory": True}),
            "update": ("patch", f"{BASE}/{e}/items/{instance_id}", {"title": "Renamed"}),
            "remove": ("delete", f"{BASE}/{e}/items/{instance_id}", None),
        }

    def _call(self, client, method, url, body):
        return client.request(method.upper(), url, json=body) if body is not None else client.request(method.upper(), url)

    @pytest.mark.parametrize("action", ["complete", "scope", "add", "update", "remove"])
    def test_owner_is_denied(self, api, owner, advisor, test_engagement, preset, action):
        instance_id = _advisor_item(api, advisor, test_engagement)
        method, url, body = self._requests(test_engagement, preset.id, instance_id)[action]
        resp = self._call(api.as_user(owner), method, url, body)
        assert resp.status_code == 403, f"{action} was NOT denied to owner: {resp.status_code}"

    @pytest.mark.parametrize("action", ["complete", "scope", "add", "update", "remove"])
    def test_outsider_is_denied(self, api, outsider, advisor, test_engagement, preset, action):
        instance_id = _advisor_item(api, advisor, test_engagement)
        method, url, body = self._requests(test_engagement, preset.id, instance_id)[action]
        resp = self._call(api.as_user(outsider), method, url, body)
        assert resp.status_code == 403, f"{action} was NOT denied to outsider: {resp.status_code}"

    @pytest.mark.parametrize("action", ["complete", "scope", "add", "update", "remove"])
    def test_advisor_is_allowed(self, api, advisor, test_engagement, preset, action):
        instance_id = _advisor_item(api, advisor, test_engagement)
        method, url, body = self._requests(test_engagement, preset.id, instance_id)[action]
        resp = self._call(api.as_user(advisor), method, url, body)
        assert resp.status_code < 300, f"{action} failed for advisor: {resp.status_code} {resp.text}"

    @pytest.mark.parametrize("action", ["complete", "scope", "add", "update", "remove"])
    def test_admin_is_allowed(self, api, admin, advisor, test_engagement, preset, action):
        instance_id = _advisor_item(api, advisor, test_engagement)
        method, url, body = self._requests(test_engagement, preset.id, instance_id)[action]
        resp = self._call(api.as_user(admin), method, url, body)
        assert resp.status_code < 300, f"{action} failed for admin: {resp.status_code} {resp.text}"


class TestNonValueBuilderEngagement:

    def test_rejected_with_400(self, api, db_session, advisor, test_engagement):
        test_engagement.tool = "sale_ready"
        db_session.flush()
        resp = api.as_user(advisor).get(f"{BASE}/{test_engagement.id}")
        assert resp.status_code == 400


# ----------------------------------------------------------------------
# Functional behaviour through HTTP
# ----------------------------------------------------------------------
class TestReadView:

    def test_preset_appears_untouched(self, api, advisor, test_engagement, preset):
        body = api.as_user(advisor).get(f"{BASE}/{test_engagement.id}").json()
        module = next(m for m in body["modules"] if m["module_code"] == "V1")

        assert module["status"] == "not_started"
        item = module["deliverables"][0]
        assert item["deliverable_id"] == str(preset.id)
        assert item["source"] == "preset"
        assert item["title"] == "Financial Health Summary"
        assert item["is_mandatory"] is True
        assert item["is_in_scope"] is True
        assert item["is_complete"] is False

    def test_presets_sort_before_advisor_added(self, api, advisor, test_engagement, preset):
        _advisor_item(api, advisor, test_engagement, module_code="V1", title="Advisor extra")
        body = api.as_user(advisor).get(f"{BASE}/{test_engagement.id}").json()
        module = next(m for m in body["modules"] if m["module_code"] == "V1")
        assert [d["source"] for d in module["deliverables"]] == ["preset", "advisor"]


class TestCompletionAndScope:

    def test_completing_flips_module_status(self, api, advisor, test_engagement, preset):
        resp = api.as_user(advisor).put(
            f"{BASE}/{test_engagement.id}/items/{preset.id}/complete", json={"is_complete": True}
        )
        assert resp.status_code == 200
        module = next(m for m in resp.json()["modules"] if m["module_code"] == "V1")
        assert module["status"] == "completed"
        assert module["deliverables"][0]["is_complete"] is True

    def test_scoping_out_preserves_completion(self, api, advisor, test_engagement, preset):
        client = api.as_user(advisor)
        client.put(f"{BASE}/{test_engagement.id}/items/{preset.id}/complete", json={"is_complete": True})
        resp = client.put(f"{BASE}/{test_engagement.id}/items/{preset.id}/scope", json={"is_in_scope": False})

        item = next(m for m in resp.json()["modules"] if m["module_code"] == "V1")["deliverables"][0]
        assert item["is_in_scope"] is False
        assert item["is_complete"] is True

    def test_uncompleting_unmaterialized_preset_is_a_noop(self, api, advisor, test_engagement, preset):
        resp = api.as_user(advisor).put(
            f"{BASE}/{test_engagement.id}/items/{preset.id}/complete", json={"is_complete": False}
        )
        assert resp.status_code == 200
        module = next(m for m in resp.json()["modules"] if m["module_code"] == "V1")
        assert module["status"] == "not_started"


class TestAdvisorDeliverables:

    def test_create_returns_the_item(self, api, advisor, test_engagement):
        resp = api.as_user(advisor).post(
            f"{BASE}/{test_engagement.id}/items",
            json={"module_code": "V5", "title": "Custom deliverable", "is_mandatory": False,
                  "description": "why"},
        )
        assert resp.status_code == 201
        item = next(m for m in resp.json()["modules"] if m["module_code"] == "V5")["deliverables"][0]
        assert item["source"] == "advisor"
        assert item["title"] == "Custom deliverable"
        assert item["description"] == "why"
        assert item["is_mandatory"] is False

    def test_create_without_title_is_400(self, api, advisor, test_engagement):
        resp = api.as_user(advisor).post(
            f"{BASE}/{test_engagement.id}/items",
            json={"module_code": "V5", "title": "   ", "is_mandatory": True},
        )
        assert resp.status_code == 400

    def test_patch_leaves_omitted_fields_alone(self, api, advisor, test_engagement):
        instance_id = _advisor_item(api, advisor, test_engagement, module_code="V6", title="Original")
        api.as_user(advisor).patch(
            f"{BASE}/{test_engagement.id}/items/{instance_id}", json={"description": "added"}
        )
        resp = api.as_user(advisor).get(f"{BASE}/{test_engagement.id}")
        item = next(m for m in resp.json()["modules"] if m["module_code"] == "V6")["deliverables"][0]
        assert item["title"] == "Original"
        assert item["description"] == "added"

    def test_delete_removes_it_from_the_view(self, api, advisor, test_engagement):
        instance_id = _advisor_item(api, advisor, test_engagement, module_code="V7")
        resp = api.as_user(advisor).delete(f"{BASE}/{test_engagement.id}/items/{instance_id}")
        assert resp.status_code == 200
        assert not any(m["module_code"] == "V7" for m in resp.json()["modules"])

    def test_deleting_a_preset_is_refused_and_leaves_it_intact(self, api, advisor, test_engagement, preset):
        """
        The status code is pinned in TestNotFoundVsBadRequest; what matters here
        is that the refusal is total - the preset is still in the view, still
        complete, and the module has not silently changed status.
        """
        client = api.as_user(advisor)
        client.put(f"{BASE}/{test_engagement.id}/items/{preset.id}/complete", json={"is_complete": True})

        assert client.delete(f"{BASE}/{test_engagement.id}/items/{preset.id}").status_code == 400

        module = next(m for m in client.get(f"{BASE}/{test_engagement.id}").json()["modules"]
                      if m["module_code"] == "V1")
        item = next(d for d in module["deliverables"] if d["deliverable_id"] == str(preset.id))
        assert item["is_complete"] is True
        assert module["status"] == "completed"

class TestNotFoundVsBadRequest:
    """
    A stale deliverable id is 404; a malformed body is 400.

    These are pinned apart deliberately. DeliverableNotFound subclasses
    ValueError, so if an endpoint ever catches the generic handler first the
    404 silently degrades to a 400 - and only a test that asserts both halves
    catches that.
    """

    @pytest.mark.parametrize("verb,url_suffix,body", [
        ("put", "/complete", {"is_complete": True}),
        ("put", "/scope", {"is_in_scope": False}),
    ])
    def test_stale_id_is_404_on_state_changes(self, api, advisor, test_engagement, verb, url_suffix, body):
        resp = api.as_user(advisor).request(
            verb.upper(), f"{BASE}/{test_engagement.id}/items/{uuid.uuid4()}{url_suffix}", json=body
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Deliverable not found"

    def test_stale_id_is_404_on_patch(self, api, advisor, test_engagement):
        resp = api.as_user(advisor).patch(
            f"{BASE}/{test_engagement.id}/items/{uuid.uuid4()}", json={"title": "Renamed"}
        )
        assert resp.status_code == 404, resp.text

    def test_stale_id_is_404_on_delete(self, api, advisor, test_engagement):
        resp = api.as_user(advisor).delete(f"{BASE}/{test_engagement.id}/items/{uuid.uuid4()}")
        assert resp.status_code == 404, resp.text

    def test_soft_deleted_item_is_404(self, api, advisor, test_engagement):
        """Already removed is gone, not merely invalid."""
        instance_id = _advisor_item(api, advisor, test_engagement, module_code="V8")
        api.as_user(advisor).delete(f"{BASE}/{test_engagement.id}/items/{instance_id}")
        resp = api.as_user(advisor).delete(f"{BASE}/{test_engagement.id}/items/{instance_id}")
        assert resp.status_code == 404, resp.text

    def test_bad_body_on_a_real_id_is_still_400(self, api, advisor, test_engagement):
        """The other half: a resolvable id with an invalid payload stays 400."""
        instance_id = _advisor_item(api, advisor, test_engagement, module_code="V9")
        resp = api.as_user(advisor).patch(
            f"{BASE}/{test_engagement.id}/items/{instance_id}", json={"title": "   "}
        )
        assert resp.status_code == 400, resp.text

    @pytest.mark.parametrize("materialized", [False, True], ids=["untouched", "materialized"])
    def test_preset_edit_and_delete_are_400_not_404(self, api, advisor, test_engagement, preset, materialized):
        """
        A preset resolves fine - refusing to edit or delete it is a rule, not a
        miss.

        Both rows matter. Untouched, the preset has no instance row at all, so
        its library id is the only id in existence - and that is precisely the
        id the read view hands out. That case is what the frontend actually
        hits, and it answered 404 for as long as these two endpoints resolved
        instance ids only, putting the guard out of reach entirely.
        """
        client = api.as_user(advisor)
        if materialized:
            client.put(f"{BASE}/{test_engagement.id}/items/{preset.id}/complete", json={"is_complete": True})

        delete_resp = client.delete(f"{BASE}/{test_engagement.id}/items/{preset.id}")
        assert delete_resp.status_code == 400, delete_resp.text

        patch_resp = client.patch(
            f"{BASE}/{test_engagement.id}/items/{preset.id}", json={"title": "Renamed"}
        )
        assert patch_resp.status_code == 400, patch_resp.text

    def test_unknown_engagement_still_wins_over_deliverable_lookup(self, api, advisor):
        """Engagement access is resolved first, so a bad engagement is 404 regardless."""
        resp = api.as_user(advisor).put(
            f"{BASE}/{uuid.uuid4()}/items/{uuid.uuid4()}/complete", json={"is_complete": True}
        )
        assert resp.status_code == 404, resp.text
