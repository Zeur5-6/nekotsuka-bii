"""
Bii・CLI対話モード
"""
import asyncio
import json

import websockets

from bii_core import BiiCore
from config import LIVE2D_WS_URL, get_logger
from voicevox_adapter import VoicevoxAdapter
from vts_adapter import VTSAdapter

log = get_logger("BiiChat")


async def main():
    bii = BiiCore()
    voice = VoicevoxAdapter()
    vts = VTSAdapter()
    ws = None
    loop = asyncio.get_running_loop()

    async def connect_live2d_server():
        nonlocal ws
        try:
            ws = await websockets.connect(LIVE2D_WS_URL)
            print("[Live2D] ✓ サーバー接続完了")
        except Exception as e:
            ws = None
            log.warning(f"Live2Dサーバーに接続できません: {e}")

    async def send_speak(text: str) -> bool:
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

    async def speak_and_express(response: str):
        """表情制御と音声合成を実行する共通処理"""
        if connected:
            emotion_tag = bii.extract_emotion_tag(response)
            if emotion_tag:
                try:
                    await asyncio.wait_for(vts.set_expression(emotion_tag), timeout=2.0)
                except asyncio.TimeoutError:
                    log.warning("表情設定がタイムアウトしました")
                except Exception as e:
                    log.warning(f"表情制御エラー: {e}")

        clean_text = bii.clean_text_for_voice(response)
        if clean_text:
            try:
                sent = await send_speak(clean_text)
                if not sent:
                    voice.play_voice(clean_text)
            except Exception as e:
                log.warning(f"音声合成エラー: {e}")

    print("==========================================")
    print("   Bii・対話モード（長期記憶）   ")
    print("==========================================")

    # Live2Dサーバーに接続（音声とリップシンクはサーバー側で実行）
    await connect_live2d_server()

    # VTSに接続
    print("\n[VTS] 接続中...")
    connected = await vts.connect()
    if not connected:
        log.warning("VTube Studioへの接続に失敗。表情制御は無効です。")
    else:
        print("[VTS] ✓ 接続完了")
        try:
            vts_expressions = await vts.get_expressions()
            if vts_expressions:
                bii.update_expressions_from_vts(vts_expressions)
        except Exception as e:
            log.warning(f"VTS表情リストの取得に失敗: {e}")

    try:
        def get_input(prompt):
            print(prompt, end="", flush=True)
            return input()

        while True:
            # input() はブロッキングなので executor で実行してイベントループを守る
            # （止めると WebSocket の Ping/Pong がタイムアウトして切断される）
            user_input = await loop.run_in_executor(None, get_input, "\nマスター: ")

            if user_input.lower() in ["exit", "quit", "おわり"]:
                break

            # コマンド処理（/vision などは重いので executor で実行）
            parsed = BiiCore.parse_command(user_input)
            if parsed:
                command, args = parsed
                result = await loop.run_in_executor(
                    None, bii.handle_command, command, args)
                if result:
                    print(f"Bii: {result}")
                    # /vision の結果だけ音声合成する（/help 等は長いのでスキップ）
                    if command in ("vision", "画面", "observe", "観察"):
                        await speak_and_express(result)
                    elif connected:
                        emotion_tag = bii.extract_emotion_tag(result)
                        if emotion_tag:
                            try:
                                await vts.set_expression(emotion_tag)
                            except Exception as e:
                                log.warning(f"表情制御エラー: {e}")
                    continue

            # 通常の対話（LLM生成は重いので executor で実行）
            response = await loop.run_in_executor(
                None, bii.generate_response, user_input)
            print(f"Bii: {response}")
            await speak_and_express(response)

    except KeyboardInterrupt:
        print("\n対話モードを終了するにゃ。お疲れ様だぞ、マスター！")
    finally:
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
        if connected:
            try:
                await vts.disconnect()
            except Exception as e:
                log.warning(f"VTS切断中にエラー: {e}")


if __name__ == "__main__":
    asyncio.run(main())
