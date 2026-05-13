"""
Live2Dデスクトップアプリ用WebSocketサーバー
PythonバックエンドとElectronアプリを連携
"""

import asyncio
import websockets
import json
import numpy as np
from bii_core import BiiCore
from voicevox_adapter import VoicevoxAdapter
from vts_adapter import VTSAdapter

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
            self.bii = BiiCore()
            self.voice = VoicevoxAdapter()
            self.vts = VTSAdapter()
            print("[Live2DServer] ✓ 初期化完了")
            # 音声再生ワーカースタート
            asyncio.create_task(self._audio_worker())
        except Exception as e:
            print(f"[Live2DServer] ✗ 初期化エラー: {e}")

    async def _audio_worker(self):
        """音声再生キューを処理するワーカー"""
        print("[Live2DServer] 音声再生ワーカー起動")
        while True:
            try:
                # キューからデータを取得（なければ待機）
                item = await self.audio_queue.get()
                
                # タプル(display_text, voice_text)か、単一文字列かを判定
                if isinstance(item, tuple):
                    display_text, voice_text = item
                else:
                    display_text = item
                    voice_text = item
                
                if voice_text:
                    print(f"[Live2DServer] 音声再生開始: {display_text[:20]}...")
                    # 音声合成と再生を実行（完了するまで待機）
                    loop = asyncio.get_event_loop()
                    # display_textも渡して、再生直前に表示させる
                    await loop.run_in_executor(None, self._play_voice_with_lipsync, display_text, voice_text, loop)
                    print(f"[Live2DServer] 音声再生完了処理")
                    
                    # 少し待機
                    await asyncio.sleep(0.3)
                
                # タスク完了を通知
                self.audio_queue.task_done()
            except Exception as e:
                print(f"[Live2DServer] 音声ワーカーエラー: {e}")
                await asyncio.sleep(1)

    def _play_voice_with_lipsync(self, display_text, voice_text, loop):
        """音声合成を実行し、リップシンクデータを送信"""
        if not self.voice or not self.voice.enabled:
            return
        
        try:
            import requests
            import io
            import pygame
            import time
            
            # 音声クエリの作成
            from urllib.parse import quote
            res1 = requests.post(
                f"{self.voice.voicevox_url}/audio_query?speaker={self.voice.speaker_id}&text={quote(voice_text)}",
                timeout=10
            )
            res1.raise_for_status()
            query = res1.json()

            # 音声データの生成（WAVバイナリ）
            res2 = requests.post(
                f"{self.voice.voicevox_url}/synthesis?speaker={self.voice.speaker_id}",
                json=query,
                timeout=60
            )
            res2.raise_for_status()

            # ここで字幕（応答テキスト）を送信！
            # 音声合成が終わって、再生する直前に表示する
            asyncio.run_coroutine_threadsafe(
                self.send_response(display_text), loop
            )

            # VOICEVOXの音素情報からリップシンクを送信
            sequence = self._build_viseme_sequence(query, fps=60)
            if sequence:
                asyncio.run_coroutine_threadsafe(
                    self._send_viseme_sequence(sequence, fps=60), loop
                )
            
            # 通常のスピーカーに再生
            sound_data = io.BytesIO(res2.content)
            pygame.mixer.music.load(sound_data)
            pygame.mixer.music.play()
            
            # 再生が終わるまで待機（タイムアウト付き）
            start_time = time.time()
            max_duration = 30  # 最大30秒待機
            
            while pygame.mixer.music.get_busy():
                if time.time() - start_time > max_duration:
                    print("[Live2DServer] 警告: 音声再生がタイムアウトしました。強制終了します。")
                    pygame.mixer.music.stop()
                    break
                pygame.time.Clock().tick(10)
            
            # 念のためストップ
            pygame.mixer.music.stop()
            pygame.mixer.music.unload() # メモリ解放
            
            print(f"[Live2DServer] ✓ 再生処理終了")
            
        except Exception as e:
            print(f"[Live2DServer] 音声合成エラー: {e}")
            import traceback
            traceback.print_exc()

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
                await self.broadcast({
                    "type": "status",
                    "status": "VTS接続完了"
                })
                return True
        except Exception as e:
            print(f"[Live2DServer] VTS接続エラー: {e}")
        return False
    
    async def handle_client(self, websocket):
        """クライアント接続を処理"""
        self.clients.add(websocket)
        # websockets 15.0では、ServerConnectionからリモートアドレスを取得
        remote_addr = getattr(websocket, 'remote_address', 'unknown')
        path = getattr(websocket, 'path', '/')
        print(f"[Live2DServer] クライアント接続: {remote_addr} (path: {path})")
        
        try:
            # 接続確認メッセージを送信
            await websocket.send(json.dumps({
                "type": "status",
                "status": "接続完了"
            }))
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(websocket, data)
                except json.JSONDecodeError:
                    print(f"[Live2DServer] 不正なJSON: {message}")
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            print(f"[Live2DServer] 接続エラー: {e}")
        finally:
            self.clients.discard(websocket)
            print(f"[Live2DServer] クライアント切断: {remote_addr}")
    
    async def handle_message(self, websocket, data):
        """メッセージを処理"""
        msg_type = data.get("type")
        
        if msg_type == "user_input":
            # ユーザー入力（音声認識などから）
            user_text = data.get("text", "")
            await self.process_user_input(user_text)
        elif msg_type == "speak":
            # 外部から指定されたテキストを音声合成（リップシンク込み）
            text = data.get("text", "")
            if text and self.voice:
                # キューに追加 (表示テキスト, 音声テキスト)
                await self.audio_queue.put((text, text))
        elif msg_type == "connect_vts":
            # VTS接続リクエスト
            await self.connect_vts()
        elif msg_type == "vision_request":
            # 視覚リクエスト
            # テキスト入力がある場合はそれも渡す
            text = data.get("text", "")
            await self.process_vision_request(text)
        elif msg_type == "ping":
            # 接続確認
            await websocket.send(json.dumps({"type": "pong"}))
    
    async def process_vision_request(self, user_text_input=""):
        """視覚リクエストを処理"""
        if not self.bii:
            return
            
        try:
            print(f"[Live2DServer] 視覚リクエスト受信: 処理を開始します (入力: {user_text_input})")
            await self.broadcast({"type": "status", "status": "画面を見ています..."})
            
            # 1. まず画面キャプチャだけ実行 (Direct access to vision module)
            print("[Live2DServer] 画面キャプチャを実行中...")
            # handle_command("vision") だと完了するまで戻ってこないので、
            # 直接 vision.capture_screen と observe_screen を分けて呼ぶ
            if hasattr(self.bii, 'vision'):
                img_base64, window_title = self.bii.vision.capture_screen(scale=0.7, save_debug=True)
                print(f"[Live2DServer] キャプチャ完了: {window_title}")
                
                 # 2. キャプチャ完了直後にウィンドウ復帰信号を送る！
                await self.broadcast({"type": "restore"})
                print("[Live2DServer] ウィンドウ復帰信号を送信しました")
                
                # 3. その後にゆっくり分析
                print("[Live2DServer] 画像分析と応答生成を開始...")
                # ユーザー入力を渡す
                response = self.bii.observe_screen(img_base64, window_title=window_title, user_input=user_text_input)
            else:
                 # フォールバック（通常ここは通らない）
                 response = self.bii.handle_command("vision")

            print(f"[Live2DServer] 分析結果取得完了: {str(response)[:50]}...")
            
            if response:
                print("[Live2DServer] 応答処理を開始")
                # 表情制御
                emotion_tag = self.extract_emotion(response)
                print(f"[Live2DServer] 抽出された感情: {emotion_tag}")
                if emotion_tag:
                    await self.send_emotion(emotion_tag)
                
                # 音声合成
                if self.voice:
                    print("[Live2DServer] 音声合成パイプラインへ投入")
                    clean_text = self.bii.clean_text_for_voice(response)
                    if clean_text:
                        await self.audio_queue.put((response, clean_text))
                    else:
                        print("[Live2DServer] 音声化テキストがありません、直接表示します")
                        await self.send_response(response)
                else:
                    print("[Live2DServer] 音声無効、直接表示します")
                    await self.send_response(response)
            else:
                print("[Live2DServer] 応答が空でした")
                await self.broadcast({"type": "status", "status": "何も見えませんでした"})

        except Exception as e:
            print(f"[Live2DServer] 視覚処理エラー発生: {e}")
            import traceback
            traceback.print_exc()
            await self.broadcast({"type": "status", "status": f"エラー: {e}"})
    
    async def process_user_input(self, user_text):
        """ユーザー入力を処理"""
        if not self.bii:
            return
        
        try:
            # コマンド処理
            if user_text.startswith("/"):
                parts = user_text[1:].strip().split(maxsplit=1)
                command = parts[0].lower()
                args = parts[1].split() if len(parts) > 1 else []
                result = self.bii.handle_command(command, args)
                if result:
                    await self.send_response(result)
                    return
            
            # 通常の対話
            response = self.bii.generate_response(user_text=user_text, vision_result=None)
            # ここではまだ送信しない（音声合成直前に送信する）
            # await self.send_response(response)
            
            # 表情制御（これは先でも良い）
            emotion_tag = self.extract_emotion(response)
            if emotion_tag:
                await self.send_emotion(emotion_tag)
            
            # 音声合成
            if self.voice:
                clean_text = self.bii.clean_text_for_voice(response)
                if clean_text:
                    # キューに追加 (表示テキスト, 音声テキスト)
                    await self.audio_queue.put((response, clean_text))
                else:
                    # 音声化するテキストがない場合はここで表示
                    await self.send_response(response)
            else:
                # 音声無効なら即表示
                await self.send_response(response)
        except Exception as e:
            print(f"[Live2DServer] 処理エラー: {e}")
            await self.broadcast({
                "type": "status",
                "status": f"エラー: {e}"
            })
    
    def extract_emotion(self, response):
        """応答から感情タグを抽出"""
        if "[Happy]" in response or "[happy]" in response:
            return "Happy"
        elif "[Sad]" in response or "[sad]" in response:
            return "Sad"
        elif "[Surprised]" in response or "[surprised]" in response or "[Shock]" in response:
            return "Surprised"
        elif "[Angry]" in response or "[angry]" in response:
            return "Angry"
        elif "[Neutral]" in response or "[neutral]" in response:
            return "Neutral"
        return None
    
    async def send_emotion(self, emotion):
        """感情をクライアントに送信"""
        await self.broadcast({
            "type": "expression",
            "name": emotion
        })
    
    async def send_response(self, response):
        """応答をクライアントに送信"""
        await self.broadcast({
            "type": "response",
            "text": response
        })
    
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

    def _map_vowel_to_viseme(self, vowel: str):
        v = (vowel or "").lower()
        if v == "a":
            return 1.0, 0.0
        if v == "i":
            return 0.35, -1.0
        if v == "u":
            return 0.45, 0.4
        if v == "e":
            return 0.6, -0.5
        if v == "o":
            return 0.8, 0.8
        if v in {"n", "cl", "pau", "sil"}:
            return 0.0, 0.0
        return 0.2, 0.0

    def _build_viseme_sequence(self, query: dict, fps: int = 60):
        sequence = []
        frame_time = 1.0 / fps

        def add_frames(duration, open_val, form_val):
            if not duration or duration <= 0.0:
                return
            frames = max(1, int(round(duration / frame_time)))
            sequence.extend([(open_val, form_val)] * frames)

        pre = query.get("prePhonemeLength", 0.0)
        add_frames(pre, 0.0, 0.0)

        for phrase in query.get("accent_phrases", []):
            for mora in phrase.get("moras", []):
                cons_len = mora.get("consonant_length", 0.0)
                if cons_len:
                    add_frames(cons_len, 0.1, 0.0)
                vowel = mora.get("vowel", "")
                vowel_len = mora.get("vowel_length", 0.0)
                open_val, form_val = self._map_vowel_to_viseme(vowel)
                add_frames(vowel_len, open_val, form_val)

            pause = phrase.get("pause_mora")
            if pause:
                pause_len = pause.get("vowel_length", 0.0)
                add_frames(pause_len, 0.0, 0.0)

        post = query.get("postPhonemeLength", 0.0)
        add_frames(post, 0.0, 0.0)

        return sequence

    async def _send_viseme_sequence(self, sequence, fps: int = 60):
        if not sequence:
            return
        frame_time = 1.0 / fps
        for open_val, form_val in sequence:
            await self.broadcast({
                "type": "lipsync",
                "value": float(open_val)
            })
            await self.broadcast({
                "type": "mouth_form",
                "value": float(form_val)
            })
            await asyncio.sleep(frame_time)
    
    # play_voice_async は削除（キュー処理に移行）
    

    
    async def _send_lipsync_data(self, audio_data, sample_rate):
        """音声データからリップシンク値を計算して送信"""
        try:
            import numpy as np
            
            # チャンクサイズ（約60FPSで送信）
            chunk_size = sample_rate // 60
            num_chunks = len(audio_data) // chunk_size
            
            for i in range(num_chunks):
                start_idx = i * chunk_size
                end_idx = min(start_idx + chunk_size, len(audio_data))
                chunk = audio_data[start_idx:end_idx]
                
                # RMS値を計算（0.0～1.0に正規化）
                rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
                normalized_rms = min(rms / 32768.0, 1.0)  # int16の最大値で正規化
                
                # WebSocket経由でリップシンク値を送信
                await self.broadcast({
                    "type": "lipsync",
                    "value": float(normalized_rms)
                })
                
                # 約16.67ms待機（60FPS）
                await asyncio.sleep(1.0 / 60.0)
                
        except Exception as e:
            print(f"[Live2DServer] リップシンクデータ送信エラー: {e}")
    
    async def run(self, host="localhost", port=8765):
        """サーバーを起動"""
        await self.init_components()
        
        print(f"[Live2DServer] WebSocketサーバーを起動: ws://{host}:{port}")
        # websockets 15.0では、ハンドラー関数はServerConnectionのみを受け取る
        async with websockets.serve(self.handle_client, host, port):
            await asyncio.Future()  # 永続的に実行


if __name__ == "__main__":
    server = Live2DServer()
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print("\n[Live2DServer] サーバーを終了します")
