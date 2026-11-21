"""Battery charge and the physical power state must both be perceptible."""
import unittest

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from qt_app.icon_provider import NavigationIconProvider


class BatteryIconTests(unittest.TestCase):
    def setUp(self):
        self.provider = NavigationIconProvider()

    def image(self, name):
        return self.provider.requestImage(name, QSize(), QSize(96, 96))

    def test_report_is_the_seventy_percent_gold_shortcut_and_not_a_live_reading(self):
        actual = self.image("battery-report/detail")
        self.assertEqual(actual, self.image("battery-70-unplugged/e4c579"))
        self.assertEqual(actual.pixelColor(40, 46).name(), "#e4c579")
        self.assertNotEqual(actual, self.image("battery/detail"))

    def test_charge_progresses_monotonically_through_zero_half_and_full(self):
        fill = []
        for percent in (0, 15, 50, 75, 100):
            image = self.image(f"battery-{percent}-unplugged/detail")
            self.assertFalse(image.isNull())
            fill.append(sum(image.pixelColor(x, 48).alpha() > 127 for x in range(18, 72)))
        self.assertEqual(fill[0], 0)
        self.assertEqual(fill[-1], 54)
        self.assertEqual(len(set(fill)), len(fill))
        self.assertEqual(fill, sorted(fill))

    def test_power_state_changes_shape_even_in_a_monochrome_system_theme(self):
        masks = {bytes(self.image(f"battery-50-{state}/ffffff").convertToFormat(QImage.Format_Alpha8).constBits())
                 for state in ("charging", "plugged", "unplugged")}
        self.assertEqual(len(masks), 3)

    def test_out_of_range_and_unknown_states_fail_closed(self):
        for invalid in ("battery-101-charging/detail", "battery--5-plugged/detail",
                        "battery-30-other/detail", "battery-30-charging/active"):
            self.assertTrue(self.image(invalid).isNull(), invalid)


if __name__ == "__main__":
    unittest.main()
