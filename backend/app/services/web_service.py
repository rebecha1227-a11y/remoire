import json
import logging
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.database import get_db

logger = logging.getLogger(__name__)
BJ_TZ = timezone(timedelta(hours=8))

BROWSER_DATA_DIR = Path("/opt/remoire/backend/data/browser_profile")
BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)

_playwright = None
_browser_context = None
_page = None
_lock = asyncio.Lock()


async def _get_page():
    global _playwright, _browser_context, _page
    async with _lock:
        if _page and not _page.is_closed():
            return _page
        try:
            from playwright.async_api import async_playwright
            if _playwright is None:
                _playwright = await async_playwright().start()
            _browser_context = await _playwright.chromium.launch_persistent_context(
                str(BROWSER_DATA_DIR),
                headless=True,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )
            _page = _browser_context.pages[0] if _browser_context.pages else await _browser_context.new_page()
            return _page
        except Exception as e:
            logger.error("启动浏览器失败: %s", e)
            raise


async def close_browser():
    global _playwright, _browser_context, _page
    if _browser_context:
        await _browser_context.close()
        _browser_context = None
        _page = None
    if _playwright:
        await _playwright.stop()
        _playwright = None


JS_EXTRACT_GENERIC = """
(() => {
    const title = document.title || '';
    const getText = (sel) => {
        const els = document.querySelectorAll(sel);
        return Array.from(els).map(e => e.innerText?.trim()).filter(Boolean);
    };
    const article = document.querySelector('article')?.innerText
        || document.querySelector('[role="main"]')?.innerText
        || document.querySelector('.content, .post-content, .article-content, main')?.innerText
        || '';
    const h1 = document.querySelector('h1')?.innerText || '';
    const paragraphs = getText('p').join('\\n');
    const body = article || paragraphs || document.body?.innerText?.substring(0, 5000) || '';
    return { title, h1, body: body.substring(0, 4000) };
})()
"""

JS_EXTRACT_XIAOHONGSHU = """
(() => {
    const title = document.querySelector('#detail-title, .title, .note-title, [class*="title"]')?.innerText || document.title || '';
    const content = document.querySelector('#detail-desc, .desc, .note-content, .content, [class*="desc"]')?.innerText || '';
    const author = document.querySelector('.author-name, .user-name, [class*="author"], [class*="nickname"]')?.innerText || '';
    const likes = document.querySelector('[class*="like"] span, .like-count')?.innerText || '';
    const comments = [];
    document.querySelectorAll('.comment-item, .comment, [class*="comment-item"], [class*="commentItem"]').forEach(el => {
        const user = el.querySelector('.user-name, .name, [class*="name"]')?.innerText || '';
        const text = el.querySelector('.content, .text, [class*="content"]')?.innerText || '';
        if (text) comments.push({ user, text: text.substring(0, 200) });
    });
    return { title, content: content.substring(0, 3000), author, likes, comments: comments.slice(0, 30) };
})()
"""

JS_EXTRACT_TWITTER = """
(() => {
    const tweets = [];
    document.querySelectorAll('article[data-testid="tweet"], article').forEach(el => {
        const author = el.querySelector('[data-testid="User-Name"], [class*="user"]')?.innerText || '';
        const text = el.querySelector('[data-testid="tweetText"], [class*="tweet-text"]')?.innerText || '';
        const time = el.querySelector('time')?.getAttribute('datetime') || '';
        const stats = el.querySelector('[role="group"]')?.innerText || '';
        if (text) tweets.push({ author: author.substring(0, 100), text: text.substring(0, 500), time, stats: stats.substring(0, 100) });
    });
    const mainTweet = tweets[0] || {};
    const replies = tweets.slice(1, 20);
    return { mainTweet, replies, pageTitle: document.title };
})()
"""

JS_SCROLL_AND_WAIT = """
window.scrollBy(0, window.innerHeight);
await new Promise(r => setTimeout(r, 1500));
"""


async def browse_url(url: str, extract_js: str = None) -> dict:
    try:
        page = await _get_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(2000)

        js = extract_js or JS_EXTRACT_GENERIC
        data = await page.evaluate(js)

        return {"ok": True, "url": url, "data": data}
    except Exception as e:
        logger.error("浏览网页失败 %s: %s", url, e)
        return {"ok": False, "url": url, "error": str(e)}


async def browse_xiaohongshu(url: str) -> dict:
    try:
        page = await _get_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        for _ in range(2):
            await page.evaluate("window.scrollBy(0, 600)")
            await page.wait_for_timeout(1000)

        data = await page.evaluate(JS_EXTRACT_XIAOHONGSHU)
        return {"ok": True, "url": url, "data": data}
    except Exception as e:
        logger.error("浏览小红书失败 %s: %s", url, e)
        return {"ok": False, "url": url, "error": str(e)}


async def browse_twitter(url: str) -> dict:
    try:
        page = await _get_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 800)")
            await page.wait_for_timeout(1500)

        data = await page.evaluate(JS_EXTRACT_TWITTER)
        return {"ok": True, "url": url, "data": data}
    except Exception as e:
        logger.error("浏览推特失败 %s: %s", url, e)
        return {"ok": False, "url": url, "error": str(e)}


