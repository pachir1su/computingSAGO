import time
import feedparser
from logger import get_logger

# Google 뉴스 한국어 RSS 피드
newsRssUrl = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"

logger = get_logger(__name__)

# 뉴스 캐시 (30분 유효 — RSS 폴링 빈도 제한)
_newsCache = None
_newsCachedAt = 0
_newsCacheTtl = 1800


def get_top_news(count: int = 3) -> list:
    global _newsCache, _newsCachedAt

    # 캐시 유효 시 API 호출 없이 반환
    now = time.time()
    if _newsCache is not None and now - _newsCachedAt < _newsCacheTtl:
        return _newsCache[:count]

    try:
        feed = feedparser.parse(newsRssUrl)
        if not feed.entries:
            raise RuntimeError("뉴스를 불러오지 못했습니다. RSS 피드를 확인해주세요.")

        # 파싱 결과 캐시 저장
        _newsCache    = [{"title": e.title, "link": e.link} for e in feed.entries]
        _newsCachedAt = now
        return _newsCache[:count]

    except Exception as e:
        logger.error("뉴스 파싱 오류: %s", e, exc_info=True)
        raise RuntimeError(f"뉴스 파싱 오류: {e}") from e
