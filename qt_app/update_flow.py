"""Protected production update lifecycle, separate from the Qt widget thread.

Only the application's own frozen Panacea.exe may use the in-place updater.
Never accept an executable path, release, checksum, or URL from QML.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import threading

from modules.updater import UpdateClient, UpdateVerificationError
from version import GITHUB_REPO, VERSION


def production_identity(*, frozen=None, executable=None):
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    path = Path(sys.executable if executable is None else executable)
    return frozen and path.name == "Panacea.exe"


class QtUpdateFlow:
    """Testable stateful adaptor to the existing SHA-256/ACL/rollback updater."""

    def __init__(self, *, frozen=None, executable=None, client_factory=UpdateClient,
                 launch=None, directory=None):
        self.executable = Path(sys.executable if executable is None else executable)
        self.frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
        self.client_factory = client_factory
        self.launch = launch
        self.directory_root = directory
        self.client = None
        self.release = None
        self._staged = None
        self._directory = None
        self.cancel_event = threading.Event()

    @property
    def install_eligible(self):
        return production_identity(frozen=self.frozen, executable=self.executable)

    def check(self):
        """HTTP read-only. The UpdateClient owns the GitHub trust boundary."""
        self.client = self.client_factory(GITHUB_REPO, VERSION)
        self.release = self.client.check()
        return self.release

    def reset_cancel(self):
        self.cancel_event.clear()

    def cancel_download(self):
        self.cancel_event.set()

    def download(self, progress=None):
        if not self.install_eligible:
            raise UpdateVerificationError("QA and source builds cannot install production updates.")
        if self.release is None or self.client is None:
            raise UpdateVerificationError("No newer trusted GitHub release has been selected.")
        if self._directory is not None:
            raise UpdateVerificationError("An update is already staged.")
        self.cancel_event.clear()
        self._directory = Path(tempfile.mkdtemp(prefix="Panacea-Qt-update-", dir=self.directory_root))

        def report(received, total):
            if progress:
                progress(received, total)
            return not self.cancel_event.is_set()

        try:
            self._staged = self.client.download(self.release, self._directory, report)
            if self.cancel_event.is_set():
                from modules.updater import UpdateCancelled
                raise UpdateCancelled("Update download cancelled.")
            return self._staged
        except Exception:
            self.cleanup()
            raise

    def start_verified_install(self):
        if not self.install_eligible or self.client is None or self.release is None:
            raise UpdateVerificationError("Production executable and trusted release are required.")
        if self._staged is None:
            raise UpdateVerificationError("No verified download to install.")
        from modules.update_install import start_self_update
        helper = self.launch or start_self_update
        # The backend performs a second checksum/PE check and protected ACL and
        # path validation before a helper is started. Never accept paths from UI.
        job = helper(self._staged, self.executable, self.release, self.client)
        self.cleanup()
        return job

    def cleanup(self):
        staged, directory = self._staged, self._directory
        self._staged = None
        self._directory = None
        if directory is None:
            return
        # Only the single exact generated candidate may be removed; never
        # enumerate, recursively delete or touch protected helper/backup files.
        from modules.updater import _assert_plain_path
        _assert_plain_path(directory)
        if staged is not None:
            staged = Path(staged)
            if staged.parent != directory:
                raise UpdateVerificationError("Update candidate moved outside its staging directory.")
            _assert_plain_path(staged)
            staged.unlink(missing_ok=True)
        directory.rmdir()
