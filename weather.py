import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# OpenWeatherMap API 엔드포인트 (Geocoding API 미사용 — 도시명 직접 호출)
apiKey     = os.getenv("OPENWEATHER_API_KEY")
weatherUrl = "https://api.openweathermap.org/data/2.5/weather"
airUrl     = "https://api.openweathermap.org/data/2.5/air_pollution"
aqiLabels  = {1: "좋음 😊", 2: "보통 😐", 3: "보통 😐", 4: "나쁨 😷", 5: "매우 나쁨 🤢"}

# 날씨 캐시 (10분 유효 — API 호출 횟수 절약)
_weatherCache = {}
_cacheTtl = 600


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
                "영문 도시명을 사용해보세요. (예: Seoul, Busan, Incheon, Daejeon)"
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

    # 결과 캐시 저장
    _weatherCache[cacheKey] = (result, now)
    return result
