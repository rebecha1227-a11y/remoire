# 2026-10-10 iMessage 连发修复交接

用户报告先回答第一条，再回答后续短信；已核对生产并修复发布。详细证据、验证、回退见 `docs/DEPLOYMENT-2026-10-10-IMESSAGE-BURST.md`。

- 修改：backend/app/services/imessage_service.py、chat_service.py，测试 backend/tests/test_imessage.py。
- 生产合并值仍 3 秒；最新短信在生成中到达时，旧草稿不保存、不发、不提取记忆，继续等待安静期后带先前 user 历史生成。
- 只重启 remoire，Node 桥继续运行。不要启动本地桥。
- 已通过本地完整 115 + 新增单项、服务器隔离 18 项；真实手机验收留给用户正常连发，不主动制造付费请求。
- 本次未提交/推送。已有 QA_Log、10/9 handover 修改以及教程文件移动保持原样。
- 后续核对用户连发是否符合预期；已进入保存/发送阶段不撤回，不承诺发送前任意时刻可中断。生成中草稿作废可能有额外模型费用。
