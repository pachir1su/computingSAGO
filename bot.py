import asyncio
import json
import os
import discord
from discord import app_commands
from dotenv import load_dotenv
from report import (
    generate_report, generate_weather_summary, generate_news_summary,
    ask_gemini, DEFAULT_SECTIONS,
)
from weather import check_weather_alerts
from news import get_available_categories
from logger import setup_logger, mask_id

load_dotenv()
log = setup_logger("bot")

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

# 항목 key -> 한글 이름 매핑
SECTION_KOR_NAMES = {
    "weather": "날씨",
    "dust":    "미세먼지",
    "news":    "뉴스",
    "outfit":  "옷차림",
    "quote":   "한마디",
}

# ──────────────────── 프로그레스 바 유틸 ────────────────────

# 애니메이션 상수
ANIM_TICK_INTERVAL = 0.8   # 프레임 간격 (초)
ANIM_BAR_WIDTH = 16        # 프로그레스 바 길이
ANIM_MAX_TICKS = 40        # 최대 애니메이션 프레임 수 (약 32초)


def progressBar(p: float, width: int = ANIM_BAR_WIDTH) -> str:
    # 블록(█▁) 스타일 프로그레스 바 생성
    p = max(0.0, min(1.0, p))
    filled = int(round(p * width))
    return "█" * filled + "▁" * (width - filled)


def progressBarAlt(p: float, width: int = ANIM_BAR_WIDTH) -> str:
    # 다이아몬드(▰▱) 스타일 프로그레스 바 생성
    p = max(0.0, min(1.0, p))
    fill = int(round(p * width))
    return "▰" * fill + "▱" * (width - fill)


class RegionButton(discord.ui.Button):
    def __init__(self, korName: str, engName: str, action: str):
        super().__init__(label=korName, style=discord.ButtonStyle.primary)
        self.engName = engName
        self.action  = action

    async def callback(self, interaction: discord.Interaction):
        try:
            # 버튼 잠금 — 중복 클릭 방지
            for child in self.view.children:
                if hasattr(child, 'disabled'):
                    child.disabled = True

            # 초기 로딩 상태 표시 (response.edit_message로 응답)
            loadEmbed = discord.Embed(title="⏳ 설정 중...", color=0xF1C40F)
            loadEmbed.add_field(
                name="진행", value=f"{progressBarAlt(0.0)} **0%**"
            )
            await interaction.response.edit_message(
                content=None, embed=loadEmbed, view=self.view
            )

            # 프로그레스 바 애니메이션 (짧은 버전)
            for pct in (30, 60, 100):
                animEmbed = discord.Embed(title="⏳ 설정 중...", color=0xF1C40F)
                animEmbed.add_field(
                    name="진행", value=f"{progressBarAlt(pct / 100)} **{pct}%**"
                )
                await interaction.edit_original_response(
                    embed=animEmbed, view=self.view
                )
                await asyncio.sleep(0.3)

            # 실제 설정 처리
            config = load_config()
            userId = str(interaction.user.id)

            if self.action == "register":
                # 신규 등록 — 기본 설정 포함
                config["users"][userId] = {
                    "region": self.engName,
                    "newsCategory": "종합",
                    "enabledSections": dict(DEFAULT_SECTIONS),
                }
                save_config(config)
                briefingTime = config.get("briefing_time", "07:00")
                log.info("[등록] 새 사용자 등록 완료 (지역: %s)", self.engName)

                # 등록 완료 임베드 표시
                resultEmbed = discord.Embed(
                    title="✅ 등록 완료!",
                    color=0x2ECC71,
                    description=(
                        f"매일 **{briefingTime}**에 **{self.engName}** 날씨 기준 "
                        f"브리핑을 DM으로 받습니다.\n\n"
                        f"🔧 **설정 명령어**\n"
                        f"• 지역 변경: `/설정 지역`\n"
                        f"• 시간 변경: `/설정 시간`\n"
                        f"• 뉴스 카테고리: `/설정 뉴스카테고리`\n"
                        f"• 항목 on/off: `/설정 항목`\n"
                        f"• 구독 취소: `/탈퇴`"
                    ),
                )
                await interaction.edit_original_response(
                    embed=resultEmbed, content=None, view=None
                )

            elif self.action == "change":
                # 지역 변경 — 등록 여부 사전 확인
                if userId not in config.get("users", {}):
                    errEmbed = discord.Embed(
                        title="❌ 등록 필요",
                        color=0xE74C3C,
                        description="먼저 `/등록`을 실행해주세요.",
                    )
                    await interaction.edit_original_response(
                        embed=errEmbed, content=None, view=None
                    )
                    return
                config["users"][userId]["region"] = self.engName
                save_config(config)
                log.info("[설정] 지역 변경 완료 → %s", self.engName)

                # 지역 변경 완료 임베드 표시
                resultEmbed = discord.Embed(
                    title="✅ 지역 변경 완료",
                    color=0x2ECC71,
                    description=f"날씨 지역이 **{self.engName}**(으)로 변경되었습니다.",
                )
                await interaction.edit_original_response(
                    embed=resultEmbed, content=None, view=None
                )

        except Exception as e:
            # 예외 발생 시 에러 임베드 표시
            log.error("[지역설정] 처리 실패: %s", e)
            try:
                errEmbed = discord.Embed(
                    title="⚠️ 처리 실패",
                    color=0xE74C3C,
                    description=f"```\n{e}\n```",
                )
                await interaction.edit_original_response(
                    embed=errEmbed, content=None, view=None
                )
            except Exception:
                pass


