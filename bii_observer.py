"""
Bii・オブザーバーモード
画面を定期的にキャプチャして Bii に喋らせるメインループ

定期観察は save_history=False / extract_facts=False で実行し、
会話履歴・長期記憶を「画面を見てにゃ」の羅列で汚さない。
"""
import asyncio
import time

from bii_core import BiiCore
from config import OBSERVER_INTERVAL, get_logger
from voicevox_adapter import VoicevoxAdapter
from vts_adapter import VTSAdapter

log = get_logger("Observer")


async def main():
    """メインループ"""
    bii = BiiCore()
    voice = VoicevoxAdapter()
    vts = VTSAdapter()
    loop = asyncio.get_running_loop()

    print("=" * 60)
    print("  Bii・オブザーバーモード 起動だにゃ！")
    print(f"  テキストモデル（ローカル）: {bii.model}")
    print(f"  画像分析モデル（クラウド）: {bii.gemini_model_name}")
    print(f"  観察間隔: {OBSERVER_INTERVAL}秒")
    print("=" * 60)

    # VTSに接続
    connected = await vts.connect()
    if not connected:
        log.warning("VTube Studioへの接続に失敗。表情制御は無効です。")
    else:
        try:
            vts_expressions = await vts.get_expressions()
            if vts_expressions:
                bii.update_expressions_from_vts(vts_expressions)
        except Exception as e:
            log.warning(f"VTS表情リストの取得に失敗: {e}")

    try:
        while True:
            print(f"\n[観察中...] ({time.strftime('%H:%M:%S')})")

            # 1. 画面をキャプチャ
            img_base64, window_title = bii.vision.capture_screen(save_debug=True)

            # 2. 画面を分析（重い処理は executor でイベントループを守る）
            #    定期観察なので履歴保存・事実抽出はしない
            response_text = await loop.run_in_executor(
                None,
                lambda: bii.observe_screen(
                    img_base64, window_title=window_title,
                    save_history=False, extract_facts=False))
            print(f"Biiの気づき: {response_text}")

            # 3. 表情制御
            emotion_tag = bii.extract_emotion_tag(response_text)
            if emotion_tag and connected:
                try:
                    await vts.set_expression(emotion_tag)
                except Exception as e:
                    log.warning(f"表情制御エラー（処理は継続）: {e}")

            # 4. 音声合成と再生
            clean_text = bii.clean_text_for_voice(response_text)
            if clean_text:
                try:
                    voice.play_voice(clean_text)
                except Exception as e:
                    log.warning(f"音声合成エラー（VOICEVOXを起動してにゃ）: {e}")

            await asyncio.sleep(OBSERVER_INTERVAL)

    except KeyboardInterrupt:
        print("\nオブザーバーモードを終了するにゃ。お疲れ様だぞ、マスター！")
    except Exception as e:
        log.error(f"予期しないエラー: {e}", exc_info=True)
    finally:
        if connected:
            try:
                await vts.disconnect()
            except Exception as e:
                log.warning(f"VTS切断中にエラー: {e}")


if __name__ == "__main__":
    asyncio.run(main())
