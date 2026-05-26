import feedparser

NEWS_RSS_URL = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"


def get_top_news(count: int = 3) -> list:
    feed = feedparser.parse(NEWS_RSS_URL)
    return [
        {"title": entry.title, "link": entry.link}
        for entry in feed.entries[:count]
    ]
