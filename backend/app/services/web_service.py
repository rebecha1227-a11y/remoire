import json
import logging
import uuid
import asyncio
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse, quote_plus

import httpx

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
    document.querySelectorAll('.cookie-banner-overlay, [class*="cookie"]').forEach(el => {
        if ((el.innerText || '').includes('Cookie Preferences')) el.remove();
    });

    // 优先从笔记详情弹窗/overlay 中提取（/explore/{id} 页面结构）
    const noteContainer = document.querySelector(
        '[class*="note-detail"], [class*="noteDetail"], .note-container, #noteContainer, '
        + '[class*="note-scroller"], [class*="interaction-container"], '
        + '.detail-wrapper, [class*="detail-content"]'
    );
    const root = noteContainer || document;

    const tryText = (...sels) => {
        for (const sel of sels) {
            const el = root.querySelector(sel);
            if (el && el.innerText && el.innerText.trim()) return el.innerText.trim();
        }
        // 也试试 document 级别
        if (root !== document) {
            for (const sel of sels) {
                const el = document.querySelector(sel);
                if (el && el.innerText && el.innerText.trim()) return el.innerText.trim();
            }
        }
        return '';
    };

    const title = tryText(
        '#detail-title', '[class*="title"][class*="note"]',
        '.title', '.note-title', 'h1[class*="title"]'
    ) || document.title || '';

    const content = tryText(
        '#detail-desc', '[class*="desc"][class*="note"]',
        '.desc', '.note-content', '[class*="note-text"]',
        '.content[class*="desc"]'
    );

    const author = tryText(
        '.author-name', '.user-name', '[class*="author-wrapper"] [class*="name"]',
        '[class*="nickname"]', '[class*="author"]'
    );

    const likes = tryText(
        '[class*="like-wrapper"] [class*="count"]', '[class*="like"] span',
        '.like-count', '[class*="likeCount"]'
    );

    const comments = [];
    const commentRoot = noteContainer || document;
    commentRoot.querySelectorAll(
        '[class*="comment-item"], [class*="commentItem"], .comment-item, .comment'
    ).forEach(el => {
        const user = el.querySelector('[class*="name"], .user-name, .name')?.innerText || '';
        const text = el.querySelector('[class*="content"], .content, .text')?.innerText || '';
        if (text) comments.push({ user: user.trim(), text: text.substring(0, 200).trim() });
    });

    // 如果以上都没拿到，尝试从 body 文本中提取（最后兜底）
    let bodyFallback = '';
    if (!title && !content) {
        bodyFallback = (document.body?.innerText || '').substring(0, 3000);
    }

    return {
        title,
        content: (content || bodyFallback).substring(0, 3000),
        author,
        likes,
        comments: comments.slice(0, 30),
    };
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

JS_EXTRACT_TWITTER_TIMELINE = """
() => {
    const tweets = [];
    document.querySelectorAll('article[data-testid="tweet"], article').forEach(el => {
        const author = el.querySelector('[data-testid="User-Name"]')?.innerText || '';
        const text = el.querySelector('[data-testid="tweetText"]')?.innerText || '';
        const time = el.querySelector('time')?.getAttribute('datetime') || '';
        const link = el.querySelector('a[href*="/status/"]')?.href || '';
        const stats = el.querySelector('[role="group"]')?.innerText || '';
        if (text || author) tweets.push({
            author: author.substring(0, 160),
            text: text.substring(0, 800),
            time,
            url: link,
            stats: stats.substring(0, 160)
        });
    });
    return {
        pageTitle: document.title,
        url: location.href,
        tweets: tweets.slice(0, 25),
        bodyHead: (document.body?.innerText || '').substring(0, 1200)
    };
}
"""

