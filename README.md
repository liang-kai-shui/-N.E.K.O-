📦 项目快速介绍：B站直播AI互动系统
🎯 项目目标
将B站直播间弹幕实时接入本地大语言模型（N.E.K.O.），获取AI文本回复并播放对应语音，同时支持观众入场通知、点歌过滤、弹幕过时丢弃等功能。

🏗️ 技术栈
Python 3.11+ + asyncio

B站接口：bilibili-api-python（获取弹幕、入场事件）

AI服务：WebSocket 连接本地 N.E.K.O. 服务（ws://localhost:48911/ws/ATLS）

音频播放：pyaudio（实时播放语音）

异步队列：asyncio.Queue（缓冲弹幕、音频数据）

🧩 模块结构（树形图）
text
BilibiliLiveAI 项目
├── 配置区（硬编码）
│   ├── ROOM_ID         # B站直播间号
│   ├── ROLE_NAME       # AI角色名（ATLS）
│   ├── WS_URL          # WebSocket地址
│   ├── SESSDATA        # B站登录凭证
│   ├── BILI_JCT
│   └── BUVID3
│
├── AudioPlayer 类
│   ├── 功能：独立播放音频，支持按speech_id过滤、重置流彻底清除旧语音
│   ├── 核心：后台任务 _player() 从队列消费 (speech_id, audio_data)
│   └── 方法：start/reset/put/set_current_speech/clear/stop
│
└── BilibiliLiveAI 类
    ├── __init__()
    │   ├── websocket, session_ready, pending_reply, danmaku_queue
    │   ├── receiver_task, ping_task, processing_task
    │   ├── audio_player, current_speech_id
    │   ├── song_keywords (点歌过滤)
    │   └── max_delay (弹幕过时阈值，默认30秒)
    │
    ├── 连接管理
    │   ├── connect_llm()       # 建立WebSocket、发送start_session、等待就绪
    │   ├── disconnect_llm()    # 关闭连接、取消任务
    │   ├── send_ping()         # 每30秒发送心跳
    │   └── receive_llm_messages()  # 接收AI消息（文本/音频/状态）
    │
    ├── 业务逻辑
    │   ├── ask_llm(prompt)     # 发送弹幕文本给AI，收集回复（自动重连）
    │   ├── _process_danmaku()  # 弹幕处理协程：从队列取消息，过时检查，重置音频，调用ask_llm，打印回复
    │   └── run_bilibili_listener()  # 启动B站监听，注册DANMU_MSG和INTERACT_WORD回调，将消息放入队列（附带时间戳）
    │
    └── main()                  # 创建实例，连接AI，运行监听
🔄 核心数据流
B站事件 → 入队（带时间戳）

弹幕（DANMU_MSG）：经点歌过滤后，放入 danmaku_queue，格式 (content, user_name, "danmaku", timestamp)

入场（INTERACT_WORD）：msg_type=1 时，放入 ( "进入直播间", user_name, "enter", timestamp )

弹幕处理（单线程顺序）

_process_danmaku 从队列取出消息

计算延迟，若 now - timestamp > max_delay 则忽略并打印

否则：重置 AudioPlayer（停止旧语音）、清空 pending_reply、构造 formatted_prompt

调用 ask_llm(prompt)

与AI交互

ask_llm 发送消息，处理连接异常（自动重连一次）

等待 pending_reply 中的文本块和 "end" 标志

返回拼接后的完整回复

AI响应处理（receive_llm_messages）

文本块（gemini_response） → 放入 pending_reply

语音块（audio_chunk 通知 + 二进制数据） → 放入 AudioPlayer 队列，附带 speech_id

会话结束（system 中 turn end） → 放入 ("end", None) 到 pending_reply

音频播放

AudioPlayer._player 从队列取 (speech_id, data)

仅当 speech_id == current_speech_id 时才播放，确保同一语音连贯

重置时取消任务、重新打开流，彻底丢弃旧语音

⚙️ 配置参数
参数	值	说明
ROOM_ID	1726390320	B站直播间号
ROLE_NAME	"ATLS"	N.E.K.O.角色名
WS_URL	ws://localhost:48911/ws/ATLS	AI服务地址
SESSDATA	（长字符串）	B站登录凭证，用于获取真实用户名
BILI_JCT	（32位hex）	B站CSRF token
BUVID3	（带infoc）	设备标识
song_keywords	["点歌"]	过滤包含这些词的弹幕
max_delay	30.0 秒	弹幕入队后超过此时间则忽略
🧪 外部依赖
Python库：bilibili-api-python, websockets, pyaudio, aiohttp

本地服务：N.E.K.O. 主服务器（端口48911） + 记忆服务器（端口48912）必须运行

🔍 已知问题（供其他程序员排查）
连接频繁断开：服务端每次回复后主动关闭连接（code 1000），客户端已实现自动重连，但日志会打印“检测到连接已断开”。

音频偶尔重复/叠加：已通过 AudioPlayer.reset() 重置流缓解，但高并发下可能仍有残留。

回复超时：ask_llm 等待回复超时15秒，若AI响应慢会出现。

文本片段去重：简单对比 last_text 可过滤连续相同片段，但服务端可能重复发送不同内容。

点歌过滤：目前仅关键词匹配，可扩展为正则。

弹幕过时忽略：依赖队列时间戳，避免处理堆积的旧弹幕。

🚀 如何运行
安装依赖：pip install bilibili-api-python websockets pyaudio aiohttp

启动 N.E.K.O. 服务（主+记忆服务器）

修改配置区（如需）

执行脚本：python your_script.py
