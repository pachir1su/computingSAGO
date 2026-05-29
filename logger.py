import logging
import os
from logging.handlers import RotatingFileHandler

# 로그 디렉토리 자동 생성
_logDir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(_logDir, exist_ok=True)

_logFile = os.path.join(_logDir, "bot.log")
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s",
                          datefmt="%Y-%m-%d %H:%M:%S")

_fileHandler = RotatingFileHandler(_logFile, maxBytes=5 * 1024 * 1024,
                                    backupCount=3, encoding="utf-8")
_fileHandler.setLevel(logging.DEBUG)
_fileHandler.setFormatter(_fmt)

_consoleHandler = logging.StreamHandler()
_consoleHandler.setLevel(logging.INFO)
_consoleHandler.setFormatter(_fmt)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.addHandler(_fileHandler)
        logger.addHandler(_consoleHandler)
        logger.propagate = False
    return logger
