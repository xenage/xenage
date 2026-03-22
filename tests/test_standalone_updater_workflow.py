from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/build-xenage-standalone.yml")


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_standalone_workflow_signs_artifacts():
    content = _workflow_text()

    assert "sign standalone artifacts" in content
    assert "TAURI_SIGNING_PRIVATE_KEY" in content
    assert "signer sign" in content


def test_standalone_workflow_generates_latest_manifest():
    content = _workflow_text()

    assert "Generated standalone updater manifest" in content
    assert "/tmp/latest.json" in content
    assert "gh release upload \"${RELEASE_TAG}\" /tmp/latest.json --repo \"${REPO}\"" in content
