# ChatGPT MCP OAuth 发布与验收 · 2026-10-05

## 结果与边界

已在生产 `2fe26c9` 加日志隐私/静态 MCP 鉴权补丁的基础上，部署 ChatGPT OAuth 支持。对应源码目前是工作区补丁，不应把它误写成全部包含在 `2fe26c9` 提交中。

- MCP 地址仍是 `https://remoire.cc/mcp`。Codex 原有独立 Bearer token 不变。
- ChatGPT 使用 OAuth 授权码 + PKCE S256；需要用户在 Remoire 授权页输入现有用户名/密码并明确允许。不是把网页登录密码交给 ChatGPT，也不是开放匿名访问。
- 服务端已部署并完成协议/兼容性验收；**用户真实 ChatGPT 账号的登录授权、工具发现和实际调用仍待用户完成**。
- 没有修改 PWA 视觉、模型配置或网页登录密码；没有写入测试聊天、记忆或日记。

## 用户连接

在 ChatGPT 自定义 MCP 连接/创建应用中填写：名称 `Remoire`，URL `https://remoire.cc/mcp`，认证选择 OAuth。客户端 ID/密钥若为选填则留空，服务支持动态客户端注册，无需粘贴 Codex token。

根据当前 [OpenAI 连接说明](https://developers.openai.com/plugins/deploy/connect-chatgpt)，开发者模式入口为设置中的 Security and login，添加入口为 ChatGPT Plugins 的加号；实际入口名称可能因账号和工作区政策不同。若界面不同，以实际截图核对，不猜测字段。

连接时只在域名为 `remoire.cc` 的授权页输入 Remoire 登录信息。授权后在新对话里选择此连接，先让 ChatGPT 列出 Remoire 工具，不调用写入工具；再按需进行只读验证。不能把 `remember` 或 `resume` 当成完全无写入的验收动作。

## 实现

- 使用 MCP Python SDK 1.30.0 的授权、动态注册、token、撤销协议处理器；版本固定于 requirements。
- 独立 SQLite provider 只新增四张 `oauth_*` 表，不改变业务表结构/数据。客户端 secret 使用现有 Fernet 密钥加密；授权码、CSRF、访问/刷新令牌仅存 SHA-256 摘要。
- 访问令牌 1 小时；授权族绝对有效期 30 天。刷新轮换，重复使用旧刷新令牌撤销整个授权族；授权码 2 分钟且事务性单次兑换，授权请求 10 分钟。
- 资源绑定 `https://remoire.cc/mcp`，权限 `remoire` 覆盖现有 MCP 工具。不是多用户权限系统，也不提供只读/读写细分 scope。
- 回调只允许 ChatGPT 官方 HTTPS 域名下的 `/connector/oauth/{callback_id}` 和 `/connector_platform_oauth_redirect`；精确匹配注册回调，禁止任意 URL、查询串、fragment 和用户信息。授权中间页不抓取客户端提供的网址。
- 支持动态注册及 `none`、`client_secret_post`、`client_secret_basic`。没有宣称支持 CIMD 或 `authorization_response_iss_parameter_supported`。
- 登录授权页有绑定请求的 Secure/HttpOnly/SameSite=Lax CSRF cookie、Origin 检查、现有登录失败限流。所有响应 no-store，无外部脚本。
- Nginx 对 OAuth 路由限流和限制 16KB 请求体。仅授权页的 CSP 允许表单重定向回 ChatGPT，PWA 保持 self-only form-action。
- Nginx MCP 每次请求仍经内部鉴权接口。匿名 401 带资源发现地址，内部接口不对公网开放。日志继续不记录 URL/查询串、密码、认证头或业务正文。

## 测试与生产检查

- 本地完整 unittest：68 项通过；生产同版 Python 3.12/依赖的隔离目录：22 项认证/OAuth 测试通过，均用临时数据库。
- 覆盖 PKCE、audience、回调、错误密码、CSRF、授权码并发单次兑换、refresh 轮换/复用撤销、过期、跨客户端、凭据摘要/加密、重复参数和大小边界。
- 线上授权发现、动态注册、授权页、跨来源拒绝和取消授权回跳通过；没有替用户模拟同意，没有发放生产测试 OAuth 令牌。临时注册和待授权记录已清理。
- 公网匿名 GET/POST/DELETE、错误 token、URL token、仅有 MCP session 无认证均拒绝；内部校验地址公网 404。
- Codex 原 token 的 initialize 和 tools/list 成功，9 个工具。临时 MCP 协议会话关闭。
- 新日志没有出现合成敏感标记或原 token；历史日志没有清除。
- 切换前后 902 条记忆、5,978 条消息、72 篇日记；三张表全部列、按 id 排序的数据 SHA-256 完全一致。SQLite quick_check=ok。数量是此次现场值，不沿用此前 903 的旧记录。

## 部署、备份与回退

- 隔离验证目录：`/opt/remoire/releases/oauth-chatgpt-20261005/`。
- 成功部署的最新备份：`/root/backups/oauth-chatgpt-20261005-r2/`，包含数据库、配置、原代码、manifest、数据指纹和部署脚本。目录仅 root 可访问。
- 第一次尝试在 Nginx reload 后过早检查，读到了旧的 HTML 路由，自动恢复了原受保护代码/配置；未恢复数据库。应用完整路由隔离测试正常。第二次增加新连接轮询确认配置生效，发布成功。
- `.env` 和 systemd 启动配置没有更改，仍使用 `/opt/remoire/venvs/2fe26c9`。
- 回退前重新备份当时最新状态。在 root 下运行 `/opt/remoire/venvs/2fe26c9/bin/python /root/backups/oauth-chatgpt-20261005-r2/deploy.py rollback-code` 可以恢复此前静态 token 保护版本；会短暂停服。此命令不回写数据库，新增 OAuth 表可保留，不删除业务数据。回退会使 ChatGPT OAuth 连接不可用，但不应开放匿名 MCP。
- 不要执行此前启用鉴权前的旧 Nginx 全量恢复。回退后重复匿名拒绝和 Codex 正确 token 验收。
- 若需紧急撤销全部 ChatGPT 授权，可由管理员在备份后将 `oauth_tokens.revoked` 全部置 1；不要更改静态 Codex token，除非它也泄露。仅在 ChatGPT 删除连接不保证客户端一定调用服务端撤销接口。
