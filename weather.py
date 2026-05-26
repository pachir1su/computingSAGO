import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# .env에서 키 로드 — 앞뒤 공백·따옴표 제거 (복붙 실수 방지)
apiKey     = (os.getenv("OPENWEATHER_API_KEY") or "").strip().strip('"').strip("'")
weatherUrl = "https://api.openweathermap.org/data/2.5/weather"
airUrl     = "https://api.openweathermap.org/data/2.5/air_pollution"
aqiLabels  = {1: "좋음 😊", 2: "보통 😐", 3: "보통 😐", 4: "나쁨 😷", 5: "매우 나쁨 🤢"}

# 날씨 캐시 (10분 유효 — API 호출 횟수 절약)
_weatherCache = {}
_cacheTtl = 600

# ── 시작 시 API 키 진단 ───────────────────────────────────────────
if not apiKey:
    print("[날씨] ❌ OPENWEATHER_API_KEY가 .env에 없습니다!")
else:
    maskedKey = apiKey[:4] + "*" * (len(apiKey) - 8) + apiKey[-4:]
    print(f"[날씨] API 키: {maskedKey} (총 {len(apiKey)}자)")

    # 공백·특수문자 포함 여부 확인
    badChars = [c for c in apiKey if not c.isalnum()]
    if badChars:
        print(f"[날씨] ⚠️  키에 이상한 문자 포함: {badChars}  ← .env 따옴표 등 확인 필요")

    # 실제 API 호출 테스트
    print("[날씨] API 연결 테스트 중...")
    try:
        testResp = requests.get(
            weatherUrl,
            params={"q": "Seoul", "appid": apiKey, "units": "metric"},
            timeout=10,
        )
        if testResp.status_code == 200:
            print("[날씨] ✅ API 연결 성공!")
        else:
            print(f"[날씨] ❌ 테스트 실패 — 코드: {testResp.status_code}")
            print(f"[날씨] 응답: {testResp.text}")
    except Exception as testErr:
        print(f"[날씨] ❌ 네트워크 오류: {testErr}")
# ─────────────────────────────────────────────────────────────────


def _request(url: str, params: dict) -> dict:
    # HTTP GET 공통 처리 — 요청/응답 전체를 터미널에 출력
    maskedParams = {k: (v[:4] + "****" if k == "appid" else v) for k, v in params.items()}
    print(f"[날씨] GET {url}")
    print(f"[날씨] 파라미터: {maskedParams}")

    try:
        resp = requests.get(url, params=params, timeout=10)
        print(f"[날씨] 응답 코드: {resp.status_code}")
        print(f"[날씨] 응답 본문: {resp.text[:300]}")

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
            print(f"[날씨] 캐시 반환 ({city})")
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
