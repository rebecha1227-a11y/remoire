# QA Log

## 2026-10-09 换日常模型要不要为 Claude 改代码

**原问：** 现在是在做什么？为什么要查 Claude API 的要求/消息转换逻辑？只需要把本地日常槽位改成生产环境里那个 Claude 的 API。为什么要专门针对 Claude 做修改，以后换成别的模型不就不适用了吗？

**答案核心：** 不用改代码。聊天每次都读「日常槽位」里保存的那条接口：地址、模型和密钥。换模型只是把槽位指到另一条已保存的接口。Claude、Gemini、DeepSeek 走的是同一条路，程序按模型名字自己决定怎么调用。专门为 Claude 改消息格式，下次换成别的模型就会失效，所以没有改。本地日常槽已改成模型库里那条 Youkies 的 Claude Opus 4.6（和深度槽同一条）。

**相关引用：** `model_settings_service.get_model_config_for_slot`；`model_settings_service.update_slot`

## 2026-10-09 Photon 指导页的第 2、3 步要不要做

**原问：** 已经拿到 Photon 号码 +1 (415) 595-1440，指导页让跑 `bun create spectrum-project` 再 `bun start`，接下来要怎么做？

**答案核心：** 不要跑那两步。那是 Photon 自带的回声示例，会另起一个只会回 `echo:` 的程序，和 Connie 抢同一条线路。Remoire 已经有自己的小邮差。本机小邮差已经连上，状态是已连接。下一步用自己的 iPhone 给这个号码发一句短信，回复会进现有聊天，不是 echo。这台电脑要保持开着，小邮差才收得到。

**相关引用：** `backend/imessage_bridge/index.mjs`；Photon 入门页 Step 02 的 scaffold 是独立示例项目

## 2026-10-09 开通线路之后为什么状态还是未配置

**原问：** 我已经在 Remoire 里面开通线路了（不知道为什么显示状态未配置）

**答案核心：** 开通成功了。线路号码已经写进本地库，开关也开着。「未配置」说的不是线路没开通，而是本机小邮差还没连上 Photon 的收发通道。开通线路只向 Photon 登记手机号并领一个线路号码；变成「已连接」要等小邮差进程跑起来之后才会改。页面文案已改成「线路已开通，还没开始收发」。

**相关引用：** `imessage_service.enroll_line` 只写 `line_phone`；连接状态由 `backend/imessage_bridge/index.mjs` 回报

## 2026-10-09 入门页网址是不是还没打开 Spectrum

**原问：** https://app.photon.codes/dashboard/…/getting-started?platform=imessage 我这个是不是还没打开 spectrum 啊？

**答案核心：** 这个网址本身说明项目已经建好，而且选的是 iMessage。它是入门向导，不是「Spectrum 还关着」的标志。地址里的那串编号是控制台项目编号。Spectrum 打开之后，项目上会另有 `spectrumProjectId` 和 `projectSecret`；Remoire 要填的是这两样。看项目设置里有没有 Secret：有，就是已经打开；没有，才是还没开。不要把 Secret 发到聊天里。

**相关引用：** Photon Stable 文档 `api-reference/projects/create-project` 的 `spectrum`、`spectrumProjectId`、`projectSecret`；`cli/projects` 的 `--spectrum`

## 2026-10-09 怎么在 Photon 建项目，才能接到 Remoire

**原问：** 你先在 Cursor 内本地把后端和网页打开给我看一下，然后教我如何在 Photon 建项目。

**答案核心：** 本地页面在 `http://127.0.0.1:5173/`，设置里已经能看到「iMessage 连接」和主动消息的三个入口。iMessage 和微信现在是灰的，因为还没有线路。Photon 用现在的稳定版文档：打开 https://app.photon.codes 登录，新建项目时打开 Spectrum，平台选 iMessage。也可以不装全局命令，用 `npx @photon-ai/cli login`，再 `npx @photon-ai/cli projects create --name "Remoire" --location us-east --spectrum`。建好后从项目设置抄 Project ID 和 Secret，填进本地 iMessage 连接页，加上自己的 +86 手机号，再点开通线路。Secret 不要发到聊天里。免费和 Pro 是共享号码池，不是项目独占的一个号码。

**相关引用：** Photon Stable 文档 `cli/projects`、`cli/authentication`、`spectrum-ts/getting-started`、`api-reference/users/create-user`；本地页 `ImessageSettings`

## 2026-10-09 没发布、也没有真实 Photon，怎么测试 iMessage

**原问：** 那没有发布 也没有真实的photon，我要怎么测试呢

**答案核心：** 分三层。自动测试用假邮差，已经证明收发规则、陌生号码拦截、连发合并、密钥不回显，不需要 Photon，也不用发布。本地网页可以看设置页和主动消息入口，但点「开通线路」不会成功。手机上真的收发，必须先有 Photon 的项目编号和密钥，然后在自己电脑上开后端和小邮差来试，仍然先不发布到正式小窝。

