"""
Bii・Webアプリ（Streamlit）
チャットUI、画面キャプチャ、画像プレビュー、VTS表情連動

VTS の WebSocket 接続は専用のバックグラウンドイベントループ上に常駐させる。
（asyncio.run() で接続すると、run() 終了と同時にループが閉じて接続が死ぬ）
"""
import asyncio
import base64
import io
import threading
import time

import streamlit as st
from PIL import Image

from bii_core import BiiCore
from voicevox_adapter import VoicevoxAdapter
from vts_adapter import VTSAdapter

# ページ設定
st.set_page_config(
    page_title="Bii",
    page_icon="🐱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# セッション状態の初期化
for key, default in [
    ("bii", None), ("voice", None), ("vts", None),
    ("vts_connected", False), ("vts_loop", None), ("messages", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def init_bii():
    """BiiCoreの初期化"""
    if st.session_state.bii is None:
        with st.spinner("Biiを起動中..."):
            st.session_state.bii = BiiCore()
            st.session_state.voice = VoicevoxAdapter()
            st.session_state.vts = VTSAdapter()
            st.success("✓ 初期化完了")


def ensure_vts_loop() -> asyncio.AbstractEventLoop:
    """VTS通信用のバックグラウンドイベントループを常駐させる"""
    loop = st.session_state.vts_loop
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        threading.Thread(target=loop.run_forever, daemon=True).start()
        st.session_state.vts_loop = loop
    return loop


def connect_vts() -> bool:
    """VTSに接続する（バックグラウンドループ上で実行）"""
    if st.session_state.vts and not st.session_state.vts_connected:
        loop = ensure_vts_loop()
        try:
            future = asyncio.run_coroutine_threadsafe(
                st.session_state.vts.connect(), loop)
            if future.result(timeout=15):
                future = asyncio.run_coroutine_threadsafe(
                    st.session_state.vts.get_expressions(), loop)
                vts_expressions = future.result(timeout=10)
                if vts_expressions:
                    st.session_state.bii.update_expressions_from_vts(vts_expressions)
                st.session_state.vts_connected = True
                return True
        except Exception as e:
            st.error(f"VTS接続エラー: {e}")
    return st.session_state.vts_connected


def apply_expression(response_text: str):
    """応答の感情タグをVTSの表情に反映する"""
    if not st.session_state.vts_connected:
        return
    tag = st.session_state.bii.extract_emotion_tag(response_text)
    if not tag:
        return
    try:
        future = asyncio.run_coroutine_threadsafe(
            st.session_state.vts.set_expression(tag), st.session_state.vts_loop)
        future.result(timeout=3)
    except Exception as e:
        st.warning(f"表情制御エラー: {e}")


def speak(response_text: str):
    """応答を音声合成する"""
    if not st.session_state.voice:
        return
    clean_text = st.session_state.bii.clean_text_for_voice(response_text)
    if clean_text:
        try:
            st.session_state.voice.play_voice(clean_text)
        except Exception as e:
            st.warning(f"音声合成エラー: {e}")


def capture_screen_with_countdown(countdown_seconds=3):
    """カウントダウン付き画面キャプチャ"""
    countdown_placeholder = st.empty()
    for i in range(countdown_seconds, 0, -1):
        countdown_placeholder.info(f"📸 {i}秒後にキャプチャします...")
        time.sleep(1)
    countdown_placeholder.info("📸 キャプチャ中...")
    img_base64, window_title = st.session_state.bii.vision.capture_screen(
        save_debug=True)
    countdown_placeholder.empty()
    return img_base64, window_title


def display_image_from_base64(img_base64):
    """Base64画像を表示"""
    try:
        image_data = base64.b64decode(img_base64)
        return Image.open(io.BytesIO(image_data))
    except Exception as e:
        st.error(f"画像表示エラー: {e}")
        return None


# メインUI
st.title("🐱 Bii・対話モード")

# サイドバー
with st.sidebar:
    st.header("設定")

    if st.button("🔄 初期化", use_container_width=True):
        st.session_state.bii = None
        st.session_state.voice = None
        st.session_state.vts = None
        st.session_state.vts_connected = False
        init_bii()

    if st.session_state.bii:
        if st.button("🎭 VTS接続", use_container_width=True,
                     disabled=st.session_state.vts_connected):
            if connect_vts():
                st.success("✓ VTS接続完了")

        st.divider()
        st.subheader("📋 コマンド")
        st.markdown("""
        - `/help` - ヘルプを表示
        - `/memory` - 長期記憶を表示
        - `/code <query>` - コード検索
        - `/search <query>` - Web検索
        - `/vision` - 画面を分析
        - `/history` - 会話履歴
        - `/clear` - 履歴クリア
        """)

        st.divider()
        st.subheader("📸 画面キャプチャ設定")
        countdown_seconds = st.slider("カウントダウン（秒）", 0, 10, 3)
        st.caption("0秒にすると即座にキャプチャします")

# 初期化
if st.session_state.bii is None:
    init_bii()

if st.session_state.bii:
    # 画面キャプチャセクション
    st.header("📸 画面キャプチャ")
    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("📷 画面をキャプチャして分析",
                     use_container_width=True, type="primary"):
            with st.spinner("準備中..."):
                img_base64, window_title = capture_screen_with_countdown(
                    countdown_seconds)

                image = display_image_from_base64(img_base64)
                if image:
                    st.image(image, caption=f"キャプチャした画面: {window_title}",
                             use_container_width=True)

                with st.spinner("画面を分析中..."):
                    response_text = st.session_state.bii.observe_screen(
                        img_base64, window_title=window_title)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "image": image,
                        "window_title": window_title,
                    })
                    apply_expression(response_text)
                    speak(response_text)

    with col2:
        st.info("💡 **使い方**\n\n1. キャプチャしたい画面を準備\n"
                "2. 「画面をキャプチャして分析」ボタンをクリック\n"
                "3. カウントダウン後に自動でキャプチャされます")

    st.divider()

    # チャットセクション
    st.header("💬 チャット")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("image"):
                st.image(msg["image"], caption=msg.get("window_title", ""),
                         use_container_width=True)

    if prompt := st.chat_input("メッセージを入力..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        parsed = BiiCore.parse_command(prompt)
        if parsed:
            command, args = parsed
            result = st.session_state.bii.handle_command(command, args)
            if result:
                st.session_state.messages.append(
                    {"role": "assistant", "content": result})
                with st.chat_message("assistant"):
                    st.markdown(result)
                    apply_expression(result)
                    if command in ("vision", "画面", "observe", "観察"):
                        speak(result)
        else:
            with st.chat_message("assistant"):
                with st.spinner("考え中..."):
                    response = st.session_state.bii.generate_response(
                        user_text=prompt)
                    st.markdown(response)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response})
                    apply_expression(response)
                    speak(response)

    if st.button("🗑️ 会話履歴をクリア", use_container_width=True):
        st.session_state.messages = []
        st.session_state.bii.clear_conversation_history()
        st.success("会話履歴をクリアしました")
        st.rerun()

else:
    st.error("初期化に失敗しました。もう一度「初期化」ボタンを押してください。")
