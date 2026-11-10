import struct
import unittest


class OriginalIconPayload(unittest.TestCase):
    def test_other_icon_resources_cannot_satisfy_brand_verification(self):
        from qt_app.verify_icon import verify_payloads
        image = b"original Panacea icon image"
        ico = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 32, 32, 0, 0, 1, 32, len(image), 22) + image
        with self.assertRaisesRegex(ValueError, "original"):
            verify_payloads([b"some other icon"], ico)
        self.assertEqual(verify_payloads([image], ico), 1)

    def test_invalid_image_offset_is_rejected(self):
        from qt_app.verify_icon import verify_payloads
        ico = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 32, 32, 0, 0, 1, 32, 10, 9999)
        with self.assertRaises(ValueError):
            verify_payloads([], ico)

    def test_only_images_referenced_by_the_default_group_are_verified(self):
        from qt_app.verify_icon import group_payloads
        group = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHIH", 32, 32, 0, 0, 1, 32, 5, 7)
        self.assertEqual(group_payloads(group, {7: [b"other"], 8: [b"brand"]}), [b"other"])