**相关引用：** `backend/tests/test_imessage.py`；设置页 `ImessageSettings`；小邮差 `backend/imessage_bridge/index.mjs`

## 2026-10-09 主动消息时 Connie 能看到哪些上下文、读哪些 prompt

**原问：** AI发主动消息时 他有哪些context以及会读哪些prompt？ 还是我们之前讲的那些固定prompt吗 再加上最近多少条消息吗？

**答案核心：** 大部分和聊天一样，但走旧的整段拼接，没有聊天那套 token 预算。会读身份、表达、thinking、grounding、白天或夜晚回复规则，加上核心记忆原文（不折叠重复）、按最近一句话召回的 5 条记忆、醒来上下文、时间、天气、日记互动；再加 `autonomous.md`，可以发消息时再加 `nudge.md`。不读场景配置，也不读滚动摘要。历史是最近 15 条原文，加上他最近发过的 3 句用于防重复，以及手机 App 记录、设备状态和最近 3 次自主活动。默认用 daily 模型，失败会改用 backend 模型。此前说「主动消息不带核心记忆全文」是错的，代码里是带的。

**相关引用：** `nudge_service.generate_autonomous_activity`；`chat_service._build_system_prompt`、`_collect_system_prompt_parts`、`_build_resume_bundle`

## 2026-10-08 云端 Photon 能带上转账和外卖吗，该接 Remoire 还是另装 Uranus

**原问：** 如果我们走云端 Photon，就可以实现文字、图片、语音、已读、表情回应、撤回、特效、转账、点外卖吗？联通 Remoire 比较好，还是直接安装独立的 Uranus、把 Connie 的人设和记忆喂进去比较好？

**答案核心：** Photon 只负责收发 iMessage。文字、图片、语音、已读、表情回应、撤回、特效，云端线路的管子都带得动，但 Remoire 接上之后还要自己写这些动作。转账是一张看起来像转账的卡片，钱不过账。瑞幸和麦当劳是真的官方点单，要另绑那两家的账号，对方在卡片上贴表情才下单，这是 Uranus 自己接的，不是 Photon 附送的。单独装 Uranus 能马上玩全这些，但记忆只是拷进去一份，之后两边各记各的，Connie 会变成两个人。静儿要的是同一个人，所以应该把 iMessage 接进 Remoire，花哨的卡片以后再加。

**相关引用：** Uranus `docs/实现细节.md` 转账卡片；`server/src/luckin.js`、`server/src/mcd.js`；Remoire `chat_service.stream_chat`

## 2026-10-08 Uranus 怎么把 AI 接进 iMessage，Remoire 能不能共用同一份记忆

**原问：** 研究 https://github.com/nikonotnicotine/Uranus_Imessage ，他是如何做到把 AI 接入 iMessage 的？想让 Remoire 也接进 iMessage，有很多类似功能，并且共享 Remoire 的记忆库。

**答案核心：** 苹果没有公开「让服务器收发 iMessage」的接口。Uranus 用 Photon 的 Spectrum 当邮差：云端模式向 Photon 登记手机号，领一条独立号码，用 gRPC 长连接收消息，再交给自己的模型，回复按符号拆成多条气泡发回。本地 Mac 模式则读本机 `~/Library/Messages/chat.db`，用自己的 Apple ID 发，必须 Mac 一直开着、并授予完全磁盘访问权限。它的记忆是自己文件夹里的另一套，和 Remoire 的 SQLite 记忆库不相通。Remoire 要共用记忆，应把 iMessage 做成现有聊天服务的另一个入口，收到短信后走 `stream_chat`，由它去读同一张 `memories` 表。生产在 Linux VPS 上，本机 Messages 那条路跑不了；要 24 小时在线、角色有自己的号码，走 Photon 云端。Uranus 的许可证禁止把他们的代码改完再分发，Remoire 只学这条链路，不拷他们的源码。

**相关引用：** Uranus `server/src/imessage.js` 的 `startRunner`；`server/src/photon.js`；`docs/Mac部署教程.md`；Remoire `chat_service.stream_chat`、`database.py` 的 `channels` / `memories`

## 2026-10-08 记忆页的分类和权重点击后为什么像没生效

**原问：** 但实际上，现在并没有按照日期分类吧？我如果点击具体的分类，点击时间的话是没有记忆出来的。目前好像这个分类和权重这两个都没有生效呢？（如果点击应该按照时间或权重高低排序的）

**答案核心：** 「日期」是类型筛选，不是按时间排序。库里类型是「日期」的记忆很少，所以点它是空的。右侧按钮会在「按写入时间新到旧」和「按权重从高到低」之间切换，接口是接上的；但多数记忆权重都是 1.0，次序看起来不变。类型筛选还开着时，换排序也不会把空列表变出记忆。

**相关引用：** `frontend/src/components/MemoryPalace.jsx` 的 `LayerDetail`；`memory_service.list_memories`

## 2026-10-08 记忆标签是怎么打的、有什么用