JS_EXTRACT_TWITTER_USERS = """
() => {
    const users = [];
    const seen = new Set();
    document.querySelectorAll('[data-testid="UserCell"], [data-testid="cellInnerDiv"]').forEach(el => {
        const text = (el.innerText || '').trim();
        if (!text) return;
        const link = Array.from(el.querySelectorAll('a[href^="/"]')).find(a => {
            const href = a.getAttribute('href') || '';
            return /^\\/[^/]+$/.test(href) && !href.includes('i/');
        });
        const href = link ? new URL(link.getAttribute('href'), location.origin).href : '';
        const lines = text.split('\\n').map(s => s.trim()).filter(Boolean);
        const name = lines[0] || '';
        const handle = lines.find(line => line.startsWith('@')) || '';
        const bio = lines.filter(line => line !== name && line !== handle && !['Follow', 'Following', '关注', '正在关注'].includes(line)).join(' ').substring(0, 240);
        const key = handle || href || text;
        if ((name || handle) && !seen.has(key)) {
            seen.add(key);
            users.push({ name, handle, bio, url: href });
        }
    });
    return {
        pageTitle: document.title,
        url: location.href,
        users: users.slice(0, 30),
        bodyHead: (document.body?.innerText || '').substring(0, 1200)
    };
}
"""

JS_EXTRACT_TWITTER_NOTIFICATIONS = """
() => {
    const items = [];
    document.querySelectorAll('[data-testid="cellInnerDiv"], article').forEach(el => {
        const text = (el.innerText || '').trim();
        const link = Array.from(el.querySelectorAll('a[href]')).map(a => a.href).find(h => h.includes('/status/') || h.includes('/notifications')) || '';
        if (text && !text.includes('Notifications\\nVerified')) items.push({ text: text.substring(0, 500), url: link });
    });
    return {
        pageTitle: document.title,
        url: location.href,
        notifications: items.slice(0, 30),
        bodyHead: (document.body?.innerText || '').substring(0, 1200)
    };
}
"""

JS_EXTRACT_TWITTER_MESSAGES = """
() => {
    const conversations = [];
    document.querySelectorAll('[data-testid="conversation"], [data-testid="cellInnerDiv"]').forEach(el => {
        const text = (el.innerText || '').trim();
        const link = Array.from(el.querySelectorAll('a[href*="/messages/"]')).map(a => a.href)[0] || '';
        if (text && (link || text.includes('@') || text.length > 10)) {
            conversations.push({ text: text.substring(0, 500), url: link });
        }
    });
    return {
        pageTitle: document.title,
        url: location.href,
        conversations: conversations.slice(0, 20),
        restricted: conversations.length === 0,
        note: conversations.length === 0 ? '没有读到私信会话；X 可能要求先设置 Chat passcode，或当前页面没有会话列表。' : ''
    };
}
"""

JS_SCROLL_AND_WAIT = """
window.scrollBy(0, window.innerHeight);
await new Promise(r => setTimeout(r, 1500));
"""


async def _browse_twitter_page(url: str, extract_js: str = JS_EXTRACT_TWITTER_TIMELINE, scrolls: int = 3) -> dict:
    try:
        page = await _get_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(3000)

        for _ in range(scrolls):
            await page.evaluate("window.scrollBy(0, 900)")
            await page.wait_for_timeout(1300)

        data = await page.evaluate(extract_js)
        return {"ok": True, "url": url, "data": data}
    except Exception as e:
        logger.error("浏览 X 页面失败 %s: %s", url, e)
        return {"ok": False, "url": url, "error": str(e)}


def _clean_twitter_username(username: str) -> str:
    username = (username or "").strip()
    username = username.removeprefix("@")
    if username.startswith("http://") or username.startswith("https://"):
        parsed = urlparse(username)
        host = parsed.netloc.lower()
        if host not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
            raise ValueError("只支持 x.com 或 twitter.com 的用户主页链接。")
        path_parts = [part for part in parsed.path.split("/") if part]
        username = path_parts[0] if path_parts else ""
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", username):
        raise ValueError("X 用户名格式不正确，只能包含字母、数字、下划线，长度 1-15。")
    return username


async def _select_twitter_home_tab(page, mode: str) -> str:
    mode = (mode or "following").lower()
    if mode in ("for_you", "for-you", "foryou"):
        labels = ["For you", "为你推荐"]
        canonical = "for_you"
    elif mode == "following":
        labels = ["Following", "正在关注"]
        canonical = "following"
    else:
        raise ValueError("mode 只能是 for_you 或 following。")

    for label in labels:
        try:
            tab = page.get_by_role("tab", name=label)
            if await tab.count():
                await tab.first.click(timeout=5000)
                await page.wait_for_timeout(2500)
                selected = await tab.first.get_attribute("aria-selected")
                return canonical if selected == "true" else f"{canonical}_clicked_unconfirmed"
        except Exception:
            continue
    return "tab_not_found"


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


