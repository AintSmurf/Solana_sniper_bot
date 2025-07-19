import logging
import os
import threading
from logging.handlers import RotatingFileHandler

try:
    import coloredlogs
except ImportError:
    coloredlogs = None
import time
import shutil
import glob




class LoggingHandler:
    _logger = None
    log_lock = threading.Lock()
    backup_thread_started = False

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

        if not LoggingHandler.backup_thread_started:
                LoggingHandler.backup_thread_started = True
                threading.Thread(
                    target=LoggingHandler._background_log_backup_runner,
                    daemon=True
                ).start()
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
    @staticmethod
    def get_token_logger(token_mint: str):
        """Returns a per-token logger for post-buy audit."""
        logger_name = f"token_logger_{token_mint}"
        token_logger = logging.getLogger(logger_name)
        token_logger.setLevel(logging.DEBUG)

        if not token_logger.handlers:
            token_log_file = os.path.join("logs", "tokens", f"{token_mint}.log")
            os.makedirs(os.path.dirname(token_log_file), exist_ok=True)

            file_handler = RotatingFileHandler(
                token_log_file, maxBytes=25_000_000, backupCount=2, encoding="utf-8"
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(message)s"
                )
            )
            token_logger.addHandler(file_handler)

        return token_logger
    @staticmethod
    def _background_log_backup_runner():
        """Background thread to periodically move old logs to backups."""
        while True:
            try:
                # 📦 Backup info logs
                LoggingHandler._backup_old_logs(
                    os.path.join("logs", "info.log"),
                    os.path.join("logs", "backups", "info"),
                    prefix="info_"
                )
                # 📦 Backup debug logs
                LoggingHandler._backup_old_logs(
                    os.path.join("logs", "debug", "debug.log"),
                    os.path.join("logs", "backups", "debug"),
                    prefix="debug_"
                )
                # 📦 Backup console logs
                LoggingHandler._backup_old_logs(
                    os.path.join("logs", "console_logs", "console.info"),
                    os.path.join("logs", "backups", "console"),
                    prefix="console_"
                )
            except Exception as e:
                print(f"[LogBackupThread] Error during backup: {e}")
            time.sleep(6000)  # 🔄 Repeat every 10 minutes

    @staticmethod
    def _backup_old_logs(log_base_path: str, backup_dir: str, prefix: str = "", keep_recent: int = 5):
        """
        Backup older rotated logs (e.g., info.log.6+) and move them to a backup folder.
        Keeps only the most recent `keep_recent` logs in-place.
        """
        os.makedirs(backup_dir, exist_ok=True)

        rotated_logs = sorted(
            glob.glob(f"{log_base_path}.*"),
            key=lambda f: int(f.split('.')[-1]) if f.split('.')[-1].isdigit() else -1
        )

        # ❌ Not enough logs to trigger backup
        if len(rotated_logs) <= keep_recent:
            return

        # 🎯 Move older ones only (e.g., keep .1 to .5, move .6+)
        logs_to_backup = rotated_logs[:-keep_recent]

        for log_path in logs_to_backup:
            filename = os.path.basename(log_path)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            dest_filename = f"{prefix}{timestamp}_{filename}"
            dest_path = os.path.join(backup_dir, dest_filename)
            try:
                shutil.move(log_path, dest_path)
            except Exception as e:
                print(f"⚠️ Failed to backup {log_path}: {e}")

    @staticmethod
    def get_named_logger(name: str):
        """Returns a custom logger with the same base config as the main app logger."""
        base_logger = LoggingHandler.get_logger()
        named_logger = logging.getLogger(name)
        named_logger.setLevel(base_logger.level)

        if not named_logger.handlers:
            for handler in base_logger.handlers:
                named_logger.addHandler(handler)

        return named_logger
