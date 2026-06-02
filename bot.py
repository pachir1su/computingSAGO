import asyncio
import json
import logging
import os
import discord
from discord import app_commands
from dotenv import load_dotenv
from report import generate_report, generate_weather_summary, generate_news_summary, ask_gemini
from weather import check_weather_alerts

load_dotenv()

logger = logging.getLogger("bot")

# 설정 파일 경로
configFile = "config.json"

# 지역 선택 버튼 목록 (표시 이름, OpenWeather 영문 도시명)
REGIONS = [
    ("서울", "Seoul"),
    ("부산", "Busan"),
    ("인천", "Incheon"),
    ("대전", "Daejeon"),
    ("대구", "Daegu"),
    ("광주", "Gwangju"),
    ("울산", "Ulsan"),
    ("수원", "Suwon"),
    ("천안", "Cheonan"),
]


class RegionButton(discord.ui.Button):
    def __init__(self, korName: str, engName: str, action: str):
        super().__init__(label=korName, style=discord.ButtonStyle.primary)
        self.engName = engName
        self.action  = action

    async def callback(self, interaction: discord.Interaction):
        try:
            config = load_config()
            userId = str(interaction.user.id)

            if self.action == "register":
                config["users"][userId] = {"region": self.engName}
                save_config(config)
                briefingTime = config.get("briefing_time", "07:00")
                await interaction.response.edit_message(
                    content=(
                        f"✅ **등록 완료!** 매일 **{briefingTime}**에 **{self.engName}** 날씨 기준 브리핑을 DM으로 받습니다.\n"
                        f"지역 변경: `/설정 지역`, 시간 변경: `/설정 시간`, 구독 취소: `/탈퇴`"
                    ),
                    view=None,
                )
                logger.info(f"사용자 {userId} 등록 완료 (지역: {self.engName})")
            elif self.action == "change":
                if userId not in config.get("users", {}):
                    await interaction.response.edit_message(
                        content="❌ 먼저 `/등록`을 실행해주세요.", view=None
                    )
                    return
                config["users"][userId]["region"] = self.engName
                save_config(config)
                await interaction.response.edit_message(
                    content=f"✅ {interaction.user.mention}의 날씨 지역이 **{self.engName}**으로 변경되었습니다.",
                    view=None,
                )
                logger.info(f"사용자 {userId} 지역 변경 → {self.engName}")
        except discord.NotFound:
            logger.debug(f"RegionButton interaction 만료 (action={self.action})")


class RegionView(discord.ui.View):
    def __init__(self, action: str):
        super().__init__(timeout=60)
        for korName, engName in REGIONS:
            self.add_item(RegionButton(korName, engName, action))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


def load_config() -> dict:
    # config.json 로드 — 없거나 손상 시 기본값 반환, 구버전 형식 자동 마이그레이션
    default = {"briefing_time": "07:00", "users": {}}
    try:
        if not os.path.exists(configFile):
            return default
        with open(configFile, "r", encoding="utf-8") as f:
            config = json.load(f)

        # 구버전 (user_id + region 전역) → 신버전 (users 딕셔너리) 마이그레이션
        oldUserId = config.pop("user_id", None)
        oldRegion = config.pop("region", "Seoul")
        if oldUserId:
            config.setdefault("users", {})
            config["users"].setdefault(str(oldUserId), {"region": oldRegion})
            save_config(config)
            logger.info(f"config 마이그레이션 완료: user_id={oldUserId}")

        config.setdefault("users", {})
        return config
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"config.json 로드 실패, 기본값 사용: {e}")
        return default


