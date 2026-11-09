"""Application logging: coloured console output plus a rotating log file."""

import logging
import logging.handlers
import sys
from pathlib import Path

from sentio.config import LOG_DIR


class ColorFormatter(logging.Formatter):
    """ANSI colour codes for console log levels."""

    COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = "%s%s%s" % (color, record.levelname, self.RESET)
        return super().format(record)


def setup_logging(
    level=logging.INFO,
    log_file=None,
    max_bytes=5 * 1024 * 1024,  # 5 MB
    backup_count=3,
):
    """
    Configure root logger with:
      - Coloured console handler
      - Optional rotating file handler

    Call once at application startup (e.g. in app.py or train script).

    Args:
        level        : Logging level (default INFO)
        log_file     : Path to log file. If None, logs/tutor.log is used.
        max_bytes    : Max log file size before rotation
        backup_count : Number of rotated log files to keep
    """
    log_fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(ColorFormatter(log_fmt, datefmt=date_fmt))
    root.addHandler(console)

    # File handler
    log_path = Path(log_file) if log_file else LOG_DIR / "tutor.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(log_fmt, datefmt=date_fmt))
    root.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return root
