import logging
import os
from datetime import datetime

class Logger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        log_dir = os.path.join(os.environ['USERPROFILE'], 'Documents', 'SystemOptimizer')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_file = os.path.join(log_dir, 'log.txt')
        
        self.logger = logging.getLogger('PanaceaLogger')
        self.logger.setLevel(logging.INFO)
        
        # File handler
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def log(self, message, level="INFO"):
        if level.upper() == "INFO":
            self.logger.info(message)
        elif level.upper() == "ERROR":
            self.logger.error(message)
        elif level.upper() == "WARNING":
            self.logger.warning(message)
        else:
            self.logger.info(message)

    def get_log_path(self):
        return os.path.join(os.environ['USERPROFILE'], 'Documents', 'SystemOptimizer', 'log.txt')