async def _xhs_get_sign(url_path: str, data=None) -> dict:
    """借浏览器的 window._webmsxyw 计算小红书 API 签名"""
    page = await _get_page()
    current = page.url or ""
    if "xiaohongshu.com" not in current:
        await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)
    try:
        result = await page.evaluate(
            """([url, data]) => {
                if (typeof window._webmsxyw === 'function') {
                    return window._webmsxyw(url, data);
                }
                return null;
            }""",
            [url_path, json.dumps(data) if data else ""],
        )
        return result or {}
    except Exception as e:
        logger.warning("XHS 签名失败: %s", e)
        return {}


async def _xhs_get_cookies() -> str:
    """从浏览器上下文提取小红书 cookies"""
    global _browser_context
    if not _browser_context:
        await _get_page()
    cookies = await _browser_context.cookies("https://www.xiaohongshu.com")
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


async def _xhs_api_request(method: str, api_path: str, params: dict = None, data: dict = None) -> dict | None:
    """带签名的小红书 API 请求"""
    url_path = f"/api/sns/web{api_path}"
    if params:
        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        sign_url = f"{url_path}?{param_str}"
    else:
        sign_url = url_path

    signs = await _xhs_get_sign(sign_url, data)
    if not signs:
        return None

    cookie_str = await _xhs_get_cookies()
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cookie": cookie_str,
        "Referer": "https://www.xiaohongshu.com/",
        "Origin": "https://www.xiaohongshu.com",
        "X-S": signs.get("X-s", ""),
        "X-T": str(signs.get("X-t", "")),
        "Content-Type": "application/json",
    }

    full_url = f"https://edith.xiaohongshu.com{url_path}"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            if method == "GET":
                resp = await client.get(full_url, headers=headers, params=params)
            else:
                resp = await client.post(full_url, headers=headers, json=data)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error("XHS API 请求失败 %s: %s", api_path, e)
        return None


async def _xhs_get_note_detail(note_id: str) -> dict:
    """通过 API 获取小红书笔记详情"""
    data = {
        "source_note_id": note_id,
        "image_formats": ["jpg", "webp", "avif"],
        "extra": {"need_body_topic": 1},
    }
    result = await _xhs_api_request("POST", "/v1/feed", data=data)
    if not result or result.get("code") != 0:
        return {}

    items = result.get("data", {}).get("items", [])
    if not items:
        return {}

    note = items[0].get("note_card", {})
    title = note.get("title", "")
    desc = note.get("desc", "")
    user = note.get("user", {})
    author = user.get("nickname", "")
    interact = note.get("interact_info", {})
    likes = interact.get("liked_count", "")
    collected = interact.get("collected_count", "")
    comment_count = interact.get("comment_count", "")

    tags = [t.get("name", "") for t in note.get("tag_list", []) if t.get("name")]

    return {
        "title": title,
        "content": desc[:3000],
        "author": author,
        "likes": str(likes),
        "collected": str(collected),
        "comment_count": str(comment_count),
        "tags": tags[:10],
    }


async def _xhs_get_comments(note_id: str, limit: int = 30) -> list[dict]:
    """通过 API 获取小红书笔记评论"""
    params = {
        "note_id": note_id,
        "cursor": "",
        "top_comment_id": "",
        "image_formats": "jpg,webp,avif",
    }
    result = await _xhs_api_request("GET", "/v2/comment/page", params=params)
    if not result or result.get("code") != 0:
        return []

    comments = []
    for c in result.get("data", {}).get("comments", []):
        user = c.get("user_info", {}).get("nickname", "")
        text = c.get("content", "")
        likes = c.get("like_count", 0)
        if text:
            comments.append({"user": user, "text": text[:200], "likes": likes})
        if len(comments) >= limit:
            break
    return comments


