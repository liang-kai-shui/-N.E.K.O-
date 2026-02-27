import asyncio
import json
import websockets
from datetime import datetime
from bilibili_api import live, Credential

# 音频播放支持
try:
    import pyaudio
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False
    print("⚠️ 未安装 pyaudio，语音播放功能将禁用。如需播放，请安装：pip install pyaudio")

# ========== 配置区==========
ROOM_ID = 0                 # 你的B站直播间ID（必要）
ROLE_NAME = "小天"                   # 你的N.E.K.O.角色名
WS_URL = f"ws://localhost:48911/ws/{ROLE_NAME}"

SESSDATA = "前往浏览器开发者页面面获取SESSDATA，确保登录状态有效" #非必须
BILI_JCT = "前往浏览器开发者页面面获取bili_jct，确保登录状态有效" #非必须
BUVID3 = "前往浏览器开发者页面面获取BUVID3，确保登录状态有效" #非必须
# ================以下就不要动了====================

class AudioPlayer:
    """独立音频播放器，支持重置以彻底清除旧语音"""
    def __init__(self):
        self.queue = asyncio.Queue()
        self.current_speech_id = None
        self._task = None
        self._p = None
        self._stream = None
        if HAS_AUDIO:
            try:
                self._p = pyaudio.PyAudio()
                self._stream = self._p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=48000,
                    output=True,
                    frames_per_buffer=2048
                )
                print("✅ 音频播放器已初始化")
            except Exception as e:
                print(f"⚠️ 音频初始化失败: {e}")

    def start(self):
        """启动播放任务"""
        if self._stream and self._task is None:
            self._task = asyncio.create_task(self._player())

    async def _player(self):
        """后台播放协程"""
        try:
            while True:
                speech_id, audio_data = await self.queue.get()
                if speech_id is None:  # 停止信号
                    break
                if speech_id == self.current_speech_id and self._stream:
                    try:
                        self._stream.write(audio_data)
                    except Exception as e:
                        print(f"🔊 音频播放出错: {e}")
        except asyncio.CancelledError:
            pass

    def reset(self):
        """重置播放器：停止当前播放，清空队列，重新打开流"""
        # 取消播放任务
        if self._task:
            self._task.cancel()
            self._task = None
        # 关闭旧流
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except:
                pass
            self._stream = None
        # 清空队列
        self.clear()
        # 重新打开流
        if self._p:
            try:
                self._stream = self._p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=48000,
                    output=True,
                    frames_per_buffer=2048
                )
            except Exception as e:
                print(f"音频流重置失败: {e}")
        # 重新启动播放任务
        self.start()
        self.current_speech_id = None

    def set_current_speech(self, speech_id):
        self.current_speech_id = speech_id

    def put(self, speech_id, audio_data):
        if self._stream:
            self.queue.put_nowait((speech_id, audio_data))

    def clear(self):
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def stop(self):
        if self._task:
            self.queue.put_nowait((None, b''))
            self._task.cancel()
            self._task = None
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._p:
            self._p.terminate()

