"""
猫使Bii・オブザーバーモード
画面を定期的にキャプチャし、Ollamaで直接処理してボク（猫使Bii）に喋らせるメインループ
"""

import asyncio
import time
import re
from vision_module import BiiVision
from bii_core import BiiCore
from voicevox_adapter import VoicevoxAdapter
from vts_adapter import VTSAdapter


# --- 設定エリア ---
OLLAMA_MODEL = "qwen2.5:7b"  # テキスト生成に使用するOllamaモデル（ローカル）
# 画像分析はGemini 2.5 Flash（クラウド）を使用
CHECK_INTERVAL = 15  # 何秒ごとに画面を見るか（最初は長めが安全だぞ）


async def main():
    """メインループ"""
    # 各モジュールの初期化
    vision = BiiVision()
    bii = BiiCore(model=OLLAMA_MODEL)  # vision_modelパラメータは削除（Geminiを使用）
    voice = VoicevoxAdapter()
    vts = VTSAdapter()

    print("=" * 60)
    print("  猫使Bii・オブザーバーモード 起動だにゃ！")
    print(f"  テキストモデル（ローカル）: {OLLAMA_MODEL}")
    print(f"  画像分析モデル（クラウド）: Gemini 2.5 Flash")
    print(f"  観察間隔: {CHECK_INTERVAL}秒")
    print("=" * 60)

    # VTSに接続
    print("\n[VTS] 接続中...")
    connected = await vts.connect()
    if not connected:
        print("[VTS] 警告: VTube Studioへの接続に失敗しました。表情制御は無効です。")
    else:
        print("[VTS] ✓ 接続完了")
        
        # VTS APIから実際にロードされている表情ファイルリストを取得してBiiCoreを更新
        print("[BiiCore] VTS APIから表情ファイルリストを取得中...")
        try:
            vts_expressions = await vts.get_expressions()
            if vts_expressions:
                bii.update_expressions_from_vts(vts_expressions)
            else:
                print("[BiiCore] 警告: VTS APIから表情リストが取得できませんでした。ファイルシステムのスキャン結果を使用します。")
        except Exception as e:
            print(f"[BiiCore] 警告: VTS APIからの表情リスト取得に失敗しました: {e}")
            print("[BiiCore] ファイルシステムのスキャン結果を使用します。")

    try:
        while True:
            print(f"\n[観察中...] ({time.strftime('%H:%M:%S')})")
            
            # 1. アクティブウィンドウをキャプチャ（Base64形式、デバッグ画像も保存、ウィンドウタイトルも取得）
            print("[Vision] アクティブウィンドウをキャプチャ中...")
            img_base64, window_title = vision.capture_screen(scale=0.7, save_debug=True)
            print(f"[Vision] ✓ キャプチャ完了（debug_vision.pngに保存済み、ウィンドウ: {window_title}）")
            
            # 2. ボク（Bii）の「脳」で画面を分析（ウィンドウタイトルも渡してメタ情報として活用）
            print("[BiiCore] 画面を分析中...")
            response_text = bii.observe_screen(img_base64, window_title=window_title, user_input=None)
            print(f"[BiiCore] ✓ 分析完了")
            print(f"Biiの気づき: {response_text}")

            # 3. 感情タグの抽出と表情制御
            emotion_tag = bii.extract_emotion_tag(response_text)
            if emotion_tag and connected:
                print(f"[VTS] 表情を設定: {emotion_tag}")
                try:
                    # set_expressionを使用（重複送信防止と自動再接続機能が含まれる）
                    await vts.set_expression(emotion_tag)
                except Exception as vts_error:
                    # VTS操作時のエラー（WebSocket no close frame等）でメインループが止まらないよう例外処理
                    print(f"[VTS] 警告: 表情制御中にエラーが発生しましたが、処理を継続します: {vts_error}")

            # 4. 音声合成と再生（コードブロックとURLを除去して喋るにゃ）
            clean_text = bii.clean_text_for_voice(response_text)
            
            if clean_text:
                print(f"[Voice] 音声合成中: {clean_text[:50]}...")
                try:
                    voice.play_voice(clean_text)
                    print("[Voice] ✓ 音声再生完了")
                except Exception as e:
                    print(f"[Voice] 警告: 音声合成中にエラーが発生しました（チャットは継続します）: {e}")
                    print(f"[Voice] （声が出せないにゃ、VOICEVOXソフトを起動してにゃ）")

            # 次の巡回まで待機
            print(f"\n[待機] {CHECK_INTERVAL}秒後に次の観察を行います...")
            await asyncio.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("オブザーバーモードを終了するにゃ。お疲れ様だぞ、マスター！")
        print("=" * 60)
    except Exception as e:
        print(f"\n[エラー] 予期しないエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # VTS接続を切断（エラーハンドリング強化）
        if connected:
            try:
                print("\n[VTS] 接続を切断中...")
                await vts.disconnect()
                print("[VTS] ✓ 切断完了")
            except Exception as disconnect_error:
                # WebSocketエラー（no close frame等）でメインループが止まらないよう例外処理
                print(f"[VTS] 警告: 切断中にエラーが発生しましたが、処理を継続します: {disconnect_error}")


if __name__ == "__main__":
    asyncio.run(main())

