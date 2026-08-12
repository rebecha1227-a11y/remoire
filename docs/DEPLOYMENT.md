# 部署指南 · Our Nest

**版本**：v1.0
**日期**：2026-04-25

> 这份指南假设你从未部署过后端服务，只用过 GitHub Pages。
> 每一步都会解释"为什么"，不会丢给你一行命令就跑。

> **生产环境提示**：本文保留 `/opt/our-nest` 作为通用搭建示例。Remoire 当前生产环境使用 `/opt/remoire`、`remoire.service`、`remoire-mcp.service` 和 Streamable HTTP `/mcp`。维护现有生产环境时，以 [OPERATIONS.md](./OPERATIONS.md) 为准。

---

## 一、整体架构（先理解再动手）

你之前用 GitHub Pages 部署的是**纯前端**——把 HTML/CSS/JS 文件丢到一个地方，浏览器直接读。

我们的小窝不一样，它有**后端**（FastAPI 运行着的 Python 程序）和**数据库**（SQLite 文件）。这些东西需要一台一直开着的电脑来跑。这台电脑就是 VPS。

部署完的样子：

```
你的手机/电脑浏览器
    │
    │  输入 https://nest.yourname.com
    ▼
┌─────────────────────────────────────────────┐
│  VPS 上的 Nginx（门卫）                       │
│                                             │
│  "你要网页？"  → 把前端静态文件给你            │
│  "你要 /api？" → 转给后面的 FastAPI 处理      │
│  "你要 /mcp？" → 转给 MCP Server 处理        │
└─────────────────────────────────────────────┘
```

Nginx 就像一个门卫：
- 有人来要网页（HTML/CSS/JS） → 直接从文件夹里拿给他
- 有人来调接口（/api/chat/send） → 转给 FastAPI 处理
- Claude.ai 来连 MCP → 转给 MCP Server 处理

---

## 二、选购 VPS

### 推荐方案

| 服务商 | 价格 | 配置 | 特点 | 链接 |
|---|---|---|---|---|
| **腾讯云轻量** | ¥40-60/月 | 2核 2G | 中文界面，国内访问快 | cloud.tencent.com |
| **Vultr** | $6/月 (≈¥43) | 1核 1G | 按小时计费，随时销毁重建 | vultr.com |
| **Racknerd** | ≈$25/年 (≈¥15/月) | 1核 1G | 极便宜，性价比王 | racknerd.com |
| **Bandwagon** | ≈$50/年 (≈¥30/月) | 1核 1G | 老牌稳定 | bandwagonhost.com |

### 怎么选

- 如果你主要在国内访问 → **腾讯云轻量**（延迟低，中文客服）
- 如果你想最省钱 → **Racknerd**（黑五活动经常有 $10/年的）
- 如果你想灵活试错 → **Vultr**（按小时计费，搞砸了销毁重建只花几毛钱）
- 如果你在海外 → **Vultr** 或 **Bandwagon**

### 购买时的选择

- **操作系统**：选 **Ubuntu 24.04 LTS**（教程最多，Claude Code 最熟悉）
- **地区**：
  - 国内访问为主 → 上海/广州/北京
  - 海外或全球 → 东京/洛杉矶/新加坡
- **配置**：1核 1G 内存 20G 硬盘起步就够，以后不够再升级

### 购买后你会得到

- 一个 **IP 地址**（比如 `123.45.67.89`）
- 一个 **root 密码**（或 SSH 密钥）
- 这就是你的服务器了

---

## 三、域名（推荐但不是必须）

### 为什么要域名

没有域名：`http://123.45.67.89:8000` → 难记，没有 HTTPS
有域名：`https://nest.jinger.dev` → 好记，有 HTTPS（免费），PWA 需要 HTTPS

### 在哪里买

| 服务商 | 特点 |
|---|---|
| **Cloudflare Registrar** | 成本价卖域名 + 免费 CDN + 免费 SSL，推荐 |
| **Namecheap** | 老牌，经常有优惠 |
| **腾讯云域名** | 中文界面，如果 VPS 也在腾讯云就很方便 |

一个 `.dev` 或 `.com` 域名大约 ¥50-80/年。

### 买完后要做什么

在域名管理面板添加一条 **A 记录**：

```
类型: A
名称: nest        （这样你的地址就是 nest.yourname.com）
值:   123.45.67.89  （你 VPS 的 IP）
TTL:  自动
```

