"""Prevent the version-specific publisher from re-running on unrelated main commits.

The live failure after merge #10 is recorded in GitHub Actions run 43089375234.
The published v2.1.0 tag is intentionally pinned to its original reviewed SHA.
"""
from pathlib import Path

from version import VERSION


APPROVED_SHA = "b751940b11f2b31fd54284aa63fc123ac047a577"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/publish-approved-v210.yml"


def test_v210_publisher_only_runs_for_original_approved_main_commit():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert VERSION == "2.1.0"
    assert "workflow_run:" in source
    assert "    workflows: [\"CI\"]" in source
    assert "    branches: [main]" in source
    condition = next(line for line in source.splitlines() if line.lstrip().startswith("if: ${{"))
    assert "github.event.workflow_run.conclusion == 'success'" in condition
    assert "github.event.workflow_run.event == 'push'" in condition
    assert "github.event.workflow_run.head_branch == 'main'" in condition
    assert f"github.event.workflow_run.head_sha == '{APPROVED_SHA}'" in condition


def test_original_release_tag_cannot_be_overwritten():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "gh release view \"$RELEASE_TAG\"" in source
    assert 'test "$object_sha" = "$SOURCE_SHA"' in source
    assert "if gh api \"repos/$GH_REPO/git/ref/tags/$RELEASE_TAG\"" in source
    assert "Unreviewed v2.1.0 tag exists; refusing to overwrite." in source
