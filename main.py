import asyncio
import os
import threading
import time

import schedule
from dotenv import load_dotenv

load_dotenv()


def _subtract_30min(timeStr: str) -> str:
    # 브리핑 시간에서 30분 뺀 알림 시간 계산
    h, m  = map(int, timeStr.split(":"))
    total = h * 60 + m - 30
    if total < 0:
        total += 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def run_scheduler(bot, loadConfigFn):
    # 백그라운드 스레드 — config.json 변경을 감지해 스케줄 자동 갱신
    currentBriefingTime = None

    while True:
        config       = loadConfigFn()
        briefingTime = config.get("briefing_time", "07:00")
        alertTime    = _subtract_30min(briefingTime)

        if briefingTime != currentBriefingTime:
            # 시간 변경 감지 시 기존 스케줄 초기화 후 재등록
            schedule.clear()
            currentBriefingTime = briefingTime

            def trigger_report():
                # 브리핑 코루틴을 Discord 이벤트 루프에 안전하게 제출
                if bot.loop and not bot.loop.is_closed():
                    asyncio.run_coroutine_threadsafe(bot.send_daily_report(), bot.loop)

            def trigger_alert():
                # 날씨 알림 코루틴을 Discord 이벤트 루프에 안전하게 제출
                if bot.loop and not bot.loop.is_closed():
                    asyncio.run_coroutine_threadsafe(bot.send_alerts(), bot.loop)

            schedule.every().day.at(briefingTime).do(trigger_report)
            schedule.every().day.at(alertTime).do(trigger_alert)
            print(f"[스케줄러] 알림: {alertTime} / 브리핑: {briefingTime}")

        schedule.run_pending()
        time.sleep(60)  # 1분 간격 폴링 (설정 변경 최대 1분 내 반영)


if __name__ == "__main__":
    from bot import bot, load_config

    # Discord 봇 토큰 유효성 확인
    discordToken = os.getenv("DISCORD_TOKEN")
    if not discordToken:
        print("[오류] .env 파일에 DISCORD_TOKEN을 설정해주세요.")
        raise SystemExit(1)

    # 스케줄러를 데몬 스레드로 실행 (봇 종료 시 자동 종료)
    schedulerThread = threading.Thread(
        target=run_scheduler, args=(bot, load_config), daemon=True
    )
    schedulerThread.start()

    # Discord 봇 실행 (메인 스레드 점유)
    bot.run(discordToken)
