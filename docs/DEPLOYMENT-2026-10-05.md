# 2026-10-05 生产发布记录

## 发布结果

- 生产版本：`2fe26c9`（`fix: protect core mobile interactions`）。
- 后端与 MCP 启动时间：北京时间 2026-10-05 00:34:55。
- 此前未提交的视觉修改已回滚，本次发布不含这些修改。
- 未修改 Nginx、网页登录配置或 MCP 认证配置。
- `remoire`、`remoire-mcp`、`nginx` 正常运行；后端与 MCP 重启计数为 0。
- 8000/8001 仅监听 127.0.0.1；自动备份定时器仍正常。

## 验证

- 待发布后端 44 个源码文件的 Git 内容指纹与提交一致。
- 新 Python 3.12 虚拟环境依赖检查通过，53 项 unittest 回归测试通过。
- 生产备份副本的数据库迁移和模型密钥加解密演练通过。
- 停止两个写入服务后创建最终 SQLite 一致性备份，再执行正式迁移。
- 正式迁移前后：903 条记忆、5,977 条消息、71 篇日记、9 个模型预设。
- 记忆 id/content、消息 id/role/content、日记 id/title/content 排序后的 SHA-256 校验值在迁移前后完全一致。
- 9 个模型预设密钥已加密存储并验证可解密；SQLite quick_check 为 ok。
- 线上 HTTPS 已认证接口 `/api/auth/me`、`/api/memory/stats`、`/api/memory?limit=1`、`/api/reminder?limit=50`、`/api/settings/model-presets`、`/api/settings/slots`、`/api/chat/status` 均通过。
- 未认证 `/api/auth/me` 返回 401；临时验收会话已撤销。
- MCP initialize、notifications/initialized、tools/list 通过，验收协议会话已关闭。
- 前端 index.html 与待发布构建指纹一致。旧哈希静态资源保留，兼容已打开的页面。
- 没有发送测试聊天、调用模型生成回复、写入测试记忆；真实聊天生成和完整浏览器交互未在本轮验收。

## 备份与依赖位置（均为服务器路径）

- 本次备份目录：`/root/backups/deploy-2fe26c9-20261005/`。
- `code-config.tar.gz`：部署前代码、前端、环境配置、systemd 与 Nginx 配置归档。
- `database.db`：在线初始备份；`final-database.db`：停写后的最终备份，回退以最终备份为准。
- `final-database.sha256`、`before.json`：最终备份校验和迁移前数据统计。
- `old-app`、`old-dist`、`old-mcp_server.py`、`old-requirements.txt`：旧代码快速恢复副本。
- `release-switch.py`：本次发布脚本；切换失败时自动恢复旧代码及最终备份。
- `deployed-version.txt`：本次成功切换版本记录。
- 新依赖：`/opt/remoire/venvs/2fe26c9`；原 `/opt/remoire/backend/venv` 保留。
- 两个服务通过各自 `/etc/systemd/system/<服务名>.service.d/90-release.conf` 使用新依赖。

## 回退注意事项

**当前部署已成功，不应直接运行回退。** 此后用户可能产生新数据，直接恢复最终备份会使线上回到切换时刻。若以后需要回退，先重新授权停机、备份当时最新数据库及配置，再评估是否必须回退数据库；不能只换旧代码，因为模型密钥已加密。

本次脚本的 `rollback` 模式会停止服务、保留失败版本及其数据库到时间戳目录、恢复旧代码和 `final-database.db`、撤销本次 systemd 覆盖配置，然后启动服务。它不是可重复执行的通用回退工具，使用前必须检查旧目录与部署状态。

## 尚未完成的独立安全项

后续已部署独立 token 鉴权、日志隐私补丁和 ChatGPT OAuth，见 `MCP-SECURITY-2026-10-05.md` 与 `CHATGPT-OAUTH-2026-10-05.md`。以下保留当时发布的阶段状态，不代表当前仍匿名。

MCP 继续沿用现有匿名连接模式，未启用独立 Bearer token 鉴权。此次只验证连接兼容性，**不代表 MCP 鉴权安全验收通过**。该公网入口的访问控制仍需单独安排，配置服务器摘要并同步客户端 token 后再验证匿名请求被拒绝。
