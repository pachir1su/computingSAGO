import sys
import logging
import os
from datetime import datetime

# ── 로깅 설정 (모든 import보다 먼저 실행) ──
def _setup_logging():
    # logs 폴더 자동 생성
    os.makedirs("logs", exist_ok=True)
    logFile = f"logs/bot_{datetime.now().strftime('%Y-%m-%d')}.log"

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 콘솔 핸들러 — stdout으로 출력 (Thonny에서 빨간색 방지)
    consoleHandler = logging.StreamHandler(sys.stdout)
    consoleHandler.setLevel(logging.INFO)
    consoleHandler.setFormatter(formatter)

    # 파일 핸들러 — 날짜별 로그 파일 자동 생성
    fileHandler = logging.FileHandler(logFile, encoding="utf-8")
    fileHandler.setLevel(logging.DEBUG)
    fileHandler.setFormatter(formatter)

    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.DEBUG)
    rootLogger.addHandler(consoleHandler)
    rootLogger.addHandler(fileHandler)

    # discord.py 내부 로그는 WARNING 이상만
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)

    return logging.getLogger("bot")

logger = _setup_logging()

# 필수 패키지 사전 검사 — 미설치 시 설치 명령어 안내 후 종료
_REQUIRED = {
    "discord":      "discord.py",
    "google.genai": "google-genai",
    "requests":     "requests",
    "feedparser":   "feedparser",
    "dotenv":       "python-dotenv",
}
_missing = []
for _module, _pkg in _REQUIRED.items():
    try:
        __import__(_module)
    except ImportError:
        _missing.append(_pkg)

if _missing:
    logger.error("아래 패키지가 설치되지 않았습니다:")
    for _pkg in _missing:
        logger.error(f"   - {_pkg}")
    logger.error(f"설치: pip install {' '.join(_missing)}")
    sys.exit(1)

import asyncio
import threading
import time

from dotenv import load_dotenv

load_dotenv()


def _subtract_30min(timeStr: str) -> str:
    h, m  = map(int, timeStr.split(":"))
    total = h * 60 + m - 30
    if total < 0:
        total += 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def _fireCoroutine(bot, coro, label: str):
    # 코루틴을 Discord 이벤트 루프에 안전하게 제출
    if not bot.loop or bot.loop.is_closed():
        logger.error(f"스케줄러: 이벤트 루프 미준비 — {label} 건너뜀")
        return
    future = asyncio.run_coroutine_threadsafe(coro, bot.loop)
    def onDone(f):
        try:
            f.result()
            logger.info(f"스케줄러: {label} 완료")
        except Exception as e:
            logger.error(f"스케줄러: {label} 실패: {type(e).__name__}: {e}")
    future.add_done_callback(onDone)


def run_scheduler(bot, loadConfigFn):
    # 백그라운드 스레드 — 매 15초마다 시간 비교로 브리핑/알림 발송 판단
    currentBriefingTime = None
    sentBriefingDate = None
    sentAlertDate = None

    while True:
        try:
            config       = loadConfigFn()
            briefingTime = config.get("briefing_time", "07:00")
            alertTime    = _subtract_30min(briefingTime)

            now = datetime.now()
            todayStr = now.strftime("%Y-%m-%d")

            # 시간 설정이 변경되면 발송 기록 초기화
            if briefingTime != currentBriefingTime:
                prevTime = currentBriefingTime
                currentBriefingTime = briefingTime
                logger.info(f"스케줄러: 알림 {alertTime} / 브리핑 {briefingTime} 등록됨")

                bH, bM = map(int, briefingTime.split(":"))
                briefingTarget = now.replace(hour=bH, minute=bM, second=0, microsecond=0)
                secSinceBriefing = (now - briefingTarget).total_seconds()

                aH, aM = map(int, alertTime.split(":"))
                alertTarget = now.replace(hour=aH, minute=aM, second=0, microsecond=0)
                secSinceAlert = (now - alertTarget).total_seconds()

                if prevTime is None:
                    # 봇 시작 시: 이미 지난 시간이면 오늘 발송 건너뜀
                    sentBriefingDate = todayStr if secSinceBriefing > 0 else None
                    sentAlertDate    = todayStr if secSinceAlert > 0 else None
                else:
                    # 사용자가 시간 변경: 90초 이내로 지난 시간이면 즉시 발송 허용
                    sentBriefingDate = todayStr if secSinceBriefing > 90 else None
                    sentAlertDate    = todayStr if secSinceAlert > 90 else None

            # 날짜가 바뀌면 발송 기록 리셋
            if sentBriefingDate is not None and sentBriefingDate != todayStr:
                sentBriefingDate = None
            if sentAlertDate is not None and sentAlertDate != todayStr:
                sentAlertDate = None

            # 브리핑 시간 도달 확인
            bH, bM = map(int, briefingTime.split(":"))
            briefingTarget = now.replace(hour=bH, minute=bM, second=0, microsecond=0)

            if now >= briefingTarget and sentBriefingDate != todayStr:
                sentBriefingDate = todayStr
                logger.info("스케줄러: 브리핑 발송 트리거됨")
                _fireCoroutine(bot, bot.send_daily_report(), "브리핑 발송")

            # 알림 시간 도달 확인
            aH, aM = map(int, alertTime.split(":"))
            alertTarget = now.replace(hour=aH, minute=aM, second=0, microsecond=0)

            if now >= alertTarget and sentAlertDate != todayStr:
                sentAlertDate = todayStr
                logger.info("스케줄러: 날씨 알림 트리거됨")
                _fireCoroutine(bot, bot.send_alerts(), "날씨 알림")

        except Exception as e:
            logger.error(f"스케줄러: 루프 에러: {type(e).__name__}: {e}")

        time.sleep(15)


if __name__ == "__main__":
    from bot import bot, load_config

    logger.info("=" * 40)
    logger.info("데일리 리포트 AI 시작")
    logger.info(f"로그 파일: logs/bot_{datetime.now().strftime('%Y-%m-%d')}.log")
    logger.info("=" * 40)

    # Discord 봇 토큰 유효성 확인
    discordToken = os.getenv("DISCORD_TOKEN")
    if not discordToken:
        logger.error(".env 파일에 DISCORD_TOKEN을 설정해주세요.")
        raise SystemExit(1)

    # 스케줄러를 데몬 스레드로 실행 (봇 종료 시 자동 종료)
    schedulerThread = threading.Thread(
        target=run_scheduler, args=(bot, load_config), daemon=True
    )
    schedulerThread.start()
    logger.info("스케줄러 스레드 시작됨")

    # Discord 봇 실행 (메인 스레드 점유)
    bot.run(discordToken)
