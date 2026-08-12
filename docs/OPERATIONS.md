# Remoire 生产运维手册

**适用环境**：`remoire.cc` 当前生产实例
**原则**：代码可以重新部署，数据库必须可恢复；任何生产操作都先确认路径，再确认备份。

## 一、生产拓扑与真实路径

| 项目 | 生产值 |
|---|---|
| 项目根目录 | `/opt/remoire` |
| 后端工作目录 | `/opt/remoire/backend` |
| 前端静态文件 | `/opt/remoire/frontend/dist` |
| 生产数据库 | `/opt/remoire/backend/data/remoire.db` |
| 环境变量 | `/opt/remoire/backend/.env` |
| 数据库备份 | `/root/backups` |
| FastAPI 服务 | `remoire.service`，监听 `127.0.0.1:8000` |
| MCP 服务 | `remoire-mcp.service`，监听 `127.0.0.1:8001` |
| 入口 | Nginx，公网只开放 80/443 |

以下文件不是生产数据库，禁止误用：

- `/opt/remoire/data/remoire.db`：历史旧库。
- `/opt/remoire/backend/remoire.db`：历史空库。
- 本地 `backend/data/remoire.db`：开发快照，不会自动与生产同步。

## 二、日常状态检查

```bash
systemctl is-active remoire remoire-mcp nginx remoire-backup.timer
systemctl list-timers remoire-backup.timer --no-pager
journalctl -u remoire -n 50 --no-pager
journalctl -u remoire-backup.service -n 20 --no-pager
```

FastAPI 和 MCP 只能监听本机回环地址：

```bash
ss -lnt | grep -E ':8000|:8001|:80 |:443 '
```

如果 8000 或 8001 显示为 `0.0.0.0`，应先修复监听地址再继续发布。

## 三、数据库备份

Remoire 使用 SQLite WAL。运行中禁止用普通 `cp` 复制主数据库；那样可能漏掉 WAL 中尚未 checkpoint 的数据。

仓库中的 `backend/scripts/backup_database.py` 使用 SQLite 在线备份 API，并完成：

1. 在线一致性快照。
2. `PRAGMA quick_check`。
3. 记忆数量验证。
4. SHA-256 校验文件。
5. 原子发布，失败时不留下半成品。
6. 只清理严格匹配命名格式且超过 30 天的旧备份。

### 自动备份

```bash
systemctl enable --now remoire-backup.timer
systemctl list-timers remoire-backup.timer --no-pager
```

定时器每天北京时间 04:00 执行，并使用 `Persistent=true`：如果服务器当时关机，恢复后会补跑。

### 手动创建并验证备份

```bash
systemctl start remoire-backup.service
journalctl -u remoire-backup.service -n 10 --no-pager

latest=$(find /root/backups -maxdepth 1 -type f -name 'remoire-*.db' | sort | tail -1)
/opt/remoire/backend/venv/bin/python \
  /opt/remoire/backend/scripts/backup_database.py --verify "$latest"
```

成功标准：输出同时包含 `"ok": true`、`"quick_check": "ok"` 和合理的 `memories` 数量。

### 下载离线副本

在开发电脑执行：

```bash
scp -i ~/.ssh/remoire_vps \
  root@你的服务器:/root/backups/remoire-YYYYMMDDTHHMMSSZ.db \
  ~/Downloads/
scp -i ~/.ssh/remoire_vps \
  root@你的服务器:/root/backups/remoire-YYYYMMDDTHHMMSSZ.db.sha256 \
  ~/Downloads/
```

建议至少每周保留一份不在 VPS 同一磁盘上的离线副本。服务器内备份不能防止整块磁盘或账号失效。

## 四、恢复演练与真实恢复

### 无停机恢复演练

恢复演练只复制到临时文件，不接触生产数据库：

```bash
install -m 600 /root/backups/remoire-YYYYMMDDTHHMMSSZ.db \
  /tmp/remoire-restore-drill.db
/opt/remoire/backend/venv/bin/python \
  /opt/remoire/backend/scripts/backup_database.py \
  --verify /tmp/remoire-restore-drill.db
rm -f /tmp/remoire-restore-drill.db
```

