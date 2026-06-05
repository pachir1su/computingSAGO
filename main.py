import sys
import logging

# discord INFO 로그가 stderr로 출력되어 Thonny에서 빨간색으로 보이는 현상 방지
logging.getLogger("discord").setLevel(logging.WARNING)

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
    print("=" * 50)
    print("❌ 아래 패키지가 설치되지 않았습니다:")
    for _pkg in _missing:
        print(f"   - {_pkg}")
    print("\n다음 명령어를 실행해 설치하세요:")
    print(f"   pip install {' '.join(_missing)}")
    print("\n또는 한 번에 전체 설치:")
    print("   pip install -r requirements.txt")
    print("=" * 50)
    sys.exit(1)

import asyncio
import os
import threading
import time
from datetime import datetime

from dotenv import load_dotenv
from logger import setup_logger

load_dotenv()
log = setup_logger("main")


def _subtract_30min(timeStr: str) -> str:
    # 브리핑 시간에서 30분 뺀 알림 시간 계산
    h, m  = map(int, timeStr.split(":"))
    total = h * 60 + m - 30
    if total < 0:
        total += 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def run_scheduler(bot, loadConfigFn):
    # 백그라운드 스레드 — 매분 사용자별 브리핑·알림 시간 도달 여부 확인
    lastCheckedMinute = None

    while True:
        try:
            now = datetime.now()
            currentMinute = now.strftime("%H:%M")

            # 분 단위 중복 실행 방지 — 같은 분에 두 번 체크하지 않음
            if currentMinute != lastCheckedMinute:
                lastCheckedMinute = currentMinute
                config = loadConfigFn()
                users = config.get("users", {})
                defaultTime = config.get("briefing_time", "07:00")

                # 현재 시각과 일치하는 사용자를 브리핑/알림 그룹으로 분류
                reportUserIds = []
                alertUserIds = []

                for userId, userConfig in users.items():
                    userTime = userConfig.get("briefingTime", defaultTime)
                    userAlertTime = _subtract_30min(userTime)

                    if currentMinute == userTime:
                        reportUserIds.append(userId)
                    if currentMinute == userAlertTime:
                        alertUserIds.append(userId)

                # 해당 시간 사용자에게만 브리핑/알림 발송
                if reportUserIds and bot.loop and not bot.loop.is_closed():
                    asyncio.run_coroutine_threadsafe(
                        bot.send_daily_report(userIds=reportUserIds), bot.loop
                    )
                    log.info("[스케줄러] 브리핑 발송 → %d명 (%s)", len(reportUserIds), currentMinute)

                if alertUserIds and bot.loop and not bot.loop.is_closed():
                    asyncio.run_coroutine_threadsafe(
                        bot.send_alerts(userIds=alertUserIds), bot.loop
                    )
                    log.info("[스케줄러] 알림 발송 → %d명 (%s)", len(alertUserIds), currentMinute)

        except Exception as e:
            log.error("[스케줄러] 오류 발생: %s", e)

        time.sleep(30)  # 30초 간격 폴링 (분 경계를 놓치지 않도록)


if __name__ == "__main__":
    from bot import bot, load_config

    # Discord 봇 토큰 유효성 확인
    discordToken = os.getenv("DISCORD_TOKEN")
    if not discordToken:
        log.error("[오류] .env 파일에 DISCORD_TOKEN을 설정해주세요.")
        raise SystemExit(1)

    # 스케줄러를 데몬 스레드로 실행 (봇 종료 시 자동 종료)
    schedulerThread = threading.Thread(
        target=run_scheduler, args=(bot, load_config), daemon=True
    )
    schedulerThread.start()
    log.info("[시작] 봇 실행 중...")

    # Discord 봇 실행 (메인 스레드 점유)
    bot.run(discordToken)
