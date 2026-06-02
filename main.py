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
    "schedule":     "schedule",
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

import schedule
from dotenv import load_dotenv

load_dotenv()


def _subtract_30min(timeStr: str) -> str:
    h, m  = map(int, timeStr.split(":"))
    total = h * 60 + m - 30
    if total < 0:
        total += 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def run_scheduler(bot, loadConfigFn):
    # 백그라운드 스레드 — config.json 변경을 감지해 스케줄 자동 갱신
    currentBriefingTime = None

    while True:
        try:
            config       = loadConfigFn()
            briefingTime = config.get("briefing_time", "07:00")
            alertTime    = _subtract_30min(briefingTime)

            if briefingTime != currentBriefingTime:
                schedule.clear()
                currentBriefingTime = briefingTime

                def trigger_report():
                    logger.info("스케줄러: 브리핑 발송 트리거됨")
                    if not bot.loop or bot.loop.is_closed():
                        logger.error("스케줄러: 이벤트 루프 미준비 — 브리핑 건너뜀")
                        return
                    future = asyncio.run_coroutine_threadsafe(bot.send_daily_report(), bot.loop)
                    def onDone(f):
                        try:
                            f.result()
                            logger.info("스케줄러: 브리핑 발송 완료")
                        except Exception as e:
                            logger.error(f"스케줄러: 브리핑 발송 실패: {type(e).__name__}: {e}")
                    future.add_done_callback(onDone)

                def trigger_alert():
                    logger.info("스케줄러: 날씨 알림 트리거됨")
                    if not bot.loop or bot.loop.is_closed():
                        logger.error("스케줄러: 이벤트 루프 미준비 — 알림 건너뜀")
                        return
                    future = asyncio.run_coroutine_threadsafe(bot.send_alerts(), bot.loop)
                    def onDone(f):
                        try:
                            f.result()
                            logger.info("스케줄러: 날씨 알림 완료")
                        except Exception as e:
                            logger.error(f"스케줄러: 날씨 알림 실패: {type(e).__name__}: {e}")
                    future.add_done_callback(onDone)

                schedule.every().day.at(briefingTime).do(trigger_report)
                schedule.every().day.at(alertTime).do(trigger_alert)
                logger.info(f"스케줄러: 알림 {alertTime} / 브리핑 {briefingTime} 등록됨")

                # 시간 변경 직후, 이미 지나간 시간이면 즉시 실행 (90초 이내)
                now = datetime.now()
                bH, bM = map(int, briefingTime.split(":"))
                briefingToday = now.replace(hour=bH, minute=bM, second=0, microsecond=0)
                secondsAgo = (now - briefingToday).total_seconds()
                if 0 < secondsAgo <= 90:
                    logger.info(f"스케줄러: 브리핑 시간({briefingTime})이 방금 지남 — 즉시 발송")
                    trigger_report()

                aH, aM = map(int, alertTime.split(":"))
                alertToday = now.replace(hour=aH, minute=aM, second=0, microsecond=0)
                alertAgo = (now - alertToday).total_seconds()
                if 0 < alertAgo <= 90:
                    logger.info(f"스케줄러: 알림 시간({alertTime})이 방금 지남 — 즉시 발송")
                    trigger_alert()

            schedule.run_pending()
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
