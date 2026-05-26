import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# OpenWeatherMap API 엔드포인트 및 키
apiKey    = os.getenv("OPENWEATHER_API_KEY")
geoUrl    = "http://api.openweathermap.org/geo/1.0/direct"
weatherUrl = "https://api.openweathermap.org/data/2.5/weather"
airUrl    = "https://api.openweathermap.org/data/2.5/air_pollution"
aqiLabels = {1: "좋음 😊", 2: "보통 😐", 3: "보통 😐", 4: "나쁨 😷", 5: "매우 나쁨 🤢"}

# 날씨 캐시 (10분 유효 — API 호출 횟수 절약)
_weatherCache = {}
_cacheTtl = 600


def _request(url: str, params: dict) -> dict:
    # HTTP GET 요청 공통 처리 — 401/연결 오류 명시적 안내
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 401:
            raise ValueError(
                "OpenWeatherMap API 키가 유효하지 않습니다.\n"
                ".env 파일의 OPENWEATHER_API_KEY를 확인하세요.\n"
                "(새로 발급한 키는 최대 2시간 후 활성화됩니다.)"
            )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        raise ConnectionError("인터넷 연결을 확인해주세요.")
    except requests.exceptions.Timeout:
        raise TimeoutError("날씨 서버 응답 시간 초과. 잠시 후 다시 시도해주세요.")


def _get_coordinates(city: str) -> tuple:
    # 도시명 → 위경도 좌표 변환 (Geocoding API)
    geoData = _request(geoUrl, {"q": city, "limit": 1, "appid": apiKey})
    if not geoData:
        raise ValueError(f"도시를 찾을 수 없습니다: '{city}'\n영문 도시명을 사용해보세요. (예: Seoul, Busan)")
    return geoData[0]["lat"], geoData[0]["lon"]


def get_weather(city: str = "Seoul") -> dict:
    # 캐시 확인 — 유효한 캐시가 있으면 API 호출 없이 반환
    cacheKey = city.lower()
    now = time.time()
    if cacheKey in _weatherCache:
        cachedData, cachedAt = _weatherCache[cacheKey]
        if now - cachedAt < _cacheTtl:
            return cachedData

    # 좌표 조회 후 날씨·대기질 병렬 요청
    lat, lon = _get_coordinates(city)
    coordParams = {"lat": lat, "lon": lon, "appid": apiKey}

    weatherData = _request(weatherUrl, {**coordParams, "units": "metric", "lang": "kr"})
    airData     = _request(airUrl, coordParams)

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

    # 결과 캐시 저장
    _weatherCache[cacheKey] = (result, now)
    return result
