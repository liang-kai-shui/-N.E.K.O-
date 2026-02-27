Bilibili Live AI Assistant 🎤🤖

将B站直播间弹幕实时接入本地大语言模型（N.E.K.O.），实现智能对话、语音回复、观众入场通知等功能的异步Python应用。

✨ 功能特性

· 实时弹幕监听：通过 bilibili-api-python 获取直播间弹幕和入场事件。
· 本地LLM集成：WebSocket连接本地N.E.K.O.服务，支持流式文本回复和语音生成。
· 语音播放：使用 pyaudio 实时播放AI返回的语音（48kHz PCM），每条弹幕独立，自动清除旧语音。
· 入场通知：观众进入直播间时，自动向AI发送 用户名 进入直播间 消息（可配置是否启用）。
· 点歌过滤：自定义关键词（如“点歌”）过滤弹幕，避免干扰AI。
· 弹幕过时丢弃：每条弹幕入队时附带时间戳，处理时若延迟超过阈值（默认30秒）则忽略，防止高并发时堆积。
· 自动重连：AI服务端每次回复后可能主动断开连接，客户端自动重连并恢复会话。
· 用户名透传：弹幕内容以 用户名：消息 格式发送给AI，使模型知道发言者。

🛠️ 技术栈

· Python 3.11+
· asyncio – 异步I/O
· bilibili-api-python – B站接口
· websockets – WebSocket客户端
· pyaudio – 音频播放
· aiohttp – HTTP客户端（bilibili-api依赖）
· N.E.K.O. – 本地LLM服务（需预先安装并运行）

📦 安装与配置

1. 克隆仓库

```bash
git clone https://github.com/yourname/bilibili-live-ai.git
cd bilibili-live-ai
```

2. 安装Python依赖

建议使用虚拟环境：

```bash
pip install bilibili-api-python websockets pyaudio aiohttp
```

3. 安装并启动N.E.K.O.服务

本项目依赖 N.E.K.O. 本地LLM服务。请参考其文档安装并启动：

· 记忆服务器（端口48912）
· 主服务器（端口48911）

确保角色（如 ATLS）已正确配置并可用。

4. 配置B站登录凭证（可选，用于获取真实用户名）

在脚本中硬编码了 SESSDATA、bili_jct、buvid3。强烈建议改为环境变量，避免隐私泄露：

```python
import os
SESSDATA = os.getenv("BILI_SESSDATA")
BILI_JCT = os.getenv("BILI_BILI_JCT")
BUVID3 = os.getenv("BILI_BUVID3")
```

然后在运行前设置环境变量：

```bash
# Windows PowerShell
$env:BILI_SESSDATA="你的值"
$env:BILI_BILI_JCT="你的值"
$env:BILI_BUVID3="你的值"
```

若不提供凭证，用户名将显示为打码状态（如 _***）。

5. 修改配置

编辑脚本开头的配置区：

· ROOM_ID – 你的B站直播间ID
· ROLE_NAME – N.E.K.O.角色名（必须与URL中的一致）
· WS_URL – WebSocket地址（默认 ws://localhost:48911/ws/角色名）
· song_keywords – 点歌过滤关键词列表
· max_delay – 弹幕过时阈值（秒）

🚀 使用方法

运行主脚本：

```bash
python bilibili_live_ai.py
```

控制台将输出：

· 音频播放器初始化状态
· LLM连接成功/失败信息
· B站直播间连接日志
· 弹幕和入场消息（带来源标记）
· AI文本回复
· 过时弹幕忽略提示等

AI的语音回复将通过扬声器实时播放。

测试独立WebSocket连接

如需单独测试N.E.K.O.服务，可使用提供的调试脚本（参考历史对话）。

⚙️ 配置参数说明

变量 默认值 说明
ROOM_ID 1726390320 B站直播间数字ID
ROLE_NAME "ATLS" N.E.K.O.角色标识符
WS_URL ws://localhost:48911/ws/ATLS WebSocket连接地址
SESSDATA （硬编码） B站登录态凭证，用于获取真实用户名
BILI_JCT （硬编码） CSRF Token
BUVID3 （硬编码） 设备标识
song_keywords ["点歌"] 包含这些关键词的弹幕将被过滤
max_delay 30.0 弹幕入队后超过此秒数则忽略（防堆积）

🔍 已知问题与注意事项

1. 连接频繁断开：N.E.K.O.服务端可能在每次回复后主动关闭WebSocket（code 1000）。客户端已实现自动重连，日志中的“检测到连接已断开”属于正常现象，不影响功能。
2. 音频偶尔叠加/残留：已通过 AudioPlayer.reset() 强制重置音频流，高并发下若仍有问题，可尝试调整 frames_per_buffer 或使用更可靠的音频队列。
3. 回复超时：ask_llm 等待回复超时默认为15秒，若AI响应较慢可增加 timeout。
4. 文本去重：简单去重机制（忽略连续相同片段）可能误删有效内容，可根据实际情况调整。
5. 点歌过滤：关键词匹配较简单，可扩展为正则表达式或更复杂的命令解析。
6. 安全提醒：代码中的B站凭证为硬编码，上传至GitHub前务必替换为环境变量读取，避免泄露。

📄 许可证

MIT

🤝 贡献

欢迎提交Issue或Pull Request。如果你有更好的优化建议，请随时联系。

---

项目状态：持续优化中。感谢 N.E.K.O. 提供的强大本地LLM服务。
