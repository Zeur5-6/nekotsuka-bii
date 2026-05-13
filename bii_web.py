"""
猫使ビィ・Webアプリ（Streamlit）
チャットUI、画面キャプチャ、画像プレビュー機能付き
"""

import streamlit as st
import asyncio
import time
import base64
from PIL import Image
import io
from bii_core import BiiCore
from voicevox_adapter import VoicevoxAdapter
from vts_adapter import VTSAdapter

# ページ設定
st.set_page_config(
    page_title="猫使ビィ",
    page_icon="🐱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# セッション状態の初期化
if "bii" not in st.session_state:
    st.session_state.bii = None
if "voice" not in st.session_state:
    st.session_state.voice = None
if "vts" not in st.session_state:
    st.session_state.vts = None
if "vts_connected" not in st.session_state:
    st.session_state.vts_connected = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "capture_countdown" not in st.session_state:
    st.session_state.capture_countdown = 0

def init_bii():
    """BiiCoreの初期化"""
    if st.session_state.bii is None:
        with st.spinner("猫使ビィを起動中..."):
            st.session_state.bii = BiiCore()
            st.session_state.voice = VoicevoxAdapter()
            st.session_state.vts = VTSAdapter()
            st.success("✓ 初期化完了")

async def connect_vts():
    """VTSに接続"""
    if st.session_state.vts and not st.session_state.vts_connected:
        try:
            connected = await st.session_state.vts.connect()
            if connected:
                # VTS APIから表情ファイルリストを取得
                vts_expressions = await st.session_state.vts.get_expressions()
                if vts_expressions:
                    st.session_state.bii.update_expressions_from_vts(vts_expressions)
                st.session_state.vts_connected = True
                return True
        except Exception as e:
            st.error(f"VTS接続エラー: {e}")
    return st.session_state.vts_connected

def capture_screen_with_countdown(countdown_seconds=3):
    """カウントダウン付き画面キャプチャ"""
    countdown_placeholder = st.empty()
    
    for i in range(countdown_seconds, 0, -1):
        countdown_placeholder.info(f"📸 {i}秒後にキャプチャします...")
        time.sleep(1)
    
    countdown_placeholder.info("📸 キャプチャ中...")
    img_base64, window_title = st.session_state.bii.vision.capture_screen(scale=0.7, save_debug=True)
    countdown_placeholder.empty()
    
    return img_base64, window_title

def display_image_from_base64(img_base64):
    """Base64画像を表示"""
    try:
        image_data = base64.b64decode(img_base64)
        image = Image.open(io.BytesIO(image_data))
        return image
    except Exception as e:
        st.error(f"画像表示エラー: {e}")
        return None

# メインUI
st.title("🐱 猫使ビィ・対話モード")

# サイドバー
with st.sidebar:
    st.header("設定")
    
    # 初期化ボタン
    if st.button("🔄 初期化", use_container_width=True):
        st.session_state.bii = None
        st.session_state.voice = None
        st.session_state.vts = None
        st.session_state.vts_connected = False
        init_bii()
    
    # VTS接続ボタン
    if st.session_state.bii:
        if st.button("🎭 VTS接続", use_container_width=True, disabled=st.session_state.vts_connected):
            asyncio.run(connect_vts())
            if st.session_state.vts_connected:
                st.success("✓ VTS接続完了")
        
        st.divider()
        
        # コマンド一覧
        st.subheader("📋 コマンド")
        st.markdown("""
        - `/help` - ヘルプを表示
        - `/memory` - 長期記憶を表示
        - `/code <query>` - コード検索
        - `/search <query>` - Web検索
        - `/history` - 会話履歴
        - `/clear` - 履歴クリア
        """)
        
        st.divider()
        
        # 画面キャプチャ設定
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
        if st.button("📷 画面をキャプチャして分析", use_container_width=True, type="primary"):
            if st.session_state.bii:
                with st.spinner("準備中..."):
                    img_base64, window_title = capture_screen_with_countdown(countdown_seconds)
                    
                    # 画像プレビュー
                    image = display_image_from_base64(img_base64)
                    if image:
                        st.image(image, caption=f"キャプチャした画面: {window_title}", use_container_width=True)
                    
                    # 分析実行
                    with st.spinner("画面を分析中..."):
                        response_text = st.session_state.bii.observe_screen(
                            img_base64, 
                            window_title=window_title, 
                            user_input=None
                        )
                        
                        # 応答を表示
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": response_text,
                            "image": image,
                            "window_title": window_title
                        })
                        
                        # 音声合成
                        if st.session_state.voice:
                            clean_text = st.session_state.bii.clean_text_for_voice(response_text)
                            if clean_text:
                                try:
                                    st.session_state.voice.play_voice(clean_text)
                                except Exception as e:
                                    st.warning(f"音声合成エラー: {e}")
    
    with col2:
        st.info("💡 **使い方**\n\n1. キャプチャしたい画面を準備\n2. 「画面をキャプチャして分析」ボタンをクリック\n3. カウントダウン後に自動でキャプチャされます")
    
    st.divider()
    
    # チャットセクション
    st.header("💬 チャット")
    
    # 会話履歴の表示
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "image" in msg and msg["image"]:
                st.image(msg["image"], caption=msg.get("window_title", ""), use_container_width=True)
    
    # ユーザー入力
    if prompt := st.chat_input("メッセージを入力..."):
        # ユーザーメッセージを追加
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # コマンド処理
        if prompt.startswith("/"):
            parts = prompt[1:].strip().split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1].split() if len(parts) > 1 else []
            
            result = st.session_state.bii.handle_command(command, args)
            if result:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": result
                })
                with st.chat_message("assistant"):
                    st.markdown(result)
                    
                    # /visionコマンドの場合は音声合成
                    if command == "vision" or command == "画面" or command == "observe" or command == "観察":
                        if st.session_state.voice:
                            clean_text = st.session_state.bii.clean_text_for_voice(result)
                            if clean_text:
                                try:
                                    st.session_state.voice.play_voice(clean_text)
                                except Exception as e:
                                    st.warning(f"音声合成エラー: {e}")
        else:
            # 通常の対話
            with st.chat_message("assistant"):
                with st.spinner("考え中..."):
                    response = st.session_state.bii.generate_response(user_text=prompt, vision_result=None)
                    st.markdown(response)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response
                    })
                    
                    # 音声合成
                    if st.session_state.voice:
                        clean_text = st.session_state.bii.clean_text_for_voice(response)
                        if clean_text:
                            try:
                                st.session_state.voice.play_voice(clean_text)
                            except Exception as e:
                                st.warning(f"音声合成エラー: {e}")
    
    # 履歴クリアボタン
    if st.button("🗑️ 会話履歴をクリア", use_container_width=True):
        st.session_state.messages = []
        st.session_state.bii.clear_conversation_history()
        st.success("会話履歴をクリアしました")
        st.rerun()

else:
    st.error("初期化に失敗しました。もう一度「初期化」ボタンを押してください。")
