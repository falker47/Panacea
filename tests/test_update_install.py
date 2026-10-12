"""Install only tiny PE fixtures into temporary directories; launch is injected."""
import hashlib
import json
from contextlib import nullcontext
from pathlib import Path
import struct

import pytest

from modules import update_install


def executable(marker):
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 132, 0x8664, 1, 0, 0, 0, 240, 0x22)
    struct.pack_into("<H", data, 152, 0x20B)
    data[480:480 + len(marker)] = marker
    return bytes(data)


@pytest.fixture
def files(tmp_path):
    folder = tmp_path / "Spazi è Unicode"
    folder.mkdir()
    staged = folder / "staged.exe"
    target = folder / "Panacea.exe"
    staged.write_bytes(executable(b"new"))
    target.write_bytes(executable(b"old"))
    return staged, target, hashlib.sha256(staged.read_bytes()).hexdigest()


@pytest.fixture
def helper_security(monkeypatch):
    # Exercise all filesystem/verification/rollback behavior; only the privileged
    # Win32 ACL-creation boundary is replaced with ordinary fixture file creation.
    monkeypatch.setattr(update_install, "_assert_admin_file", lambda path: None)
    monkeypatch.setattr(update_install, "_open_exclusive", lambda path, protected=False: path.open("xb+"))
    monkeypatch.setattr(update_install, "_transaction_guard", lambda target, protected=False: nullcontext())


def test_verified_install_retains_backup_until_readiness(files):
    staged, target, digest = files
    launched = []
    result = update_install.install_verified(staged, target, digest, lambda path, token: launched.append((path, token)))
    assert result.success
    assert target.read_bytes() == executable(b"new")
    assert result.backup.read_bytes() == executable(b"old")
    assert launched == [(target, result.readiness_token)]
    assert update_install.acknowledge_ready(target, result.readiness_token)
    assert not result.backup.exists()
    assert not update_install.readiness_path(target).exists()


def test_bad_staged_checksum_never_replaces_or_launches(files):
    staged, target, _ = files
    launched = []
    result = update_install.install_verified(staged, target, "0" * 64, lambda path, token: launched.append(path))
    assert not result.success
    assert target.read_bytes() == executable(b"old")
    assert not launched
    assert sorted(path.name for path in target.parent.iterdir()) == ["Panacea.exe", "staged.exe"]


def test_target_rename_permission_failure_leaves_old_app(files, monkeypatch):
    staged, target, digest = files
    real_replace = update_install.os.replace

    def locked(source, destination):
        if Path(source) == target:
            raise PermissionError("running executable locked")
        return real_replace(source, destination)

    monkeypatch.setattr(update_install.os, "replace", locked)
    result = update_install.install_verified(staged, target, digest, lambda path, token: pytest.fail("must not launch"))
    assert not result.success
    assert not result.rolled_back
    assert target.read_bytes() == executable(b"old")
    assert sorted(path.name for path in target.parent.iterdir()) == ["Panacea.exe", "staged.exe"]


def test_candidate_replace_failure_rolls_back(files, monkeypatch):
    staged, target, digest = files
    real_replace = update_install.os.replace

    def denied(source, destination):
        if Path(source).suffix == ".candidate":
            raise PermissionError("target cannot be replaced")
        return real_replace(source, destination)

    monkeypatch.setattr(update_install.os, "replace", denied)
    result = update_install.install_verified(staged, target, digest, lambda path, token: pytest.fail("must not launch"))
    assert not result.success
    assert result.rolled_back
    assert target.read_bytes() == executable(b"old")


def test_launch_failure_rolls_back(files):
    staged, target, digest = files

    def fail(path, token):
        raise OSError("launch denied")

    result = update_install.install_verified(staged, target, digest, fail)
    assert not result.success
    assert result.rolled_back
    assert target.read_bytes() == executable(b"old")
    assert not update_install.readiness_path(target).exists()


def test_immediate_new_process_crash_rolls_back(files):
    staged, target, digest = files

    class Crashed:
        def poll(self):
            return 7

    result = update_install.install_verified(staged, target, digest, lambda path, token: Crashed())
    assert not result.success
    assert result.rolled_back
    assert target.read_bytes() == executable(b"old")


