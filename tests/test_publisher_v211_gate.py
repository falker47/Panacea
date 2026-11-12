"""Release-specific 2.1.1 publication guard: no unreviewed main commit may publish."""
from pathlib import Path

from version import VERSION


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/publish-approved-v211.yml"
NOTES = Path(__file__).resolve().parents[1] / "docs/releases/2.1.1.md"


def test_v211_only_publishes_from_successful_main_push_with_version_transition():
    assert VERSION == "2.1.1"
    assert NOTES.is_file()
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_run:" in workflow
    assert 'workflows: ["CI"]' in workflow
    assert "branches: [main]" in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "github.event.workflow_run.event == 'push'" in workflow
    assert "github.event.workflow_run.head_branch == 'main'" in workflow
    assert 'test "$(git rev-parse HEAD)" = "$SOURCE_SHA"' in workflow
    assert 'test "$(gh api "repos/$GH_REPO/branches/main" --jq .commit.sha)" = "$SOURCE_SHA"' in workflow
    assert 'previous_version="$(git show "$SOURCE_SHA^:version.py"' in workflow
    assert 'if test "$previous_version" != "2.1.0"; then' in workflow
    assert "fetch-depth: 2" in workflow


def test_v211_requires_all_native_gates_and_refuses_existing_unreviewed_tag():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for name in ("windows-smoke", "Disposable Windows image/cleanup integration",
                 "Protected installer / update / uninstall"):
        assert name in workflow
    assert 'test "$count" -ne 1' in workflow
    assert "Panacea-Windows-candidate" in workflow
    assert 'test "$(find release-assets -maxdepth 1 -type f | wc -l)" -eq 4' in workflow
    assert "sha256sum --check Panacea.exe.sha256" in workflow
    assert "sha256sum --check PanaceaSetup.exe.sha256" in workflow
    assert "if gh release view \"$RELEASE_TAG\"" in workflow
    assert "if gh api \"repos/$GH_REPO/git/ref/tags/$RELEASE_TAG\"" in workflow
    assert 'test "$object_sha" = "$SOURCE_SHA"' in workflow
    assert "Unreviewed v2.1.1 tag exists; refusing to overwrite." in workflow
    assert 'RELEASE_TAG: v2.1.1' in workflow
    assert "docs/releases/2.1.1.md" in workflow
    assert "gh release download" in workflow
    assert "cmp \"release-assets/$file\" \"verify-assets/$file\"" in workflow
