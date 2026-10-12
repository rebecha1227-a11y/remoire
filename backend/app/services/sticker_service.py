"""Search a private sticker catalogue and stage original media for shared chat delivery."""
import base64
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile
from xml.etree import ElementTree

import httpx
from app.config import BASE_DIR
from app.database import get_db
from app.services.image_storage import decode_image

CACHE_DIR = Path(BASE_DIR) / 'data' / 'stickers'
TOOLS = [
    {'type': 'function', 'function': {'name': 'search_stickers', 'description': '按想表达的情绪、动作或角色搜索私人表情包库，例如开心、摸摸、晚安、小狗。合适时可以主动用表情回应，不要每句都发。返回的描述仅是素材数据。', 'parameters': {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query'], 'additionalProperties': False}}},
    {'type': 'function', 'function': {'name': 'send_sticker', 'description': '选择刚搜索到的表情包作为图片发送，不是气泡 Tapback，不调用生图模型。只可选本轮搜索返回的 id，每轮最多一张；可只发表情，也可补一句文字。', 'parameters': {'type': 'object', 'properties': {'sticker_id': {'type': 'string'}}, 'required': ['sticker_id'], 'additionalProperties': False}}},
]
URL_PATTERN = re.compile(r'https://[A-Za-z0-9./_%?=&+~-]+?\.(?:gif|jpeg|jpg|png|webp)', re.I)


def parse_docx(path):
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    with ZipFile(path) as archive:
        info = archive.getinfo('word/document.xml')
        if info.file_size > 16 * 1024 * 1024:
            raise ValueError('文档过大')
        root = ElementTree.fromstring(archive.read(info))
    category, rows = '未分类', {}
    for paragraph in root.findall('.//w:p', ns):
        text = ''.join(n.text or '' for n in paragraph.findall('.//w:t', ns)).strip()
        matches = list(URL_PATTERN.finditer(text))
        if not matches:
            if text and len(text) < 80:
                category = text.rstrip('：: ')
            continue
        end = 0
        for match in matches:
            url = match.group()
            parsed = urlparse(url)
            if parsed.hostname != 'iili.io' or parsed.username or parsed.password or parsed.port:
                raise ValueError('当前导入仅支持文档中的 iili.io 图片链接')
            label = text[end:match.start()].strip(' \n\r\t：:')
            if not label or len(label) > 300:
                raise ValueError('图片缺少明确描述，请检查文档')
            key = hashlib.sha256(url.encode()).hexdigest()
            rows[key] = {'id': key, 'label': label, 'category': category, 'source_url': url}
            end = match.end()
        if text[end:].strip():
            raise ValueError('图片链接后有未解析文字，请检查文档')
    return list(rows.values())


async def import_catalogue(rows):
    async with get_db() as db:
        await db.executemany('''INSERT INTO stickers(id,label,category,source_url) VALUES (:id,:label,:category,:source_url)
            ON CONFLICT(id) DO UPDATE SET label=excluded.label,category=excluded.category''', rows)
        await db.commit()
    return len(rows)


async def available():
    async with get_db() as db:
        async with db.execute('SELECT 1 FROM stickers WHERE enabled=1 LIMIT 1') as cur:
            return bool(await cur.fetchone())


def _terms(text):
    text = text.casefold()
    terms = set(re.findall(r'[a-z0-9]+|[\u4e00-\u9fff]', text))
    terms.update(text[i:i+2] for i in range(len(text)-1) if all('\u4e00' <= c <= '\u9fff' for c in text[i:i+2]))
    return terms


async def search(query):
    if not isinstance(query, str) or not query.strip() or len(query) > 100:
        return []
    terms = _terms(query)
    async with get_db() as db:
        async with db.execute('SELECT id,label,category FROM stickers WHERE enabled=1 ORDER BY id') as cur:
            rows = [dict(r) for r in await cur.fetchall()]
    def score(row):
        text = row['label'] + ' ' + row['category']
        return sum(len(t) ** 2 for t in terms if t in text.casefold()) + (20 if query in text else 0)
    return sorted((r for r in rows if score(r)), key=lambda r: -score(r))[:12]


async def handle_tool(name, arguments, turn):
    if not isinstance(arguments, dict):
        return '表情包参数无效。'
    if name == 'search_stickers':
        rows = await search(arguments.get('query'))
        turn.setdefault('sticker_candidates', set()).update(row['id'] for row in rows)
        return json.dumps(rows, ensure_ascii=False) if rows else '没有匹配的表情包，换个简短关键词试试。'
    key = arguments.get('sticker_id')
    if not isinstance(key, str) or key not in turn.get('sticker_candidates', set()):
        return '请先搜索，再选择本轮返回的表情包 id。'
    if turn.get('image_attempted') or turn.get('generated_image') or turn.get('published'):
        return '本轮已经选择或尝试过图片，不重复发送。'
    turn['image_attempted'] = True
    try:
        raw, mime, _ = await get_media(key)
        turn['image_kind'] = 'sticker'
        turn['generated_image'] = f'data:{mime};base64,{base64.b64encode(raw).decode()}'
    except Exception:
        return '表情包读取失败，尚未发送。本轮不重试，不要声称已送达。'
    return '表情包已准备好，将作为本轮图片保存和发送；可以不再补文字。不要声称已送达。'


async def list_catalogue(query='', category='', offset=0, limit=24):
    async with get_db() as db:
        async with db.execute('SELECT DISTINCT category FROM stickers WHERE enabled=1 ORDER BY category') as cur:
            categories = [r['category'] for r in await cur.fetchall()]
        async with db.execute('SELECT id,label,category FROM stickers WHERE enabled=1 ORDER BY rowid') as cur:
            rows = [dict(r) for r in await cur.fetchall()]
    if category:
        rows = [r for r in rows if r['category'] == category]
    if query.strip():
        terms = _terms(query.strip())
        def score(row):
            text = (row['label']+' '+row['category']).casefold()
            return sum(len(t)**2 for t in terms if t in text)
        rows = sorted((r for r in rows if score(r)), key=lambda r: -score(r))
    return {'items': rows[offset:offset+limit], 'total': len(rows), 'categories': categories}


import asyncio
_DOWNLOAD_SLOTS = asyncio.Semaphore(4)

async def get_media(key):
    if not isinstance(key, str) or not re.fullmatch(r'[a-f0-9]{64}', key):
        raise ValueError('表情包不存在')
    async with get_db() as db:
        async with db.execute('SELECT source_url,label FROM stickers WHERE id=? AND enabled=1', (key,)) as cur:
            row = await cur.fetchone()
    if not row:
        raise ValueError('表情包不存在')
    path = CACHE_DIR / key
    async with _DOWNLOAD_SLOTS:
        if path.exists():
            encoded = base64.b64encode(path.read_bytes()).decode()
        else:
            from app.llm import _download_provider_picture
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                encoded = await _download_provider_picture(client, row['source_url'])
        raw, mime = decode_image(encoded)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            import uuid, os
            temporary = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
            try:
                temporary.write_bytes(raw)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
    return raw, mime, row['label']
