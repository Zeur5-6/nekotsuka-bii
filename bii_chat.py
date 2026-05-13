import asyncio
import re
import json
import websockets
from bii_core import BiiCore
from voicevox_adapter import VoicevoxAdapter
from vts_adapter import VTSAdapter

async def main():
    # コアの初期化
    bii = BiiCore()
    voice = VoicevoxAdapter()
    vts = VTSAdapter()
    ws = None
    
    async def connect_live2d_server():
        nonlocal ws
        try:
            ws = await websockets.connect("ws://localhost:8765")
            print("[Live2D] ✓ サーバー接続完了")
        except Exception as e:
            ws = None
            print(f"[Live2D] 警告: サーバーに接続できません: {e}")
    
    async def send_speak(text: str):
        if not text or not text.strip():
            return False
        if ws is None:
            await connect_live2d_server()
            if ws is None:
                return False
        try:
            await ws.send(json.dumps({"type": "speak", "text": text}))
            return True
        except Exception:
            try:
                await connect_live2d_server()
                if ws is None:
                    return False
                await ws.send(json.dumps({"type": "speak", "text": text}))
                return True
            except Exception:
                return False
    
    print("==========================================")
    print("   Bii・対話テストモード（長期記憶）   ")
    print("==========================================")
    
    # Live2Dサーバーに接続（音声とリップシンクはサーバー側で実行）
    await connect_live2d_server()
    
    # VTSに接続
    print("\n[VTS] 接続中...")
    connected = await vts.connect()
    if not connected:
        print("[VTS] 警告: VTube Studioへの接続に失敗しました。表情制御は無効です。")
        connected = False
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
        loop = asyncio.get_running_loop()
        
        # 入力用ヘルパー関数（スレッド内で実行される）
        def get_input(prompt):
            print(prompt, end="", flush=True)
            return input()
            
        while True:
            # input()はブロッキングなので、run_in_executorで別スレッドで実行してイベントループを止めないようにする
            # そうしないとWebSocketのPing/Pongがタイムアウトして切断される
            user_input = await loop.run_in_executor(None, get_input, "\nマスター: ")
            
            if user_input.lower() in ["exit", "quit", "おわり"]:
                break
                
            # コマンド処理
            if user_input.startswith("/"):
                parts = user_input[1:].strip().split(maxsplit=1)
                command = parts[0].lower()
                args = parts[1].split() if len(parts) > 1 else []
                
                result = bii.handle_command(command, args)
                if result:
                    print(f"Bii: {result}")
                    
                    # 感情タグの抽出と表情制御
                    if connected:
                        emotion_tag = bii.extract_emotion_tag(result)
                        if emotion_tag:
                            try:
                                await vts.set_expression(emotion_tag)
                            except Exception as vts_error:
                                print(f"[VTS] 警告: 表情制御中にエラーが発生しましたが、処理を継続します: {vts_error}")
                    
                    # /visionコマンドの結果は音声合成する（画面分析結果を読み上げる）
                    if command == "vision" or command == "画面" or command == "observe" or command == "観察":
                        clean_text = bii.clean_text_for_voice(result)
                        if clean_text:
                            try:
                                sent = await send_speak(clean_text)
                                if not sent:
                                    voice.play_voice(clean_text)
                            except Exception as e:
                                print(f"[Voice] 警告: 音声合成中にエラーが発生しました: {e}")
                    # その他のコマンド（/help, /historyなど）は音声合成をスキップ（長いテキストのため）
                    
                    continue
            
            # 画像なしで対話のみ実行
            print("[Debug] 生成を開始します...")
            # ここが重いので別スレッドで実行
            response = await loop.run_in_executor(None, bii.generate_response, user_input, None)
            print("[Debug] 生成完了")
            
            print(f"Bii: {response}")
            
            # 感情タグの抽出と表情制御
            if connected:
                emotion_tag = bii.extract_emotion_tag(response)
                if emotion_tag:
                    print(f"[VTS] 表情を設定: {emotion_tag}")
                    try:
                        # タイムアウト付きで実行
                        await asyncio.wait_for(vts.set_expression(emotion_tag), timeout=2.0)
                    except asyncio.TimeoutError:
                        print("[VTS] 警告: 表情設定がタイムアウトしました")
                    except Exception as vts_error:
                        print(f"[VTS] 警告: 表情制御エラー: {vts_error}")
            
            # 音声合成
            print("[Debug] 音声合成リクエスト...")
            clean_text = bii.clean_text_for_voice(response)
            if clean_text:
                try:
                    sent = await send_speak(clean_text)
                    if sent:
                        print("[Debug] 音声サーバーへ送信完了")
                    else:
                        print("[Debug] 音声サーバー送信失敗、ローカル再生を試みます")
                        voice.play_voice(clean_text)
                except Exception as e:
                    print(f"[Voice] 警告: 音声合成エラー: {e}")
                    
            print("[Debug] ループの先頭に戻ります")
    
    except KeyboardInterrupt:
        print("\n対話モードを終了するにゃ。お疲れ様だぞ、マスター！")
    finally:
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
        # VTS接続を切断
        if connected:
            try:
                print("\n[VTS] 接続を切断中...")
                await vts.disconnect()
                print("[VTS] ✓ 切断完了")
            except Exception as disconnect_error:
                print(f"[VTS] 警告: 切断中にエラーが発生しましたが、処理を継続します: {disconnect_error}")

if __name__ == "__main__":
    asyncio.run(main())
