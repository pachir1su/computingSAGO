import os
import threading
from google import genai
from dotenv import load_dotenv
from weather import get_weather, get_forecast
from news import get_top_news
from logger import setup_logger

load_dotenv()
log = setup_logger("report")

# 다중 API 키 라운드 로빈 — 키당 20회/일, 3키 = 60회/일
_API_KEYS = [k for k in [
    os.getenv("GEMINI_API_KEY"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
] if k]
_clients  = [genai.Client(api_key=k) for k in _API_KEYS]
_MODEL    = "gemini-2.5-flash"
_keyIndex = 0
_keyLock  = threading.Lock()

# 브리핑 항목 기본값 (전체 활성화)
DEFAULT_SECTIONS = {
    "weather": True,
    "dust":    True,
    "news":    True,
    "outfit":  True,
    "quote":   True,
}

# 섹션별 이모지·제목·설명 매핑
_SECTION_META = {
    "weather": ("🌤", "오늘의 날씨", "오늘 날씨 친근하게 설명 + 내일 날씨 한 줄 예고 포함 (데이터가 있는 경우)"),
    "dust":    ("💨", "미세먼지", "등급과 주의사항 (1-2문장)"),
    "news":    ("📰", "주요 뉴스", "각 뉴스를 한 줄로 요약"),
    "outfit":  ("👗", "옷차림 추천", "날씨에 맞는 옷차림 (2-3문장)"),
    "quote":   ("💬", "오늘의 한마디", "하루를 시작하는 짧은 응원 메시지"),
}


def _ask(prompt: str) -> str:
    # 라운드 로빈으로 Gemini 클라이언트 순회, 429 시 자동 키 전환
    global _keyIndex
    if not _clients:
        raise RuntimeError("Gemini API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")

    for _ in range(len(_clients)):
        with _keyLock:
            idx = _keyIndex
        try:
            response = _clients[idx].models.generate_content(model=_MODEL, contents=prompt)
            with _keyLock:
                _keyIndex = (idx + 1) % len(_clients)
            return response.text
        except Exception as e:
            errMsg = str(e)
            if "429" in errMsg or "RESOURCE_EXHAUSTED" in errMsg:
                log.warning("Gemini API 키 %d 한도 초과, 다음 키로 전환", idx)
                with _keyLock:
                    _keyIndex = (idx + 1) % len(_clients)
                continue
            raise RuntimeError(f"Gemini AI 오류: {e}")

    raise RuntimeError("모든 Gemini API 키의 일일 한도를 초과했습니다. 내일 다시 이용해주세요.")


def generate_report(city: str = "Seoul", newsCategory: str = "종합",
                    enabledSections: dict = None) -> str:
    # 활성화된 섹션에 필요한 데이터만 수집 후, Gemini에 맞춤 프롬프트 전송
    sections = enabledSections if enabledSections else dict(DEFAULT_SECTIONS)

    # 날씨 데이터가 필요한 섹션 존재 여부 판별
    needsWeather = any(sections.get(s) for s in ("weather", "dust", "outfit"))
    needsNews = sections.get("news", True)

    weatherData = None
    forecastData = None
    newsList = None

    # 날씨 API 호출 (날씨·미세먼지·옷차림 중 하나라도 켜져 있으면)
    if needsWeather:
        try:
            weatherData = get_weather(city)
            forecastData = get_forecast(city)
        except Exception as e:
            log.error("날씨 데이터 조회 실패 (%s): %s", city, e)

    # 뉴스 RSS 호출 (뉴스 항목이 켜져 있으면)
    if needsNews:
        try:
            newsList = get_top_news(3, category=newsCategory)
        except Exception as e:
            log.error("뉴스 데이터 조회 실패 (%s): %s", newsCategory, e)

    # 데이터 블록 구성
    dataBlock = ""
    if weatherData:
        dataBlock += (
            f"\n[오늘 날씨]\n"
            f"도시: {weatherData['city']}\n"
            f"기온: {weatherData['temp']}°C (체감: {weatherData['feelsLike']}°C)\n"
            f"날씨: {weatherData['description']}, "
            f"습도: {weatherData['humidity']}%, 풍속: {weatherData['windSpeed']}m/s\n"
            f"미세먼지: {weatherData['aqiLabel']} "
            f"(PM2.5: {weatherData['pm25']:.1f}㎍/㎥, PM10: {weatherData['pm10']:.1f}㎍/㎥)\n"
        )
        if forecastData:
            rainNote = " (비 예보 있음 ☔)" if forecastData["rainExpected"] else ""
            dataBlock += (
                f"\n[내일 날씨 예보]\n"
                f"최저 {forecastData['minTemp']}°C / 최고 {forecastData['maxTemp']}°C, "
                f"{forecastData['description']}{rainNote}\n"
            )

    if newsList:
        newsText = "\n".join(f"- {n['title']}" for n in newsList)
        dataBlock += f"\n[오늘의 주요 뉴스]\n{newsText}\n"

    # 요청 섹션 목록 동적 구성
    sectionLines = []
    sectionNum = 1
    for key in ("weather", "dust", "news", "outfit", "quote"):
        if sections.get(key, True):
            emoji, title, desc = _SECTION_META[key]
            sectionLines.append(f"{sectionNum}. {emoji} **{title}** - {desc}")
            sectionNum += 1

    if not sectionLines:
        return "활성화된 브리핑 항목이 없습니다. `/설정 항목`으로 항목을 켜주세요."

    sectionsText = "\n".join(sectionLines)

    prompt = (
        f"다음 데이터를 바탕으로 자연스러운 한국어 아침 브리핑을 작성해주세요.\n"
        f"{dataBlock}\n"
        f"다음 형식으로 작성해주세요:\n"
        f"{sectionsText}\n\n"
        f"친근하고 따뜻한 톤으로 작성해주세요."
    )
    return _ask(prompt)


def generate_weather_summary(city: str = "Seoul") -> str:
    # 날씨 + 내일 예보 단독 Gemini 요약
    w = get_weather(city)
    forecast = get_forecast(city)

    forecastLine = ""
    if forecast:
        rainNote = " 비 예보 있음" if forecast["rainExpected"] else ""
        forecastLine = (
            f"\n내일: 최저 {forecast['minTemp']}°C / 최고 {forecast['maxTemp']}°C, "
            f"{forecast['description']}{rainNote}"
        )

    prompt = (
        f"다음 날씨 정보를 친근한 한국어로 3-4문장으로 요약해주세요.\n"
        f"오늘: 기온 {w['temp']}°C (체감 {w['feelsLike']}°C), 날씨 {w['description']}, "
        f"습도 {w['humidity']}%, 미세먼지 {w['aqiLabel']}{forecastLine}"
    )
    return f"🌤 **{city} 날씨**\n\n{_ask(prompt)}"


def generate_news_summary(category: str = "종합") -> str:
    # 뉴스 헤드라인 Gemini 요약 생성 (카테고리 반영)
    newsList = get_top_news(5, category=category)
    newsText = "\n".join(f"- {n['title']}" for n in newsList)
    prompt = (
        f"다음 뉴스 헤드라인을 각각 한 줄로 요약해주세요. "
        f"친근하고 이해하기 쉽게 작성해주세요.\n{newsText}"
    )
    return f"📰 **오늘의 주요 뉴스 ({category})**\n\n{_ask(prompt)}"


def ask_gemini(question: str) -> str:
    # 사용자 자유 질문을 Gemini에 전달
    return _ask(question)