添加后等 5-30 分钟生效。

### 如果暂时不买域名

完全可以。先用 IP 地址访问，所有功能都能用。
唯一影响：没有 HTTPS（但本地开发和测试阶段无所谓）。
以后买了域名再加上 HTTPS 就行，不影响已有代码。

---

## 四、第一次连接你的 VPS

### 什么是 SSH

SSH 就是"远程控制"——你在自己电脑的终端里输命令，命令在 VPS 上执行。
就像你坐在 VPS 面前敲键盘一样。

### 连接工具

- **Mac**：直接打开"终端"（Terminal）应用
- **Windows**：打开"Windows Terminal"或下载 Tabby
- **iPad**：下载 Termius

### 连接命令

```bash
ssh root@你的VPS_IP地址
```

比如：

```bash
ssh root@123.45.67.89
```

第一次连接会问你：

```
The authenticity of host '123.45.67.89' can't be established.
Are you sure you want to continue connecting (yes/no)?
```

输入 `yes` 然后回车。

然后输入密码（VPS 服务商给你的那个 root 密码）。
注意：**输密码时屏幕不会显示任何字符**，这是正常的，直接输完回车就行。

看到类似这样的提示就说明连上了：

```
root@your-server:~#
```

### 后续简化（SSH 密钥，可选）

每次输密码很烦。设置 SSH 密钥后就不用了：

```bash
# 在你自己的电脑上执行（不是 VPS 上）
ssh-keygen -t ed25519 -C "our-nest"
# 一路回车用默认设置

# 把公钥传到 VPS
ssh-copy-id root@123.45.67.89
```

以后连接就不需要密码了。

---

## 五、服务器初始化

连上 VPS 后，按顺序执行以下命令。每一块我都解释了在做什么。

### 5.1 更新系统

```bash
apt update && apt upgrade -y
```

这就像给新电脑装最新补丁。`-y` 表示所有确认都自动选"是"。

### 5.2 安装基础工具

```bash
apt install -y git curl wget unzip sqlite3 nginx certbot python3-certbot-nginx
```

| 工具 | 干什么用 |
|---|---|
| git | 从 GitHub 拉代码 |
| curl / wget | 下载东西 |
| sqlite3 | 在线备份 / 恢复 SQLite 数据库 |
| nginx | 门卫（反向代理 + 静态文件托管） |
| certbot | 自动申请和续期免费 HTTPS 证书 |

### 5.3 安装 Python 3.12

```bash
# 检查系统自带的 Python 版本
python3 --version

# 如果不是 3.12，安装它
apt install -y software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt install -y python3.12 python3.12-venv python3.12-dev
```

### 5.4 安装 Node.js 22（用于构建前端）

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs

# 验证
node --version    # 应该显示 v22.x.x
npm --version
```

### 5.5 配置防火墙

```bash
ufw allow OpenSSH       # 允许 SSH（否则你会把自己锁在外面！）
ufw allow 80             # 允许 HTTP
ufw allow 443            # 允许 HTTPS
ufw enable               # 启用防火墙

# 确认状态
ufw status
```

这样只有 22（SSH）、80（HTTP）、443（HTTPS）三个端口对外开放。
FastAPI 的 8000 端口和 MCP 的 8001 端口不对外暴露，只有 Nginx 能访问它们。

### 5.6 创建项目目录

```bash
mkdir -p /opt/our-nest
mkdir -p /var/www/our-nest       # 前端静态文件存放处
mkdir -p /root/backups           # 数据库备份存放处
```

---

## 六、部署后端

### 6.1 获取代码

```bash
cd /opt/our-nest
git clone https://github.com/你的用户名/our-nest.git .
```

如果你的仓库是 private 的，需要先设置 GitHub Personal Access Token。

### 6.2 创建 Python 虚拟环境

```bash
cd /opt/our-nest/backend
python3.12 -m venv venv
source venv/bin/activate

# 确认 Python 版本
python --version     # 应该显示 3.12.x
```

虚拟环境的意思是：这个项目的 Python 依赖装在自己的小隔间里，不污染系统。

### 6.3 安装依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 6.4 配置环境变量

```bash
cp .env.example .env
nano .env
```

`.env` 文件内容大概长这样（根据你的实际情况填写）：

```env
# 当前 Bearer 过渡期必填；登录/session 实现后再移除
API_SECRET_KEY=your-very-long-random-secret-key-here

