"""
Only backend/files/public is served without authentication.

backend/files was once mounted whole at /files, which served every upload,
prompt, scoring map, fixture and export to anyone who knew the path - while the
engagement download endpoint went to the trouble of checking access first.
These tests pin the narrowed mount so that cannot come back by accident.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Mount

from app.main import app

FILES_DIR = Path(__file__).resolve().parents[1] / "files"


@pytest.fixture
def client():
    # Static routes need no database, so this deliberately skips the api fixture.
    return TestClient(app)


def test_public_is_the_only_static_mount():
    mounts = [r.path for r in app.routes if isinstance(r, Mount)]
    assert mounts == ["/files/public"]


@pytest.mark.parametrize("path", [
    "scoring_map.json",
    "task_library.json",
    "diagnostic-surveyjs.json",
    "prompts/system_prompt.md",
    "sale_ready/dd_templates.json",
])
def test_private_files_are_not_served(client, path):
    """Each of these exists on disk under backend/files and must not be public."""
    if not (FILES_DIR / path).exists():
        pytest.skip(f"{path} is not present in this checkout")
    assert client.get(f"/files/{path}").status_code == 404


def test_uploads_are_not_served(client):
    assert client.get("/files/uploads/users/whoever/some-document.pdf").status_code == 404


def test_public_directory_is_served(client, tmp_path_factory):
    """Avatars live here: an <img> cannot send a bearer token, so this stays public."""
    public_dir = FILES_DIR / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    probe = public_dir / "mount-probe.txt"
    probe.write_text("served", encoding="utf-8")
    try:
        response = client.get("/files/public/mount-probe.txt")
        assert response.status_code == 200
        assert response.text == "served"
    finally:
        probe.unlink()
