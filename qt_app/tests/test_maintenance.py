"""No Windows changes: all maintenance tests use isolated fake managers."""
import threading
import unittest
from types import SimpleNamespace

from qt_app.maintenance import MaintenanceService


class FakeGuard:
    def __init__(self):
        self.blocked = False
        self.marked = 0
        self.last_error = "Reboot required"

    def is_blocked(self):
        return self.blocked

    def mark_unknown(self):
        self.marked += 1
        self.blocked = True
        return True


class MaintenanceContracts(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.guard = FakeGuard()
        events = self.events

        class Commands:
            completion_unknown = False
            restart_required = False

            def run_command_stream(self, command, description, log):
                events.append(("command", command))
                log(description)
                return True

        class Cleanup:
            def __init__(self):
                self.last_result = SimpleNamespace(preview=False, skipped=[], errors=[])

            def clean_temp_files(self, progress_callback=None):
                events.append("temp")
                return 4, 1024

            def clean_browser_caches(self):
                events.append("browsers")
                return 2, 512

            def empty_recycle_bin(self):
                events.append("bin")
                return True, "Bin emptied"

            def open_disk_cleanup(self):
                events.append("cleanmgr")
                return True

        class Disk:
            completion_unknown = False

            def get_drive_info(self):
                return [{"letter": "C:", "available": True},
                        {"letter": "D:", "available": False}]

            def analyze_optimize_drive(self, letter, progress_callback=None):
                events.append(("disk", letter))
                return True

            def open_optimize_gui(self):
                events.append("dfrgui")
                return True

        class Restore:
            def create_restore_point(self, description):
                events.append("restore")
                return True, "Verified restore point"

        class Perf:
            def set_turbo(self, enabled):
                events.append(("turbo", enabled))
                return True, "Originals saved/restored"

            def set_power_plan(self, enabled):
                events.append(("power", enabled))
                return True, "Updated"

        self.commands = Commands()
        self.cleanup = Cleanup()
        self.disk = Disk()
        self.restore = Restore()
        self.perf = Perf()
        self.service = MaintenanceService(
            factories={"guard": lambda: self.guard, "commands": lambda: self.commands,
                       "cleanup": lambda: self.cleanup, "disk": lambda: self.disk,
                       "restore": lambda: self.restore, "performance": lambda: self.perf},
            is_admin=lambda: True, platform="nt",
        )

    def tearDown(self):
        self.service.close()

    def confirm(self, action, drive=""):
        return self.service.prepare(action, drive)["nonce"]

    def test_no_action_without_fresh_one_time_confirmation(self):
        with self.assertRaises(ValueError):
            self.service.execute("not-a-token")
        with self.assertRaises(ValueError):
            self.service.prepare("powershell -EncodedCommand ...")
        self.assertEqual(self.events, [])
        token = self.confirm("sfc")
        self.assertEqual(self.service.execute(token)["status"], "completed")
        with self.assertRaises(ValueError):
            self.service.execute(token)
        self.assertEqual(self.events, [("command", "sfc /scannow")])

    def test_drive_is_revalidated_after_confirmation(self):
        with self.assertRaises(ValueError):
            self.service.prepare("drive_optimize", "C: & del *")
        with self.assertRaises(ValueError):
            self.service.prepare("sfc", "C:")
        token = self.confirm("drive_optimize", "D:")
        with self.assertRaises(ValueError):
            self.service.execute(token)
        token = self.confirm("drive_optimize", "C:")
        self.assertEqual(self.service.execute(token)["status"], "completed")
        self.assertEqual(self.events, [("disk", "C:")])

    def test_guard_and_elevation_fail_closed_without_side_effects(self):
        self.guard.blocked = True
        token = self.confirm("temp_clean")
        with self.assertRaises(RuntimeError):
            self.service.execute(token)
        self.assertEqual(self.events, [])
        self.guard.blocked = False
        self.service._is_admin = lambda: False
        token = self.confirm("temp_clean")
        with self.assertRaises(PermissionError):
            self.service.execute(token)
        self.assertEqual(self.events, [])

    def test_failed_or_skipped_cleanup_not_success(self):
        self.cleanup.last_result.skipped = ["locked file"]
        token = self.confirm("temp_clean")
        result = self.service.execute(token)
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["success"])
        self.assertEqual(result["skipped"], 1)

    def test_completion_unknown_persists_guard_and_blocks_next_operation(self):
        def uncertain(*_):
            self.commands.completion_unknown = True
            return False
        self.commands.run_command_stream = uncertain
        result = self.service.execute(self.confirm("sfc"))
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(self.guard.marked, 1)
        with self.assertRaises(RuntimeError):
            self.service.execute(self.confirm("dns_flush"))

    def test_cancelled_sequence_does_not_run_next_step(self):
        self.service.cancel()
        # A new explicit request resets cancellation; cancellation during the first step stops later steps.
        original = self.restore.create_restore_point
        def cancel_after_restore(description):
            result = original(description)
            self.service.cancel()
            return result
        self.restore.create_restore_point = cancel_after_restore
        result = self.service.execute(self.confirm("resurrection"))
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(self.events, ["restore"])

    def test_restore_point_is_hard_gate(self):
        self.restore.create_restore_point = lambda description: (False, "Protection disabled")
        result = self.service.execute(self.confirm("resurrection"))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["steps"]), 1)
        self.assertEqual(self.events, [])

    def test_quick_cleanup_tracks_all_steps_and_external_utility(self):
        result = self.service.execute(self.confirm("quick_cleanup"))
        self.assertEqual(result["status"], "completed")
        self.assertEqual([e for e in self.events if isinstance(e, str)],
                         ["temp", "bin", "cleanmgr"])
        self.assertIn("Windows Disk Cleanup opened", result["message"])

    def test_reentrant_confirmation_does_not_overlap_running_work(self):
        enter, release = threading.Event(), threading.Event()
        def slow(*_):
            enter.set()
            release.wait(2)
            return True
        self.commands.run_command_stream = slow
        token = self.confirm("sfc")
        thread = threading.Thread(target=lambda: self.service.execute(token))
        thread.start()
        try:
            self.assertTrue(enter.wait(2))
            with self.assertRaises(RuntimeError):
                self.service.prepare("dns_flush")
        finally:
            release.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
