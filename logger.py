import logging
import os
from logging.handlers import RotatingFileHandler

# 로그 디렉토리·파일 경로
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "bot.log")


def setup_logger(name: str = "bot") -> logging.Logger:
    # 로거 초기화 — 터미널(INFO) + 파일(DEBUG) 동시 출력
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # 공통 포맷: 시간, 레벨, 메시지
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 터미널 핸들러 (INFO 이상만 출력)
    consoleHandler = logging.StreamHandler()
    consoleHandler.setLevel(logging.INFO)
    consoleHandler.setFormatter(formatter)
    logger.addHandler(consoleHandler)

    # 파일 핸들러 (10 MB × 5 로테이션, DEBUG 이상 기록)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        fileHandler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        fileHandler.setLevel(logging.DEBUG)
        fileHandler.setFormatter(formatter)
        logger.addHandler(fileHandler)
    except OSError as e:
        logger.warning("로그 파일 핸들러 생성 실패: %s", e)

    return logger


def mask_id(userId: str) -> str:
    # Discord ID 마스킹 — 앞 4자리만 노출, 나머지 '*' 처리
    if len(userId) <= 4:
        return "****"
    return userId[:4] + "*" * (len(userId) - 4)
