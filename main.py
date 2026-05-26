import asyncio
import os
import threading
import time

import schedule
from dotenv import load_dotenv

load_dotenv()


def run_scheduler(bot, load_config_fn):
    """백그라운드 스레드에서 schedule 라이브러리를 실행합니다.
    config.json의 briefing_time이 바뀌면 자동으로 스케줄을 갱신합니다."""
    current_time = None

    while True:
        config = load_config_fn()
        briefing_time = config.get("briefing_time", "07:00")

        if briefing_time != current_time:
            schedule.clear()
            current_time = briefing_time

            def trigger():
                if bot.loop and not bot.loop.is_closed():
                    asyncio.run_coroutine_threadsafe(bot.send_daily_report(), bot.loop)

            schedule.every().day.at(briefing_time).do(trigger)
            print(f"[스케줄러] 매일 {briefing_time}에 브리핑 발송 예정")

        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    from bot import bot, load_config

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("[오류] .env 파일에 DISCORD_TOKEN을 설정해주세요.")
        raise SystemExit(1)

    scheduler_thread = threading.Thread(
        target=run_scheduler, args=(bot, load_config), daemon=True
    )
    scheduler_thread.start()

    bot.run(token)
