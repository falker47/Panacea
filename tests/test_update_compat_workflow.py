from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_workflow_checks_exact_sha_and_limits_privileged_execution():
    workflow = yaml.load((ROOT / ".github/workflows/update-compat.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"push", "pull_request", "workflow_dispatch"}
    assert workflow["on"]["push"]["branches"] == ["main"]
    assert workflow["permissions"] == {"contents": "read"}
    assert "github.ref" in workflow["concurrency"]["group"]
    assert workflow["env"]["SOURCE_SHA"] == "${{ github.event.pull_request.head.sha || github.sha }}"
    ci = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    source_steps = ci["jobs"]["windows-smoke"]["steps"]
    for job in workflow["jobs"].values():
        steps = job["steps"]
        assert steps[0]["with"]["ref"] == source_steps[0]["with"]["ref"]
        assert steps[1] == source_steps[1]
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


def test_transport_control_runs_before_native_probes_and_uploads_only_json():
    workflow = yaml.load((ROOT / ".github/workflows/update-compat.yml").read_text(), Loader=yaml.BaseLoader)
    jobs = workflow["jobs"]
    for job in ("native-install", "client-acceptance"):
        assert "transport-canary" in jobs[job]["needs"]
    steps = jobs["transport-canary"]["steps"]
    cleanup, = [step for step in steps if "tls_canary --cleanup" in step.get("run", "")]
    assert "always()" in cleanup["if"]
    assert steps[-1]["with"]["path"] == "build/update-compat/loopback-tls.json"


@pytest.mark.parametrize("missing", ["GITHUB_ACTIONS", "RUNNER_ENVIRONMENT", "PANACEA_ALLOW_HOSTED_PROBE"])
@pytest.mark.parametrize(("module", "args"), [
    ("acceptance", ["v2.1.1"]),
    ("installed", ["v2.1.1", "transaction"]),
    ("installed", ["v2.1.1", "rollback"]),
    ("installed", ["v2.1.1", "manual"]),
    ("fixture_helper", []),
    ("stamp_candidate", []),
    ("tls_canary", []),
    ("tls_canary", ["--cleanup"]),
])
def test_each_native_entry_refuses_incomplete_hosted_environment(module, args, missing, monkeypatch, tmp_path):
    import importlib
    import sys
    from types import SimpleNamespace
    from scripts import hosted_installer_probe
    from scripts.update_compat import hosted

    probe = importlib.import_module("scripts.update_compat." + module)
    flags = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
             "PANACEA_ALLOW_HOSTED_PROBE": "true"}
    del flags[missing]
    monkeypatch.setattr(hosted, "os", SimpleNamespace(name="nt", getenv=flags.get))
    monkeypatch.setattr(hosted_installer_probe, "disposable_guard",
                        lambda: pytest.fail("Probe crossed the hosted guard into Windows preflight"))
    monkeypatch.setattr(sys, "argv", [module, *args])
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="explicitly enabled GitHub-hosted Windows runner"):
        probe.main()
    assert not list(tmp_path.iterdir())
