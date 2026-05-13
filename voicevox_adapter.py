"""
VOICEVOX API アダプター
VOICEVOXを使用してテキストを音声合成・再生するクラス
"""

import requests
import io
import pygame
from typing import Optional
from urllib.parse import quote


class VoicevoxAdapter:
    """
    VOICEVOX API を使用してテキストを音声合成・再生するアダプタークラス
    
    主な機能:
    - play_voice(text): テキストを音声合成して再生
    """
    
    def __init__(self, voicevox_url: str = "http://localhost:50021", speaker_id: int = 58):
        """
        VoicevoxAdapterを初期化
        
        Args:
            voicevox_url: VOICEVOX API のURL（デフォルト: http://localhost:50021）
            speaker_id: スピーカーID（デフォルト: 58 = 四国めたん（ノーマル））
        """
        self.voicevox_url = voicevox_url
        self.speaker_id = speaker_id
        self.enabled = True
        
        # pygameの初期化（音声出力用）
        try:
            pygame.mixer.pre_init(
                frequency=24000,
                size=-16,
                channels=1,
                devicename="CABLE Input (VB-Audio Virtual Cable)"
            )
            pygame.mixer.init()
            print("[VoicevoxAdapter] pygame初期化完了（CABLE Input）")
        except Exception as e:
            print(f"[VoicevoxAdapter] 警告: CABLE Inputでの初期化に失敗しました: {e}")
            try:
                pygame.mixer.pre_init(
                    frequency=24000,
                    size=-16,
                    channels=1
                )
                pygame.mixer.init()
                print("[VoicevoxAdapter] pygame初期化完了（既定デバイス）")
            except Exception as e2:
                print(f"[VoicevoxAdapter] 警告: pygame初期化に失敗しました: {e2}")
                self.enabled = False
    
    def play_voice(self, text: str) -> bool:
        """
        VOICEVOXを使用してテキストを音声合成・再生
        
        Args:
            text: 音声化するテキスト
            
        Returns:
            bool: 成功した場合はTrue、失敗した場合はFalse
        """
        if not self.enabled:
            print("[VoicevoxAdapter] 警告: VOICEVOXが無効です")
            return False
        
        if not text or not text.strip():
            print("[VoicevoxAdapter] 警告: テキストが空です")
            return False
        
        try:
            # 音声クエリの作成
            res1 = requests.post(
                f"{self.voicevox_url}/audio_query?speaker={self.speaker_id}&text={quote(text)}",
                timeout=10
            )
            res1.raise_for_status()
            query = res1.json()

            # 音声データの生成（WAVバイナリ）
            res2 = requests.post(
                f"{self.voicevox_url}/synthesis?speaker={self.speaker_id}",
                json=query,
                timeout=60
            )
            res2.raise_for_status()
            
            # pygameで再生
            sound_data = io.BytesIO(res2.content)
            pygame.mixer.music.load(sound_data)
            pygame.mixer.music.play()

            # 再生が終わるまで待機しない（非同期再生のため）
            # while pygame.mixer.music.get_busy():
            #    pygame.time.Clock().tick(10)
            
            print(f"[VoicevoxAdapter] ✓ 音声再生開始: {text[:30]}...")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"[VoicevoxAdapter] エラー: VOICEVOXへの接続に失敗しました: {e}")
            return False
        except Exception as e:
            print(f"[VoicevoxAdapter] エラー: 音声合成に失敗しました: {e}")
            return False


# テスト実行用
if __name__ == "__main__":
    adapter = VoicevoxAdapter()
    adapter.play_voice("こんにちは、猫使ビィですにゃ！")

