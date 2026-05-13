"""
猫使ビィ・デスクトップ常駐型アプリ
Live2Dモデルをデスクトップ上に常駐表示し、音声入力で操作可能
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import asyncio
import threading
import time
from PIL import Image, ImageTk
import pyautogui
import pygetwindow as gw
from bii_core import BiiCore
from voicevox_adapter import VoicevoxAdapter
from vts_adapter import VTSAdapter
import speech_recognition as sr
import queue

class BiiDesktopApp:
    """猫使ビィ・デスクトップ常駐アプリ"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🐱 猫使ビィ・デスクトップ常駐")
        self.root.geometry("400x600")
        self.root.attributes("-topmost", True)  # 常に最前面に表示
        self.root.attributes("-alpha", 0.95)  # 少し透明に
        
        # 初期化
        self.bii = None
        self.voice = None
        self.vts = None
        self.vts_connected = False
        self.is_listening = False
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.message_queue = queue.Queue()
        
        # UI構築
        self._build_ui()
        
        # 非同期処理用のイベントループ
        self.loop = None
        self.loop_thread = None
        
        # 初期化
        self._init_components()
        
        # メッセージキュー処理
        self.root.after(100, self._process_queue)
    
    def _build_ui(self):
        """UIを構築"""
        # タイトル
        title_frame = tk.Frame(self.root, bg="#2C3E50", height=50)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="🐱 猫使ビィ",
            font=("Arial", 16, "bold"),
            bg="#2C3E50",
            fg="white"
        )
        title_label.pack(pady=10)
        
        # メインコンテンツ
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # ステータス表示
        self.status_label = tk.Label(
            main_frame,
            text="初期化中...",
            font=("Arial", 10),
            fg="gray"
        )
        self.status_label.pack(anchor=tk.W, pady=5)
        
        # VTS画面表示エリア
        vts_frame = tk.LabelFrame(main_frame, text="Live2Dモデル", font=("Arial", 10, "bold"))
        vts_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.vts_canvas = tk.Canvas(vts_frame, bg="black", height=300)
        self.vts_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.vts_label = tk.Label(
            self.vts_canvas,
            text="VTS接続待機中...\n（VTSを起動して「VTS接続」ボタンを押してください）",
            fg="white",
            bg="black",
            font=("Arial", 10),
            justify=tk.CENTER
        )
        self.vts_canvas.create_window(150, 150, window=self.vts_label)
        
        self.vts_image_id = None
        self.vts_window = None
        
        # チャット表示エリア
        chat_frame = tk.LabelFrame(main_frame, text="チャット", font=("Arial", 10, "bold"))
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.chat_text = scrolledtext.ScrolledText(
            chat_frame,
            height=8,
            font=("Arial", 9),
            wrap=tk.WORD
        )
        self.chat_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.chat_text.config(state=tk.DISABLED)
        
        # コントロールボタン
        control_frame = tk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=5)
        
        self.listen_btn = tk.Button(
            control_frame,
            text="🎤 音声入力開始",
            command=self._toggle_listening,
            bg="#3498DB",
            fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.FLAT,
            padx=10,
            pady=5
        )
        self.listen_btn.pack(side=tk.LEFT, padx=5)
        
        self.vts_btn = tk.Button(
            control_frame,
            text="🎭 VTS接続",
            command=self._connect_vts,
            bg="#E74C3C",
            fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.FLAT,
            padx=10,
            pady=5
        )
        self.vts_btn.pack(side=tk.LEFT, padx=5)
        
        # 最小化ボタン
        minimize_btn = tk.Button(
            control_frame,
            text="📌 最小化",
            command=self._minimize_window,
            bg="#95A5A6",
            fg="white",
            font=("Arial", 9),
            relief=tk.FLAT,
            padx=5,
            pady=5
        )
        minimize_btn.pack(side=tk.RIGHT, padx=5)
    
    def _init_components(self):
        """コンポーネントを初期化"""
        def init_async():
            try:
                self.bii = BiiCore()
                self.voice = VoicevoxAdapter()
                self.vts = VTSAdapter()
                self.status_label.config(text="✓ 初期化完了", fg="green")
                self._add_chat_message("システム", "猫使ビィが起動しましたにゃ！")
            except Exception as e:
                self.status_label.config(text=f"✗ 初期化失敗: {e}", fg="red")
        
        threading.Thread(target=init_async, daemon=True).start()
        
        # マイクの初期化
        try:
            self.microphone = sr.Microphone()
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
        except Exception as e:
            self._add_chat_message("システム", f"マイク初期化エラー: {e}")
    
    def _start_async_loop(self):
        """非同期イベントループを開始"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def _connect_vts(self):
        """VTSに接続"""
        if not self.vts:
            self._add_chat_message("システム", "初期化が完了していません")
            return
        
        if self.vts_connected:
            self._add_chat_message("システム", "既にVTSに接続されています")
            return
        
        def connect_async():
            try:
                if not self.loop:
                    self.loop_thread = threading.Thread(target=self._start_async_loop, daemon=True)
                    self.loop_thread.start()
                    time.sleep(0.5)  # ループの起動を待つ
                
                future = asyncio.run_coroutine_threadsafe(self.vts.connect(), self.loop)
                connected = future.result(timeout=10)
                
                if connected:
                    # 表情リストを取得
                    future = asyncio.run_coroutine_threadsafe(self.vts.get_expressions(), self.loop)
                    vts_expressions = future.result(timeout=10)
                    if vts_expressions:
                        self.bii.update_expressions_from_vts(vts_expressions)
                    
                    self.vts_connected = True
                    self.vts_btn.config(text="✓ VTS接続済", bg="#27AE60", state=tk.DISABLED)
                    self.vts_label.place_forget()  # ラベルを非表示（プレビューを表示）
                    self._add_chat_message("システム", "VTSに接続しましたにゃ！")
                else:
                    self._add_chat_message("システム", "VTS接続に失敗しました")
            except Exception as e:
                self._add_chat_message("システム", f"VTS接続エラー: {e}")
        
        threading.Thread(target=connect_async, daemon=True).start()
    
    def _toggle_listening(self):
        """音声入力を開始/停止"""
        if not self.microphone:
            self._add_chat_message("システム", "マイクが利用できません")
            return
        
        if self.is_listening:
            self.is_listening = False
            self.listen_btn.config(text="🎤 音声入力開始", bg="#3498DB")
            self._add_chat_message("システム", "音声入力を停止しました")
        else:
            self.is_listening = True
            self.listen_btn.config(text="⏹ 音声入力停止", bg="#E74C3C")
            self._add_chat_message("システム", "音声入力を開始しました...")
            threading.Thread(target=self._listen_loop, daemon=True).start()
    
    def _listen_loop(self):
        """音声認識ループ"""
        while self.is_listening:
            try:
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                
                try:
                    # 音声をテキストに変換（日本語）
                    text = self.recognizer.recognize_google(audio, language="ja-JP")
                    self.message_queue.put(("user", text))
                except sr.UnknownValueError:
                    pass  # 音声が認識できなかった場合はスキップ
                except sr.RequestError as e:
                    self.message_queue.put(("system", f"音声認識エラー: {e}"))
            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                if self.is_listening:
                    self.message_queue.put(("system", f"音声認識エラー: {e}"))
    
    def _process_queue(self):
        """メッセージキューを処理"""
        try:
            while True:
                item = self.message_queue.get_nowait()
                if isinstance(item, tuple) and len(item) == 2:
                    msg_type, content = item
                    if msg_type == "user":
                        self._handle_user_input(content)
                    elif msg_type == "system":
                        self._add_chat_message("システム", content)
                    elif msg_type == "assistant":
                        # アシスタントの応答を処理（表情制御、音声合成）
                        self._process_assistant_response(content)
                    elif msg_type == "chat":
                        # チャットに表示
                        role, text = content
                        self._add_chat_message(role, text)
        except queue.Empty:
            pass
        
        self.root.after(100, self._process_queue)
    
    def _handle_user_input(self, user_text):
        """ユーザー入力を処理"""
        self._add_chat_message("マスター", user_text)
        
        if not self.bii:
            self._add_chat_message("ビィ", "[Sad] まだ初期化中だにゃ...")
            return
        
        def process_async():
            try:
                # コマンド処理
                if user_text.startswith("/"):
                    parts = user_text[1:].strip().split(maxsplit=1)
                    command = parts[0].lower()
                    args = parts[1].split() if len(parts) > 1 else []
                    result = self.bii.handle_command(command, args)
                    if result:
                        self.message_queue.put(("assistant", result))
                        return
                
                # 通常の対話
                response = self.bii.generate_response(user_text=user_text, vision_result=None)
                self.message_queue.put(("assistant", response))
                self.message_queue.put(("chat", ("assistant", response)))
            except Exception as e:
                self.message_queue.put(("assistant", f"[Sad] エラーが発生したにゃ: {e}"))
        
        threading.Thread(target=process_async, daemon=True).start()
    
    def _add_chat_message(self, role, content):
        """チャットにメッセージを追加"""
        self.chat_text.config(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        self.chat_text.insert(tk.END, f"[{timestamp}] {role}: {content}\n")
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)
    
    def _process_assistant_response(self, response):
        """アシスタントの応答を処理（表情制御、音声合成）"""
        # 表情制御
        if self.vts_connected and self.vts and self.loop:
            emotion_tag = None
            if "[Happy]" in response or "[happy]" in response:
                emotion_tag = "Happy"
            elif "[Sad]" in response or "[sad]" in response:
                emotion_tag = "Sad"
            elif "[Surprised]" in response or "[surprised]" in response or "[Shock]" in response:
                emotion_tag = "Surprised"
            elif "[Angry]" in response or "[angry]" in response:
                emotion_tag = "Angry"
            elif "[Neutral]" in response or "[neutral]" in response:
                emotion_tag = "Neutral"
            
            if emotion_tag:
                def set_expression_async():
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            self.vts.set_expression(emotion_tag),
                            self.loop
                        )
                        future.result(timeout=5)
                    except Exception:
                        pass
                threading.Thread(target=set_expression_async, daemon=True).start()
        
        # 音声合成
        if self.voice and self.bii:
            def play_voice_async():
                try:
                    clean_text = self.bii.clean_text_for_voice(response)
                    if clean_text:
                        self.voice.play_voice(clean_text)
                except Exception:
                    pass
            threading.Thread(target=play_voice_async, daemon=True).start()
    
    def _minimize_window(self):
        """ウィンドウを最小化"""
        self.root.iconify()
    
    def _update_vts_preview(self):
        """VTS画面のプレビューを更新（定期的にキャプチャ）"""
        if self.vts_connected:
            try:
                # VTSウィンドウを探す
                vts_windows = gw.getWindowsWithTitle("VTube Studio")
                if vts_windows:
                    vts_window = vts_windows[0]
                    if vts_window.visible:
                        # VTSウィンドウのスクリーンショットを取得
                        left = vts_window.left
                        top = vts_window.top
                        width = min(vts_window.width, 300)  # 表示サイズを制限
                        height = min(vts_window.height, 300)
                        
                        # スクリーンショットを取得
                        screenshot = pyautogui.screenshot(region=(left, top, width, height))
                        
                        # Canvasサイズに合わせてリサイズ
                        canvas_width = self.vts_canvas.winfo_width()
                        canvas_height = self.vts_canvas.winfo_height()
                        if canvas_width > 1 and canvas_height > 1:
                            screenshot = screenshot.resize((canvas_width, canvas_height), Image.LANCZOS)
                            
                            # Tkinter用の画像に変換
                            photo = ImageTk.PhotoImage(screenshot)
                            
                            # 既存の画像を削除
                            if self.vts_image_id:
                                self.vts_canvas.delete(self.vts_image_id)
                            
                            # 画像を表示
                            self.vts_image_id = self.vts_canvas.create_image(
                                canvas_width // 2,
                                canvas_height // 2,
                                image=photo,
                                anchor=tk.CENTER
                            )
                            
                            # 画像参照を保持（ガベージコレクションを防ぐ）
                            self.vts_canvas.image = photo
                            
                            # ラベルを非表示
                            self.vts_label.place_forget()
                else:
                    # VTSウィンドウが見つからない場合
                    if not self.vts_label.winfo_viewable():
                        self.vts_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
                        self.vts_label.config(text="VTSウィンドウが見つかりません\n（VTube Studioを起動してください）")
            except Exception as e:
                if self.vts_connected:
                    if not self.vts_label.winfo_viewable():
                        self.vts_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
                    self.vts_label.config(text=f"プレビューエラー: {str(e)[:30]}")
        
        self.root.after(500, self._update_vts_preview)  # 0.5秒ごとに更新
    
    def run(self):
        """アプリを起動"""
        self._update_vts_preview()
        self.root.mainloop()


if __name__ == "__main__":
    app = BiiDesktopApp()
    app.run()
