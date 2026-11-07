"""Use the same Windows message-box family as Tk's legacy confirmations.

Only presentation lives here. Execution still requires the bridge's unchanged
single-use confirmation, privilege, guard and updater-integrity checks.
"""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QObject, QTimer


def windows_message_box(owner, title, detail):
    show = ctypes.windll.user32.MessageBoxW
    show.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
    show.restype = ctypes.c_int
    # YES/NO, warning icon, default NO, modal to the owning Qt window.
    result = show(owner, detail, title, 0x4 | 0x30 | 0x100)
    if result == 0:
        raise OSError("Windows confirmation dialog could not be shown")
    return result == 6


class NativeConfirmations(QObject):
    def __init__(self, maintenance, updater, owner, *, show=windows_message_box, parent=None):
        super().__init__(parent)
        self._maintenance = maintenance
        self._updater = updater
        self._owner = owner
        self._show = show
        self._scheduled = False
        self._opening = False
        maintenance.changed.connect(self._changed)
        if updater is not None:
            updater.changed.connect(self._changed)

    def _changed(self):
        if self._scheduled or self._opening:
            return
        if self._maintenance.awaitingConfirmation or (self._updater is not None and self._updater.pending):
            self._scheduled = True
            QTimer.singleShot(0, self._present)

    def _present(self):
        self._scheduled = False
        if self._opening:
            return
        maintenance = self._maintenance
        updater = self._updater
        self._opening = True
        try:
            if maintenance.awaitingConfirmation:
                token = maintenance._pending
                title, _, detail = maintenance.details.partition("\n")
                try:
                    accepted = self._show(self._owner(), title, detail)
                except Exception as exc:
                    maintenance._output = "Confirmation unavailable: " + str(exc)
                    maintenance.reject()
                    return
                if token == maintenance._pending and maintenance.awaitingConfirmation:
                    maintenance.confirm() if accepted else maintenance.reject()
            elif updater is not None and updater.pending:
                version = updater.availableVersion
                italian = maintenance._language == "it"
                title = "Installa aggiornamento verificato" if italian else "Install verified update"
                detail = (("Scaricare, verificare SHA-256 e installare Panacea " if italian else
                           "Download, verify SHA-256 and install Panacea ") + version + "?\n" +
                          ("L'applicazione esistente rimane disponibile fino alla conferma del nuovo avvio." if italian else
                           "The existing application remains available until new startup is confirmed."))
                try:
                    accepted = self._show(self._owner(), title, detail)
                except Exception:
                    updater.reject()
                    return
                if updater.pending and version == updater.availableVersion:
                    updater.confirmInstall() if accepted else updater.reject()
        finally:
            self._opening = False
