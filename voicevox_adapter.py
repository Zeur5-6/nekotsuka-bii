"""
VOICEVOX API アダプター

- synthesize(): テキスト → (audio_query, WAVバイナリ)。リップシンク用に query も返す
- play_wav(): WAV バイナリを pygame で再生（ブロッキング可）
- play_voice(): 上記2つを組み合わせた従来互換 API（非ブロッキング再生）

live2d_server.py 側に重複していた合成ロジックはここに一本化した。
"""
import io
import time
from typing import Optional, Tuple
from urllib.parse import quote

import pygame
import requests

from config import (AUDIO_DEVICE_NAME, VOICEVOX_SPEAKER_ID, VOICEVOX_URL,
                    get_logger)

log = get_logger("Voicevox")


class VoicevoxAdapter:
    """VOICEVOX API を使用してテキストを音声合成・再生するアダプター"""

    def __init__(self, voicevox_url: str = None, speaker_id: int = None):
        """
        Args:
            voicevox_url: VOICEVOX API の URL（None なら config.VOICEVOX_URL）
            speaker_id: スタイルID（None なら config.VOICEVOX_SPEAKER_ID。
                        既定 58 = 猫使ビィ（ノーマル））
        """
        self.voicevox_url = voicevox_url or VOICEVOX_URL
        self.speaker_id = speaker_id if speaker_id is not None else VOICEVOX_SPEAKER_ID
        self.enabled = True

        try:
            pygame.mixer.pre_init(
                frequency=24000, size=-16, channels=1,
                devicename=AUDIO_DEVICE_NAME)
            pygame.mixer.init()
            log.info(f"pygame初期化完了（{AUDIO_DEVICE_NAME}）")
        except Exception as e:
            log.warning(f"{AUDIO_DEVICE_NAME} での初期化に失敗、既定デバイスを試します: {e}")
            try:
                pygame.mixer.pre_init(frequency=24000, size=-16, channels=1)
                pygame.mixer.init()
                log.info("pygame初期化完了（既定デバイス）")
            except Exception as e2:
                log.warning(f"pygame初期化に失敗（音声無効）: {e2}")
                self.enabled = False

    def synthesize(self, text: str) -> Optional[Tuple[dict, bytes]]:
        """テキストを音声合成して (audio_query, WAVバイナリ) を返す

        audio_query にはモーラ長情報が含まれ、リップシンク生成
        （lipsync_utils.build_viseme_sequence）に使える。失敗時は None。
        """
        if not text or not text.strip():
            return None
        try:
            res1 = requests.post(
                f"{self.voicevox_url}/audio_query?speaker={self.speaker_id}&text={quote(text)}",
                timeout=10)
            res1.raise_for_status()
            query = res1.json()

            res2 = requests.post(
                f"{self.voicevox_url}/synthesis?speaker={self.speaker_id}",
                json=query, timeout=60)
            res2.raise_for_status()
            return query, res2.content
        except requests.exceptions.RequestException as e:
            log.error(f"VOICEVOXへの接続に失敗しました: {e}")
            return None

    def play_wav(self, wav_bytes: bytes, blocking: bool = False,
                 max_duration: float = 30.0) -> bool:
        """WAV バイナリを再生する

        Args:
            blocking: True なら再生完了（または max_duration 経過）まで待つ
        """
        if not self.enabled:
            return False
        try:
            pygame.mixer.music.load(io.BytesIO(wav_bytes))
            pygame.mixer.music.play()
            if blocking:
                start = time.time()
                while pygame.mixer.music.get_busy():
                    if time.time() - start > max_duration:
                        log.warning("音声再生がタイムアウトしました。強制停止します。")
                        break
                    pygame.time.Clock().tick(10)
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
            return True
        except Exception as e:
            log.error(f"音声再生に失敗しました: {e}")
            return False

    def play_voice(self, text: str) -> bool:
        """テキストを音声合成して再生する（非ブロッキング、従来互換 API）"""
        if not self.enabled:
            log.warning("VOICEVOXが無効です（pygame初期化失敗）")
            return False
        result = self.synthesize(text)
        if result is None:
            return False
        _, wav_bytes = result
        ok = self.play_wav(wav_bytes, blocking=False)
        if ok:
            log.info(f"音声再生開始: {text[:30]}...")
        return ok


# テスト実行用
if __name__ == "__main__":
    adapter = VoicevoxAdapter()
    adapter.play_voice("こんにちは、Biiですにゃ！")
