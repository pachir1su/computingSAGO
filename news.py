import time
import feedparser
from logger import setup_logger

log = setup_logger("news")

# 카테고리별 Google 뉴스 한국어 RSS 피드 URL
NEWS_CATEGORIES = {
    "종합": "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko",
    "경제": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtdHZHZ0pMVWlnQVAB?hl=ko&gl=KR&ceid=KR:ko",
    "IT":   "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtdHZHZ0pMVWlnQVAB?hl=ko&gl=KR&ceid=KR:ko",
    "스포츠": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FtdHZHZ0pMVWlnQVAB?hl=ko&gl=KR&ceid=KR:ko",
}

# 카테고리별 뉴스 캐시 (30분 유효)
_newsCache: dict = {}
_newsCacheTtl = 1800


def get_available_categories() -> list:
    # 사용 가능한 뉴스 카테고리 목록 반환
    return list(NEWS_CATEGORIES.keys())


def get_top_news(count: int = 3, category: str = "종합") -> list:
    # 캐시 유효 시 API 호출 없이 반환, 카테고리별 독립 캐싱
    now = time.time()
    if category in _newsCache:
        articles, cachedAt = _newsCache[category]
        if now - cachedAt < _newsCacheTtl:
            log.debug("뉴스 캐시 사용 (카테고리: %s)", category)
            return articles[:count]

    # 카테고리에 해당하는 RSS URL 결정 (없으면 종합)
    rssUrl = NEWS_CATEGORIES.get(category, NEWS_CATEGORIES["종합"])

    try:
        feed = feedparser.parse(rssUrl)
        if not feed.entries:
            raise RuntimeError("뉴스를 불러오지 못했습니다. RSS 피드를 확인해주세요.")

        # 파싱 결과 캐시 저장
        articles = [{"title": e.title, "link": e.link} for e in feed.entries]
        _newsCache[category] = (articles, now)
        log.info("뉴스 피드 갱신 완료 (카테고리: %s, %d건)", category, len(articles))
        return articles[:count]

    except Exception as e:
        log.error("뉴스 파싱 실패 (카테고리: %s): %s", category, e)
        raise RuntimeError(f"뉴스 파싱 오류: {e}")
