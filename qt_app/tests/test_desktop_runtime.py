"""End-to-end input, section routing, accessibility and localized fixture states."""
import unittest

from qt_app.feature_catalog import ACTIONS as FEATURE_ACTIONS
from qt_app.maintenance import ACTIONS
from qt_app.tests.qml_probe import probe


class DesktopRuntimeTests(unittest.TestCase):
    def test_every_catalog_operation_can_be_prepared_in_two_clicks(self):
        for language in ("it", "en"):
            # Optional 2.2 feature actions need a target chosen on their own page.
            self.assertEqual(set(probe("actions", language)["actions"]), ACTIONS - FEATURE_ACTIONS.keys())

    def test_bilingual_palette_matches_exact_action_and_requires_consent(self):
        for language in ("en", "it"):
            data = probe("palette", language)
            self.assertEqual((data["section"], data["action"], data["executions"]), ("cleanup", "temp_clean", 0))
            self.assertEqual(data["shortcuts"], ["home", "cleanup", "startup", "repair", "performance", "guided", "settings"])

    def test_close_requests_cancellation_and_show_is_explicit(self):
        data = probe("closing")
        self.assertEqual((data["before_show"], data["after_show"]), ("settings", "repair"))
        self.assertFalse(data["maintenance_close"])
        self.assertEqual(data["cancels"], 1)
        self.assertFalse(data["helper_close"])
        self.assertTrue(data["visible"])

    def test_tab_reaches_navigation_palette_and_section_controls(self):
        for scale in (1, 1.5):
            data = probe("keyboard", "it", scale)
            self.assertIn("nav_guided", data["focus"])
            self.assertIn("openPalette", data["focus"])
            self.assertIn("action_quick_cleanup", data["focus"])
            self.assertEqual(data["widths"], [64, 64, 240, 240, 240])
            self.assertEqual(data["collapsed"], 64)

    def test_all_fixture_states_render_in_each_language_with_accessible_geometry(self):
        for language in ("it", "en"):
            self.assertEqual(probe("localize", language)["count"], 90)

    def test_update_page_exposes_release_notes_status_and_verified_install_confirmation(self):
        for lang, heading, available in (("en", "Navigation", "available"), ("it", "Navigazione", "disponibile")):
            data = probe("updates", lang)
            self.assertIn(heading, data["notes"])
            self.assertIn(available, data["status"])
            self.assertTrue(data["pending"])
            self.assertFalse(data["installing"])
            self.assertFalse(data["repeated"])
