# 2026-10-12 表情图库发布

## 版本与范围

应用提交 `c9427ef8f3d8c55c50b16039b4ed508203fea107`，直接提交并推送 main，无额外分支合并。发布目录 `/opt/remoire/releases/20261012-c9427ef`。

- 共享表情库工具 search_stickers/send_sticker，复用网页和 iMessage 图片交付。
- 网页「＋ → 表情包」搜索、分类、分页、点选发送和预览。没有新增 iMessage 选择界面或网页 Tapback。
- messages.image_kind 区分表情/普通图片，表情缩小显示，保留原图。
- 独立导入用户授权的 826 条、9 类图库清单；原 Word、清单、缓存与数据库不进入 Git。没有用本地数据库覆盖生产。

## 验证与发布过程

本地完整后端 155 项、服务器隔离完整后端 155 项通过，前端 build 和相关组件 ESLint 通过。服务器初次隔离检查缺少测试目录和 scripts 模块，补齐后完整通过；前两次检查未切换生产。

更新前核对六个相关后端文件的生产基线 SHA256，全部匹配。确认 outbox 无 pending、最近入站已超过 120 秒，停止桥/后端/MCP后使用 SQLite backup API 生成一致快照并验证 quick_check。更新六个后端文件和前端资源，初始化增量 schema并导入图库，恢复原三服务；没有改生产密钥、人设提示词或模型预设。

迁移前后数量保持一致：messages 6458、memories 1041、model_presets 10、prompt_profiles 4。该数量是切换时核验，不代表此后停止产生新数据。

发布后独立只读核验：

- 六个后端文件和前端入口与发布包逐字节一致。
- 数据库 quick_check=ok，启用图库条目 826。
- remoire、remoire-mcp、remoire-imessage、nginx 均 active；iMessage connected。
- 公网 readiness 和首页均 200，首页内容匹配新构建。
- 匿名图库请求 401，认证保护保留。

用户于 2026-10-12 明确反馈已在真机验收表情包功能正常。未逐一验证全部外链，不据此宣称全部 iMessage 功能验收完成。Agent 没有主动发测试短信或调用付费模型；服务重启保留既有调度行为。

## 备份与回退

备份目录 `/root/backups/release-20261012-c9427ef`：`final.db` 为 SQLite backup API 一致快照（0600），`code-before.tar.gz` 为更新文件及前端入口，`new-files.json` 记录新增文件，`counts.json` 和 `tests.log` 保存计数及隔离回归结果。目录权限 0700。

回退应用时先停 remoire-imessage/remoire/remoire-mcp，从代码归档恢复已有文件，按 new-files.json 将新文件移到保留目录，恢复旧前端入口；旧 assets 已保留。再启动三服务并检查 readiness。新增 stickers 表和 image_kind 字段可保留，不用旧数据库覆盖发布后的新消息。数据库快照仅用于明确的数据恢复事件。

## 同日历史图片重试 422 修复

用户反馈首次发照片未收到回复，随后点击重新生成两次，均出现 422；服务器脱敏日志记录两次 POST 422。代码确认历史 image 字段为认证 URL，而重试直接作为 Base64 image 提交，必然被图片校验拒绝。前端现先通过认证接口读取历史原图，再编码提交；拒绝任意外部 URL，读取失败明确提示。另显示后端可读错误，完整空回复不再静默结束。首次未回复的具体供应商原因无法由现有日志确认。

本次前端构建、相关组件 lint、3 项图片重试测试通过（新图不变、历史 GIF 原字节转换、读取失败/外链拒绝）。仅前端变更，不修改后端数据。修复后真实模型重试尚待用户验收。
