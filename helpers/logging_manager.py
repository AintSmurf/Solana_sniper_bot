import logging
import os
import threading
from logging.handlers import RotatingFileHandler

try:
    import coloredlogs
except ImportError:
    coloredlogs = None


class LoggingHandler:
    _logger = None
    log_lock = threading.Lock()

    @staticmethod
    def _setup_logger():
        """Setup a thread-safe logging system with proper separation of logs."""

        # 📂 Log Directories
        LOG_DIR = "logs"
        DEBUG_DIR = os.path.join(LOG_DIR, "debug")
        CONSOLE_LOG_DIR = os.path.join(LOG_DIR, "console_logs")

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
            log_handler.setLevel(logging.INFO)
            log_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
                )
            )
            logger.addHandler(log_handler)

            # 🛠️ DEBUG Log File Handler (Only stores DEBUG logs)
            debug_handler = RotatingFileHandler(
                debug_file, maxBytes=2_500_000_000, backupCount=10, encoding="utf-8"
            )
            debug_handler.setLevel(logging.DEBUG)
            debug_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
                )
            )
            logger.addHandler(debug_handler)

            # 📢 Console Log File Handler
            console_handler = RotatingFileHandler(
                console_log_file, maxBytes=50_000_000, backupCount=5, encoding="utf-8"
            )
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
                )
            )
            logger.addHandler(console_handler)

            # 🖥️ Terminal stream handler (will be colored below)
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.INFO)
            logger.addHandler(stream_handler)

            # 🎨 Colored logs (terminal only)
            if coloredlogs:
                coloredlogs.install(
                    level="INFO",
                    logger=logger,
                    fmt="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
                    level_styles={
                        "debug": {"color": "cyan"},
                        "info": {"color": "green"},
                        "warning": {"color": "yellow"},
                        "error": {"color": "red"},
                        "critical": {"color": "magenta"},
                    },
                )
            else:
                stream_handler.setFormatter(
                    logging.Formatter(
                        "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
                    )
                )

        return logger

    @staticmethod
    def get_logger():
        """Returns the singleton logger instance (thread-safe)."""
        if LoggingHandler._logger is None:
            with LoggingHandler.log_lock:
                if LoggingHandler._logger is None:
                    LoggingHandler._logger = LoggingHandler._setup_logger()
        return LoggingHandler._logger

    @staticmethod
    def get_special_debug_logger():
        """Returns a separate logger for special debug cases, logs to file only."""
        special_logger = logging.getLogger("special_debug_logger")
        special_logger.setLevel(logging.DEBUG)

        if not special_logger.handlers:
            special_debug_file = os.path.join("logs", "debug", "special_debug.log")
            os.makedirs(os.path.dirname(special_debug_file), exist_ok=True)

            file_handler = RotatingFileHandler(
                special_debug_file,
                maxBytes=100_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
                )
            )
            special_logger.addHandler(file_handler)

        return special_logger
