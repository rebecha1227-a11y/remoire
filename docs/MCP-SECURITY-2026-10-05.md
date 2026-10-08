# MCP 鉴权与日志隐私验收 · 2026-10-05

## 生产状态

后续更新：现已增加 ChatGPT OAuth，同时保留本文的 Codex 静态 token 接入；以 `CHATGPT-OAUTH-2026-10-05.md` 为最新状态。用户已经确认 Codex 实际调用成功。下文是启用静态鉴权时的原始阶段记录，不代表当前仍不支持 OAuth。

已在 `2fe26c9` 基础上部署本次安全补丁。没有修改前端视觉、网页登录密码或业务数据。

- HTTPS `/mcp` 的每次请求先经过 Nginx `auth_request`，由 `/api/auth/mcp-check` 校验独立 Bearer token 摘要。
- 这是预配置共享 token 的私人服务接入方案，不是 OAuth 授权发现实现。
- 内部校验接口禁止公网直接调用；MCP 仍仅监听 127.0.0.1:8001。
- `.env` 只保留 `MCP_API_TOKEN_SHA256`，权限 600。随机 token 使用 48 字节熵。
- 原始 token 已安全交付到本机 `/Users/rebecha/.config/remoire/mcp-token-20261005`（权限 600），未显示在聊天或日志中。
- 用于交付和验收的服务器临时明文 token 已删除。本机私密副本保留。
- 无 token 的旧 MCP 客户端需要重新配置；网页会话不使用该 token。

## 日志整改

- 移除待办提取原文、自主活动摘要、模型回复片段、日记判断原因与标题的直接日志输出。
- API 和 MCP 入口安装统一 LogRecord 工厂：普通业务与第三方库日志只输出来源模块、函数、行号和异常类型，不格式化自由文本、异常正文或堆栈。
- 请求审计仅保留服务端生成的请求 ID、方法、框架路由模板、状态码和耗时；不信任客户端传入的请求 ID。
- Uvicorn 访问日志隐藏 IP 和请求目标，保留方法和状态码。
- Nginx 访问日志仅保留时间、白名单方法、状态码和耗时，不记录 URL、参数、IP、正文、认证头、Referer 或 User-Agent。
- 该站点的 Nginx 请求错误日志不写入磁盘，避免原始 URI 经错误日志泄露；代价是必须依赖状态审计与应用代码位置排障。Nginx 配置检查日志仍可用。
- **历史日志没有清空或重写。** 此改动阻止新的相关日志泄露，不能撤回之前已落盘内容；历史日志处置需要单独指定范围，不能直接清空全系统 journal。
- 数据库里的聊天、日记、自主活动记录属于产品数据，不属于本次删除范围，均保留。

## 验收结果

- 本地 56 项回归测试通过；服务器同版依赖环境 3 项日志隐私专项测试通过。
- 匿名 GET/POST/DELETE `/mcp`：401，带 Bearer challenge。
- 错误 token、尾斜杠入口及 URL token 参数请求：拒绝。
- 公网直接请求 `/api/auth/mcp-check`：404。
- 正确 token：initialize、tools/list、read_diary(limit=1) 成功；正文仅在服务器内存中用于验收，不输出到工具日志。
- 有效 MCP session ID 但去掉 Authorization：401，不能用会话绕过鉴权。
- 网页会话身份、记忆统计、提醒、模型设置、聊天状态接口：200；未登录身份请求：401。
- 验收临时网页登录会话和 MCP 协议会话均已撤销。
- 实际请求携带的合成敏感标记，在本次重启后的应用 journal 与新 Nginx 访问日志中均未出现；实际 token 也未出现。
- 验收时 903 条记忆，SQLite quick_check=ok，服务正常且 NRestarts=0。
- 没有写入测试聊天或记忆，没有调用模型生成回复。完整真实聊天生成、生产写入流程和 Codex 客户端接入仍未端到端验收。

## Codex 桌面端填写

在用户此前截图的“连接到自定义 MCP”界面，可选择直接标头方式：

| 字段 | 值 |
| --- | --- |
| 名称 | Remoire |
| 类型 | 流式 HTTP |
| URL | `https://remoire.cc/mcp` |
| Bearer 令牌环境变量 | 留空（这里接收的是变量名，不是 token） |
| 标头：键 | `Authorization` |
| 标头：值 | `Bearer ` 加私密文件里的 token，中间一个空格 |
| 来自环境变量的标头 | 留空 |

不要把实际 token 放进项目文件、URL、截图或聊天。静态标头会保存在客户端本地配置中；如不希望凭据存进配置，可改用客户端进程能够读取的环境变量，此时“Bearer 令牌环境变量”填写变量名，而不是文件路径。

参考：[OpenAI 官方 MCP 配置说明](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)。保存后重新连接；如果当前对话工具列表未刷新，在新对话中验证能否列出 Remoire 工具，并先测试只读操作。

## 运维与回退

- 服务器备份：`/root/backups/mcp-auth-20261005/code-config.tar.gz`、`database.db`。
- 预检代码：`/opt/remoire/releases/mcp-auth-20261005/`。
- Nginx 配置：`/etc/nginx/sites-available/remoire`、`/etc/nginx/conf.d/remoire-logging.conf`。
- 备份是启用鉴权之前的版本。**不能直接恢复旧 Nginx 配置，否则会重新开放匿名 MCP。**
- 如需回退业务代码，应保留鉴权配置和 token 摘要；先 `nginx -t`，再 reload，重复匿名拒绝/正确 token 成功验收。
- 不需要为了回退本次日志修改恢复数据库。本次没有新增业务数据库迁移。
- 若 token 丢失或泄露：生成新的随机 token、更新服务端摘要并重启后端，再同步客户端；不得恢复匿名连接。