def test_missing_or_wrong_readiness_token_keeps_backup(files):
    staged, target, digest = files
    result = update_install.install_verified(staged, target, digest, lambda path, token: None)
    assert not update_install.acknowledge_ready(target, "0" * 64)
    assert result.backup.exists()
    target.write_bytes(executable(b"tampered"))
    assert not update_install.acknowledge_ready(target, result.readiness_token)
    assert result.backup.exists()


def test_existing_pending_update_is_never_discarded(files):
    staged, target, digest = files
    first = update_install.install_verified(staged, target, digest, lambda path, token: None)
    second = update_install.install_verified(staged, target, digest, lambda path, token: pytest.fail("must not launch"))
    assert first.success and not second.success
    assert first.backup.read_bytes() == executable(b"old")


def test_forged_readiness_backup_path_cannot_delete_other_file(files):
    staged, target, digest = files
    result = update_install.install_verified(staged, target, digest, lambda path, token: None)
    sentinel = target.parent / "sentinel.txt"
    sentinel.write_text("keep")
    marker = update_install.readiness_path(target)
    data = json.loads(marker.read_text())
    data["backup"] = str(sentinel)
    marker.write_text(json.dumps(data))
    assert not update_install.acknowledge_ready(target, result.readiness_token)
    assert sentinel.read_text() == "keep"
    assert result.backup.exists()


