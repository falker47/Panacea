from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_workflow_checks_exact_sha_and_limits_privileged_execution():
    workflow = yaml.load((ROOT / ".github/workflows/update-compat.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"push", "pull_request", "workflow_dispatch"}
    assert workflow["on"]["push"]["branches"] == ["main"]
    assert workflow["permissions"] == {"contents": "read"}
    assert "github.ref" in workflow["concurrency"]["group"]
    assert workflow["env"]["SOURCE_SHA"] == "${{ github.event.pull_request.head.sha || github.sha }}"
    for job in workflow["jobs"].values():
        steps = job["steps"]
        assert steps[0]["with"]["ref"] == "${{ env.SOURCE_SHA }}"
        assert "git rev-parse HEAD" in steps[1]["run"] and "SOURCE_SHA" in steps[1]["run"]
        if job["runs-on"] == "windows-latest":
            guard = job["if"]
            assert "github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name == github.repository" in guard
            assert "&& github.ref == 'refs/heads/main'" in guard
            assert job["env"]["PANACEA_ALLOW_HOSTED_PROBE"] == "true"
            assert any("hosted_guard()" in step.get("run", "") for step in steps)
            assert steps[-1]["if"] == "always()"


def test_matrix_keeps_all_required_published_versions():
    jobs = yaml.load((ROOT / ".github/workflows/update-compat.yml").read_text(), Loader=yaml.BaseLoader)["jobs"]
    assert set(jobs["client-acceptance"]["strategy"]["matrix"]["from"]) >= {
        "v2.0.0", "v2.0.1", "v2.0.2", "v2.1.0", "v2.1.1"}
    rows = jobs["native-install"]["strategy"]["matrix"]["include"]
    assert {(r["mode"], r["from"]) for r in rows} >= {
        ("transaction", "v2.1.1"), ("transaction", "v2.1.0"), ("transaction", "v2.0.2"),
        ("manual", "v2.1.1"), ("rollback", "v2.1.1")}


def test_probe_denies_other_runner_environments_before_win32_access(monkeypatch):
    import pytest
    from types import SimpleNamespace
    from scripts.update_compat import hosted

    required = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
                "PANACEA_ALLOW_HOSTED_PROBE": "true"}
    for missing in required:
        env = {key: value for key, value in required.items() if key != missing}
        monkeypatch.setattr(hosted, "os", SimpleNamespace(name="nt", getenv=env.get))
        with pytest.raises(RuntimeError, match="GitHub-hosted"):
            hosted.hosted_guard()
