from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/build-xenage-gui.yml")


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_gui_workflow_uploads_updater_artifacts():
    content = _workflow_text()

    assert "verify updater artifacts (post-build)" in content
    assert "bundle/**/latest.json" in content
    assert "No latest.json or *.sig updater artifacts were found." in content
    assert "bundle/**/*.sig" in content
    assert "bundle/**/*.tar.gz" in content
    assert "bundle/**/*.zip" in content


def test_gui_workflow_publishes_canonical_latest_json():
    content = _workflow_text()

    assert "Synthesized updater manifest into" in content
    assert "Constructed updater manifest from" in content
    assert "/tmp/latest.json" in content
    assert "gh release upload \"${RELEASE_TAG}\" /tmp/latest.json --repo \"${REPO}\"" in content
