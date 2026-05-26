import requests
import json

city = "Seoul"
# 발급받으신 API Key를 확인해주세요. 
# 만약 방금 가입하셨다면 활성화에 10분~수십 분이 걸릴 수 있습니다.
apiKey = "your_api_key_ssakssak" 
lang = 'kr'
units = 'metric'
api = f"https://api.openweathermap.org/data/2.5/weather?q={city}&APPID={apiKey}&lang={lang}&units={units}"

result = requests.get(api)
result = json.loads(result.text)

# 디버깅을 위해 API가 반환한 실제 응답 전체를 출력해봅니다.
# 정상적이라면 날씨 정보가, 문제가 있다면 에러 메시지(cod: 401 등)가 출력됩니다.
if 'main' in result:
    print(f"온도: {result['main']['temp']}°C")
    print(f"날씨: {result['weather'][0]['description']}")
else:
    print("⚠️ API 요청에 실패했습니다. 아래 응답 내용을 확인하세요:")
    print(json.dumps(result, indent=4, ensure_ascii=False))
