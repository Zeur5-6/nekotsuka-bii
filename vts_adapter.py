"""
VTube Studio API アダプター
WebSocket 経由で VTube Studio の表情を制御するクラス

感情タグ → 表情ファイルのマッピングは固定値ではなく、VTS API から取得した
実際のファイルリスト（get_expressions）を基に emotion_utils で動的に構築する。
これにより shock.exp3.json / surprised.exp3.json のような命名差を吸収できる。
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import websockets

from config import VTS_TOKEN_FILE, VTS_URL, get_logger
from emotion_utils import build_emotion_to_file_map, normalize_tag_name

log = get_logger("VTSAdapter")

PLUGIN_NAME = "Bii-Lab-Assistant"
PLUGIN_DEVELOPER = "Master"


class VTSAdapter:
    """VTube Studio API を使用して表情とモーションを制御するアダプター

    注意: VTube Studio 側で「APIを有効にする」設定が必要。
    設定方法: VTube Studio → 設定 → API → 「APIを有効にする」を ON

    主な機能:
    - connect(): 接続と認証（トークンはファイルに保存して再利用）
    - get_expressions(): 表情ファイル一覧を取得し、タグ→ファイルの対応を更新
    - set_expression(emotion_tag): 感情タグに対応する表情を設定
    - trigger_expression(expression_file): 表情ファイルを直接実行
    - clear_expressions(): 全ての表情をリセット
    - set_hotkey(hotkey_name): ホットキーのモーションを実行
    """

    def __init__(self, vts_url: str = None):
        self.vts_url = vts_url or VTS_URL
        self.websocket = None
        self.auth_token: Optional[str] = None
        self.is_connected = False
        self.current_expression: Optional[str] = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

        # 感情タグ → Expressionファイル の初期マッピング。
        # get_expressions() 実行時に実際のファイルリストで上書きされる。
        self.emotion_to_expression: Dict[str, Optional[str]] = {
            "Happy": "happy.exp3.json",
            "Sad": "sad.exp3.json",
            "Angry": "angry.exp3.json",
            "Surprised": "surprised.exp3.json",
            "Neutral": None,  # Neutral は全表情リセット
        }

    # ------------------------------------------------------------------
    # 認証トークン
    # ------------------------------------------------------------------

    def _load_token(self) -> Optional[str]:
        token_path = Path(VTS_TOKEN_FILE)
        if token_path.exists():
            try:
                with open(token_path, 'r', encoding='utf-8') as f:
                    return json.load(f).get('authenticationToken')
            except Exception as e:
                log.warning(f"トークンファイルの読み込みに失敗: {e}")
        return None

    def _save_token(self, token: str):
        try:
            with open(VTS_TOKEN_FILE, 'w', encoding='utf-8') as f:
                json.dump({'authenticationToken': token}, f, indent=2)
            log.info(f"認証トークンを保存しました: {VTS_TOKEN_FILE}")
        except Exception as e:
            log.warning(f"トークンの保存に失敗: {e}")

    # ------------------------------------------------------------------
    # 低レベル通信
    # ------------------------------------------------------------------

    async def _send_request(self, request_type: str,
                            data: Dict[str, Any] = None) -> Dict[str, Any]:
        """VTube Studio にリクエストを送信してレスポンスを返す"""
        if not self.websocket:
            raise ConnectionError(
                "WebSocketが接続されていません。先にconnect()を呼び出してください。")

        try:
            request = {
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "requestID": f"req_{int(time.time() * 1000)}",
                "messageType": request_type,
                "data": data or {},
            }
            await self.websocket.send(json.dumps(request))
            response = await self.websocket.recv()
            return json.loads(response)

        except (websockets.exceptions.ConnectionClosed,
                websockets.exceptions.InvalidState) as e:
            error_code = getattr(e, 'code', None)
            log.warning(f"WebSocket接続が閉じられました (code: {error_code}): {e}")
            self.is_connected = False
            self.websocket = None

            # Protocol Error 1002 等は自動再接続を試行
            if error_code == 1002 or isinstance(e, websockets.exceptions.ConnectionClosed):
                if self.reconnect_attempts < self.max_reconnect_attempts:
                    log.info(f"自動再接続を試行 "
                             f"({self.reconnect_attempts + 1}/{self.max_reconnect_attempts})...")
                    if await self._reconnect():
                        self.reconnect_attempts = 0
                        return await self._send_request(request_type, data)
                    self.reconnect_attempts += 1
                else:
                    log.warning("最大再接続試行回数に達しました")
                    self.reconnect_attempts = 0
            raise
        except Exception as e:
            log.warning(f"WebSocket操作中にエラー: {e}")
            raise

    async def _reconnect(self) -> bool:
        try:
            log.info("再接続中...")
            if self.websocket:
                try:
                    await self.websocket.close()
                except Exception:
                    pass
            self.websocket = None
            self.is_connected = False
            return await self.connect()
        except Exception as e:
            log.error(f"再接続に失敗: {e}")
            return False

    # ------------------------------------------------------------------
    # 接続・認証
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """VTube Studio に接続し、認証を行う（2段階認証フロー）"""
        try:
            log.info(f"VTube Studioに接続中: {self.vts_url}")
            self.websocket = await websockets.connect(self.vts_url)
            self.is_connected = True
            self.reconnect_attempts = 0

            self.auth_token = self._load_token()

            # ケース1: 保存済みトークンで認証
            if self.auth_token:
                response = await self._send_request(
                    "AuthenticationRequest",
                    {"pluginName": PLUGIN_NAME,
                     "pluginDeveloper": PLUGIN_DEVELOPER,
                     "authenticationToken": self.auth_token})
                if response.get("data", {}).get("authenticated"):
                    log.info("認証成功（既存トークン）")
                    return True
                log.info("既存トークンが無効でした。新規認証を行います...")
                self.auth_token = None

            # ケース2: 新規トークン取得（VTS側で「許可」ボタンを押す必要あり）
            log.info("新規認証トークンを要求中。VTube Studio側で認証を許可してください。")
            token_response = await self._send_request(
                "AuthenticationTokenRequest",
                {"pluginName": PLUGIN_NAME, "pluginDeveloper": PLUGIN_DEVELOPER})

            new_token = token_response.get("data", {}).get("authenticationToken")
            if not new_token:
                message = token_response.get("data", {}).get(
                    "message", "トークンの取得に失敗しました")
                log.error(f"{message} — VTS側の「APIを有効にする」設定と"
                          f"認証ダイアログの「許可」を確認してください")
                return False

            self.auth_token = new_token
            self._save_token(new_token)

            auth_response = await self._send_request(
                "AuthenticationRequest",
                {"pluginName": PLUGIN_NAME,
                 "pluginDeveloper": PLUGIN_DEVELOPER,
                 "authenticationToken": self.auth_token})
            if auth_response.get("data", {}).get("authenticated"):
                log.info("認証成功")
                return True
            log.error(auth_response.get("data", {}).get("message", "認証に失敗しました"))
            return False

        except websockets.exceptions.InvalidURI:
            log.error(f"無効なURLです: {self.vts_url}")
            self.is_connected = False
            return False
        except ConnectionRefusedError:
            log.error("VTube Studioへの接続が拒否されました。"
                      "VTSが起動しているか、APIが有効か確認してください。")
            self.is_connected = False
            return False
        except Exception as e:
            log.error(f"接続中にエラー: {e}")
            self.is_connected = False
            return False

    # ------------------------------------------------------------------
    # 表情制御
    # ------------------------------------------------------------------

    async def get_expressions(self) -> List[Dict[str, Any]]:
        """利用可能な Expression ファイルのリストを取得し、
        感情タグ → ファイルのマッピングを実際のファイルリストで更新する"""
        if not self.is_connected or not self.websocket:
            log.error("VTube Studioに接続されていません")
            return []

        try:
            expressions = await self._get_expressions_internal()
            if expressions:
                files = [e.get("file") for e in expressions if e.get("file")]
                self.emotion_to_expression = build_emotion_to_file_map(files)
                log.info(f"利用可能な表情: {len(expressions)}個 / "
                         f"タグ対応: { {k: v for k, v in self.emotion_to_expression.items()} }")
            else:
                log.warning("利用可能な表情が見つかりませんでした")
            return expressions
        except Exception as e:
            log.error(f"表情リストの取得中にエラー: {e}")
            return []

    async def set_expression(self, emotion_tag: str) -> bool:
        """感情タグに対応する表情を設定する（重複送信防止付き）"""
        if not self.is_connected or not self.websocket:
            log.error("VTube Studioに接続されていません")
            return False

        emotion_tag = normalize_tag_name(emotion_tag)

        # Neutral は全表情リセット
        if emotion_tag == "Neutral":
            if self.current_expression == "Neutral":
                return True
            result = await self.clear_expressions()
            if result:
                self.current_expression = "Neutral"
            return result

        expression_file = self.emotion_to_expression.get(emotion_tag)
        if not expression_file:
            log.warning(f"未対応の感情タグです: {emotion_tag} "
                        f"(対応済み: {list(self.emotion_to_expression)})")
            return False

        # 前回と同じ表情なら送信しない（VTS側の負荷軽減）
        if self.current_expression == emotion_tag:
            return True

        result = await self.trigger_expression(expression_file)
        if result:
            self.current_expression = emotion_tag
        return result

    async def trigger_expression(self, expression_file: str) -> bool:
        """指定された Expression ファイルを実行する"""
        if not self.is_connected or not self.websocket:
            log.error("VTube Studioに接続されていません")
            return False
        if not expression_file or not expression_file.strip():
            log.error("Expressionファイル名が指定されていません")
            return False

        expression_file = expression_file.strip()

        try:
            # 実際にロードされているファイルか検証（同時にタグ対応も更新される）
            expressions = await self.get_expressions()
            available = [e.get("file") for e in expressions if e.get("file")]
            if expression_file not in available:
                log.error(f"Expressionファイル '{expression_file}' が見つかりません。"
                          f"利用可能: {available}")
                return False

            await self._reset_all_expressions()

            response = await self._send_request(
                "ExpressionActivationRequest",
                {"expressionFile": expression_file, "active": True})

            data = response.get("data", {})
            has_error = data.get("errorID") is not None
            if response.get("messageType") == "ExpressionActivationResponse" and not has_error:
                log.info(f"表情を実行しました: {expression_file}")
                return True

            message = data.get("message", "表情の実行に失敗しました")
            log.error(f"{message} (errorID: {data.get('errorID', '')})")
            return False

        except Exception as e:
            log.error(f"表情の実行中にエラー: {e}")
            return False

    async def trigger_expression_timed(self, expression_file: str,
                                       duration: float = 5.0) -> bool:
        """表情を実行し、指定時間後に自動でリセットする"""
        if not self.is_connected or not self.websocket:
            log.error("VTube Studioに接続されていません")
            return False

        success = await self.trigger_expression(expression_file)
        if success:
            async def auto_reset():
                await asyncio.sleep(duration)
                await self.clear_expressions()
                log.info(f"{duration}秒経過後、表情をリセットしました")
            asyncio.create_task(auto_reset())
        return success

    async def clear_expressions(self) -> bool:
        """現在適用されている全ての表情をオフにする"""
        if not self.is_connected or not self.websocket:
            log.error("VTube Studioに接続されていません")
            return False
        try:
            result = await self._reset_all_expressions()
            if result:
                log.info("全ての表情をリセットしました")
            return result
        except (websockets.exceptions.ConnectionClosed,
                websockets.exceptions.InvalidState) as e:
            log.warning(f"WebSocketエラーが発生しましたが処理を継続します: {e}")
            self.is_connected = False
            self.websocket = None
            return False
        except Exception as e:
            log.error(f"表情のリセット中にエラー: {e}")
            return False

    async def set_hotkey(self, hotkey_name: str) -> bool:
        """指定されたホットキー名のモーションを実行する"""
        if not self.is_connected or not self.websocket:
            log.error("VTube Studioに接続されていません")
            return False
        if not hotkey_name or not hotkey_name.strip():
            log.error("ホットキー名が指定されていません")
            return False

        try:
            response = await self._send_request(
                "HotkeyTriggerRequest", {"hotkeyID": hotkey_name})
            if response.get("messageType") == "HotkeyTriggerResponse":
                log.info(f"モーションを実行しました: {hotkey_name}")
                return True
            log.error(response.get("data", {}).get("message", "モーションの実行に失敗"))
            return False
        except Exception as e:
            log.error(f"モーションの実行中にエラー: {e}")
            return False

    # ------------------------------------------------------------------
    # 内部処理
    # ------------------------------------------------------------------

    async def _get_expressions_internal(self) -> List[Dict[str, Any]]:
        """表情リスト取得の内部実装（マッピング更新なし・無限ループ回避用）"""
        if not self.is_connected or not self.websocket:
            return []
        try:
            response = await self._send_request("ExpressionStateRequest")
            return response.get("data", {}).get("expressions", [])
        except Exception as e:
            log.warning(f"表情リストの取得中にエラー: {e}")
            return []

    async def _reset_all_expressions(self) -> bool:
        """アクティブな表情を個別に無効化する"""
        try:
            expressions = await self._get_expressions_internal()
            active = [e for e in expressions if e.get("active", False)]
            if not active:
                return True

            success = True
            for expr in active:
                file_name = expr.get("file")
                if not file_name:
                    continue
                try:
                    response = await self._send_request(
                        "ExpressionActivationRequest",
                        {"expressionFile": file_name, "active": False})
                    data = response.get("data", {})
                    if (response.get("messageType") != "ExpressionActivationResponse"
                            or data.get("errorID") is not None):
                        success = False
                except Exception as e:
                    log.warning(f"表情 '{file_name}' のリセットに失敗: {e}")
                    success = False
            return success
        except Exception as e:
            log.warning(f"表情のリセット中にエラー: {e}")
            return True

    # ------------------------------------------------------------------
    # 切断・コンテキストマネージャ
    # ------------------------------------------------------------------

    async def disconnect(self):
        """VTube Studio との接続を切断する"""
        if self.websocket:
            try:
                await self.websocket.close()
                log.info("接続を切断しました")
            except Exception as e:
                log.warning(f"切断中にエラーが発生しましたが処理を継続します: {e}")
            finally:
                self.websocket = None
                self.is_connected = False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


# ==========================================
# 使用例・手動テスト
# ==========================================
async def test_vts_adapter():
    """VTSAdapter の手動テスト（VTube Studio 起動時のみ動作）"""
    async with VTSAdapter() as vts:
        if not vts.is_connected:
            print("接続に失敗しました。テストを終了します。")
            return

        expressions = await vts.get_expressions()
        print(f"{len(expressions)}個の表情が見つかりました")

        for emotion in ["Happy", "Surprised", "Sad", "Angry", "Neutral"]:
            print(f"{emotion} の表情を設定中...")
            ok = await vts.set_expression(emotion)
            print("  ✓ 成功" if ok else "  ✗ 失敗")
            await asyncio.sleep(1)

        await vts.clear_expressions()
        print("テスト完了")


if __name__ == "__main__":
    asyncio.run(test_vts_adapter())