async def _xhs_search_notes(keyword: str, page: int = 1) -> list[dict]:
    """通过 API 搜索小红书笔记"""
    data = {
        "keyword": keyword,
        "page": page,
        "page_size": 20,
        "search_id": "",
        "sort": "general",
        "note_type": 0,
    }
    result = await _xhs_api_request("POST", "/v1/search/notes", data=data)
    if not result or result.get("code") != 0:
        return []

    items = result.get("data", {}).get("items", [])
    results = []
    for item in items:
        note = item.get("note_card", {})
        if not note:
            continue
        note_id = item.get("id", "")
        title = note.get("display_title", "")
        author = note.get("user", {}).get("nickname", "")
        likes = note.get("interact_info", {}).get("liked_count", "")
        url = f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else ""
        if title:
            results.append({
                "title": title[:100],
                "author": author[:50],
                "url": url,
                "likes": str(likes),
            })
    return results[:10]


def _extract_xhs_note_id(url: str) -> str | None:
    """从各种小红书 URL 格式中提取 note_id"""
    m = re.search(r'/(?:explore|search_result|discovery/item)/([a-f0-9]{24})', url)
    if m:
        return m.group(1)
    m = re.search(r'noteId=([a-f0-9]{24})', url)
    if m:
        return m.group(1)
    return None


def _normalize_xhs_url(url: str) -> str:
    import re
    m = re.search(r'/(?:search_result|discovery/item)/([a-f0-9]{24})', url)
    if m:
        return f"https://www.xiaohongshu.com/explore/{m.group(1)}"
    m = re.search(r'/explore/([a-f0-9]{24})', url)
    if m:
        return f"https://www.xiaohongshu.com/explore/{m.group(1)}"
    return url


async def browse_xiaohongshu(url: str) -> dict:
    # 短链（xhslink.com）直接用原始 URL 导航——小红书正常跳转链能通过反爬
    if "xhslink.com" in url:
        result = await _browse_xiaohongshu_dom(url)
        if result.get("ok"):
            data = result.get("data", {})
            if data.get("title") or data.get("content"):
                return result

    note_id = _extract_xhs_note_id(url)

    if not note_id and ("xhslink.com" in url or "xiaohongshu.com" in url):
        try:
            page = await _get_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)
            note_id = _extract_xhs_note_id(page.url)
        except Exception:
            pass

    if not note_id:
        return {"ok": False, "url": url, "error": "无法从 URL 提取笔记 ID"}

    # /explore/{id} 直链会被反爬拦截，改为在搜索页点击对应笔记卡片
    click_result = await _browse_xhs_via_click(note_id)
    if click_result.get("ok"):
        data = click_result.get("data", {})
        if data.get("title") or data.get("content"):
            return click_result

    return {
        "ok": True,
        "url": f"https://www.xiaohongshu.com/explore/{note_id}",
        "data": {
            "note_id": note_id,
            "title": "",
            "content": "",
            "author": "",
            "comments": [],
            "note": "小红书反爬限制，无法读取这篇笔记的正文和评论。可以通过搜索关键词找到相关内容摘要。",
        },
    }


async def _browse_xiaohongshu_dom(url: str) -> dict:
    """直接导航到 URL 并提取页面内容"""
    try:
        page = await _get_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        for _ in range(2):
            await page.evaluate("window.scrollBy(0, 600)")
            await page.wait_for_timeout(1000)

        data = await page.evaluate(JS_EXTRACT_XIAOHONGSHU)
        return {"ok": True, "url": page.url, "data": data}
    except Exception as e:
        logger.error("浏览小红书失败 %s: %s", url, e)
        return {"ok": False, "url": url, "error": str(e)}


