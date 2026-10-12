# 2026-10-12 图片、iMessage 交互与主动消息修复发布

- 应用版本 `f4beea8`，已快进合并并推送 main，包含 `592f87f` 引用/Tapback、`93b121b` 图片和原图查看、`f4beea8` 主动消息连续性与状态恢复。
- Tapback 为 iMessage 气泡上的标准表情，支持双向添加与 Connie 仅贴表情；移除/撤回尚未实现，真实手机效果待用户验收。网页不增加表情 UI。
- 发布目录 `/opt/remoire/releases/20261012-f4beea8`，生产 Python `/opt/remoire/venvs/2fe26c9/bin/python`、Node `/opt/remoire/node22/bin/node`。
- 生产隔离回归 148 项、Node 协议 8 项通过；前端构建通过。备份副本迁移前后 messages 6451、memories 1039、model_presets 9、prompt_profiles 4 数量不变，quick_check=ok。
- 发布前 outbox pending=0、最近入站超过 120 秒。备份代码后停止桥、后端与 MCP，在线备份 final.db，替换 19 个相关后端/桥/规则文件与前端资源，重启服务。模型密钥、身份表达原文、其他生产提示词未覆盖；仅 autonomous.md 在确认基线指纹相同后更新。
- 发布后四服务 active，readiness=200，数据库 quick_check=ok，新交互表存在；所有 Python 文件、桥协议与前端入口指纹匹配。iMessage 账号 enabled=1/status=connected。公网首页匹配构建，内部桥接口匿名返回 401。
- 内置浏览器真实生产主动设置页确认 iMessage 可选，并按用户此前要求切换为 iMessage，界面显示已保存；未主动发送测试短信或调用生图模型。服务启动本身保留既有定时/补跑行为，不能据此声称没有任何后台模型活动。

## 回退

备份目录 `/root/backups/release-20261012-f4beea8`：在线备份 `remoire-20261012T035756Z.db` 及校验和、停服时一致快照 `final.db`、`code-before.tar.gz`、`new-files.json`。回退时先停三服务，解开代码归档到 `/opt/remoire`，按 new-files 清单移走本次新增代码文件（保留以便恢复），启动三服务并复核 readiness；旧前端 assets 保留。新增数据表可保留，不用旧库覆盖发布后的消息。备份含私人数据，不提交 Git。
