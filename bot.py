import json
import os
import discord
from discord import app_commands
from dotenv import load_dotenv
from report import generate_report, generate_weather_summary, generate_news_summary, ask_gemini

load_dotenv()

CONFIG_FILE = "config.json"


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"briefing_time": "07:00", "region": "Seoul", "user_id": None}


def save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


class DailyReportBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f"[봇 준비 완료] {self.user} 로그인됨")

    async def send_daily_report(self):
        config = load_config()
        user_id = config.get("user_id") or int(os.getenv("DISCORD_USER_ID", 0))
        if not user_id:
            print("[오류] DISCORD_USER_ID가 설정되지 않았습니다.")
            return

        user = await self.fetch_user(user_id)
        region = config.get("region", "Seoul")
        try:
            report = generate_report(region)
            await user.send(f"📋 **데일리 브리핑**\n\n{report}")
            print(f"[브리핑 발송 완료] → {user}")
        except Exception as e:
            await user.send(f"⚠️ 리포트 생성 중 오류가 발생했습니다: {e}")
            print(f"[오류] {e}")


bot = DailyReportBot()


@bot.tree.command(name="리포트", description="즉시 데일리 리포트를 생성합니다")
async def cmd_report(interaction: discord.Interaction):
    await interaction.response.defer()
    config = load_config()
    report = generate_report(config.get("region", "Seoul"))
    await interaction.followup.send(f"📋 **데일리 브리핑**\n\n{report}")


@bot.tree.command(name="날씨", description="현재 날씨를 조회합니다")
async def cmd_weather(interaction: discord.Interaction):
    await interaction.response.defer()
    config = load_config()
    result = generate_weather_summary(config.get("region", "Seoul"))
    await interaction.followup.send(result)


@bot.tree.command(name="뉴스", description="최신 뉴스를 요약합니다")
async def cmd_news(interaction: discord.Interaction):
    await interaction.response.defer()
    result = generate_news_summary()
    await interaction.followup.send(result)


@bot.tree.command(name="질문", description="Gemini AI에게 자유롭게 질문합니다")
@app_commands.describe(내용="Gemini에게 물어볼 내용")
async def cmd_ask(interaction: discord.Interaction, 내용: str):
    await interaction.response.defer()
    result = ask_gemini(내용)
    await interaction.followup.send(f"💬 **Gemini 답변**\n\n{result}")


@bot.tree.command(name="설정", description="브리핑 시간 또는 지역을 변경합니다")
@app_commands.describe(항목="변경할 항목 (시간 또는 지역)", 값="설정할 값 (예: 08:00 또는 Busan)")
async def cmd_settings(interaction: discord.Interaction, 항목: str, 값: str):
    config = load_config()

    if 항목 == "시간":
        try:
            hh, mm = 값.split(":")
            if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
                raise ValueError
            config["briefing_time"] = 값
            save_config(config)
            await interaction.response.send_message(f"✅ 브리핑 시간이 **{값}**으로 변경되었습니다.")
        except ValueError:
            await interaction.response.send_message("❌ 올바른 시간 형식을 입력해주세요. 예: `08:30`")

    elif 항목 == "지역":
        config["region"] = 값
        save_config(config)
        await interaction.response.send_message(f"✅ 날씨 조회 지역이 **{값}**으로 변경되었습니다.")

    else:
        await interaction.response.send_message("❌ 알 수 없는 항목입니다. `시간` 또는 `지역`을 입력해주세요.")
