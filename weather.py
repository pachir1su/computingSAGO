import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GEO_URL = "http://api.openweathermap.org/geo/1.0/direct"
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
AIR_URL = "https://api.openweathermap.org/data/2.5/air_pollution"

AQI_LABELS = {1: "좋음 😊", 2: "보통 😐", 3: "보통 😐", 4: "나쁨 😷", 5: "매우 나쁨 🤢"}


def _get_coordinates(city: str) -> tuple:
    response = requests.get(GEO_URL, params={"q": city, "limit": 1, "appid": OPENWEATHER_API_KEY})
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError(f"도시를 찾을 수 없습니다: {city}")
    return data[0]["lat"], data[0]["lon"]


def get_weather(city: str = "Seoul") -> dict:
    lat, lon = _get_coordinates(city)

    weather_resp = requests.get(
        WEATHER_URL,
        params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "kr"},
    )
    weather_resp.raise_for_status()
    w = weather_resp.json()

    air_resp = requests.get(AIR_URL, params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY})
    air_resp.raise_for_status()
    a = air_resp.json()

    aqi = a["list"][0]["main"]["aqi"]
    components = a["list"][0]["components"]

    return {
        "city": city,
        "temp": round(w["main"]["temp"]),
        "feels_like": round(w["main"]["feels_like"]),
        "description": w["weather"][0]["description"],
        "humidity": w["main"]["humidity"],
        "wind_speed": w["wind"]["speed"],
        "aqi": aqi,
        "aqi_label": AQI_LABELS.get(aqi, "알 수 없음"),
        "pm25": components.get("pm2_5", 0),
        "pm10": components.get("pm10", 0),
    }