async def search_on_page(platform: str, query: str) -> dict:
    from urllib.parse import quote_plus
    search_urls = {
        "xiaohongshu": f"https://www.xiaohongshu.com/search_result?keyword={quote_plus(query)}",
        "twitter": f"https://x.com/search?q={quote_plus(query)}&src=typed_query",
        "web": f"https://www.bing.com/search?q={quote_plus(query)}",
    }
    url = search_urls.get(platform, search_urls["web"])

    try:
        page = await _get_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        if platform == "xiaohongshu":
            js = """
            (() => {
                const results = [];
                document.querySelectorAll('.note-item, [class*="note-item"], section a').forEach(el => {
                    const title = el.querySelector('.title, [class*="title"], .footer .desc')?.innerText || el.innerText?.substring(0, 100) || '';
                    const author = el.querySelector('.author, [class*="author"], .name')?.innerText || '';
                    const href = el.href || el.querySelector('a')?.href || '';
                    if (title.trim()) results.push({ title: title.substring(0, 100), author, url: href });
                });
                return results.slice(0, 10);
            })()
            """
        elif platform == "twitter":
            js = """
            (() => {
                const results = [];
                document.querySelectorAll('article[data-testid="tweet"], article').forEach(el => {
                    const author = el.querySelector('[data-testid="User-Name"]')?.innerText || '';
                    const text = el.querySelector('[data-testid="tweetText"]')?.innerText || '';
                    const time = el.querySelector('time')?.getAttribute('datetime') || '';
                    const link = el.querySelector('a[href*="/status/"]')?.href || '';
                    if (text) results.push({ author: author.substring(0, 50), text: text.substring(0, 200), time, url: link });
                });
                return results.slice(0, 10);
            })()
            """
        else:
            js = """
            (() => {
                const results = [];
                document.querySelectorAll('#b_results > li.b_algo').forEach(el => {
                    const title = el.querySelector('h2 a')?.innerText || '';
                    const snippet = el.querySelector('.b_caption p, .b_lineclamp2')?.innerText || '';
                    const href = el.querySelector('h2 a')?.href || '';
                    if (title) results.push({ title, snippet: snippet.substring(0, 200), url: href });
                });
                return results.slice(0, 10);
            })()
            """

        data = await page.evaluate(js)
        return {"ok": True, "platform": platform, "query": query, "results": data}
    except Exception as e:
        logger.error("搜索失败 %s/%s: %s", platform, query, e)
        return {"ok": False, "platform": platform, "query": query, "error": str(e)}


async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """用 DuckDuckGo HTML 版搜索，纯 HTTP 请求，不需要浏览器。"""
    import httpx
    import re as _re
    from html import unescape
    from urllib.parse import quote_plus, unquote
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            html = resp.text

        titles_hrefs = _re.findall(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, _re.DOTALL)
        snippets = _re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)', html, _re.DOTALL)

        results = []
        for i, (raw_href, raw_title) in enumerate(titles_hrefs[:max_results]):
            title = unescape(_re.sub(r'<[^>]+>', '', raw_title)).strip()
            snippet = unescape(_re.sub(r'<[^>]+>', '', snippets[i])).strip() if i < len(snippets) else ""
            href = raw_href
            if "duckduckgo.com/l/" in href:
                uddg_m = _re.search(r'uddg=([^&]+)', href)
                if uddg_m:
                    href = unquote(uddg_m.group(1))
            results.append({"title": title, "url": href, "snippet": snippet[:200]})

        return results
    except Exception as e:
        logger.error("DuckDuckGo HTML 搜索失败: %s", e)
        return []


async def web_search_ddg(query: str, max_results: int = 5) -> list[dict]:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [{"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")} for r in results]
    except Exception as e:
        logger.error("DuckDuckGo 搜索失败: %s", e)
        return []


async def save_browsed_content(source: str, title: str, url: str, summary: str, tags: list[str] = None) -> str:
    content_id = str(uuid.uuid4())
    now = datetime.now(BJ_TZ).isoformat()
    async with get_db() as db:
        await db.execute(
            """INSERT INTO browsed_content (id, source, title, url, summary, tags_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (content_id, source, title, url, summary, json.dumps(tags or [], ensure_ascii=False), now),
        )
        await db.commit()
    return content_id


async def get_recent_browsed(limit: int = 10, source: str = None) -> list[dict]:
    async with get_db() as db:
        if source:
            sql = "SELECT * FROM browsed_content WHERE source = ? ORDER BY created_at DESC LIMIT ?"
            params = (source, limit)
        else:
            sql = "SELECT * FROM browsed_content ORDER BY created_at DESC LIMIT ?"
            params = (limit,)
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d.pop("tags_json", "[]") or "[]")
        result.append(d)
    return result


async def get_unshared_browsed(limit: int = 5) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM browsed_content WHERE shared = 0 ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d.pop("tags_json", "[]") or "[]")
        result.append(d)
    return result


async def mark_shared(content_id: str):
    async with get_db() as db:
        await db.execute("UPDATE browsed_content SET shared = 1 WHERE id = ?", (content_id,))
        await db.commit()
