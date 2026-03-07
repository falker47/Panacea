import logging
import os


class Logger:
    """Singleton logger that writes to both console and file."""

    _instance: "Logger | None" = None

    def __new__(cls) -> "Logger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        log_dir = os.path.join(
            os.environ["USERPROFILE"], "Documents", "SystemOptimizer")
        os.makedirs(log_dir, exist_ok=True)

        log_file = os.path.join(log_dir, "log.txt")

        self.logger = logging.getLogger("PanaceaLogger")
        self.logger.setLevel(logging.INFO)

        # Avoid adding duplicate handlers when module is reloaded
        if not self.logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s")

            fh = logging.FileHandler(log_file)
            fh.setLevel(logging.INFO)
            fh.setFormatter(formatter)

            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch.setFormatter(formatter)

            self.logger.addHandler(fh)
            self.logger.addHandler(ch)

    def log(self, message: str, level: str = "INFO") -> None:
        level_upper = level.upper()
        if level_upper == "ERROR":
            self.logger.error(message)
        elif level_upper == "WARNING":
            self.logger.warning(message)
        else:
            self.logger.info(message)

    def get_log_path(self) -> str:
        return os.path.join(
            os.environ["USERPROFILE"], "Documents", "SystemOptimizer", "log.txt")
