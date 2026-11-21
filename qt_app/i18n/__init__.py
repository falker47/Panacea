"""Catalog translations and locale-aware formatting used by the Qt shell."""
from __future__ import annotations

from functools import lru_cache
import json
import math
from pathlib import Path
import re

from PySide6.QtCore import QDateTime, QLocale, QObject, Property, Qt, Signal, Slot


@lru_cache(maxsize=2)
def messages(language: str) -> dict[str, str]:
    filename = "it.json" if language == "it" else "en.json"
    return json.loads(Path(__file__).with_name(filename).read_text(encoding="utf-8"))


class I18n(QObject):
    languageChanged = Signal()

    def __init__(self, settings, language_override=None, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._override = language_override if language_override in ("it", "en") else None
        self._language = ""
        self._resolve()
        settings.languageChoiceChanged.connect(self._resolve)

    def _resolve(self):
        language = self._override or self._settings.resolved_language()
        if language != self._language:
            self._language = language
            self._locale = QLocale("it_IT" if language == "it" else "en_US")
            self._messages = messages(language)
            self.languageChanged.emit()

    @Property(str, notify=languageChanged)
    def language(self):
        return self._language

    @Slot(str, result=str)
    @Slot(str, "QVariantMap", result=str)
    def t(self, key, params=None):
        template = self._messages.get(key, key)
        if not params:
            return template
        return re.sub(r"\{(\w+)\}", lambda m: str(params.get(m[1], m[0])), template)

    @Slot(float, result=str)
    @Slot(float, int, result=str)
    def number(self, value, digits=0):
        if not math.isfinite(value):
            return self.t("format.unknown")
        return self._locale.toString(float(value), "f", max(0, min(9, digits)))

    @Slot(float, result=str)
    def bytes(self, value):
        if not math.isfinite(value) or not 0 <= value < 2**63:
            return self.t("format.unknown")
        return self._locale.formattedDataSize(int(value), 1, QLocale.DataSizeTraditionalFormat)

    @Slot(str, result=str)
    def dateTime(self, iso):
        value = QDateTime.fromString(iso, Qt.ISODateWithMs)
        if not value.isValid():
            return self.t("format.unknown")
        return self._locale.toString(value.toLocalTime(), QLocale.ShortFormat)

    @Slot(str, result=str)
    def relativeTime(self, iso):
        value = QDateTime.fromString(iso, Qt.ISODateWithMs)
        if not value.isValid():
            return self.t("format.unknown")
        seconds = value.secsTo(QDateTime.currentDateTimeUtc())
        elapsed = abs(seconds)
        if elapsed < 60:
            return self.t("time.now")
        for unit, duration in (("day", 86400), ("hour", 3600), ("minute", 60)):
            if elapsed >= duration:
                count = elapsed // duration
                direction = "ago" if seconds >= 0 else "in"
                key = f"time.{direction}.{unit}{'s' if count != 1 else ''}"
                return self.t(key, {"count": self.number(count)})
