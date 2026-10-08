# 用户视觉恢复 · 2026-10-05 已发布前端

针对用户部署后反馈修复，不做重新设计；本次仅发布前端静态文件，不修改生产后端、配置或数据。

- 主界面恢复 `8dcd849` 之前 room.css 使用的 Noto Serif SC；专属日记/纸条/共读/平行字体槽位不变。
- 聊天气泡操作按钮从硬性 44×44 恢复旧版 19×19（13px 图标加 3px padding），连带恢复原消息行高度；未放大气泡正文行高。
- 输入框垂直 padding 从 8px 修正到 12px，44px 单行输入框内的 20px 行高与模型槽垂直中心对齐。
- 聊天气泡与输入框改用 `--font-chat`，解决上传字体仅预览生效的问题；测试真实 TTF 上传、刷新保持、恢复默认。
- 两类开关圆点均为不透明白色，固定在轨道之上，不引用随主题变色的玻璃背景变量。
- 共读和星空平行空间按 `15f73ef` 前的前端设计恢复，保留“筹备中”、书籍和批注示意、进入/返回预览。尚未实现后台的添加/续写按钮禁用，不产生虚构业务写入。
- 日记编辑器使用独立纸色和深灰墨色，不再继承夜间浅黄文字；保存/取消/正文及留言按钮保持可读。去掉字段失焦时修改整个 body 高度的强制重排，字段间切换不再改动 body style。

## 验证

旧版和修复版在同一虚构数据、430×860 Chrome 浏览器中对照：操作按钮 44 → 19；输入文字与模型槽中心偏差 4px → 0；自定义 chat font 从无效变为有效；夜间日记文字从 rgb(239,227,205) 变为 rgb(61,50,41)；字段切换的 body style 修改次数 2 → 0。

前端 build、lint 通过。浏览器回归覆盖真实字体上传/刷新/恢复、三种强调色下白色开关、共读/平行预览和返回、日记编辑器/留言对比度。补齐本地 `/autonomous/dates` 和 `/autonomous/logs` 的数组型虚构数据后，生活日志入口、日历切换和返回通过，无浏览器异常。ConnieTimeline 生产组件未修改。

真实 iPhone 键盘与 PWA 合成层闪烁仍需用户在设备上确认，桌面模拟不能代替真机验收。

## 本地复现

在项目根目录启动 `node frontend/scripts/visual-preview.mjs`，仅监听 `127.0.0.1:4175`，所有 API 在预览服务器中返回虚构数据，写入请求统一拒绝，不访问生产数据库或模型。**不能用此脚本部署生产。**

另一个终端执行 `backend/venv/bin/python frontend/scripts/check-visuals.py`。使用已安装 Chrome 和 Python Playwright。非 macOS 需将 `REMOIRE_TEST_FONT` 指向一份测试 TTF 字体。截图保存到忽略提交的 `output/playwright/`。

## 发布记录

- main 已推送 `cfad834d6f52999fc7c83764e6f70b0a163a50ef`，仅含旧 main 的视觉适配、生产视觉 patch 和说明，没有合并后端加固分支。
- 生产构建源码：`2fe26c96d1322b7b578f323b0602126fcb15596c` + 七个视觉文件，对应本地 `0ee1c70911366c024a4384707ce0df3b51ace71b`。main 的发布说明和 `deploy/frontend-visual-20261005.patch` 可以复现这次源代码差异。不得直接构建旧 main 覆盖生产。
- 新资源：`index-Be3_FdDo.css`、`index-Cnb_LUev.js`；校验上传 SHA-256 后原子替换 index.html，保留旧资源。
- 新 index.html SHA-256：`ce019c182ca04bce4b0f09d893663e97c1270bf29b5a32fdadcb0f5565864d25`。
- 备份：服务器 `/root/backups/ui-20261005-0ee1c70/frontend-dist.tar.gz`，权限 600，完整目录 23 个归档条目；SHA-256 `d5ace6d7111b5e95e135f80c67af7665af725a575f4a84f078534f40bd332344`。
- 发布前后 backend/app Python 文件集合、mcp_server.py、.env 和 Nginx 配置集合摘要一致。remoire / remoire-mcp / nginx 全部 active，启动时间未变，无重启。
- 未上传后端文件、未运行迁移、未写测试聊天或记忆，未覆盖数据库。
- 公网最终验收：首页及两份新 JS/CSS 均 HTTP 200，内容 SHA-256 与本地构建逐一相同；匿名 auth/me、生活日志 API、MCP 均保持 401；430×860 Chrome 实际打开线上登录页成功，无 JavaScript 异常。未使用生产登录凭据，也未冒充已完成生产登录后的全流程验收。

### 回退（仅在用户要求或发布故障时执行）

在服务器验证备份 SHA-256 后，将归档解压到其独立备份目录（不是生产目录），得到旧 dist。将旧 index.html 复制为生产目录的 `.index-rollback.html`，确认内容后原子重命名为 index.html。旧 hash 资源仍在原目录，不需删除新资源，也不需恢复数据库或重启服务。
