import json
import os
import discord
from discord import app_commands
from dotenv import load_dotenv
from report import generate_report, generate_weather_summary, generate_news_summary, ask_gemini

load_dotenv()

# 설정 파일 경로
configFile = "config.json"


def load_config() -> dict:
    # config.json 로드 — 파일 없거나 손상 시 기본값 반환
    try:
        if os.path.exists(configFile):
            with open(configFile, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return {"briefing_time": "07:00", "region": "Seoul", "user_id": None}


def save_config(config: dict):
    # 변경된 설정을 config.json에 즉시 저장
    with open(configFile, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


class DailyReportBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # 봇 시작 시 슬래시 커맨드를 Discord에 전역 등록
        await self.tree.sync()

    async def on_ready(self):
        print(f"[봇 준비 완료] {self.user} 로그인됨")

    async def send_daily_report(self):
        # 설정된 사용자에게 DM으로 데일리 브리핑 자동 발송
        config = load_config()
        userId = config.get("user_id") or int(os.getenv("DISCORD_USER_ID", 0))
        if not userId:
            print("[오류] DISCORD_USER_ID가 설정되지 않았습니다. .env 파일을 확인하세요.")
            return

        try:
            targetUser = await self.fetch_user(userId)
            region     = config.get("region", "Seoul")
            report     = generate_report(region)
            await targetUser.send(f"📋 **데일리 브리핑**\n\n{report}")
            print(f"[브리핑 발송 완료] → {targetUser}")
        except discord.NotFound:
            print(f"[오류] User ID {userId}를 찾을 수 없습니다.")
        except Exception as e:
            print(f"[오류] 브리핑 발송 실패: {e}")


bot = DailyReportBot()


@bot.tree.command(name="리포트", description="즉시 데일리 리포트를 생성합니다")
async def cmd_report(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        # 현재 설정 지역으로 전체 리포트 생성
        config = load_config()
        report = generate_report(config.get("region", "Seoul"))
        await interaction.followup.send(f"📋 **데일리 브리핑**\n\n{report}")
    except Exception as e:
        await interaction.followup.send(f"⚠️ 리포트 생성 실패\n```\n{e}\n```")


@bot.tree.command(name="날씨", description="현재 날씨를 조회합니다")
async def cmd_weather(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        # 설정된 지역의 날씨 단독 조회
        config = load_config()
        result = generate_weather_summary(config.get("region", "Seoul"))
        await interaction.followup.send(result)
    except Exception as e:
        await interaction.followup.send(f"⚠️ 날씨 조회 실패\n```\n{e}\n```")


@bot.tree.command(name="뉴스", description="최신 뉴스를 요약합니다")
async def cmd_news(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        # RSS 파싱 후 Gemini 요약
        result = generate_news_summary()
        await interaction.followup.send(result)
    except Exception as e:
        await interaction.followup.send(f"⚠️ 뉴스 조회 실패\n```\n{e}\n```")


@bot.tree.command(name="질문", description="Gemini AI에게 자유롭게 질문합니다")
@app_commands.describe(내용="Gemini에게 물어볼 내용")
async def cmd_ask(interaction: discord.Interaction, 내용: str):
    await interaction.response.defer()
    try:
        # 사용자 질문을 Gemini에 전달하고 답변 반환
        result = ask_gemini(내용)
        await interaction.followup.send(f"💬 **Gemini 답변**\n\n{result}")
    except Exception as e:
        await interaction.followup.send(f"⚠️ 질문 처리 실패\n```\n{e}\n```")


# 설정 서브커맨드 그룹 — /설정 시간, /설정 지역으로 분리해 직관성 향상
settingsGroup = app_commands.Group(name="설정", description="봇 설정 변경")


@settingsGroup.command(name="시간", description="자동 브리핑 시간을 변경합니다")
@app_commands.describe(시간="HH:MM 형식으로 입력 (예: 08:30)")
async def cmd_set_time(interaction: discord.Interaction, 시간: str):
    # 브리핑 시간 유효성 검사 후 저장
    config = load_config()
    try:
        hh, mm = 시간.split(":")
        if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
            raise ValueError
        config["briefing_time"] = 시간
        save_config(config)
        await interaction.response.send_message(f"✅ 브리핑 시간이 **{시간}**으로 변경되었습니다.")
    except ValueError:
        await interaction.response.send_message("❌ 올바른 형식으로 입력해주세요. 예: `08:30`")


@settingsGroup.command(name="지역", description="날씨 조회 지역을 변경합니다")
@app_commands.describe(지역="영문 도시명 (예: Seoul, Busan, Incheon, Daejeon, Cheonan)")
async def cmd_set_region(interaction: discord.Interaction, 지역: str):
    # 날씨 지역 변경 및 저장
    config = load_config()
    config["region"] = 지역
    save_config(config)
    await interaction.response.send_message(f"✅ 날씨 조회 지역이 **{지역}**으로 변경되었습니다.")


bot.tree.add_command(settingsGroup)
