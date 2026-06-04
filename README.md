# computingSAGO
2026 한국기술교육대학교 컴퓨팅사고 27분반 팀 프로젝트

---
## 버전 기록
v0.2.8 QA 통과 -> '/설정 시간' 멸령으로 리포트 받으려면 최소 65초 전에 보낼 것. <br>
v0.3.0-rc.1 -> v0.2.19에서 v0.2.8 코드로 revert : QA 통과 <br> 
v0.3.1 QA 통과  <br>
v0.3.2 QA 통과

---

## 봇 초대
https://discord.com/oauth2/authorize?client_id=1508347619989262557

---

## 데일리 리포트 AI

> 설정한 시간에(기본 아침) AI가 날씨 · 뉴스 · 미세먼지를 종합해 Discord DM으로 자동 브리핑해주는 개인 비서 봇

---

## 프로젝트 소개

매일 아침 날씨 앱, 뉴스 앱, 미세먼지 앱을 따로따로 확인해야 하는 게 불편해서 만들었습니다.<br>
**데일리 리포트 AI**는 이 모든 정보를 자동으로 수집하고 Gemini API가 자연어 리포트로 종합하여 Discord 개인 DM으로 자동 발송합니다.  
사용자는 아무것도 하지 않아도 매일 아침 브리핑을 받을 수 있습니다.

---

## 주요 기능

### 자동 데일리 브리핑
매일 지정한 시간(기본값 : 오전 7시)에 자동으로 실행되어 Discord DM으로 리포트를 발송합니다.

| 항목 | 내용 |
|------|------|
| 날씨 | 오늘 날씨 + 기온 + 체감 기온 |
| 미세먼지 | 등급 (좋음 / 보통 / 나쁨 / 매우 나쁨) |
| 뉴스 | 주요 뉴스 3건 AI 요약 |
| 오늘의 한마디 | Gemini가 생성하는 오늘의 메시지 |


### Discord 슬래시 커맨드

| 명령어 | 설명 |
|--------|------|
| `/리포트` | 즉시 리포트 생성 및 발송 |
| `/날씨` | 현재 날씨 단독 조회 |
| `/뉴스` | 최신 뉴스 단독 요약 |
| `/질문 [내용]` | Gemini에게 자유 질문 |
| `/설정 시간 [HH:MM]` | 자동 브리핑 시간 변경 |
| `/설정 지역 [지역명]` | 날씨 조회 지역 변경 |

---



## 설치 및 실행

### 1. 저장소 클론

```bash
git clone https://github.com/pachir1su/computingSAGO.git
cd computingSAGO
```

### 2. 라이브러리 설치

```bash
pip install -r requirements.txt
```

또는 Thonny에서 `도구 → 패키지 관리`에서 아래 패키지를 설치하세요.

```
discord.py
google-generativeai
schedule
requests
feedparser
python-dotenv
```

### 3. API 키 설정

`.env.example`을 복사하여 `.env` 파일을 생성하고 키를 입력합니다.

```bash
cp .env.example .env
```

```env
GEMINI_API_KEY=여기에_Gemini_API_키_입력
DISCORD_TOKEN=여기에_Discord_봇_토큰_입력
OPENWEATHER_API_KEY=여기에_OpenWeatherMap_API_키_입력
DISCORD_USER_ID=여기에_본인_Discord_사용자_ID_입력
```

### 4. 실행

```bash
python main.py
```

---

## API 키 발급 방법

| API | 발급처 | 비고 |
|-----|--------|------|
| Gemini API | [Google AI Studio](https://aistudio.google.com) | 무료 |
| Discord Bot Token | [Discord Developer Portal](https://discord.com/developers) | 무료 |
| OpenWeatherMap | [openweathermap.org](https://openweathermap.org/api) | 무료 플랜 사용 |

---

## 시스템 흐름도

```
[schedule - 매일 지정 시간 자동 트리거]
                │
                ▼
     ┌─────────────────────┐
     │     데이터 수집      │
     │  날씨 / 미세먼지 API │
     │  뉴스 RSS 파싱       │
     └──────────┬──────────┘
                │
                ▼
     ┌─────────────────────┐
     │    Gemini AI 처리    │
     │  자연어 리포트 생성   │
     │  옷차림 / 한마디 생성 │
     └──────────┬──────────┘
                │
                ▼
     ┌─────────────────────┐
     │    Discord 봇       │
     │  개인 DM 자동 발송   │
     │  슬래시 커맨드 응답  │
     └─────────────────────┘
```

