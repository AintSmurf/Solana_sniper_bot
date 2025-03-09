import logging
import os
import threading
from logging.handlers import RotatingFileHandler


class LoggingHandler:
    _logger = None
    log_lock = threading.Lock()

    @staticmethod
    def _setup_logger():
        """Setup a thread-safe logging system with proper separation of logs."""

        # 📂 Log Directories
        LOG_DIR = "logs"
        DEBUG_DIR = "logs/debug"
        CONSOLE_LOG_DIR = "logs/console_logs"

        os.makedirs(LOG_DIR, exist_ok=True)
        os.makedirs(DEBUG_DIR, exist_ok=True)
        os.makedirs(CONSOLE_LOG_DIR, exist_ok=True)

        # Log File Paths
        log_file = os.path.join(LOG_DIR, "info.log")
        debug_file = os.path.join(DEBUG_DIR, "debug.log")
        console_log_file = os.path.join(CONSOLE_LOG_DIR, "console.info")

        # Create logger (Singleton)
        logger = logging.getLogger("app_logger")
        logger.setLevel(logging.DEBUG)

        # 🔥 Prevent duplicate handlers
        if not logger.handlers:

            # 📄 INFO Log File Handler (Only stores INFO & higher)
            log_handler = RotatingFileHandler(
                log_file, maxBytes=250_000_000, backupCount=5, encoding="utf-8"
            )
            log_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            log_handler.setLevel(logging.INFO)  # 🚨 Only logs INFO & higher (no DEBUG)
            logger.addHandler(log_handler)

            # 🛠️ DEBUG Log File Handler (Only stores DEBUG logs)
            debug_handler = RotatingFileHandler(
                debug_file, maxBytes=250_000_000, backupCount=5, encoding="utf-8"
            )
            debug_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            debug_handler.setLevel(logging.DEBUG)  # 🚨 Only logs DEBUG messages
            logger.addHandler(debug_handler)

            # 📢 Console Log File Handler (Only stores INFO & WARNINGS)
            console_handler = RotatingFileHandler(
                console_log_file, maxBytes=50_000_000, backupCount=5, encoding="utf-8"
            )
            console_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            console_handler.setLevel(logging.INFO)  # 🚨 Only logs INFO & WARNINGS
            logger.addHandler(console_handler)

            # 🖥️ Console Handler (Real-time logging to terminal)
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            stream_handler.setLevel(logging.INFO)  # 🚨 Only logs INFO & higher
            logger.addHandler(stream_handler)

        return logger

    @staticmethod
    def get_logger():
        """Returns the singleton logger instance (thread-safe)."""
        if LoggingHandler._logger is None:
            with LoggingHandler.log_lock:  # Ensure thread safety when initializing logger
                if LoggingHandler._logger is None:
                    LoggingHandler._logger = LoggingHandler._setup_logger()
        return LoggingHandler._logger
