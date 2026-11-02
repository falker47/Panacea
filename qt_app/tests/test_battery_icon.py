"""Dynamic battery pictogram uses the exact V2 drawing, with allowlisting."""
import unittest
from PySide6.QtCore import QSize
from qt_app.icon_provider import NavigationIconProvider


class BatteryIconTests(unittest.TestCase):
    def test_battery_fill_and_power_state_change_render(self):
        provider = NavigationIconProvider()
        full = provider.requestImage("battery-100-plugged/detail", QSize(), QSize(96, 96))
        empty = provider.requestImage("battery-0-unplugged/detail", QSize(), QSize(96, 96))
        charging = provider.requestImage("battery-70-charging/detail", QSize(), QSize(96, 96))
        self.assertFalse(full.isNull())
        self.assertFalse(charging.isNull())
        self.assertNotEqual(full.pixelColor(60, 47), empty.pixelColor(60, 47))
        self.assertNotEqual(charging.pixelColor(47, 45), empty.pixelColor(47, 45))

    def test_out_of_range_and_unknown_states_fail_closed(self):
        provider = NavigationIconProvider()
        for invalid in ("battery-101-charging/detail", "battery--5-plugged/detail",
                        "battery-30-other/detail", "battery-30-charging/active"):
            self.assertTrue(provider.requestImage(invalid, QSize(), QSize()).isNull())


if __name__ == "__main__":
    unittest.main()
