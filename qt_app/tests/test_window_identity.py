import unittest


class WindowIdentity(unittest.TestCase):
    def test_qa_and_source_windows_never_share_the_stable_taskbar_identity(self):
        from qt_app.branding import application_id
        self.assertEqual(application_id(smoke=True, frozen=True, executable="Panacea.exe"), "Panacea.QtQA")
        self.assertEqual(application_id(smoke=False, frozen=True, executable="PanaceaQtCandidate.exe"), "Panacea.QtQA")
        self.assertEqual(application_id(smoke=False, frozen=False, executable="python.exe"), "Panacea.QtQA")
        self.assertEqual(application_id(smoke=False, frozen=True, executable="Panacea.exe"), "Panacea.Desktop")