def test_reparse_staging_is_rejected_before_launch(files, monkeypatch):
    staged, target, digest = files
    original = Path.lstat

    def fake_reparse(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == staged:
            class Reparse:
                st_mode = info.st_mode
                st_file_attributes = 0x400
            return Reparse()
        return info

    monkeypatch.setattr(Path, "lstat", fake_reparse)
    result = update_install.install_verified(staged, target, digest, lambda path, token: pytest.fail("must not launch"))
    assert not result.success
    assert target.read_bytes() == executable(b"old")


def test_failed_rollback_retains_recovery_backup(files, monkeypatch):
    staged, target, digest = files
    real_replace = update_install.os.replace

    def locked_backup(source, destination):
        if Path(source).suffix == ".backup":
            raise PermissionError("locked backup")
        return real_replace(source, destination)

    monkeypatch.setattr(update_install.os, "replace", locked_backup)
    result = update_install.install_verified(staged, target, digest, lambda path, token: (_ for _ in ()).throw(OSError("no launch")))
    assert not result.success and not result.rolled_back
    assert result.backup.read_bytes() == executable(b"old")
    assert update_install.readiness_path(target).exists()
    assert "recover" in result.error.lower()


@pytest.mark.parametrize("sddl,expected", [
    ("O:BAG:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FR;;;BU)", True),
    ("O:BAG:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;BU)", False),
    ("O:S-1-5-21-123G:BAD:P(A;;FA;;;BA)", False),
    ("O:BAG:BAD:P(A;;0x1200a9;;;BU)(A;;FA;;;BA)", True),
    ("O:BAG:BAD:P(A;;0x1301bf;;;BU)(A;;FA;;;BA)", False),
    ("O:BAG:BAD:NO_ACCESS_CONTROL", False),
])
def test_elevated_helper_requires_admin_owned_non_user_writable_directory(sddl, expected):
    assert update_install._protected_sddl(sddl) is expected


def test_self_update_refuses_source_interpreter(files, monkeypatch):
    staged, target, digest = files
    monkeypatch.setattr(update_install.sys, "frozen", False, raising=False)
    with pytest.raises(update_install.UpdateVerificationError):
        update_install.start_self_update(staged, target, None, None)
    assert target.read_bytes() == executable(b"old")


def test_helper_rechecks_authoritative_checksum_before_install(files, monkeypatch, helper_security):
    staged, target, digest = files
    workspace = target.parent / "panacea-update-" / "safe"
    workspace.mkdir(parents=True)
    (workspace / "staged.exe").write_bytes(executable(b"tampered"))
    (workspace / "job.json").write_text(json.dumps({"target": str(target), "version": "1.49.0"}))
    monkeypatch.setattr(update_install, "_assert_helper_context", lambda path: None)
    monkeypatch.setattr(update_install, "_assert_admin_directory", lambda path: None)

    class Client:
        def __init__(self, repo, current_version):
            pass
        def check(self):
            from modules.updater import Release
            return Release("1.49.0", "url", "url", 512, "url")
        def fetch_checksum(self, release):
            return digest

    code = update_install.run_update_helper(workspace, client_factory=Client,
                                           popen=lambda *args, **kwargs: pytest.fail("unverified executable launched"))
    assert code == 1
    assert target.read_bytes() == executable(b"old")
    assert json.loads((workspace / "status.json").read_text())["status"] == "failed"


def test_helper_detects_process_exit_before_readiness_and_restores_backup(files, monkeypatch, helper_security):
    staged, target, digest = files
    workspace = target.parent / "panacea-update-fixture"
    workspace.mkdir()
    (workspace / "staged.exe").write_bytes(staged.read_bytes())
    (workspace / "job.json").write_text(json.dumps({"target": str(target), "version": "1.49.0"}))
    monkeypatch.setattr(update_install, "_assert_helper_context", lambda path: None)
    monkeypatch.setattr(update_install, "_assert_admin_directory", lambda path: None)

    class Client:
        def __init__(self, repo, current_version):
            pass
        def check(self):
            from modules.updater import Release
            return Release("1.49.0", "url", "url", 512, "url")
        def fetch_checksum(self, release):
            return digest

    class Process:
        calls = 0
        def poll(self):
            self.calls += 1
            return None if self.calls == 1 else 7

    code = update_install.run_update_helper(workspace, client_factory=Client, popen=lambda *args, **kwargs: Process())
    assert code == 1
    assert target.read_bytes() == executable(b"old")
    assert json.loads((workspace / "status.json").read_text())["status"] == "failed"


def test_helper_success_waits_for_new_application_acknowledgment(files, monkeypatch, helper_security):
    staged, target, digest = files
    workspace = target.parent / "panacea-update-fixture"
    workspace.mkdir()
    (workspace / "staged.exe").write_bytes(staged.read_bytes())
    (workspace / "job.json").write_text(json.dumps({"target": str(target), "version": "1.49.0"}))
    monkeypatch.setattr(update_install, "_assert_helper_context", lambda path: None)
    monkeypatch.setattr(update_install, "_assert_admin_directory", lambda path: None)
    monkeypatch.setenv("PANACEA_UPDATE_TEST_SENTINEL", "restart-sentinel")
    monkeypatch.setenv("PYINSTALLER_RESET_ENVIRONMENT", "0")
    monkeypatch.setenv("_PYI_ARCHIVE_FILE", "retiring-bundle.exe")
    launches = []

    class Client:
        def __init__(self, repo, current_version):
            pass
        def check(self):
            from modules.updater import Release
            return Release("1.49.0", "url", "url", 512, "url")
        def fetch_checksum(self, release):
            return digest

    class Process:
        def poll(self):
            return None

    def launch(arguments, **kwargs):
        launches.append(kwargs)
        assert arguments[:2] == [str(target), "--panacea-update-ready"]
        assert update_install.acknowledge_ready(target, arguments[2])
        return Process()

    code = update_install.run_update_helper(workspace, client_factory=Client, popen=launch)
    assert code == 0
    assert target.read_bytes() == executable(b"new")
    assert json.loads((workspace / "status.json").read_text())["status"] == "ready"
    child_env = launches[0].get("env")
    assert child_env is not None
    assert child_env is not update_install.os.environ
    assert child_env["PANACEA_UPDATE_TEST_SENTINEL"] == "restart-sentinel"
    assert child_env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert child_env["_PYI_ARCHIVE_FILE"] == "retiring-bundle.exe"
    assert update_install.os.environ["PYINSTALLER_RESET_ENVIRONMENT"] == "0"


def test_prepared_helper_copies_current_image_never_staged_image(files, monkeypatch):
    staged, target, digest = files
    workspace = target.parent / "panacea-update-fixture"
    workspace.mkdir()
    monkeypatch.setattr(update_install.sys, "frozen", True, raising=False)
    monkeypatch.setattr(update_install.sys, "executable", str(target))
    monkeypatch.setattr(update_install, "_assert_admin_directory", lambda path: None)
    monkeypatch.setattr(update_install, "_assert_admin_file", lambda path: None)
    monkeypatch.setattr(update_install, "_create_admin_workspace", lambda parent: workspace)
    monkeypatch.setattr(update_install, "_open_exclusive", lambda path, protected=False: path.open("xb+"))
    monkeypatch.setenv("PANACEA_UPDATE_TEST_SENTINEL", "helper-sentinel")
    monkeypatch.setenv("PYINSTALLER_RESET_ENVIRONMENT", "0")
    monkeypatch.setenv("_PYI_ARCHIVE_FILE", "retiring-bundle.exe")
    launches = []

    class Client:
        def fetch_checksum(self, release):
            return digest

    class Process:
        def poll(self):
            return None

    from modules.updater import Release
    release = Release("1.49.0", "url", "url", 512, "url")

    def launch(arguments, **kwargs):
        launches.append(kwargs)
        return Process()

    job = update_install.start_self_update(staged, target, release, Client(), popen=launch)
    assert (workspace / "Panacea-updater.exe").read_bytes() == executable(b"old")
    assert (workspace / "staged.exe").read_bytes() == executable(b"new")
    assert target.read_bytes() == executable(b"old")
    assert job.poll()["status"] == "preparing"
    child_env = launches[0].get("env")
    assert child_env is not None
    assert child_env is not update_install.os.environ
    assert child_env["PANACEA_UPDATE_TEST_SENTINEL"] == "helper-sentinel"
    assert child_env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert child_env["_PYI_ARCHIVE_FILE"] == "retiring-bundle.exe"
    assert update_install.os.environ["PYINSTALLER_RESET_ENVIRONMENT"] == "0"


def test_readiness_cleanup_failure_keeps_backup_and_records_ack(files, monkeypatch):
    staged, target, digest = files
    result = update_install.install_verified(staged, target, digest, lambda path, token: None)
    original = Path.unlink

    def locked(path, *args, **kwargs):
        if path == result.backup:
            raise PermissionError("backup cleanup denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked)
    assert update_install.acknowledge_ready(target, result.readiness_token)
    assert result.backup.exists()
    assert json.loads(update_install.readiness_path(target).read_text())["ready"] is True


def test_protected_file_creation_failure_never_installs_or_launches(files, monkeypatch):
    staged, target, digest = files

    def no_secure_create(path, protected=False):
        assert protected
        raise PermissionError("cannot create Administrators-owned candidate")

    monkeypatch.setattr(update_install, "_open_exclusive", no_secure_create)
    result = update_install.install_verified(staged, target, digest,
                                            lambda path, token: pytest.fail("must not launch"), protected=True)
    assert not result.success
    assert target.read_bytes() == executable(b"old")


@pytest.mark.parametrize("suffix", ["candidate", "backup"])
def test_generated_path_collision_never_deletes_existing_file(files, monkeypatch, suffix):
    staged, target, digest = files
    token = "a" * 64
    monkeypatch.setattr(update_install.secrets, "token_hex", lambda size: token)
    sentinel = target.with_name(f".{target.name}.{token}.{suffix}")
    sentinel.write_bytes(b"existing data")
    result = update_install.install_verified(staged, target, digest, lambda path, token: pytest.fail("must not launch"))
    assert not result.success
    assert result.backup is None
    assert target.read_bytes() == executable(b"old")
    assert sentinel.read_bytes() == b"existing data"


@pytest.mark.parametrize("locked_kind", ["backup", "marker"])
def test_next_update_recovers_acknowledged_cleanup_after_transient_lock(files, monkeypatch, locked_kind):
    staged, target, digest = files
    first = update_install.install_verified(staged, target, digest, lambda path, token: None)
    marker = update_install.readiness_path(target)
    original = Path.unlink

    def locked(path, *args, **kwargs):
        if path == (first.backup if locked_kind == "backup" else marker):
            raise PermissionError("transient cleanup lock")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked)
    assert update_install.acknowledge_ready(target, first.readiness_token)
    assert marker.exists()
    assert first.backup.exists() is (locked_kind == "backup")
    monkeypatch.setattr(Path, "unlink", original)
    staged.write_bytes(executable(b"next"))
    next_digest = hashlib.sha256(staged.read_bytes()).hexdigest()
    second = update_install.install_verified(staged, target, next_digest, lambda path, token: None)
    assert second.success
    assert target.read_bytes() == executable(b"next")
    assert second.backup.read_bytes() == executable(b"new")
    assert not first.backup.exists()
    assert json.loads(marker.read_text())["token"] == second.readiness_token


def test_completed_cleanup_that_is_still_locked_keeps_backup_and_blocks_replacement(files, monkeypatch):
    staged, target, digest = files
    first = update_install.install_verified(staged, target, digest, lambda path, token: None)
    marker = update_install.readiness_path(target)
    original = Path.unlink

    def locked(path, *args, **kwargs):
        if path == first.backup:
            raise PermissionError("still locked")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked)
    assert update_install.acknowledge_ready(target, first.readiness_token)
    second = update_install.install_verified(staged, target, digest, lambda path, token: pytest.fail("must not launch"))
    assert not second.success
    assert first.backup.read_bytes() == executable(b"old")
    assert target.read_bytes() == executable(b"new")
    assert json.loads(marker.read_text())["token"] == first.readiness_token


