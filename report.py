import os
import google.generativeai as genai
from dotenv import load_dotenv
from weather import get_weather
from news import get_top_news

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")


def _ask(prompt: str) -> str:
    return model.generate_content(prompt).text


def generate_report(city: str = "Seoul") -> str:
    weather = get_weather(city)
    news_list = get_top_news(3)
    news_text = "\n".join(f"- {n['title']}" for n in news_list)

    prompt = f"""
다음 데이터를 바탕으로 자연스러운 한국어 아침 브리핑을 작성해주세요.

[날씨 데이터]
도시: {weather['city']}
기온: {weather['temp']}°C (체감: {weather['feels_like']}°C)
날씨: {weather['description']}, 습도: {weather['humidity']}%, 풍속: {weather['wind_speed']}m/s
미세먼지: {weather['aqi_label']} (PM2.5: {weather['pm25']:.1f}㎍/㎥, PM10: {weather['pm10']:.1f}㎍/㎥)

[오늘의 주요 뉴스]
{news_text}

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
    w = get_weather(city)
    prompt = f"""
다음 날씨 정보를 친근한 한국어로 3-4문장으로 요약해주세요.
기온 {w['temp']}°C (체감 {w['feels_like']}°C), 날씨 {w['description']},
습도 {w['humidity']}%, 미세먼지 {w['aqi_label']}
"""
    return f"🌤 **{city} 현재 날씨**\n\n{_ask(prompt)}"


def generate_news_summary() -> str:
    news_list = get_top_news(5)
    news_text = "\n".join(f"- {n['title']}" for n in news_list)
    prompt = f"""
다음 뉴스 헤드라인을 각각 한 줄로 요약해주세요. 친근하고 이해하기 쉽게 작성해주세요.
{news_text}
"""
    return f"📰 **오늘의 주요 뉴스**\n\n{_ask(prompt)}"


def ask_gemini(question: str) -> str:
    return _ask(question)
