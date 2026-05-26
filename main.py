import asyncio
import os
import threading
import time

import schedule
from dotenv import load_dotenv

load_dotenv()


def run_scheduler(bot, loadConfigFn):
    # 백그라운드 스레드 — config.json 변경을 감지해 스케줄 자동 갱신
    currentTime = None

    while True:
        config       = loadConfigFn()
        briefingTime = config.get("briefing_time", "07:00")

        if briefingTime != currentTime:
            # 시간 변경 감지 시 기존 스케줄 초기화 후 재등록
            schedule.clear()
            currentTime = briefingTime

            def trigger():
                # Discord 이벤트 루프에 코루틴을 스레드 안전하게 제출
                if bot.loop and not bot.loop.is_closed():
                    asyncio.run_coroutine_threadsafe(bot.send_daily_report(), bot.loop)

            schedule.every().day.at(briefingTime).do(trigger)
            print(f"[스케줄러] 매일 {briefingTime}에 브리핑 발송 예정")

        schedule.run_pending()
        time.sleep(60)  # 1분 간격으로 폴링 (설정 변경 최대 1분 내 반영)


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
