from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/build-xenage-standalone.yml")
PREPARE_SCRIPT_PATH = Path(".github/scripts/prepare-xenage-standalone-version.mjs")


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


def test_standalone_workflow_supports_unified_nightly_and_tag_releases():
    content = _workflow_text()
    prepare_script = PREPARE_SCRIPT_PATH.read_text(encoding="utf-8")

    assert 'tags: [ "*" ]' in content
    assert "verify tagged release points to main" in content
    assert "releaseTag = 'nightly'" in prepare_script