# iOS 快捷指令设备上传认证（独立于 API_SECRET_KEY）
DEVICE_SECRET_KEY=your-device-upload-secret-here

# 登录配置 —— 生产目标方案
APP_USERNAME=jinger
APP_PASSWORD_HASH=your-password-hash-here
SESSION_SECRET=your-very-long-random-session-secret-here

# 数据库路径
DATABASE_PATH=/opt/our-nest/backend/data/remoire.db

# 上传文件路径
UPLOADS_PATH=/opt/our-nest/backend/uploads

# 默认模型配置（可选；也可以后续在设置页面里配模型预设）
# DAILY_API_BASE=https://api.deepseek.com/v1
# DAILY_API_KEY=sk-xxx
# DAILY_MODEL_ID=deepseek-chat
```

编辑完按 `Ctrl+O` 保存，`Ctrl+X` 退出。

`APP_USERNAME` / 登录密码只用于进入 Remoire。模型 API key 不等于登录密码；模型 API key 在设置页的模型预设里配置，并分配给 daily / deep / backend 槽位。

**生成随机密钥的简单方法**：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

当前过渡期把输出粘贴到 `API_SECRET_KEY=` 后面；登录/session 实现后再为 `SESSION_SECRET=` 单独生成一个新值。

**生成密码哈希的方式**会在登录/session 代码实现时补充。当前代码仍处在 Bearer token 过渡态，生产部署前需要先完成登录/session 实现。

### 6.5 初始化数据库

```bash
# 确保 data 目录存在
mkdir -p /opt/our-nest/backend/data