class BilibiliLiveAI:
    def __init__(self):
        self.websocket = None
        self.session_ready = asyncio.Event()
        self.pending_reply = asyncio.Queue()
        self.receiver_task = None
        self.ping_task = None
        self.danmaku_queue = asyncio.Queue()
        self.processing_task = None
        self.audio_player = AudioPlayer()
        self.current_speech_id = None
        self.song_keywords = ["点歌"]
        self.max_delay = 30.0  # 弹幕最大允许延迟（秒）

    async def connect_llm(self):
        """建立与N.E.K.O.的WebSocket连接"""
        await self.disconnect_llm()
        try:
            self.websocket = await websockets.connect(WS_URL)
            print("✅ 已连接到本地LLM服务")

            await self.websocket.send(json.dumps({
                "action": "start_session",
                "input_type": "text",
                "new_session": True
            }))
            print("📤 [LLM] 发送 start_session")

            self.session_ready.clear()
            self.receiver_task = asyncio.create_task(self.receive_llm_messages())
            self.ping_task = asyncio.create_task(self.send_ping())

            try:
                await asyncio.wait_for(self.session_ready.wait(), timeout=60)
                print("✅ LLM会话已就绪")
                return True
            except asyncio.TimeoutError:
                print("❌ LLM会话启动超时")
                await self.disconnect_llm()
                return False
        except Exception as e:
            print(f"❌ 连接LLM失败: {e}")
            return False

    async def disconnect_llm(self):
        """关闭LLM连接并清理任务"""
        if self.receiver_task:
            self.receiver_task.cancel()
            self.receiver_task = None
        if self.ping_task:
            self.ping_task.cancel()
            self.ping_task = None
        if self.websocket:
            try:
                await self.websocket.send(json.dumps({"action": "end_session"}))
            except:
                pass
            await self.websocket.close()
            self.websocket = None

    async def receive_llm_messages(self):
        """处理所有来自LLM的消息"""
        try:
            async for message in self.websocket:
                if isinstance(message, bytes):
                    if self.current_speech_id:
                        self.audio_player.put(self.current_speech_id, message)
                    continue

                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")
                timestamp = datetime.now().strftime("%H:%M:%S")

                if msg_type == "gemini_response":
                    text = data.get("text", "")
                    if text:
                        await self.pending_reply.put(("text", text))
                elif msg_type == "system" and data.get("data") == "turn end":
                    await self.pending_reply.put(("end", None))
                elif msg_type == "session_started":
                    self.session_ready.set()
                elif msg_type == "audio_chunk":
                    self.current_speech_id = data.get("speech_id")
                    self.audio_player.set_current_speech(self.current_speech_id)
        except asyncio.CancelledError:
            pass
        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            print(f"❌ 接收LLM消息出错: {e}")

    async def send_ping(self):
        try:
            while True:
                await asyncio.sleep(30)
                if self.websocket:
                    try:
                        await self.websocket.send(json.dumps({"action": "ping"}))
                    except:
                        break
        except asyncio.CancelledError:
            pass

    async def ask_llm(self, prompt: str) -> str:
        for attempt in range(2):
            try:
                if self.websocket is None:
                    await self.connect_llm()
                while not self.pending_reply.empty():
                    self.pending_reply.get_nowait()
                await self.websocket.send(json.dumps({
                    "action": "stream_data",
                    "input_type": "text",
                    "data": prompt
                }))
                while not self.pending_reply.empty():
                    self.pending_reply.get_nowait()
                break
            except (websockets.ConnectionClosed, AttributeError) as e:
                print(f"🔄 检测到连接已断开，正在重连 ({attempt+1}/2)...")
                await self.disconnect_llm()
                if attempt == 0:
                    continue
                else:
                    return "（无法连接到LLM服务）"
            except Exception as e:
                print(f"发送消息异常: {e}")
                return "（发送消息失败）"
        # 后续收集回复代码不变...

        # 收集回复，最多等待15秒
        reply_parts = []
        last_text = None
        try:
            while True:
                item = await asyncio.wait_for(self.pending_reply.get(), timeout=15)
                if item[0] == "text":
                    text = item[1]
                    if text != last_text:
                        reply_parts.append(text)
                        last_text = text
                elif item[0] == "end":
                    break
        except asyncio.TimeoutError:
            reply_parts.append("（回复超时）")
        return "".join(reply_parts)

    async def _process_danmaku(self):
        """后台任务：顺序处理弹幕队列（带来源标记和过时过滤）"""
        self.audio_player.start()
        while True:
            # 从队列取出消息，包含时间戳
            content, user_name, msg_type, timestamp = await self.danmaku_queue.get()
            now = asyncio.get_running_loop().time()
            # 检查是否过时
            if now - timestamp > self.max_delay:
                source = "弹幕" if msg_type == "danmaku" else "入场"
                print(f"⏭️ [忽略] 过时的{source}消息: [{user_name}]: {content} (延迟 {now-timestamp:.1f}s)")
                continue

            source = "弹幕" if msg_type == "danmaku" else "入场"
            print(f"\n[{source}] [{user_name}]: {content}")

            # 重置音频播放器，彻底清除上一段语音
            self.audio_player.reset()
            self.current_speech_id = None

            # 构造发送给LLM的文本
            if msg_type == "danmaku":
                formatted_prompt = f"{user_name}：{content}"
            else:  # 入场
                formatted_prompt = f"{user_name} 进入直播间"

            reply = await self.ask_llm(formatted_prompt)
            print(f"🤖 [AI {ROLE_NAME}]: {reply}")

    async def run_bilibili_listener(self):
        """运行B站弹幕监听"""
        credential = Credential(
            sessdata=SESSDATA,
            bili_jct=BILI_JCT,
            buvid3=BUVID3
        )
        print("🔑 使用B站登录凭证，将显示真实用户名")

        room = live.LiveDanmaku(ROOM_ID, credential=credential)

        @room.on('DANMU_MSG')
        async def on_danmaku(event):
            content = event['data']['info'][1]
            user_name = event['data']['info'][2][1]
            # 点歌过滤
            if any(keyword in content for keyword in self.song_keywords):
                print(f"🎵 [过滤] 点歌消息: [{user_name}]: {content}")
                return
            # 获取当前时间戳（单调时间）
            timestamp = asyncio.get_running_loop().time()
            await self.danmaku_queue.put((content, user_name, "danmaku", timestamp))

        @room.on('INTERACT_WORD')
        async def on_interact_word(event):
            try:
                data = event['data']['data']
                user_name = data.get('uname', '未知用户')
                interact_type = data.get('msg_type', 0)
                if interact_type == 1:  # 进入直播间
                    print(f"👋 检测到 [{user_name}] 进入直播间")
                    timestamp = asyncio.get_running_loop().time()
                    await self.danmaku_queue.put(("进入直播间", user_name, "enter", timestamp))
            except Exception as e:
                print(f"处理入场消息出错: {e}")

        self.processing_task = asyncio.create_task(self._process_danmaku())
        print(f"🎥 开始监听直播间 {ROOM_ID} ...")
        await room.connect()

async def main():
    ai = BilibiliLiveAI()
    try:
        if not await ai.connect_llm():
            print("无法连接到LLM服务，请检查服务是否运行。")
            return
        await ai.run_bilibili_listener()
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断")
    finally:
        await ai.disconnect_llm()
        if ai.processing_task:
            ai.processing_task.cancel()
        ai.audio_player.stop()

if __name__ == "__main__":

    asyncio.run(main())