def save_config(config: dict):
    with open(configFile, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


class DailyReportBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("슬래시 커맨드 Discord 동기화 완료")

    async def on_ready(self):
        logger.info(f"봇 준비 완료: {self.user} 로그인됨")
        logger.warning("이 봇을 동시에 여러 곳에서 실행하면 명령이 작동하지 않습니다. 반드시 하나만 실행하세요.")

    async def _dm_send(self, user, content: str):
        # Discord 2000자 제한 — 초과 시 문단 단위로 분할 전송
        limit = 1900
        if len(content) <= limit:
            await user.send(content)
            return
        lines, chunk = content.split("\n"), ""
        for line in lines:
            if len(chunk) + len(line) + 1 > limit:
                await user.send(chunk)
                chunk = line
            else:
                chunk = (chunk + "\n" + line) if chunk else line
        if chunk:
            await user.send(chunk)

    async def send_daily_report(self):
        # 등록된 모든 사용자에게 각자 지역 기준으로 DM 브리핑 발송
        config = load_config()
        users  = config.get("users", {})
        if not users:
            logger.warning("브리핑: 등록된 사용자가 없습니다. /등록을 먼저 실행하세요.")
            return

        logger.info(f"브리핑: {len(users)}명에게 발송 시작")
        for userId, userConfig in users.items():
            region = userConfig.get("region", "Seoul")
            try:
                targetUser = await self.fetch_user(int(userId))
                logger.debug(f"브리핑: {targetUser} ({region}) 리포트 생성 중...")
                report     = await asyncio.to_thread(generate_report, region)
                await self._dm_send(targetUser, f"📋 **데일리 브리핑**\n\n{report}")
                logger.info(f"브리핑: 발송 완료 → {targetUser} ({region})")
            except discord.NotFound:
                logger.error(f"브리핑: 사용자 {userId}를 찾을 수 없음")
            except discord.Forbidden:
                logger.error(f"브리핑: 사용자 {userId} DM 거부됨 (DM 설정 확인 필요)")
            except Exception as e:
                logger.error(f"브리핑: 사용자 {userId} 발송 실패: {type(e).__name__}: {e}")

    async def send_alerts(self):
        # 비·미세먼지 조건 확인 후 조건 충족 사용자에게만 경보 DM 발송
        config = load_config()
        users  = config.get("users", {})

        logger.info(f"알림: {len(users)}명 날씨 조건 확인 시작")
        for userId, userConfig in users.items():
            region = userConfig.get("region", "Seoul")
            try:
                alerts = await asyncio.to_thread(check_weather_alerts, region)
                if not alerts:
                    logger.debug(f"알림: {userId} ({region}) 경보 조건 없음")
                    continue
                targetUser = await self.fetch_user(int(userId))
                alertMsg   = "⚠️ **날씨 주의 알림**\n\n" + "\n".join(alerts)
                await self._dm_send(targetUser, alertMsg)
                logger.info(f"알림: 발송 완료 → {targetUser} ({region})")
            except discord.NotFound:
                logger.error(f"알림: 사용자 {userId}를 찾을 수 없음")
            except discord.Forbidden:
                logger.error(f"알림: 사용자 {userId} DM 거부됨 (DM 설정 확인 필요)")
            except Exception as e:
                logger.error(f"알림: 사용자 {userId} 알림 실패: {type(e).__name__}: {e}")


bot = DailyReportBot()


@bot.tree.command(name="등록", description="데일리 브리핑을 구독합니다")
async def cmd_register(interaction: discord.Interaction):
    view = RegionView(action="register")
    await interaction.response.send_message(
        "📍 **지역을 선택해주세요:**",
        view=view,
        ephemeral=True,
    )


@bot.tree.command(name="탈퇴", description="데일리 브리핑 구독을 취소합니다")
async def cmd_unregister(interaction: discord.Interaction):
    config = load_config()
    userId = str(interaction.user.id)
    if userId in config.get("users", {}):
        del config["users"][userId]
        save_config(config)
        await interaction.response.send_message("✅ 구독이 취소되었습니다.", ephemeral=True)
        logger.info(f"사용자 {userId} 탈퇴 완료")
    else:
        await interaction.response.send_message("❌ 등록된 정보가 없습니다. 먼저 `/등록`을 실행해주세요.", ephemeral=True)


@bot.tree.command(name="리포트", description="즉시 데일리 리포트를 생성합니다")
async def cmd_report(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        config = load_config()
        userId = str(interaction.user.id)
        region = config.get("users", {}).get(userId, {}).get("region", "Seoul")
        logger.info(f"명령 /리포트: {interaction.user} ({region})")
        report = await asyncio.to_thread(generate_report, region)
        await interaction.followup.send(f"📋 **데일리 브리핑**\n\n{report}")
    except Exception as e:
        logger.error(f"명령 /리포트 실패: {type(e).__name__}: {e}")
        await interaction.followup.send(f"⚠️ 리포트 생성 실패\n```\n{e}\n```")


@bot.tree.command(name="날씨", description="현재 날씨와 내일 예보를 조회합니다")
async def cmd_weather(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        config = load_config()
        userId = str(interaction.user.id)
        region = config.get("users", {}).get(userId, {}).get("region", "Seoul")
        logger.info(f"명령 /날씨: {interaction.user} ({region})")
        result = await asyncio.to_thread(generate_weather_summary, region)
        await interaction.followup.send(result)
    except Exception as e:
        logger.error(f"명령 /날씨 실패: {type(e).__name__}: {e}")
        await interaction.followup.send(f"⚠️ 날씨 조회 실패\n```\n{e}\n```")


@bot.tree.command(name="뉴스", description="최신 뉴스를 요약합니다")
async def cmd_news(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        logger.info(f"명령 /뉴스: {interaction.user}")
        result = await asyncio.to_thread(generate_news_summary)
        await interaction.followup.send(result)
    except Exception as e:
        logger.error(f"명령 /뉴스 실패: {type(e).__name__}: {e}")
        await interaction.followup.send(f"⚠️ 뉴스 조회 실패\n```\n{e}\n```")


@bot.tree.command(name="질문", description="Gemini AI에게 자유롭게 질문합니다")
@app_commands.describe(내용="Gemini에게 물어볼 내용")
async def cmd_ask(interaction: discord.Interaction, 내용: str):
    await interaction.response.defer()
    try:
        logger.info(f"명령 /질문: {interaction.user}")
        result = await asyncio.to_thread(ask_gemini, 내용)
        await interaction.followup.send(f"💬 **Gemini 답변**\n\n{result}")
    except Exception as e:
        logger.error(f"명령 /질문 실패: {type(e).__name__}: {e}")
        await interaction.followup.send(f"⚠️ 질문 처리 실패\n```\n{e}\n```")


# 설정 서브커맨드 그룹 — /설정 시간, /설정 지역으로 분리
settingsGroup = app_commands.Group(name="설정", description="봇 설정 변경")


@settingsGroup.command(name="시간", description="자동 브리핑 시간을 변경합니다 (전체 공통)")
@app_commands.describe(시간="HH:MM 형식으로 입력 (예: 08:30)")
async def cmd_set_time(interaction: discord.Interaction, 시간: str):
    config = load_config()
    try:
        hh, mm = 시간.split(":")
        if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
            raise ValueError
        config["briefing_time"] = 시간
        save_config(config)
        await interaction.response.send_message(
            f"✅ 브리핑 시간이 **{시간}**으로 변경되었습니다.\n"
            f"(날씨 알림은 브리핑 30분 전인 **{_subtract_30min(시간)}**에 발송됩니다.)"
        )
        logger.info(f"브리핑 시간 변경: {시간} (by {interaction.user})")
    except ValueError:
        await interaction.response.send_message("❌ 올바른 형식으로 입력해주세요. 예: `08:30`")


@settingsGroup.command(name="지역", description="내 날씨 조회 지역을 변경합니다")
async def cmd_set_region(interaction: discord.Interaction):
    config = load_config()
    userId = str(interaction.user.id)
    if userId not in config.get("users", {}):
        await interaction.response.send_message("❌ 먼저 `/등록`을 실행해주세요.", ephemeral=True)
        return
    view = RegionView(action="change")
    await interaction.response.send_message(
        "📍 **변경할 지역을 선택해주세요:**",
        view=view,
        ephemeral=True,
    )


bot.tree.add_command(settingsGroup)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandInvokeError):
        original = error.original
        if isinstance(original, discord.NotFound) and original.code == 10062:
            cmdName = interaction.command.name if interaction.command else "?"
            logger.warning(
                f"'/{cmdName}' 응답 실패 (interaction 만료) "
                f"— 봇이 동시에 여러 개 실행되고 있지 않은지 확인하세요."
            )
            return
    cmdName = interaction.command.name if interaction.command else "?"
    logger.error(f"'/{cmdName}' 실행 실패: {error}")
    try:
        if interaction.response.is_done():
            await interaction.followup.send("⚠️ 명령 처리 중 오류가 발생했습니다.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ 명령 처리 중 오류가 발생했습니다.", ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        pass


def _subtract_30min(timeStr: str) -> str:
    h, m    = map(int, timeStr.split(":"))
    total   = h * 60 + m - 30
    if total < 0:
        total += 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"