async def _browse_xhs_via_click(note_id: str) -> dict:
    """在小红书页面上点击包含目标 note_id 的卡片，从 SPA 弹窗中提取内容"""
    try:
        page = await _get_page()

        # 确保在小红书域名下
        current = page.url or ""
        if "xiaohongshu.com" not in current:
            await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)

        # 找到页面上包含 note_id 的链接并点击
        clicked = await page.evaluate(f"""
        (() => {{
            const links = document.querySelectorAll('a[href*="{note_id}"]');
            for (const link of links) {{
                if (link.offsetParent !== null || link.offsetWidth > 0) {{
                    link.click();
                    return true;
                }}
            }}
            // 也试试 section.note-item 里的封面图
            const items = document.querySelectorAll('section.note-item');
            for (const item of items) {{
                const a = item.querySelector('a[href*="{note_id}"]');
                if (a) {{
                    const cover = item.querySelector('a.cover, a, img');
                    if (cover) {{ cover.click(); return true; }}
                }}
            }}
            return false;
        }})()
        """)

        if not clicked:
            # 当前页面没有这篇笔记，导航到它的 /explore/{id} 页面触发 SPA 加载
            # 虽然直接 goto /explore/{id} 可能被重定向，但从小红书域名内跳转概率更高
            logger.info("XHS 页面上没找到 note_id=%s 的卡片，尝试 SPA 内导航", note_id)
            await page.evaluate(f"history.pushState(null, '', '/explore/{note_id}')")
            await page.evaluate("window.dispatchEvent(new PopStateEvent('popstate'))")
            await page.wait_for_timeout(3000)
            # 检查 URL 是否变了
            if note_id not in (page.url or ""):
                # SPA 导航失败，直接 goto
                await page.goto(f"https://www.xiaohongshu.com/explore/{note_id}",
                                wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(3000)

        # 等待详情弹窗/页面加载
        await page.wait_for_timeout(3000)

        # 等待笔记详情容器出现
        for sel in ['[class*="note-detail"]', '[class*="noteDetail"]', '#detail-title',
                     '[class*="note-scroller"]', '.note-container']:
            try:
                await page.wait_for_selector(sel, timeout=3000)
                break
            except Exception:
                continue

        for _ in range(2):
            await page.evaluate("window.scrollBy(0, 600)")
            await page.wait_for_timeout(1000)

        data = await page.evaluate(JS_EXTRACT_XIAOHONGSHU)

        # 关闭弹窗（按 Esc 或点击遮罩），恢复到列表页
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
        except Exception:
            pass

        return {"ok": True, "url": f"https://www.xiaohongshu.com/explore/{note_id}", "data": data}
    except Exception as e:
        logger.error("XHS 点击浏览失败 note_id=%s: %s", note_id, e)
        return {"ok": False, "error": str(e)}


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


async def browse_twitter_profile(username: str = "rebekhakkk_") -> dict:
    username = _clean_twitter_username(username or "rebekhakkk_")
    return await _browse_twitter_page(f"https://x.com/{username}", JS_EXTRACT_TWITTER_TIMELINE)


async def browse_twitter_user_tweets(username: str) -> dict:
    username = _clean_twitter_username(username)
    return await _browse_twitter_page(f"https://x.com/{username}", JS_EXTRACT_TWITTER_TIMELINE)


async def browse_twitter_home_feed(mode: str = "following") -> dict:
    try:
        page = await _get_page()
        await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(3500)
        selected = await _select_twitter_home_tab(page, mode)
        if selected == "tab_not_found":
            return {"ok": False, "url": "https://x.com/home", "error": "没有找到 X 首页的 For You / Following 标签，无法确认读取的是目标时间线。"}

        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 900)")
            await page.wait_for_timeout(1300)
        data = await page.evaluate(JS_EXTRACT_TWITTER_TIMELINE)
        data["requestedMode"] = mode
        data["selectedMode"] = selected
        if selected.endswith("_clicked_unconfirmed"):
            data["note"] = "已点击目标标签，但 X 没有返回明确选中状态；结果可能受页面状态影响。"
        return {"ok": True, "url": "https://x.com/home", "data": data}
    except Exception as e:
        logger.error("读取 X 首页时间线失败: %s", e)
        return {"ok": False, "url": "https://x.com/home", "error": str(e)}


async def browse_twitter_following(username: str = "rebekhakkk_") -> dict:
    username = _clean_twitter_username(username or "rebekhakkk_")
    return await _browse_twitter_page(f"https://x.com/{username}/following", JS_EXTRACT_TWITTER_USERS, scrolls=4)


async def browse_twitter_followers(username: str = "rebekhakkk_") -> dict:
    username = _clean_twitter_username(username or "rebekhakkk_")
    return await _browse_twitter_page(f"https://x.com/{username}/followers", JS_EXTRACT_TWITTER_USERS, scrolls=4)


