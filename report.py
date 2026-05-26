import os
import google.generativeai as genai
from dotenv import load_dotenv
from weather import get_weather
from news import get_top_news

load_dotenv()

# Gemini 모델 초기화
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
geminiModel = genai.GenerativeModel("gemini-2.5-flash")


def _ask(prompt: str) -> str:
    # Gemini에 프롬프트 전송 및 텍스트 응답 반환
    try:
        response = geminiModel.generate_content(prompt)
        return response.text
    except Exception as e:
        raise RuntimeError(f"Gemini AI 오류: {e}")


def generate_report(city: str = "Seoul") -> str:
    # 날씨 + 뉴스 데이터를 합쳐 전체 아침 브리핑 생성
    weatherData = get_weather(city)
    newsList    = get_top_news(3)
    newsText    = "\n".join(f"- {n['title']}" for n in newsList)

    prompt = f"""
다음 데이터를 바탕으로 자연스러운 한국어 아침 브리핑을 작성해주세요.

[날씨 데이터]
도시: {weatherData['city']}
기온: {weatherData['temp']}°C (체감: {weatherData['feelsLike']}°C)
날씨: {weatherData['description']}, 습도: {weatherData['humidity']}%, 풍속: {weatherData['windSpeed']}m/s
미세먼지: {weatherData['aqiLabel']} (PM2.5: {weatherData['pm25']:.1f}㎍/㎥, PM10: {weatherData['pm10']:.1f}㎍/㎥)

[오늘의 주요 뉴스]
{newsText}

다음 형식으로 작성해주세요:
1. 🌤 **오늘의 날씨** - 날씨를 친근하게 설명 (2-3문장)
2. 💨 **미세먼지** - 등급과 주의사항 (1-2문장)
3. 📰 **주요 뉴스** - 각 뉴스를 한 줄로 요약
4. 👗 **옷차림 추천** - 날씨에 맞는 옷차림 (2-3문장)
5. 💬 **오늘의 한마디** - 하루를 시작하는 짧은 응원 메시지

친근하고 따뜻한 톤으로 작성해주세요.
"""
    return _ask(prompt)


def generate_weather_summary(city: str = "Seoul") -> str:
    # 날씨 단독 Gemini 요약 생성
    w = get_weather(city)
    prompt = f"""
다음 날씨 정보를 친근한 한국어로 3-4문장으로 요약해주세요.
기온 {w['temp']}°C (체감 {w['feelsLike']}°C), 날씨 {w['description']},
습도 {w['humidity']}%, 미세먼지 {w['aqiLabel']}
"""
    return f"🌤 **{city} 현재 날씨**\n\n{_ask(prompt)}"


def generate_news_summary() -> str:
    # 뉴스 헤드라인 Gemini 요약 생성
    newsList = get_top_news(5)
    newsText = "\n".join(f"- {n['title']}" for n in newsList)
    prompt   = f"""
다음 뉴스 헤드라인을 각각 한 줄로 요약해주세요. 친근하고 이해하기 쉽게 작성해주세요.
{newsText}
"""
    return f"📰 **오늘의 주요 뉴스**\n\n{_ask(prompt)}"


def ask_gemini(question: str) -> str:
    # 사용자 자유 질문을 Gemini에 전달
    return _ask(question)