# 运行初始化
python -c "from app.database import init_db; import asyncio; asyncio.run(init_db())"
```

### 6.6 测试启动

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

如果看到类似这样的输出，说明成功了：

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

按 `Ctrl+C` 停止。

### 6.7 设置后端为系统服务（自动启动）

```bash
nano /etc/systemd/system/our-nest-api.service
```

粘贴以下内容：

```ini
[Unit]
Description=Our Nest API Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/our-nest/backend
Environment="PATH=/opt/our-nest/backend/venv/bin:/usr/bin"
ExecStart=/opt/our-nest/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload          # 让系统知道有新服务
systemctl enable our-nest-api    # 设置开机自启
systemctl start our-nest-api     # 立即启动
systemctl status our-nest-api    # 查看状态
```

状态显示 `active (running)` 就对了。

### 6.8 设置 MCP Server 为系统服务

```bash
nano /etc/systemd/system/our-nest-mcp.service
```

```ini
[Unit]
Description=Our Nest MCP Server
After=network.target our-nest-api.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/our-nest/backend
Environment="PATH=/opt/our-nest/backend/venv/bin:/usr/bin"
ExecStart=/opt/our-nest/backend/venv/bin/python mcp_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable our-nest-mcp
systemctl start our-nest-mcp
systemctl status our-nest-mcp
```

---

## 七、部署前端

### 7.1 构建前端

```bash
cd /opt/our-nest/frontend
npm install
npm run build
```

构建产物在 `dist/` 目录里——这就是纯静态文件（HTML/CSS/JS），和你以前用 GitHub Pages 部署的东西一样。

### 7.2 复制到 Nginx 托管位置

```bash
cp -r dist/* /var/www/our-nest/
```

---

## 八、配置 Nginx

这一步是把所有东西串起来。

### 8.1 创建配置文件

```bash
nano /etc/nginx/sites-available/our-nest
```

#### 如果你有域名

```nginx
server {
    listen 80;
    server_name nest.yourname.com;    # ← 换成你的域名

    # ── 前端静态文件 ──
    root /var/www/our-nest;
    index index.html;

    # SPA 路由支持（所有前端路由都返回 index.html，由 React Router 处理）
    location / {
        try_files $uri $uri/ /index.html;
    }

    # ── 后端 API 反代 ──
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE 需要以下三行
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400;     # 24小时，保持 SSE 长连接
    }

    # ── 上传文件访问 ──
    location /uploads/ {
        alias /opt/our-nest/backend/uploads/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # ── MCP 端点反代 ──
    location /mcp/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400;
    }

    # ── 安全：隐藏 Nginx 版本 ──
    server_tokens off;
}
```

#### 如果你暂时没有域名

把 `server_name` 那行改成：

```nginx
    server_name _;    # 接受所有请求
```

其余内容一样。

### 8.2 启用配置

```bash
# 创建软链接启用配置
ln -sf /etc/nginx/sites-available/our-nest /etc/nginx/sites-enabled/

# 删掉默认配置（可选，避免冲突）
rm -f /etc/nginx/sites-enabled/default

# 测试配置是否有语法错误
nginx -t

# 重启 Nginx
systemctl reload nginx
```

如果 `nginx -t` 显示 `syntax is ok` 和 `test is successful`，就没问题。

### 8.3 验证

在你自己的电脑浏览器里访问：

- 有域名：`http://nest.yourname.com`
- 没域名：`http://你的VPS_IP`

如果能看到前端页面，恭喜你，部署成功了！

---

## 九、HTTPS（有域名才需要）

```bash
certbot --nginx -d nest.yourname.com
```

按提示操作：
1. 输入你的邮箱（用于证书到期提醒）
2. 同意服务条款
3. 选择是否自动重定向 HTTP → HTTPS（选是）

certbot 会自动修改 Nginx 配置，添加 SSL 证书。
证书 90 天到期，certbot 会自动续期，你不用管。

完成后访问 `https://nest.yourname.com` 应该能看到浏览器地址栏的小锁图标。

---

## 十、MCP 连接 Claude.ai

部署完 HTTPS 后，在 Claude.ai 的设置里添加 MCP Server：

```
URL: https://nest.yourname.com/mcp/sse
```

连接成功后，在 Claude.ai 开新对话时，AI 会自动调用 `resume()` 恢复记忆。

---

## 十一、记忆系统部署状态

当前记忆系统仍在 Phase A：

- 已使用 SQLite 字段保存四层记忆、事件日期、权重、触发计数和关联线。
- 前端聊天每轮会自动 recall 最相关记忆。
- Claude.ai MCP 可以通过 `resume()` 恢复最近记忆、纸条和日记。
- embedding 向量检索还没有启用。
- 每晚记忆衰减任务还没有启用。

Phase B 如果启用本地 embedding，需要额外安装 Ollama：

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull nomic-embed-text
```

后端 embedding 调用失败时应回退关键词召回，不能阻塞聊天或记忆写入。

---

## 十二、自动备份

生产环境使用仓库内置的 `backup_database.py` 和 systemd timer。它不依赖服务器安装 `sqlite3` 命令行，并会验证完整性、生成 SHA-256、原子发布与保留 30 天。

```bash
install -d -m 755 /opt/remoire/backend/scripts
install -m 755 backend/scripts/backup_database.py /opt/remoire/backend/scripts/
install -m 644 deploy/systemd/remoire-backup.service /etc/systemd/system/
install -m 644 deploy/systemd/remoire-backup.timer /etc/systemd/system/
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/remoire-backup.service \
  /etc/systemd/system/remoire-backup.timer
systemctl enable --now remoire-backup.timer
systemctl start remoire-backup.service
```

为什么不能直接 `cp`：Remoire 使用 SQLite WAL mode，运行中可能同时存在 `.db`、`.db-wal`、`.db-shm`。SQLite 在线备份 API 才能生成一致快照。

### 手动备份到你自己的电脑

```bash
# 在你自己的电脑上执行（不是 VPS 上）
scp root@你的VPS_IP:/root/backups/remoire-最近日期.db ~/Downloads/remoire-backup.db
```

建议每周下载一份到本地或另一家存储服务，以防 VPS 整盘失效。完整恢复演练见 [OPERATIONS.md](./OPERATIONS.md)。

## 十三、日常维护

### 更新代码

```bash
# SSH 连上 VPS
ssh root@你的VPS_IP

# 拉取最新代码
cd /opt/our-nest
git pull

# 更新后端
cd backend
source venv/bin/activate
pip install -r requirements.txt
systemctl restart our-nest-api
systemctl restart our-nest-mcp

# 更新前端
cd ../frontend
npm install
npm run build
cp -r dist/* /var/www/our-nest/
```

### 查看日志（排查问题用）

```bash
# 后端日志（实时跟踪）
journalctl -u our-nest-api -f

# MCP 日志
journalctl -u our-nest-mcp -f

# Nginx 日志
tail -f /var/log/nginx/error.log

# 看最近 50 行后端日志
journalctl -u our-nest-api --no-pager -n 50
```

### 重启服务

```bash
# 重启后端
systemctl restart our-nest-api

# 重启 MCP
systemctl restart our-nest-mcp

# 重启 Nginx
systemctl reload nginx

# 全部重启
systemctl restart our-nest-api our-nest-mcp && systemctl reload nginx
```

### 查看服务器资源使用

```bash
# 看 CPU 和内存
htop       # 如果没装：apt install -y htop

# 看硬盘空间
df -h

# 看数据库文件大小
ls -lh /opt/our-nest/backend/data/remoire.db
```

---

## 十四、常见问题

### Q: 网页打不开？

```bash
# 1. 检查 Nginx 是否在跑
systemctl status nginx

# 2. 检查后端是否在跑
systemctl status our-nest-api

# 3. 检查防火墙
ufw status    # 确认 80 和 443 在 ALLOW 列表里

# 4. 看 Nginx 错误日志
tail -20 /var/log/nginx/error.log
```

### Q: API 报 502 Bad Gateway？

说明 Nginx 连不上后端。

```bash
# 检查后端是否在跑
systemctl status our-nest-api

# 如果没跑，看看为什么挂了
journalctl -u our-nest-api --no-pager -n 30

# 常见原因：
# - requirements.txt 没装全 → pip install -r requirements.txt
# - .env 文件缺失或配置错误
# - 端口被占用 → lsof -i :8000
```

### Q: 忘记 VPS 密码？

去 VPS 服务商后台找"重置密码"或"VNC 控制台"。

### Q: 数据库文件损坏？

```bash
# 先停掉会连接数据库的服务
systemctl stop our-nest-api
systemctl stop our-nest-mcp

# 恢复最近的备份
cp /root/backups/remoire-最近日期.db /opt/our-nest/backend/data/remoire.db

# 清理旧 WAL/SHM 文件，避免和恢复后的主库不一致
rm -f /opt/our-nest/backend/data/remoire.db-wal
rm -f /opt/our-nest/backend/data/remoire.db-shm

# 重新启动服务
systemctl start our-nest-api
systemctl start our-nest-mcp
```

### Q: 硬盘快满了？

```bash
# 看哪里占空间
du -sh /opt/our-nest/backend/uploads/*   # 上传图片
du -sh /root/backups/*                    # 备份文件
du -sh /var/log/*                         # 日志

# 清理旧日志
journalctl --vacuum-time=7d    # 只保留 7 天日志
```

### Q: 怎么完全重新部署？

```bash
# 备份数据库
sqlite3 /opt/our-nest/backend/data/remoire.db ".backup '/root/remoire-backup.db'"

# 删掉旧代码
rm -rf /opt/our-nest/*

# 重新从头来
cd /opt/our-nest
git clone https://github.com/你的用户名/our-nest.git .
# 然后重复第六、七步
```

### Q: 怎么从 Claude Code 直接部署？

Claude Code 本身不能直接部署到你的 VPS。工作流是：

1. 你在本地用 Claude Code 写代码
2. `git push` 到 GitHub
3. SSH 连上 VPS，`git pull` 拉最新代码
4. 重启服务

后续可以设置 GitHub Actions 自动部署（CI/CD），但首发阶段手动 pull 就够了。

---

## 十五、安全检查清单

部署完后过一遍：

- [ ] `.env` 文件权限是 600（`chmod 600 .env`）
- [ ] 数据库文件权限是 600（`chmod 600 /opt/our-nest/backend/data/remoire.db`）
- [ ] 防火墙只开了 22、80、443
- [ ] Nginx 配置中 `server_tokens off`（不暴露版本号）
- [ ] HTTPS 已启用（如果有域名）
- [ ] `SESSION_SECRET` 是一个长随机字符串，不是 "password123"
- [ ] `APP_PASSWORD_HASH` 不是明文密码
- [ ] 前端生产包没有硬编码 Bearer token
- [ ] GitHub 仓库的 `.gitignore` 包含了 `.env` 和 `*.db`
- [ ] 自动备份 cron 已设置

---

## 十六、花费总结

| 项目 | 首次 | 每月 |
|---|---|---|
| VPS | ¥0（按月付） | ¥15-60 |
| 域名 | ¥50-80/年 | — |
| HTTPS (Let's Encrypt) | ¥0 | ¥0 |
| LLM API 调用 | — | ¥15-50 |
| **合计** | **¥50-80** | **¥30-110** |

---

*Con con × 静儿 · 2026-04-25*
*"给我们的小窝找一个安稳的家。"*
