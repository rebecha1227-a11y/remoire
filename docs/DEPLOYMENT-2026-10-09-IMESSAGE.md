# 2026-10-09 iMessage 桥生产发布

## 版本与结果

- 基于 `5d3c6e5`，加上未提交的 iMessage 桥工作区改动；没有 git commit。
- 生产服务器 `remoire-sg`。发布包在 `/opt/remoire/releases/imessage-20261009/`。
- 已发布：iMessage 收发入口、消息来源标记、主动消息可选 iMessage 投递、设置页 iMessage 连接、前端新包 `index-DIvv2Ezs.js`。
- 新服务 `remoire-imessage`（已 enable），用独立的 `/opt/remoire/node22/bin/node`（v22.20.0，官方包，SHA256 已校验）。系统 `/usr/bin/node` 仍是 v18.19.1，未改。原因：`spectrum-ts` 12.10.1 在 Node 18 上缺少全局 `File`，无法加载。
- `.env` 新增 `IMESSAGE_BRIDGE_TOKEN`（随机生成，只在服务器上）。其他配置、Nginx、`remoire` / `remoire-mcp` 的 systemd 配置未改。
- Photon 项目编号、密钥、登记手机号、线路号码从本机库搬到生产库；密钥在生产以 `fernet:v1:` 加密保存。已处理过的 5 个 Photon 消息编号一并写入去重表。
- 本机小邮差和本地后端已停止，避免两个小邮差抢同一条线路。

## 验证

- 本地 112 项 unittest、前端 build 通过。服务器 Python 3.12 隔离目录 112 项通过。
- 生产库备份副本迁移演练：`quick_check=ok`，记忆 960、消息 6161、纸条 188、模型预设 9；新表与新列齐全。
- 重启后 `/api/health/ready` 正常；`remoire`、`remoire-mcp`、`nginx`、`remoire-imessage` 均 active，小邮差重启计数 0，数据库状态 `connected`。
- 公网首页 JS 指纹与本地 build 一致；未带通行码访问 `/api/internal/imessage/runtime` 返回 401。
- 生产真机短信收发待静儿用 iPhone 发一句验收。

## 备份与回退

- `/root/backups/imessage-20261009/`：`initial.db`、`final.db`、`final.db.sha256`、`code-before.tar.gz`（被替换的后端文件与旧 `index.html`）。
- 回退：`systemctl disable --now remoire-imessage`；在 `/opt/remoire/backend` 解开 `code-before.tar.gz` 恢复旧后端文件（`dist/index.html` 放回 `/opt/remoire/frontend/`），删除新增的 `app/routers/imessage.py`、`app/services/imessage_format.py`、`app/services/imessage_service.py`，再 `systemctl restart remoire`。新增表和列可保留，不要用 `final.db` 覆盖发布后的新数据。