async def browse_twitter_notifications() -> dict:
    return await _browse_twitter_page("https://x.com/notifications", JS_EXTRACT_TWITTER_NOTIFICATIONS, scrolls=3)


async def browse_twitter_messages() -> dict:
    return await _browse_twitter_page("https://x.com/messages", JS_EXTRACT_TWITTER_MESSAGES, scrolls=2)


async def browse_twitter_bookmarks() -> dict:
    return await _browse_twitter_page("https://x.com/i/bookmarks", JS_EXTRACT_TWITTER_TIMELINE, scrolls=4)


async def search_on_page(platform: str, query: str) -> dict:
    if platform == "xiaohongshu":
        try:
            results = await _xhs_search_notes(query)
            if results:
                return {"ok": True, "platform": platform, "query": query, "results": results}
        except Exception as e:
            logger.warning("XHS API 搜索失败，降级 DOM: %s", e)
        return await _search_xiaohongshu_dom(query)

    search_urls = {
        "twitter": f"https://x.com/search?q={quote_plus(query)}&src=typed_query",
        "web": f"https://www.bing.com/search?q={quote_plus(query)}",
    }
    url = search_urls.get(platform, search_urls["web"])

    try:
        page = await _get_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        if platform == "twitter":
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


async def _search_xiaohongshu_dom(query: str) -> dict:
    """DOM 抓取兜底搜索（API 失败时用）"""
    url = f"https://www.xiaohongshu.com/search_result?keyword={quote_plus(query)}"
    try:
        page = await _get_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        try:
            await page.wait_for_selector("section.note-item", timeout=12000)
        except Exception:
            await page.wait_for_timeout(5000)

        js = """
        (() => {
            const results = [];
            const seen = new Set();
            document.querySelectorAll('.cookie-banner-overlay, [class*="cookie"]').forEach(el => {
                if ((el.innerText || '').includes('Cookie Preferences')) el.remove();
            });
            document.querySelectorAll('section.note-item').forEach(el => {
                const links = Array.from(el.querySelectorAll('a'));
                const linkEl =
                    links.find(a => (a.href || '').includes('/search_result/') && (a.href || '').includes('xsec_token='))
                    || links.find(a => (a.href || '').includes('/explore/'));
                const hrefRaw = linkEl?.href || '';
                const href = hrefRaw.startsWith('http') ? hrefRaw : (hrefRaw ? new URL(hrefRaw, location.origin).href : '');
                const text = (el.innerText || '').trim();
                if (!text) return;
                const lines = text.split('\\n').map(s => s.trim()).filter(Boolean);
                if (lines.length < 2) return;
                const title = lines[0] || '';
                const author = lines[1] || '';
                const bad =
                    ['大家都在搜', '发现', '直播', '发布', '通知', '沪ICP备', '营业执照', 'Cookie Preferences', 'Your Cookie Preferences']
                        .some(word => title.includes(word) || author.includes(word));
                const key = href || `${title}|${author}`;
                if (title && (href.includes('/explore/') || href.includes('/search_result/')) && !bad && !seen.has(key)) {
                    seen.add(key);
                    let cleanUrl = href;
                    const idMatch = href.match(/\\/(?:search_result|discovery\\/item)\\/([a-f0-9]{24})/);
                    if (idMatch) cleanUrl = 'https://www.xiaohongshu.com/explore/' + idMatch[1];
                    results.push({ title: title.substring(0, 100), author: author.substring(0, 50), url: cleanUrl });
                }
            });
            return results.slice(0, 10);
        })()
        """
        data = await page.evaluate(js)
        return {"ok": True, "platform": "xiaohongshu", "query": query, "results": data}
    except Exception as e:
        logger.error("XHS DOM 搜索失败 %s: %s", query, e)
        return {"ok": False, "platform": "xiaohongshu", "query": query, "error": str(e)}


async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """用 DuckDuckGo HTML 版搜索，纯 HTTP 请求，不需要浏览器。"""
    import re as _re
    from html import unescape
    from urllib.parse import unquote
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
