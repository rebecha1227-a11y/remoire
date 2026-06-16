# 小红书浏览方案（Playwright）

> Connie 通过 Playwright 浏览器浏览小红书笔记的技术方案。
> 文件：`backend/app/services/web_service.py`

---

## 背景

小红书有强反爬机制。直接用 Playwright 访问 `https://www.xiaohongshu.com/explore/{note_id}` 会被服务端重定向到 `/explore` 主页，拿不到目标笔记的内容。

但通过**模拟真人操作**（点击卡片打开弹窗、跟随短链跳转），可以正常读取笔记正文和评论。

---

## 核心发现

### 什么能用

| 方式 | 原理 | 能否读到内容 |
|---|---|---|
| `xhslink.com` 短链 | 浏览器跟随 302 跳转，小红书认为是正常用户点进来的 | ✅ |
| 搜索页点击卡片 | SPA 内部弹窗，跟真人操作一样 | ✅ |
| 搜索关键词 | 搜索结果页正常加载 | ✅（标题+作者） |

### 什么不能用

| 方式 | 原因 | 结果 |
|---|---|---|
| 直接 `page.goto("/explore/{id}")` | 服务端 302 重定向到 `/explore` 主页 | ❌ 拿到的是 feed 随机内容 |
| XHS API (`edith.xiaohongshu.com`) | 账号被标记异常 / IP 被封 | ❌ 返回 406 或 300011 |
| `playwright-stealth` + 改 UA | 反而暴露了自动化特征 | ❌ 更容易被检测 |
| SPA pushState 导航 | 触发前端路由但被重定向 | ❌ 同直接访问 |

### 关键教训

1. **不要"归一化" URL**。之前的 bug 就是把 `xhslink.com` 短链转成了 `/explore/{id}`，丢失了跳转信任链。
2. **不要加"反检测"手段**（stealth、改 UA、禁用 AutomationControlled）。小红书能检测到你在"伪装"，反而更可疑。用最原始的 Playwright 配置就好。
3. **Browser profile 不能被两个进程同时使用**。不要写独立测试脚本，只能通过运行中的服务来测试浏览器功能。

---

## 架构

```
用户发短链 ──→ browse_xiaohongshu(url)
                  │
                  ├─ xhslink.com？ ──→ _browse_xiaohongshu_dom(原始URL)
                  │                      └─ page.goto(短链) → 自然跳转 → 提取内容 ✅
                  │
                  └─ /explore/{id}？ ──→ _browse_xhs_via_click(note_id)
                                          ├─ 当前页面有卡片？ → 点击 → 弹窗 → 提取 ✅
                                          └─ 没有卡片？ → SPA导航兜底 → 可能失败

Connie 自主活动 ──→ search_on_page("xiaohongshu", 关键词)
                       └─ 搜索结果页加载 → 返回标题+作者+URL
                  ──→ browse_xiaohongshu(搜索结果URL)
                       └─ 搜索结果页还在 → 点击卡片 → 弹窗 → 提取 ✅
```

---

## 关键函数

### `browse_xiaohongshu(url: str)`

入口函数。根据 URL 类型分流：
- **短链**（`xhslink.com`）→ 直接导航，浏览器自然跟随跳转
- **直链**（`/explore/{id}`）→ 通过点击卡片方式打开

### `_browse_xiaohongshu_dom(url: str)`

最简单的方式：`page.goto(url)` → 等 3 秒 → 滚动 → 提取内容。
短链走这个，因为浏览器跟随跳转后页面正常加载。

### `_browse_xhs_via_click(note_id: str)`

模拟真人操作：
1. 确保当前在小红书域名下
2. 在页面上找包含 `note_id` 的 `<a>` 链接
3. 找到 → 点击 → 等待 SPA 弹窗加载 → 提取内容 → 按 Esc 关闭弹窗
4. 没找到 → 尝试 SPA pushState 导航（兜底，不一定成功）

### `_search_xiaohongshu_dom(query: str)`

搜索功能：
1. 导航到 `xiaohongshu.com/search_result?keyword=...`
2. 等待 `section.note-item` 出现
3. 提取每个卡片的标题、作者、URL