@pytest.mark.parametrize("field,value", [
    ("token", "invalid"), ("target", "elsewhere.exe"), ("backup", "sentinel.exe"),
    ("sha256", "0" * 64), ("backup_sha256", "0" * 64), ("ready", False),
])
def test_completed_marker_recovery_rejects_forged_or_unready_state(files, monkeypatch, field, value):
    staged, target, digest = files
    first = update_install.install_verified(staged, target, digest, lambda path, token: None)
    marker = update_install.readiness_path(target)
    original = Path.unlink

    def locked(path, *args, **kwargs):
        if path == first.backup:
            raise PermissionError("backup lock")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked)
    assert update_install.acknowledge_ready(target, first.readiness_token)
    monkeypatch.setattr(Path, "unlink", original)
    state = json.loads(marker.read_text())
    state[field] = value
    marker.write_text(json.dumps(state))
    sentinel = target.parent / "sentinel.exe"
    sentinel.write_bytes(executable(b"sentinel"))
    second = update_install.install_verified(staged, target, digest, lambda path, token: pytest.fail("must not launch"))
    assert not second.success
    assert first.backup.read_bytes() == executable(b"old")
    assert sentinel.read_bytes() == executable(b"sentinel")
    assert target.read_bytes() == executable(b"new")
    assert json.loads(marker.read_text()) == state


