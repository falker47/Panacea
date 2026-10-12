import logging
from unittest.mock import patch


def test_unwritable_log_directory_does_not_prevent_startup(tmp_path, monkeypatch):
    from modules.logger import Logger
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    log = logging.getLogger("PanaceaLogger")
    original_handlers = log.handlers[:]
    original_instance = Logger._instance
    log.handlers.clear()
    Logger._instance = None
    try:
        with patch("logging.FileHandler", side_effect=PermissionError("read-only directory")):
            logger = Logger()
            logger.log("Application started.")
        assert log.handlers
    finally:
        for handler in log.handlers:
            handler.close()
        log.handlers[:] = original_handlers
        Logger._instance = original_instance