### `JS_EXTRACT_XIAOHONGSHU`

页面内容提取的 JS 脚本，从 DOM 中读取：
- 标题（`#detail-title` 等选择器）
- 正文（`#detail-desc` 等）
- 作者（`.author-name` 等）
- 点赞数
- 评论列表（用户名 + 内容）

支持从笔记详情弹窗（overlay）和独立页面两种 DOM 结构中提取。

---

## 浏览器配置

```python
_browser_context = await _playwright.chromium.launch_persistent_context(
    str(BROWSER_DATA_DIR),       # /opt/remoire/backend/data/browser_profile
    headless=True,
    user_agent="...Chrome/120...",  # 不要用太新的版本号
    viewport={"width": 1280, "height": 800},
    locale="zh-CN",
    timezone_id="Asia/Shanghai",
    # 不要加 --disable-blink-features、不要加 stealth
)
```

**注意**：
- UA 用 Chrome/120，不要改成更新的版本（测试过 Chrome/137 反而被检测）
- 不要加任何"反检测"参数
- 登录态保存在 `browser_profile/` 目录，持久化的（persistent context）

---

## 登录

小红书登录需要手动操作一次（扫码或短信验证）：

```bash
# 在 VPS 上用有界面的方式启动浏览器
# 注意：必须先停掉 remoire 服务，否则 browser profile 被锁
systemctl stop remoire
python3 -c "
from playwright.sync_api import sync_playwright
p = sync_playwright().start()
ctx = p.chromium.launch_persistent_context(
    '/opt/remoire/backend/data/browser_profile',
    headless=False
)
page = ctx.pages[0]
page.goto('https://www.xiaohongshu.com')
input('登录完成后按回车...')
ctx.close()
p.stop()
"
systemctl start remoire
```

VPS 是 headless 环境，需要用 VNC 或 X11 转发才能看到浏览器界面。

登录态大约能维持 1-2 个月。如果开始大面积出现 `300011 账号异常`，说明需要重新登录或换账号。

---

## 排查问题

### Connie 说"笔记打不开"

1. 检查日志：`journalctl -u remoire --since "1 hour ago" | grep -i "xhs\|xiaohongshu"`
2. 常见错误：
   - `被重定向到 /explore` → 直链被拦，检查是否走了点击路径
   - `406 Not Acceptable` → API 被封，正常，DOM 方式会兜底
   - `启动浏览器失败` → browser profile 被锁或 Playwright 崩溃，重启服务

### 搜索能用但浏览不行

说明 Connie 搜到帖子后离开了搜索页，回来点击时卡片已经不在了。
检查 `_browse_xhs_via_click` 里的 `clicked` 是否为 `false`。

### 短链能用但直链不行

这是**正常的**。小红书对直链的反爬比短链严格得多。自主活动场景下依赖搜索 → 点击的流程，不需要直链。

---

## 历史踩坑记录

| 日期 | 问题 | 原因 | 解决 |
|---|---|---|---|
| 2026-06-11 | 搜索结果的帖子链接打不开 | URL 带 `xsec_token` 被拦 | 归一化为 `/explore/{id}` |
| 2026-06-15 | `/explore/{id}` 也打不开 | 小红书加强了直链反爬 | 改为搜索页点击卡片 |
| 2026-06-16 | 所有方式都失败 | 加了 stealth + 新 UA 反而被检测 | 恢复原始浏览器配置 |
| 2026-06-16 | 短链被代码转成直链 | `_normalize_xhs_url` 过早执行 | 短链保留原始 URL 直接导航 |

---

## 未来可能需要的改进

1. **搜索结果页停留**：Connie 搜索后如果要连续看多篇帖子，需要保持在搜索结果页不离开，逐个点击卡片。
2. **登录态监控**：定期检查登录是否过期（比如访问个人主页看是否跳转到登录页）。
3. **IP 轮换**：如果 VPS IP 被小红书封了，可能需要换 IP 或用代理。
4. **API 方案备用**：代码里保留了 `_xhs_get_sign` / `_xhs_api_request` 等函数，如果账号恢复正常或换了新号，API 方式更快更稳。
