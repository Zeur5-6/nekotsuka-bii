"""
Live2Dデスクトップアプリ用WebSocketサーバー
PythonバックエンドとElectronアプリを連携する

重要: LLM生成・Gemini分析などの重い同期処理は必ず run_in_executor で
別スレッドに逃がすこと。イベントループ上で直接呼ぶと、生成が終わるまで
WebSocketのping/pongや音声ワーカーまで全部止まる。
"""
import asyncio
import json

import websockets

from bii_core import BiiCore
from config import LIVE2D_WS_HOST, LIVE2D_WS_PORT, get_logger
from lipsync_utils import build_viseme_sequence
from voicevox_adapter import VoicevoxAdapter
from vts_adapter import VTSAdapter

log = get_logger("Live2DServer")


class Live2DServer:
    """Live2Dアプリ用WebSocketサーバー"""

    def __init__(self):
        self.bii = None
        self.voice = None
        self.vts = None
        self.clients = set()
        self.vts_connected = False
        self.audio_queue = asyncio.Queue()

    async def init_components(self):
        """コンポーネントを初期化"""
        try:
            loop = asyncio.get_running_loop()
            # BiiCore の初期化は埋め込みモデルの読み込みで重いので executor で
            self.bii = await loop.run_in_executor(None, BiiCore)
            self.voice = await loop.run_in_executor(None, VoicevoxAdapter)
            self.vts = VTSAdapter()
            log.info("初期化完了")
            asyncio.create_task(self._audio_worker())
        except Exception as e:
            log.error(f"初期化エラー: {e}")

    # ------------------------------------------------------------------
    # 音声再生キュー
    # ------------------------------------------------------------------

    async def _audio_worker(self):
        """音声再生キューを処理するワーカー"""
        log.info("音声再生ワーカー起動")
        loop = asyncio.get_running_loop()
        while True:
            try:
                item = await self.audio_queue.get()
                if isinstance(item, tuple):
                    display_text, voice_text = item
                else:
                    display_text = voice_text = item

                if voice_text:
                    log.info(f"音声再生開始: {display_text[:20]}...")
                    await loop.run_in_executor(
                        None, self._play_voice_with_lipsync,
                        display_text, voice_text, loop)
                    await asyncio.sleep(0.3)

                self.audio_queue.task_done()
            except Exception as e:
                log.error(f"音声ワーカーエラー: {e}")
                await asyncio.sleep(1)

    def _play_voice_with_lipsync(self, display_text, voice_text, loop):
        """音声合成を実行し、字幕・リップシンクデータを送信して再生する
        （executor スレッドで実行される）"""
        if not self.voice or not self.voice.enabled:
            return
        try:
            result = self.voice.synthesize(voice_text)
            if result is None:
                return
            query, wav_bytes = result

            # 合成完了・再生直前に字幕を表示する
            asyncio.run_coroutine_threadsafe(
                self.send_response(display_text), loop)

            # VOICEVOXの音素情報からリップシンクを送信
            sequence = build_viseme_sequence(query, fps=60)
            if sequence:
                asyncio.run_coroutine_threadsafe(
                    self._send_viseme_sequence(sequence, fps=60), loop)

            # 再生完了までブロック（executorスレッドなのでループは止まらない）
            self.voice.play_wav(wav_bytes, blocking=True)
            log.info("再生処理終了")
        except Exception as e:
            log.error(f"音声合成エラー: {e}")

    async def _send_viseme_sequence(self, sequence, fps: int = 60):
        if not sequence:
            return
        frame_time = 1.0 / fps
        for open_val, form_val in sequence:
            await self.broadcast({"type": "lipsync", "value": float(open_val)})
            await self.broadcast({"type": "mouth_form", "value": float(form_val)})
            await asyncio.sleep(frame_time)

    # ------------------------------------------------------------------
    # VTS
    # ------------------------------------------------------------------

    async def connect_vts(self):
        """VTSに接続"""
        if not self.vts:
            return False
        try:
            connected = await self.vts.connect()
            if connected:
                vts_expressions = await self.vts.get_expressions()
                if vts_expressions:
                    self.bii.update_expressions_from_vts(vts_expressions)
                self.vts_connected = True
                await self.broadcast({"type": "status", "status": "VTS接続完了"})
                return True
        except Exception as e:
            log.error(f"VTS接続エラー: {e}")
        return False

    # ------------------------------------------------------------------
    # クライアント処理
    # ------------------------------------------------------------------

    async def handle_client(self, websocket):
        """クライアント接続を処理"""
        self.clients.add(websocket)
        remote_addr = getattr(websocket, 'remote_address', 'unknown')
        log.info(f"クライアント接続: {remote_addr}")

        try:
            await websocket.send(json.dumps({"type": "status", "status": "接続完了"}))
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(websocket, data)
                except json.JSONDecodeError:
                    log.warning(f"不正なJSON: {message}")
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            log.error(f"接続エラー: {e}")
        finally:
            self.clients.discard(websocket)
            log.info(f"クライアント切断: {remote_addr}")

    async def handle_message(self, websocket, data):
        """メッセージを処理"""
        msg_type = data.get("type")

        if msg_type == "user_input":
            await self.process_user_input(data.get("text", ""))
        elif msg_type == "speak":
            text = data.get("text", "")
            if text and self.voice:
                await self.audio_queue.put((text, text))
        elif msg_type == "connect_vts":
            await self.connect_vts()
        elif msg_type == "vision_request":
            await self.process_vision_request(data.get("text", ""))
        elif msg_type == "ping":
            await websocket.send(json.dumps({"type": "pong"}))

    async def process_vision_request(self, user_text_input=""):
        """視覚リクエストを処理"""
        if not self.bii:
            return
        try:
            log.info(f"視覚リクエスト受信 (入力: {user_text_input})")
            await self.broadcast({"type": "status", "status": "画面を見ています..."})
            loop = asyncio.get_running_loop()

            # 1. 画面キャプチャ（速いので executor 不要）
            img_base64, window_title = self.bii.vision.capture_screen(save_debug=True)
            log.info(f"キャプチャ完了: {window_title}")

            # 2. キャプチャ完了直後にウィンドウ復帰信号を送る
            await self.broadcast({"type": "restore"})

            # 3. Gemini分析 + 応答生成は重いので executor で実行
            response = await loop.run_in_executor(
                None,
                lambda: self.bii.observe_screen(
                    img_base64, window_title=window_title,
                    user_input=user_text_input))

            if response:
                emotion_tag = self.bii.extract_emotion_tag(response)
                if emotion_tag:
                    await self.send_emotion(emotion_tag)

                if self.voice:
                    clean_text = self.bii.clean_text_for_voice(response)
                    if clean_text:
                        await self.audio_queue.put((response, clean_text))
                    else:
                        await self.send_response(response)
                else:
                    await self.send_response(response)
            else:
                await self.broadcast({"type": "status",
                                      "status": "何も見えませんでした"})
        except Exception as e:
            log.error(f"視覚処理エラー: {e}")
            await self.broadcast({"type": "status", "status": f"エラー: {e}"})

    async def process_user_input(self, user_text):
        """ユーザー入力を処理"""
        if not self.bii:
            return
        try:
            loop = asyncio.get_running_loop()

            # コマンド処理（/vision などは重いので executor で）
            parsed = BiiCore.parse_command(user_text)
            if parsed:
                command, args = parsed
                result = await loop.run_in_executor(
                    None, self.bii.handle_command, command, args)
                if result:
                    await self.send_response(result)
                    return

            # 通常の対話（LLM生成は重いので executor で）
            response = await loop.run_in_executor(
                None, lambda: self.bii.generate_response(user_text=user_text))

            emotion_tag = self.bii.extract_emotion_tag(response)
            if emotion_tag:
                await self.send_emotion(emotion_tag)

            if self.voice:
                clean_text = self.bii.clean_text_for_voice(response)
                if clean_text:
                    # 字幕は音声合成完了直前に _play_voice_with_lipsync が送る
                    await self.audio_queue.put((response, clean_text))
                else:
                    await self.send_response(response)
            else:
                await self.send_response(response)
        except Exception as e:
            log.error(f"処理エラー: {e}")
            await self.broadcast({"type": "status", "status": f"エラー: {e}"})

    # ------------------------------------------------------------------
    # 送信
    # ------------------------------------------------------------------

    async def send_emotion(self, emotion):
        await self.broadcast({"type": "expression", "name": emotion})

    async def send_response(self, response):
        await self.broadcast({"type": "response", "text": response})

    async def broadcast(self, message):
        """すべてのクライアントにメッセージを送信"""
        if self.clients:
            message_str = json.dumps(message, separators=(",", ":"))
            disconnected = set()
            for client in self.clients:
                try:
                    await client.send(message_str)
                except websockets.exceptions.ConnectionClosed:
                    disconnected.add(client)
            self.clients -= disconnected

    # ------------------------------------------------------------------
    # 起動
    # ------------------------------------------------------------------

    async def run(self, host=None, port=None):
        """サーバーを起動"""
        host = host or LIVE2D_WS_HOST
        port = port or LIVE2D_WS_PORT
        await self.init_components()
        log.info(f"WebSocketサーバーを起動: ws://{host}:{port}")
        async with websockets.serve(self.handle_client, host, port):
            await asyncio.Future()  # 永続的に実行


if __name__ == "__main__":
    server = Live2DServer()
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print("\n[Live2DServer] サーバーを終了します")
