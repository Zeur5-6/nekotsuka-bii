"""
Bii 全体の設定値を一元管理するモジュール

各値は環境変数（.env に BII_* を書くか、シェルで export）で上書きできる。
散らばっていた URL・話者ID・デバイス名・間隔などはすべてここに集約する。
"""
import logging
import os

from dotenv import load_dotenv

load_dotenv()

# --- LLM (Ollama) ---
OLLAMA_URL = os.getenv("BII_OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("BII_OLLAMA_MODEL", "qwen2.5:7b")

# --- Gemini Vision ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- VOICEVOX ---
VOICEVOX_URL = os.getenv("BII_VOICEVOX_URL", "http://localhost:50021")
# 58 = 猫使ビィ（ノーマル）
VOICEVOX_SPEAKER_ID = int(os.getenv("BII_VOICEVOX_SPEAKER", "58"))
# VB-Audio 仮想デバイスが無い環境では自動で既定デバイスにフォールバックする
AUDIO_DEVICE_NAME = os.getenv("BII_AUDIO_DEVICE", "CABLE Input (VB-Audio Virtual Cable)")

# --- VTube Studio ---
VTS_URL = os.getenv("BII_VTS_URL", "ws://localhost:8001")
VTS_TOKEN_FILE = os.getenv("BII_VTS_TOKEN_FILE", "./vts_token.json")

# --- Live2D WebSocket サーバー (Python ⇔ Electron) ---
LIVE2D_WS_HOST = os.getenv("BII_LIVE2D_WS_HOST", "localhost")
LIVE2D_WS_PORT = int(os.getenv("BII_LIVE2D_WS_PORT", "8765"))
LIVE2D_WS_URL = f"ws://{LIVE2D_WS_HOST}:{LIVE2D_WS_PORT}"

# --- 画面キャプチャ ---
# 長辺の最大ピクセル数。画面上の文字を Gemini が読めるよう 1024 を既定にする
VISION_MAX_PX = int(os.getenv("BII_VISION_MAX_PX", "1024"))

# --- オブザーバーモード ---
OBSERVER_INTERVAL = int(os.getenv("BII_OBSERVER_INTERVAL", "15"))

# --- データ ---
DB_PATH = os.getenv("BII_DB_PATH", "bii_memory.db")
RAG_CACHE_PATH = os.getenv("BII_RAG_CACHE", ".rag_cache")

# --- ログ ---
LOG_LEVEL = os.getenv("BII_LOG_LEVEL", "INFO")

_configured = False


def get_logger(name: str) -> logging.Logger:
    """モジュール用ロガーを返す（初回呼び出し時にルート設定を行う）"""
    global _configured
    if not _configured:
        logging.basicConfig(
            level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        _configured = True
    return logging.getLogger(name)