def test_idempotent_finalizer_requires_matching_operation_token(files, monkeypatch):
    staged, target, digest = files
    first = update_install.install_verified(staged, target, digest, lambda path, token: None)
    original = Path.unlink

    def locked(path, *args, **kwargs):
        if path == first.backup:
            raise PermissionError("backup lock")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked)
    assert update_install.acknowledge_ready(target, first.readiness_token)
    monkeypatch.setattr(Path, "unlink", original)
    assert not update_install.finalize_ready(target, token="0" * 64)
    assert first.backup.exists()
    assert update_install.finalize_ready(target, token=first.readiness_token)
    assert not first.backup.exists()
    assert not update_install.readiness_path(target).exists()
    assert update_install.finalize_ready(target, token=first.readiness_token)


def test_older_helper_never_waits_on_or_deletes_a_later_update_marker(files, monkeypatch, helper_security):
    staged, target, digest = files
    workspace = target.parent / "panacea-update-fixture"
    workspace.mkdir()
    (workspace / "staged.exe").write_bytes(staged.read_bytes())
    (workspace / "job.json").write_text(json.dumps({"target": str(target), "version": "1.49.0"}))
    monkeypatch.setattr(update_install, "_assert_helper_context", lambda path: None)
    monkeypatch.setattr(update_install, "_assert_admin_directory", lambda path: None)
    later = []

    class Client:
        def __init__(self, repo, current_version):
            pass
        def check(self):
            from modules.updater import Release
            return Release("1.49.0", "url", "url", 512, "url")
        def fetch_checksum(self, release):
            return digest

    class Process:
        def poll(self):
            return None
        def terminate(self):
            pytest.fail("older ready process must never be terminated")

    def launch(arguments, **kwargs):
        assert update_install.acknowledge_ready(target, arguments[2])
        staged.write_bytes(executable(b"later"))
        later.append(update_install.install_verified(staged, target, hashlib.sha256(staged.read_bytes()).hexdigest(),
                                                     lambda path, token: None))
        return Process()

    code = update_install.run_update_helper(workspace, client_factory=Client, popen=launch, timeout=0)
    assert code == 0
    assert later[0].success
    assert target.read_bytes() == executable(b"later")
    assert later[0].backup.read_bytes() == executable(b"new")
    assert json.loads(update_install.readiness_path(target).read_text())["token"] == later[0].readiness_token