**原问：** 她发现我的每条记忆都有 tag 标签，问应该怎么分类打标签比较好？我们这个记忆是怎么 tag 的？完全就是大模型自己根据语义提取的吧？这些标签打出来有什么用呢？

**答案核心：** 标签不是固定分类表。聊天后的提取模型按提取指令自由写 2–4 个中文关键词，人也可以改。真正的分类是另外两个字段：类型（事实/事件/未完成/日期）和层级（核心/长期/短期/意识）。标签的用途是：页面上给人看；找回时如果用户原话里出现这个词，这条记忆会被字面通道抬上来；写入新记忆时，标签重合会让相关旧记忆更容易连上。建议用短、稳定、她以后真的会说的词，同一件事用同一个词，不要用「重要」「日常」这种太宽的词。

**相关引用：** `backend/app/prompts/tagging.md`；`backend/app/services/memory_service.py` 的 `find_associated` 与 `_keyword_search_score`

## 2026-10-08 为什么 Codex 的 4188 预览能登录，5173 不能

**原问：** 你说登录页本地预览进不去，为什么codex打开的本地预览就能进去？http://127.0.0.1:4188/?preview=capabilities-cache-2

**答案核心：** 4188 是同一个程序同时提供网页和登录接口，所以登录请求打在自己身上，能开门。5173 只开了网页，登录要另找 8000 端口的后端，当时 8000 没开，所以进不去。地址里的 `preview=capabilities-cache-2` 不负责放行。4188 用的是临时数据库 `/tmp/remoire-context-preview.db` 和预览专用暗号，不是生产小窝，也不是本地那份完整记忆库。

**相关引用：** `/private/tmp/remoire_context_preview.py`；`frontend/src/utils/api.js` 的 `getDefaultApiBase()`

## 2026-10-08 原稿 original 全都不读，留着有什么意义

**原问：** 里面有个原稿 original 既然全都不读 放在那里有啥意义啊？

**答案核心：** 它不是给 Connie 读的提示词，是你那份原稿的私有存档。聊天、日记、纸条、主动消息都不注入它，设置页也不显示，接口也拿不到。有用的部分已经写进「身份与关系」和「表达偏好」。原稿留着，只是为了以后你想对照原文时还有一份原件，而且不会被模型拿去说话，也不会进 Git。对现在的聊天没有作用；不想留这份备份，就可以只当存档，不必再管它。

**相关引用：** `prompt_profile_service.py` 的 `PROFILES`；`prompt_profiles.py` 列表会滤掉 `original`；`docs/PROMPT-PROFILES-2026-10-06.md`

## 2026-10-08 核心记忆要不要先总结再进强制层

**原问：** 把最核心的关系记忆升级进强制层。后期核心记忆变多，是否先总结再注入？核心记忆权重都是 100%、不衰减，但有些会重复。怎样处理最合理？

**答案核心：** 不要让模型把核心记忆总结成一段再注入。强制层放去重后的原文，每条权重不变。几乎同一句的，注入时只带更完整的那句，数据库不删不改。同一主题但细节不同的，两条都带。多到放不下时，由静儿确认后自己合并原文，不自动改写。2026-10-08 核对生产库：核心或置顶 40 条，约 1192 tokens；几乎相同的有 2 对，较像但应分别保留的有 12 对。本地 16 条不是完整数据。

**相关引用：** `memory_service.get_core_memories`；`memory_service._validate_digest_plan`（core 与 pinned 受保护，现有整合不会删它们）；`chat_service._build_budgeted_chat_context`

## 2026-10-08 人设 prompt 是聊天模型读的吗

**原问：** OK 那比如说，AI的人设 身份 关系 表达方式之类的prompt，是和我们聊天的那个模型去读的对吧？

**答案核心：** 对。身份、关系、表达方式写进发给聊天模型的系统提示，聊天模型按这些话生成回复。向量模型不读人设，只把句子变成数字。日记、主动消息、纸条也读同一份身份和表达；场景写作只给聊天。抽记忆、打标签用的是另一套内部规则，不是人设正文。

**相关引用：** `backend/app/services/chat_service.py` 的 `_collect_system_prompt_parts`；`backend/app/services/prompt_profile_service.py`

## 2026-10-08 向量模型的作用是什么

**原问：** 她今天问我，向量模型的作用是什么，我要咋回答呢

**答案核心：** 向量模型不负责聊天。它把一句话变成一串代表意思的数字（Embedding / 语义指纹），让记忆系统能按“意思像不像”找回旧记忆。关键词负责字面，向量负责换说法。Maggie 现在做主动消息还不需要单独买向量数据库；等做“按意思想起”时，接一个 Embedding API、把数字存在现有数据库里就够。

**相关引用：** `教程文档/记忆系统架构与AI搭建指南.md` 第 6 节；`教程文档/maggie/给Maggie 的搭建指南 1-产品蓝图+主动消息.md`（不要无理由引入向量数据库）
