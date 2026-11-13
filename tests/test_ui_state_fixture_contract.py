"""The native Tk screenshot fixture must implement the maintenance lease API.

This checks only an inert test double. The actual Windows journal and mutex
are exercised by separate native integration tests.
"""
import unittest

from scripts.ui_state_check import InertMaintenanceGuard


class InertMaintenanceFixtureContracts(unittest.TestCase):
    def test_verified_fixture_operation_provides_the_real_lease_interface(self):
        fixture = InertMaintenanceGuard()
        self.assertFalse(fixture.is_blocked())
        with fixture.operation() as lease:
            self.assertTrue(hasattr(lease, "resolve"))
            lease.resolve()
        self.assertFalse(fixture.is_blocked())

    def test_fixture_cannot_write_a_real_unknown_completion_marker(self):
        fixture = InertMaintenanceGuard()
        with self.assertRaises(AssertionError):
            fixture.mark_unknown()


if __name__ == "__main__":
    unittest.main()