至少每月执行一次恢复演练。

### 真实恢复

真实恢复会覆盖生产数据，只有在明确选择了正确备份后执行：

1. 先运行一次 `remoire-backup.service` 保存事故现场。
2. 停止 `remoire` 和 `remoire-mcp`。
3. 再次验证目标备份的 SHA-256 和 `quick_check`。
4. 把现有数据库移动到带时间戳的隔离路径，不直接删除。
5. 安装备份为新的 `remoire.db`，权限设为 `600`。
6. 启动服务，核对记忆数量、聊天和 MCP。
7. 验证完成前不要删除隔离的事故现场数据库。

## 五、发布代码

### 后端

只上传本次已经测试过的文件，随后重启并检查日志：

```bash
scp -i ~/.ssh/remoire_vps backend/app/路径/文件.py \
  root@你的服务器:/opt/remoire/backend/app/对应路径/
ssh -i ~/.ssh/remoire_vps root@你的服务器 \
  'systemctl restart remoire && systemctl status remoire --no-pager'
```

修改 MCP 后重启 `remoire-mcp`。修改数据库结构前必须先做备份和迁移演练。

### 前端

```bash
cd frontend
npm ci
npm run build
scp -i ~/.ssh/remoire_vps dist/assets/*.js dist/assets/*.css \
  root@你的服务器:/opt/remoire/frontend/dist/assets/
scp -i ~/.ssh/remoire_vps dist/index.html \
  root@你的服务器:/opt/remoire/frontend/dist/
```

发布后必须在真实手机尺寸检查登录、聊天、记忆宫殿、日记和错误反馈。

## 六、密钥与隐私

- `.env`、API key、Bearer token、session secret 不得写入源码、handover、截图或日志。
- Handover 只记录变量名和存放路径，不记录真实值。
- 浏览器端不得包含任何能直接访问完整 API 的生产密钥。
- 密钥泄露后必须轮换；仅从当前文件删除不能撤销历史泄露。
- 数据库和备份权限保持 `600`，备份目录保持 `700`。
- 日志与诊断输出不得打印记忆正文、API key 或完整认证头。

### 登录认证配置与轮换

在后端目录运行密码散列生成器；它通过隐藏输入读取密码，不会把密码留在 shell history：

```bash
cd /opt/remoire/backend
./venv/bin/python -m scripts.generate_password_hash
```

只把输出的 scrypt 散列写入 `/opt/remoire/backend/.env` 的 `APP_PASSWORD_HASH`。生产认证变量至少包括：

```dotenv
APP_USERNAME=connie
APP_PASSWORD_HASH=<上一步输出>
SESSION_COOKIE_SECURE=true
SESSION_TTL_DAYS=30
ALLOW_LEGACY_BEARER=false
TRUSTED_ORIGINS=https://remoire.cc
ALLOWED_HOSTS=remoire.cc,localhost,127.0.0.1
```

切换旧部署时，先短暂设置 `ALLOW_LEGACY_BEARER=true` 并发布后端，再发布登录版前端；确认新登录成功后立即改回 `false`、生成新的随机 `API_SECRET_KEY` 并重启。旧值即使仍存在 Git 历史中也会随轮换失效。修改认证配置会使旧 Bearer 失效；删除 `auth_sessions` 中的记录可强制所有浏览器重新登录。

Nginx 使用仓库中的 `deploy/nginx/remoire.conf`。上线前先运行 `nginx -t`，它负责 HTTPS、HSTS、CSP 和正确转发客户端 IP/协议。

## 七、交付门禁

一次生产发布只有同时满足以下条件才算完成：

- 相关自动化测试通过。
- 最新备份通过 SHA-256 和 SQLite 完整性验证。
- systemd 服务和定时器状态正常。
- 8000/8001 没有直接暴露公网。
- 生产数据库数量与发布前预期一致。
- 关键用户流程已在真实生产域名验证。
- 仓库与 handover 中没有新增明文密钥。
