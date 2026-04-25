# 编码规范 · Our Nest

---

## 通用

- 变量名、函数名、注释用英文；面向用户的文案用中文
- UTF-8 编码
- 缩进：前端 2 空格，后端 4 空格
- 行宽上限：100 字符
- 不引入暂时用不到的依赖——先跑起来，需要时再加

---

## Python 后端

### 风格

- 所有函数参数和返回值标注 type hints
- 优先使用 async/await，所有 I/O 操作异步化
- 使用 Pydantic BaseModel 做请求/响应校验
- f-string 做字符串格式化
- 不用 ORM，直接写 SQL（aiosqlite），保持对数据库的完全控制

### 架构分层

```
router → service → database
  │
  └→ llm.py（统一 LLM 调用）
```

- **router 层**：接收请求、参数校验、调用 service、返回响应。不写业务逻辑。
- **service 层**：所有业务逻辑在这里。数据库操作、LLM 调用、记忆关联计算。
- **database 层**：连接管理、init_db()、PRAGMA 设置。

### 错误处理

- 业务错误用 `HTTPException` 抛出，带清晰的中文 detail
- LLM 调用必须 try/except，失败时返回友好提示，不让用户看到 traceback
- 数据库操作失败要 log 错误并返回 `{"ok": false, "error": "..."}`

### LLM 调用规则

- 所有 LLM 调用必须经过 `app/llm.py` 的 `call_llm()` 函数
- 不在业务代码中直接拼 httpx 请求
- `call_llm()` 接受 `ModelConfig` 对象（含 api_base / api_key / model_id）
- 流式和非流式通过 `stream=True/False` 参数切换
- 槽位选择逻辑在 service 层决定，不在 router 层

### 数据库规则

- 连接时必须执行三个 PRAGMA（WAL / foreign_keys / busy_timeout）
- 表名全小写下划线：`memory_candidates`
- 主键统一用 TEXT 类型的 UUID v4
- 时间字段统一 ISO 8601 格式存储：`2026-04-25T15:30:00`
- JSON 字段用 TEXT 存，应用层 json.loads() 解析
- 消息存储和候选提取是两个独立 INSERT，不要包在同一个事务里

### 文件命名

- 全小写下划线：`memory_service.py`
- router 文件名对应路由前缀：`chat.py` → `/api/chat`
- 与 Python 关键字冲突的加下划线后缀：`import_.py`

### API 响应格式

```python
# 成功
{"ok": True, "data": {...}}

# 失败
{"ok": False, "error": "描述"}

# 分页
{"ok": True, "data": {"items": [...], "total": 100, "page": 1, "limit": 20, "has_more": True}}
```

### prompt 管理

- 所有 system prompt 模板放在 `app/prompts/` 目录下，用 .md 文件存储
- prompt 中的变量用 `{variable_name}` 占位，运行时 f-string 替换
- 身份人设（identity.md）不要散落在业务代码里

---

## React 前端

### 风格

- 函数组件 + Hooks，不用 class 组件
- 组件文件用 PascalCase：`ChatBubble.jsx`
- 工具函数用 camelCase：`formatTime.js`
- 页面组件放 `pages/`，可复用组件放 `components/`
- 每个组件一个文件，不在一个文件里导出多个组件

### 样式

- Tailwind CSS utility class 做布局和间距
- 颜色、字体、圆角、阴影全部通过 CSS Variables 引用
- 绝对不在组件中硬编码颜色值（包括 Tailwind 的 `bg-white`、`text-gray-500`）
- 暗色模式通过 `[data-theme="dark"]` 切换 CSS Variables，不用 Tailwind dark: 前缀
- 如果某个组件需要特殊样式，用 CSS Modules 或 `<style>` 标签

### 颜色引用方式

```jsx
// ✅ 正确：通过 CSS Variable
<div style={{ background: 'var(--bg-elevated)' }}>
// 或者在 globals.css 中定义 Tailwind 扩展

// ❌ 错误：硬编码
<div className="bg-white">
<div style={{ background: '#FAF8F4' }}>
```

### 状态管理

- 简单状态用 useState / useReducer
- 跨组件状态用 React Context
- 不提前引入 Zustand / Redux，除非复杂度明显上升

### API 调用

- 统一封装在 `utils/api.js`
- 使用 fetch，不额外引入 axios
- 所有请求带 `Authorization: Bearer <token>` header
- 流式响应用 ReadableStream 处理
- SSE 主动消息用自定义 hook（useSSE）处理
- 图片上传用 FormData

```javascript
// utils/api.js 示例结构
const API_BASE = '/api';

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getToken()}`,
      ...options.headers,
    },
  });
  return res.json();
}

export const api = {
  chat: {
    send: (message) => request('/chat/send', { method: 'POST', body: JSON.stringify({ message }) }),
    history: (params) => request(`/chat/history?${new URLSearchParams(params)}`),
    status: () => request('/chat/status'),
  },
  memory: { ... },
  diary: { ... },
  // ...
};
```

### 组件设计原则

- 先写移动端，430px 为基准
- 所有可交互元素最小触摸区域 44x44px
- 动效克制，参考 DESIGN_SYSTEM.md 的动效规范
- 加载状态用骨架屏（Skeleton），不用 spinner
- 空状态要有温度的文案，不是冷冰冰的"暂无数据"

### 空状态文案示例

```
记忆列表为空 → "还没有记忆呢，聊聊天就会有了"
日记列表为空 → "今天还没写日记，要不要现在开始？"
小纸条历史为空 → "还没收到过小纸条呢"
```

---

## Git 规范

### Commit Message

```
<type>: <简短描述>

类型：
feat     新功能
fix      修复
style    样式调整（不影响逻辑）
refactor 重构
docs     文档
chore    构建/依赖/工具
```

### 分支

- `main` — 稳定版本
- `dev` — 开发分支
- `feat/xxx` — 功能分支（如 feat/chat, feat/memory）

### .gitignore 必须包含

```
.env
*.db
__pycache__/
node_modules/
dist/
.DS_Store
backend/data/
backend/uploads/
```

---

## 测试

- 后端关键 service 写单元测试（pytest + pytest-asyncio）
- LLM 相关功能用 mock 测试，不实际调用 API
- 前端暂不强制测试，优先保证功能完整
- 手动测试检查清单：
  1. 发消息能收到流式回复
  2. 记忆候选能正确提取和确认
  3. 确认记忆时能返回关联旧记忆
  4. 提醒到时间能收到 SSE 推送
  5. 暗色模式切换不会出现硬编码颜色

---

## 安全

- `.env` 文件永远不进 git
- API Key 不在前端代码中出现
- 前端存的 auth token 放 localStorage（单用户产品可接受）
- 后端 model_configs 表的 api_key 字段首发明文存储，后续可改进
- CORS 只允许自己的域名
