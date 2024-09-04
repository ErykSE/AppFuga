import logging
import os
from logging.handlers import RotatingFileHandler
from functools import partial


class CustomLogger:
    """
    Klasa definiująca loggery służące do lepszej analizy algorytmu.
    """

    @staticmethod
    def setup_logger(name, log_file, level=logging.INFO):
        # Sprawdź, czy plik istnieje
        if os.path.exists(log_file):
            # Jeśli istnieje, usuń go
            os.remove(log_file)

        # Utwórz logger
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Utwórz handler dla pliku
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)

        # Dodaj handler do loggera
        logger.addHandler(file_handler)

        # Dodajemy nowe metody do loggera
        def highlight(logger, msg):
            logger._log(logging.INFO, f"\n{'=' * 50}\n{msg}\n{'=' * 50}", ())

        def section(logger, name):
            logger._log(logging.INFO, f"\n{'-' * 20} {name} {'-' * 20}", ())

        def important(logger, msg):
            logger._log(logging.INFO, f"!!! {msg} !!!", ())

        def success(logger, msg):
            logger._log(logging.INFO, f"[SUCCESS] {msg}", ())

        def custom_warning(logger, msg):
            logger._log(logging.WARNING, f"[WARNING] {msg}", ())

        def error_highlight(logger, msg):
            logger._log(logging.ERROR, f"\n{'!' * 50}\n{msg}\n{'!' * 50}", ())

        logger.highlight = partial(highlight, logger)
        logger.section = partial(section, logger)
        logger.important = partial(important, logger)
        logger.success = partial(success, logger)
        logger.warning = partial(custom_warning, logger)
        logger.error_highlight = partial(error_highlight, logger)

        return logger


def get_loggers():
    info_logger = CustomLogger.setup_logger(
        "info_logger", "info.log", level=logging.INFO
    )
    error_logger = CustomLogger.setup_logger(
        "error_logger", "error.log", level=logging.ERROR
    )
    return info_logger, error_logger