class RegionView(discord.ui.View):
    def __init__(self, action: str):
        super().__init__(timeout=60)
        for korName, engName in REGIONS:
            self.add_item(RegionButton(korName, engName, action))

    async def on_timeout(self):
        # 60초 후 버튼 비활성화
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

        config.setdefault("users", {})
        return config
    except (json.JSONDecodeError, IOError):
        log.warning("config.json 파싱 실패, 기본값으로 초기화")
        return default


def save_config(config: dict):
    # 변경된 설정을 config.json에 즉시 저장
    try:
        with open(configFile, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except IOError as e:
        log.error("config.json 저장 실패: %s", e)


def _get_user_sections(userConfig: dict) -> dict:
    # 사용자별 활성화 섹션 반환 (미설정 시 전체 활성화)
    return userConfig.get("enabledSections", dict(DEFAULT_SECTIONS))


# ──────────────────── 애니메이션 헬퍼 ────────────────────

async def _send_followup_split(interaction: discord.Interaction, content: str):
    # Discord 2000자 제한에 맞춰 followup 메시지 분할 전송
    limit = 1900
    try:
        if len(content) <= limit:
            await interaction.followup.send(content)
            return
        lines = content.split("\n")
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 1 > limit:
                await interaction.followup.send(chunk)
                chunk = line
            else:
                chunk = (chunk + "\n" + line) if chunk else line
        if chunk:
            await interaction.followup.send(chunk)
    except Exception as e:
        log.error("[followup] 분할 전송 실패: %s", e)


async def _animated_command(interaction: discord.Interaction, *, title: str,
                            workFn, workArgs: tuple = (), resultPrefix: str = "",
                            errorLabel: str = "작업"):
    # 프로그레스 바 애니메이션과 함께 동기 작업을 백그라운드 실행하고 결과 표시
    try:
        # 초기 로딩 임베드 전송 (Discord 3초 타임아웃 회피)
        initEmbed = discord.Embed(title=f"⏳ {title}...", color=0xF1C40F)
        initEmbed.add_field(name="진행", value=f"{progressBar(0.0)} **0%**")
        await interaction.response.send_message(embed=initEmbed)

        # 백그라운드에서 실제 작업 시작
        task = asyncio.create_task(asyncio.to_thread(workFn, *workArgs))

        # 작업 완료까지 프로그레스 바 애니메이션 루프
        tick = 0
        while not task.done() and tick < ANIM_MAX_TICKS:
            tick += 1
            # 로그 곡선으로 자연스러운 진행률 표시 (최대 90%)
            p = min(1 - 1 / (1 + tick * 0.15), 0.9)
            pct = int(p * 100)
            tickEmbed = discord.Embed(title=f"⏳ {title}...", color=0xF1C40F)
            tickEmbed.add_field(name="진행", value=f"{progressBar(p)} **{pct}%**")
            try:
                await interaction.edit_original_response(embed=tickEmbed)
            except discord.NotFound:
                break
            await asyncio.sleep(ANIM_TICK_INTERVAL)

        # 작업 결과 수신
        result = await task

        # 100% 완료 임베드 표시
        doneEmbed = discord.Embed(title=f"✅ {title} 완료!", color=0x2ECC71)
        doneEmbed.add_field(name="진행", value=f"{progressBar(1.0)} **100%**")
        try:
            await interaction.edit_original_response(embed=doneEmbed)
        except discord.NotFound:
            pass
        await asyncio.sleep(0.5)

        # 결과 텍스트 조합
        content = f"{resultPrefix}{result}" if resultPrefix else result

        # 결과 전송 — 길이에 따라 인라인 수정 또는 followup 분할
        if len(content) <= 1900:
            try:
                await interaction.edit_original_response(
                    content=content, embed=None
                )
            except discord.NotFound:
                await interaction.followup.send(content)
        else:
            try:
                await interaction.edit_original_response(
                    embed=discord.Embed(
                        title=f"✅ {title} 완료!", color=0x2ECC71
                    ),
                )
            except discord.NotFound:
                pass
            await _send_followup_split(interaction, content)

    except Exception as e:
        # 에러 발생 시 에러 임베드 표시
        log.error("[%s] 실패: %s", errorLabel, e)
        errEmbed = discord.Embed(
            title=f"⚠️ {errorLabel} 실패",
            color=0xE74C3C,
            description=f"```\n{e}\n```",
        )
        try:
            await interaction.edit_original_response(embed=errEmbed, content=None)
        except Exception:
            try:
                await interaction.followup.send(embed=errEmbed)
            except Exception:
                pass


class DailyReportBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # 봇 시작 시 슬래시 커맨드를 Discord에 전역 등록
        await self.tree.sync()

    async def on_ready(self):
        log.info("[봇 준비 완료] 로그인 성공")

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
        # 등록된 모든 사용자에게 각자 설정 기준으로 DM 브리핑 발송
        config = load_config()
        users  = config.get("users", {})
        if not users:
            log.info("[브리핑] 등록된 사용자가 없습니다.")
            return

        successCount = 0
        failCount = 0

        for userId, userConfig in users.items():
            region = userConfig.get("region", "Seoul")
            newsCategory = userConfig.get("newsCategory", "종합")
            enabledSections = _get_user_sections(userConfig)
            maskedId = mask_id(userId)
            targetUser = None
            try:
                # 사용자 조회 및 리포트 생성·발송
                targetUser = await self.fetch_user(int(userId))
                report = await asyncio.to_thread(
                    generate_report, region, newsCategory, enabledSections,
                )
                await self._dm_send(targetUser, f"📋 **데일리 브리핑**\n\n{report}")
                log.info("[브리핑] 발송 완료 → %s (%s)", maskedId, region)
                successCount += 1
            except discord.NotFound:
                log.warning("[브리핑] 사용자 %s 를 찾을 수 없음", maskedId)
                failCount += 1
            except discord.Forbidden:
                log.warning("[브리핑] 사용자 %s DM 거부됨 (DM 설정 확인 필요)", maskedId)
                failCount += 1
            except Exception as e:
                log.error("[브리핑] 사용자 %s 발송 실패: %s: %s",
                          maskedId, type(e).__name__, e)
                failCount += 1
                # 실패 알림 DM 전송 시도 (사용자 조회 성공 시에만)
                if targetUser:
                    try:
                        await self._dm_send(
                            targetUser,
                            f"⚠️ **데일리 브리핑 발송 실패**\n\n"
                            f"오늘의 브리핑 생성 중 오류가 발생했습니다.\n"
                            f"```\n{type(e).__name__}: {e}\n```\n"
                            f"잠시 후 `/리포트` 명령어로 수동 조회를 시도해보세요."
                        )
                        log.info("[브리핑] 실패 알림 DM 발송 → %s", maskedId)
                    except Exception as dmErr:
                        log.warning("[브리핑] 실패 알림 DM 발송도 실패 → %s: %s",
                                    maskedId, dmErr)

        log.info("[브리핑] 전체 발송 결과 — 성공: %d, 실패: %d", successCount, failCount)

    async def send_alerts(self):
        # 비·미세먼지 조건 확인 후 조건 충족 사용자에게만 경보 DM 발송
        config = load_config()
        users  = config.get("users", {})

        for userId, userConfig in users.items():
            region = userConfig.get("region", "Seoul")
            maskedId = mask_id(userId)
            try:
                alerts = await asyncio.to_thread(check_weather_alerts, region)
                if not alerts:
                    continue
                targetUser = await self.fetch_user(int(userId))
                alertMsg   = "⚠️ **날씨 주의 알림**\n\n" + "\n".join(alerts)
                await self._dm_send(targetUser, alertMsg)
                log.info("[알림] 발송 완료 → %s (%s)", maskedId, region)
            except discord.NotFound:
                log.warning("[알림] 사용자 %s 를 찾을 수 없음", maskedId)
            except discord.Forbidden:
                log.warning("[알림] 사용자 %s DM 거부됨 (DM 설정 확인 필요)", maskedId)
            except Exception as e:
                log.error("[알림] 사용자 %s 알림 실패: %s: %s",
                          maskedId, type(e).__name__, e)


bot = DailyReportBot()


# ──────────────────── 슬래시 커맨드 ────────────────────

@bot.tree.command(name="등록", description="데일리 브리핑을 구독합니다")
async def cmd_register(interaction: discord.Interaction):
    # 지역 선택 버튼 표시
    view = RegionView(action="register")
    await interaction.response.send_message(
        "📍 **지역을 선택해주세요:**",
        view=view,
        ephemeral=True,
    )


@bot.tree.command(name="탈퇴", description="데일리 브리핑 구독을 취소합니다")
async def cmd_unregister(interaction: discord.Interaction):
    # config.json에서 사용자 항목 삭제
    config = load_config()
    userId = str(interaction.user.id)
    if userId in config.get("users", {}):
        del config["users"][userId]
        save_config(config)
        log.info("[탈퇴] 사용자 구독 취소 완료")
        await interaction.response.send_message(
            "✅ 구독이 취소되었습니다.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "❌ 등록된 정보가 없습니다. 먼저 `/등록`을 실행해주세요.", ephemeral=True
        )


@bot.tree.command(name="리포트", description="즉시 데일리 리포트를 생성합니다")
async def cmd_report(interaction: discord.Interaction):
    # 호출한 사용자의 등록 설정 사용 (미등록 시 기본값)
    config = load_config()
    userId = str(interaction.user.id)
    userConfig = config.get("users", {}).get(userId, {})
    region = userConfig.get("region", "Seoul")
    newsCategory = userConfig.get("newsCategory", "종합")
    enabledSections = _get_user_sections(userConfig)

    # 애니메이션과 함께 리포트 생성
    await _animated_command(
        interaction,
        title="리포트 생성 중",
        workFn=generate_report,
        workArgs=(region, newsCategory, enabledSections),
        resultPrefix="📋 **데일리 브리핑**\n\n",
        errorLabel="리포트",
    )


@bot.tree.command(name="날씨", description="현재 날씨와 내일 예보를 조회합니다")
async def cmd_weather(interaction: discord.Interaction):
    # 호출한 사용자의 등록 지역 사용 (미등록 시 Seoul)
    config = load_config()
    userId = str(interaction.user.id)
    region = config.get("users", {}).get(userId, {}).get("region", "Seoul")

    # 애니메이션과 함께 날씨 조회
    await _animated_command(
        interaction,
        title="날씨 조회 중",
        workFn=generate_weather_summary,
        workArgs=(region,),
        errorLabel="날씨",
    )


@bot.tree.command(name="뉴스", description="최신 뉴스를 요약합니다")
async def cmd_news(interaction: discord.Interaction):
    # 호출한 사용자의 뉴스 카테고리 반영
    config = load_config()
    userId = str(interaction.user.id)
    newsCategory = config.get("users", {}).get(userId, {}).get("newsCategory", "종합")

    # 애니메이션과 함께 뉴스 조회
    await _animated_command(
        interaction,
        title="뉴스 조회 중",
        workFn=generate_news_summary,
        workArgs=(newsCategory,),
        errorLabel="뉴스",
    )


@bot.tree.command(name="질문", description="Gemini AI에게 자유롭게 질문합니다")
@app_commands.describe(내용="Gemini에게 물어볼 내용")
async def cmd_ask(interaction: discord.Interaction, 내용: str):
    # 애니메이션과 함께 Gemini 질문 처리
    await _animated_command(
        interaction,
        title="Gemini 응답 대기 중",
        workFn=ask_gemini,
        workArgs=(내용,),
        resultPrefix="💬 **Gemini 답변**\n\n",
        errorLabel="질문",
    )


# ──────────────────── 설정 서브커맨드 그룹 ────────────────────

settingsGroup = app_commands.Group(name="설정", description="봇 설정 변경")


@settingsGroup.command(name="시간", description="자동 브리핑 시간을 변경합니다 (전체 공통)")
@app_commands.describe(시간="HH:MM 형식으로 입력 (예: 08:30)")
async def cmd_set_time(interaction: discord.Interaction, 시간: str):
    config = load_config()
    userId = str(interaction.user.id)

    # 등록 여부 확인 — 미등록 시 시간 변경 차단
    if userId not in config.get("users", {}):
        await interaction.response.send_message(
            "❌ 먼저 `/등록`을 실행해주세요.", ephemeral=True
        )
        return

    # 브리핑 시간 유효성 검사 후 전역 저장
    try:
        hh, mm = 시간.split(":")
        if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
            raise ValueError
        config["briefing_time"] = 시간
        save_config(config)
        log.info("[설정] 브리핑 시간 변경 → %s", 시간)
        await interaction.response.send_message(
            f"✅ 브리핑 시간이 **{시간}**으로 변경되었습니다.\n"
            f"(날씨 알림은 브리핑 30분 전인 **{_subtract_30min(시간)}**에 발송됩니다.)"
        )
    except ValueError:
        await interaction.response.send_message(
            "❌ 올바른 형식으로 입력해주세요. 예: `08:30`"
        )


@settingsGroup.command(name="지역", description="내 날씨 조회 지역을 변경합니다")
async def cmd_set_region(interaction: discord.Interaction):
    config = load_config()
    userId = str(interaction.user.id)
    if userId not in config.get("users", {}):
        await interaction.response.send_message(
            "❌ 먼저 `/등록`을 실행해주세요.", ephemeral=True
        )
        return
    # 지역 선택 버튼 표시
    view = RegionView(action="change")
    await interaction.response.send_message(
        "📍 **변경할 지역을 선택해주세요:**",
        view=view,
        ephemeral=True,
    )


@settingsGroup.command(name="뉴스카테고리", description="관심 뉴스 카테고리를 설정합니다")
@app_commands.describe(카테고리="뉴스 카테고리 선택")
@app_commands.choices(카테고리=[
    app_commands.Choice(name="종합", value="종합"),
    app_commands.Choice(name="경제", value="경제"),
    app_commands.Choice(name="IT", value="IT"),
    app_commands.Choice(name="스포츠", value="스포츠"),
])
async def cmd_set_news_category(interaction: discord.Interaction,
                                카테고리: app_commands.Choice[str]):
    # 등록 여부 확인 후 뉴스 카테고리 저장
    config = load_config()
    userId = str(interaction.user.id)
    if userId not in config.get("users", {}):
        await interaction.response.send_message(
            "❌ 먼저 `/등록`을 실행해주세요.", ephemeral=True
        )
        return

    config["users"][userId]["newsCategory"] = 카테고리.value
    save_config(config)
    log.info("[설정] 뉴스 카테고리 변경 → %s", 카테고리.value)
    await interaction.response.send_message(
        f"✅ 뉴스 카테고리가 **{카테고리.value}**(으)로 설정되었습니다.\n"
        f"브리핑과 `/뉴스` 명령에 반영됩니다.",
        ephemeral=True,
    )


@settingsGroup.command(name="항목", description="브리핑 항목을 켜거나 끕니다")
@app_commands.describe(항목="설정할 브리핑 항목", 상태="on 또는 off")
@app_commands.choices(
    항목=[
        app_commands.Choice(name="날씨", value="weather"),
        app_commands.Choice(name="미세먼지", value="dust"),
        app_commands.Choice(name="뉴스", value="news"),
        app_commands.Choice(name="옷차림", value="outfit"),
        app_commands.Choice(name="한마디", value="quote"),
    ],
    상태=[
        app_commands.Choice(name="on", value="on"),
        app_commands.Choice(name="off", value="off"),
    ],
)
async def cmd_set_section(interaction: discord.Interaction,
                          항목: app_commands.Choice[str],
                          상태: app_commands.Choice[str]):
    # 등록 여부 확인 후 개별 브리핑 항목 on/off 저장
    config = load_config()
    userId = str(interaction.user.id)
    if userId not in config.get("users", {}):
        await interaction.response.send_message(
            "❌ 먼저 `/등록`을 실행해주세요.", ephemeral=True
        )
        return

    # 기존 섹션 설정 로드 (미설정 시 전체 활성화)
    enabledSections = _get_user_sections(config["users"][userId])
    enabledSections[항목.value] = (상태.value == "on")
    config["users"][userId]["enabledSections"] = enabledSections
    save_config(config)

    statusEmoji = "✅ 켜짐" if 상태.value == "on" else "❌ 꺼짐"
    log.info("[설정] 항목 변경 — %s → %s", 항목.name, 상태.value)

    # 현재 전체 항목 상태 표시
    statusLines = []
    for key in ("weather", "dust", "news", "outfit", "quote"):
        korName = SECTION_KOR_NAMES[key]
        onOff = "✅" if enabledSections.get(key, True) else "❌"
        statusLines.append(f"  {onOff} {korName}")
    statusSummary = "\n".join(statusLines)

    await interaction.response.send_message(
        f"**{항목.name}** 항목이 **{statusEmoji}**(으)로 변경되었습니다.\n\n"
        f"📋 **현재 브리핑 항목 상태:**\n{statusSummary}",
        ephemeral=True,
    )


bot.tree.add_command(settingsGroup)


def _subtract_30min(timeStr: str) -> str:
    # 브리핑 시간에서 30분 뺀 알림 시간 계산
    h, m    = map(int, timeStr.split(":"))
    total   = h * 60 + m - 30
    if total < 0:
        total += 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"
