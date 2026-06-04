import os
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# .env에서 키 로드 — 앞뒤 공백·따옴표 제거 (복붙 실수 방지)
apiKey      = (os.getenv("OPENWEATHER_API_KEY") or "").strip().strip('"').strip("'")
weatherUrl  = "https://api.openweathermap.org/data/2.5/weather"
forecastUrl = "https://api.openweathermap.org/data/2.5/forecast"
airUrl      = "https://api.openweathermap.org/data/2.5/air_pollution"
aqiLabels   = {1: "좋음 😊", 2: "보통 😐", 3: "보통 😐", 4: "나쁨 😷", 5: "매우 나쁨 🤢"}

# 날씨·예보 캐시 (10분 유효)
_weatherCache  = {}
_forecastCache = {}
_cacheTtl = 600

if not apiKey:
    print("[날씨] ❌ OPENWEATHER_API_KEY가 .env에 없습니다!")


def _request(url: str, params: dict) -> dict:
    # HTTP GET 공통 처리 — 상태 코드별 명확한 오류 안내
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 401:
            raise ValueError(
                "OpenWeatherMap API 키가 유효하지 않습니다.\n"
                ".env 파일의 OPENWEATHER_API_KEY를 확인하세요.\n"
                "(새로 발급한 키는 최대 2시간 후 활성화됩니다.)"
            )
        if resp.status_code == 404:
            raise ValueError(
                "도시를 찾을 수 없습니다.\n"
                "영문 도시명을 사용해보세요. (예: Seoul, Busan, Incheon, Cheonan)"
            )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        raise ConnectionError("인터넷 연결을 확인해주세요.")
    except requests.exceptions.Timeout:
        raise TimeoutError("날씨 서버 응답 시간 초과. 잠시 후 다시 시도해주세요.")


def get_weather(city: str = "Seoul") -> dict:
    # 캐시 유효 시 API 호출 없이 반환
    cacheKey = city.lower()
    now = time.time()
    if cacheKey in _weatherCache:
        cachedData, cachedAt = _weatherCache[cacheKey]
        if now - cachedAt < _cacheTtl:
            return cachedData

    # 도시명으로 날씨 직접 조회 — 응답에 좌표 포함
    weatherData = _request(weatherUrl, {
        "q": city, "appid": apiKey, "units": "metric", "lang": "kr"
    })

    # 날씨 응답의 좌표로 미세먼지 조회 (Geocoding API 불필요)
    lat        = weatherData["coord"]["lat"]
    lon        = weatherData["coord"]["lon"]
    airData    = _request(airUrl, {"lat": lat, "lon": lon, "appid": apiKey})
    aqi        = airData["list"][0]["main"]["aqi"]
    components = airData["list"][0]["components"]

    result = {
        "city":        city,
        "temp":        round(weatherData["main"]["temp"]),
        "feelsLike":   round(weatherData["main"]["feels_like"]),
        "description": weatherData["weather"][0]["description"],
        "humidity":    weatherData["main"]["humidity"],
        "windSpeed":   weatherData["wind"]["speed"],
        "aqi":         aqi,
        "aqiLabel":    aqiLabels.get(aqi, "알 수 없음"),
        "pm25":        components.get("pm2_5", 0),
        "pm10":        components.get("pm10", 0),
    }

    _weatherCache[cacheKey] = (result, now)
    return result


def get_forecast(city: str = "Seoul") -> dict | None:
    # 내일 날씨 예보 조회 (OpenWeatherMap 5일 예보 API)
    cacheKey = city.lower()
    now = time.time()
    if cacheKey in _forecastCache:
        cachedData, cachedAt = _forecastCache[cacheKey]
        if now - cachedAt < _cacheTtl:
            return cachedData

    try:
        data = _request(forecastUrl, {
            "q": city, "appid": apiKey, "units": "metric", "lang": "kr", "cnt": 16
        })
    except Exception:
        return None

    # 내일 날짜에 해당하는 예보 항목만 필터링
    tomorrowDate  = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrowItems = [item for item in data["list"] if item["dt_txt"].startswith(tomorrowDate)]
    if not tomorrowItems:
        return None

    temps       = [item["main"]["temp"] for item in tomorrowItems]
    rainWeather = {"Rain", "Drizzle", "Thunderstorm"}
    rainExpected = any(item["weather"][0]["main"] in rainWeather for item in tomorrowItems)
    midItem      = tomorrowItems[len(tomorrowItems) // 2]

    result = {
        "minTemp":     round(min(temps)),
        "maxTemp":     round(max(temps)),
        "description": midItem["weather"][0]["description"],
        "rainExpected": rainExpected,
    }

    _forecastCache[cacheKey] = (result, now)
    return result


def check_weather_alerts(city: str = "Seoul") -> list:
    # 미세먼지·강수 조건 확인 — 조건 충족 시 경보 문자열 반환
    alerts = []
    try:
        w = get_weather(city)
        if w["aqi"] >= 4:
            alerts.append(f"💨 미세먼지 **{w['aqiLabel']}** — 외출 시 마스크를 꼭 착용하세요!")
    except Exception:
        pass

    try:
        forecast = get_forecast(city)
        if forecast and forecast["rainExpected"]:
            alerts.append("☔ 오늘 **비 예보**가 있습니다. 우산을 챙기세요!")
    except Exception:
        pass

    return alerts
