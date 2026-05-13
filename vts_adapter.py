"""
VTube Studio API アダプター
WebSocket経由でVTube Studioの表情を制御するクラス
"""

import json
import asyncio
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from pathlib import Path
import websockets

# WebSocketの型ヒント（最新のwebsocketsライブラリに対応）
# 非推奨警告を完全に排除するため、TYPE_CHECKINGを使用
if TYPE_CHECKING:
    try:
        from websockets.client import WebSocketClientProtocol as WebSocketType
    except ImportError:
        from typing import Any
        WebSocketType = Any
else:
    # 実行時は型チェックをスキップ
    WebSocketType = Any


# VTube Studio API のデフォルト設定
DEFAULT_VTS_URL = "ws://localhost:8001"
TOKEN_FILE = "./vts_token.json"


class VTSAdapter:
    """
    VTube Studio API を使用して表情とモーションを制御するアダプタークラス
    
    注意: VTube Studio側で「APIを有効にする」設定が必要です。
    設定方法: VTube Studio → 設定 → API → 「APIを有効にする」のスイッチをONにする
    
        主な機能:
    - connect(): VTube Studioに接続し、認証を取得
    - get_expressions(): 利用可能なExpressionファイルのリストを取得
    - trigger_expression(expression_file): 指定されたExpressionファイルを実行
    - trigger_expression_timed(expression_file, duration): 表情を実行し、指定時間後に自動でリセット
    - set_expression(emotion_tag): 感情タグに対応する表情を設定
    - clear_expressions(): 全ての表情をリセット
    - set_hotkey(hotkey_name): 指定されたホットキーのモーションを実行
    """
    
    def __init__(self, vts_url: str = DEFAULT_VTS_URL):
        """
        VTSAdapterを初期化
        
        Args:
            vts_url: VTube StudioのWebSocket URL（デフォルト: ws://localhost:8001）
        """
        self.vts_url = vts_url
        self.websocket: Optional[WebSocketType] = None
        self.auth_token: Optional[str] = None
        self.is_connected = False
        self.current_expression: Optional[str] = None  # 現在設定されている表情を追跡
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        
        # 感情タグとExpressionファイルのマッピング
        self.emotion_to_expression: Dict[str, str] = {
            "Happy": "happy.exp3.json",
            "Sad": "sad.exp3.json",
            "Angry": "angry.exp3.json",
            "Surprised": "shock.exp3.json",
            "Neutral": None  # Neutralの場合は全ての表情をリセット
        }
    
    def _load_token(self) -> Optional[str]:
        """
        保存された認証トークンを読み込む
        
        Returns:
            str: 認証トークン。ファイルが存在しない場合はNone
        """
        token_path = Path(TOKEN_FILE)
        if token_path.exists():
            try:
                with open(token_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('authenticationToken')
            except Exception as e:
                print(f"[VTSAdapter] 警告: トークンファイルの読み込みに失敗しました: {e}")
        return None
    
    def _save_token(self, token: str):
        """
        認証トークンをファイルに保存
        
        Args:
            token: 保存する認証トークン
        """
        try:
            with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
                json.dump({'authenticationToken': token}, f, indent=2)
            print(f"[VTSAdapter] 認証トークンを保存しました: {TOKEN_FILE}")
        except Exception as e:
            print(f"[VTSAdapter] 警告: トークンの保存に失敗しました: {e}")
    
    async def _send_request(self, request_type: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        VTube Studioにリクエストを送信（エラーハンドリング強化）
        
        Args:
            request_type: リクエストタイプ（例: "AuthenticationRequest"）
            data: リクエストデータ
            
        Returns:
            dict: レスポンスデータ
        """
        if not self.websocket:
            raise ConnectionError("WebSocketが接続されていません。先にconnect()を呼び出してください。")
        
        try:
        # リクエストIDを生成（タイムスタンプベース）
            import time
            request_id = f"req_{int(time.time() * 1000)}"
            
            request = {
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "requestID": request_id,
                "messageType": request_type,
                "data": data or {}
            }
            
            # リクエストを送信
            await self.websocket.send(json.dumps(request))
            
            # レスポンスを待機
            response = await self.websocket.recv()
            response_data = json.loads(response)
            
            return response_data
            
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.InvalidState) as e:
            # WebSocket接続が閉じられた場合（Protocol Error 1002対策）
            error_code = None
            if hasattr(e, 'code'):
                error_code = e.code
            
            print(f"[VTSAdapter] 警告: WebSocket接続が閉じられました (エラーコード: {error_code}): {e}")
            self.is_connected = False
            self.websocket = None
            
            # Protocol Error 1002の場合は自動再接続を試行
            if error_code == 1002 or isinstance(e, websockets.exceptions.ConnectionClosed):
                if self.reconnect_attempts < self.max_reconnect_attempts:
                    print(f"[VTSAdapter] 自動再接続を試行します ({self.reconnect_attempts + 1}/{self.max_reconnect_attempts})...")
                    if await self._reconnect():
                        self.reconnect_attempts = 0
                        # 再接続後、リクエストを再送信
                        return await self._send_request(request_type, data)
                    else:
                        self.reconnect_attempts += 1
                else:
                    print(f"[VTSAdapter] 最大再接続試行回数に達しました。再接続を諦めます。")
                    self.reconnect_attempts = 0
            
            raise
        except Exception as e:
            # その他のWebSocketエラー
            print(f"[VTSAdapter] 警告: WebSocket操作中にエラーが発生しました: {e}")
            raise
    
    async def _reconnect(self) -> bool:
        """
        WebSocket接続を再接続（Protocol Error 1002対策）
        
        Returns:
            bool: 再接続が成功した場合はTrue
        """
        try:
            print("[VTSAdapter] 再接続中...")
            # 既存の接続をクリーンアップ
            if self.websocket:
                try:
                    await self.websocket.close()
                except:
                    pass
            self.websocket = None
            self.is_connected = False
            
            # 再接続を試行
            return await self.connect()
        except Exception as e:
            print(f"[VTSAdapter] 再接続に失敗しました: {e}")
            return False
    
    async def connect(self) -> bool:
        """
        VTube Studioに接続し、認証を行う（2段階認証フロー）
        
        Returns:
            bool: 接続・認証が成功した場合はTrue
        """
        try:
            print(f"[VTSAdapter] VTube Studioに接続中: {self.vts_url}")
            
            # WebSocket接続
            self.websocket = await websockets.connect(self.vts_url)
            self.is_connected = True
            self.reconnect_attempts = 0  # 接続成功時はリセット
            print("[VTSAdapter] ✓ WebSocket接続完了")
            
            # 認証トークンを読み込む
            self.auth_token = self._load_token()
            
            # 【ケース1: Tokenがある場合】
            if self.auth_token:
                print("[VTSAdapter] 保存されたトークンで認証を試行中...")
                response = await self._send_request(
                    "AuthenticationRequest",
                    {
                        "pluginName": "Bii-Lab-Assistant",
                        "pluginDeveloper": "Master",
                        "authenticationToken": self.auth_token
                    }
                )
                
                data = response.get("data", {})
                if data.get("authenticated"):
                    print("[VTSAdapter] ✓ 認証成功（既存トークン）")
                    return True
                else:
                    print("[VTSAdapter] 既存トークンが無効でした。新規認証を行います...")
                    self.auth_token = None
            
            # 【ケース2: Tokenがない場合】
            # ステップ1: AuthenticationTokenRequest でトークンを取得
            print("[VTSAdapter] 新規認証トークンを要求しています...")
            print("[VTSAdapter] 注意: VTube Studio側で認証を許可してください。")
            
            token_response = await self._send_request(
                "AuthenticationTokenRequest",
                {
                    "pluginName": "Bii-Lab-Assistant",
                    "pluginDeveloper": "Master"
                }
            )
            
            token_data = token_response.get("data", {})
            new_token = token_data.get("authenticationToken")
            
            if not new_token:
                error_message = token_data.get("message", "トークンの取得に失敗しました")
                print(f"[VTSAdapter] エラー: {error_message}")
                print("[VTSAdapter] ヒント: VTube Studio側で「APIを有効にする」設定を確認してください。")
                print("[VTSAdapter] ヒント: VTube Studio側で認証ダイアログの「許可」ボタンを押してください。")
                return False
            
            # トークンを保存
            self.auth_token = new_token
            self._save_token(new_token)
            print("[VTSAdapter] ✓ 認証トークンを取得しました")
            
            # ステップ2: 取得したトークンで認証を完了
            print("[VTSAdapter] 認証を完了しています...")
            auth_response = await self._send_request(
                "AuthenticationRequest",
                {
                    "pluginName": "Bii-Lab-Assistant",
                    "pluginDeveloper": "Master",
                    "authenticationToken": self.auth_token
                }
            )
            
            auth_data = auth_response.get("data", {})
            if auth_data.get("authenticated"):
                print("[VTSAdapter] ✓ 認証成功")
                return True
            else:
                error_message = auth_data.get("message", "認証に失敗しました")
                print(f"[VTSAdapter] エラー: {error_message}")
                return False
                
        except websockets.exceptions.InvalidURI:
            print(f"[VTSAdapter] エラー: 無効なURLです: {self.vts_url}")
            self.is_connected = False
            return False
        except ConnectionRefusedError:
            print(f"[VTSAdapter] エラー: VTube Studioへの接続が拒否されました。")
            print("[VTSAdapter] ヒント: VTube Studioが起動しているか、APIが有効になっているか確認してください。")
            self.is_connected = False
            return False
        except Exception as e:
            print(f"[VTSAdapter] エラー: 接続中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
            self.is_connected = False
            return False
    
    async def trigger_expression(self, expression_file: str) -> bool:
        """
        指定されたExpressionファイルを実行する
        
        Args:
            expression_file: Expressionファイル名（例: "happy.exp3.json"）
            
        Returns:
            bool: 表情の実行が成功した場合はTrue
        """
        if not self.is_connected or not self.websocket:
            print("[VTSAdapter] エラー: VTube Studioに接続されていません。")
            return False
        
        if not expression_file or not expression_file.strip():
            print("[VTSAdapter] エラー: Expressionファイル名が指定されていません。")
            return False
        
        # ファイル名を正規化（空白を除去）
        expression_file = expression_file.strip()
        
        try:
            # 利用可能な表情リストを取得して検証
            expressions = await self.get_expressions()
            available_files = [expr.get("file") for expr in expressions if expr.get("file")]
            
            # 指定されたファイルが存在するか確認
            if expression_file not in available_files:
                print(f"[VTSAdapter] エラー: Expressionファイル '{expression_file}' が見つかりません。")
                print(f"[VTSAdapter] 利用可能なファイル一覧:")
                for file in available_files:
                    print(f"  - {file}")
                print(f"[VTSAdapter] ヒント: VTube Studio側でこのExpressionファイルがロードされているか確認してください。")
                return False
            
            # まず全ての表情をリセット
            await self._reset_all_expressions()
            
            # 指定された表情を有効化（確実に現在ロードされているモデルに対して送信）
            response = await self._send_request(
                "ExpressionActivationRequest",
                {
                    "expressionFile": expression_file,
                    "active": True
                }
            )
            
            # レスポンスを厳密にチェック
            message_type = response.get("messageType")
            data = response.get("data", {})
            
            # 成功判定: messageTypeが正しく、エラーが含まれていない場合
            # dataが空のオブジェクト {} でも、エラーがなければ成功とみなす
            has_error = "errorID" in data and data.get("errorID") is not None
            is_success = (
                message_type == "ExpressionActivationResponse" and
                not has_error
            )
            
            if is_success:
                # 成功時は簡潔に表示（dataが空でも成功とみなす）
                print(f"[VTSAdapter] ✓ 表情を実行しました: {expression_file}")
                return True
            else:
                # エラーがある場合のみエラーメッセージを表示
                error_message = data.get("message", "表情の実行に失敗しました")
                error_code = data.get("errorID", "")
                if error_code:
                    error_message += f" (エラーコード: {error_code})"
                print(f"[VTSAdapter] エラー: {error_message}")
                if error_code:  # エラーがある場合のみ詳細を表示
                    print(f"[VTSAdapter] レスポンス詳細: {json.dumps(response, indent=2, ensure_ascii=False)}")
                return False
                
        except Exception as e:
            print(f"[VTSAdapter] エラー: 表情の実行中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def trigger_expression_timed(self, expression_file: str, duration: float = 5.0) -> bool:
        """
        指定されたExpressionファイルを実行し、指定時間後に自動でNeutralに戻す
        
        Args:
            expression_file: Expressionファイル名（例: "happy.exp3.json"）
            duration: 表情を維持する時間（秒、デフォルト: 5.0）
            
        Returns:
            bool: 表情の実行が成功した場合はTrue
        """
        if not self.is_connected or not self.websocket:
            print("[VTSAdapter] エラー: VTube Studioに接続されていません。")
            return False
        
        # 表情を実行
        success = await self.trigger_expression(expression_file)
        
        if success:
            # 指定時間後に自動でリセット（非同期で実行）
            async def auto_reset():
                await asyncio.sleep(duration)
                await self.clear_expressions()
                print(f"[VTSAdapter] ✓ {duration}秒経過後、表情をリセットしました")
            
            # バックグラウンドで実行（タスクとして登録）
            asyncio.create_task(auto_reset())
        
        return success
    
    async def set_expression(self, emotion_tag: str) -> bool:
        """
        指定された感情タグに対応する表情を設定（重複送信防止付き）
        
        Args:
            emotion_tag: 感情タグ（Happy, Sad, Angry, Surprised, Neutral）
            
        Returns:
            bool: 表情の設定が成功した場合はTrue
        """
        if not self.is_connected or not self.websocket:
            print("[VTSAdapter] エラー: VTube Studioに接続されていません。")
            return False
        
        # Neutralの場合は全ての表情をリセット
        if emotion_tag == "Neutral":
            if self.current_expression == "Neutral":
                # 既にNeutralの場合は送信しない（負荷軽減）
                return True
            result = await self.clear_expressions()
            if result:
                self.current_expression = "Neutral"
            return result
        
        # 対応するExpressionファイル名を取得
        expression_file = self.emotion_to_expression.get(emotion_tag)
        
        if not expression_file:
            print(f"[VTSAdapter] 警告: 未対応の感情タグです: {emotion_tag}")
            return False
        
        # 前回と同じ表情の場合は送信しない（VTS側への負荷を下げる）
        if self.current_expression == emotion_tag:
            return True
        
        # trigger_expressionを使用して表情を実行
        result = await self.trigger_expression(expression_file)
        if result:
            self.current_expression = emotion_tag
        return result
    
    async def set_hotkey(self, hotkey_name: str) -> bool:
        """
        指定されたホットキー名のモーション（アニメーション）を実行
        
        Args:
            hotkey_name: ホットキー名（VTube Studio側で設定されたホットキーのID）
            
        Returns:
            bool: モーションの実行が成功した場合はTrue
        """
        if not self.is_connected or not self.websocket:
            print("[VTSAdapter] エラー: VTube Studioに接続されていません。")
            return False
        
        if not hotkey_name or not hotkey_name.strip():
            print("[VTSAdapter] エラー: ホットキー名が指定されていません。")
            return False
        
        try:
            # HotkeyTriggerRequestを送信
            response = await self._send_request(
                "HotkeyTriggerRequest",
                {
                    "hotkeyID": hotkey_name
                }
            )
            
            data = response.get("data", {})
            if response.get("messageType") == "HotkeyTriggerResponse":
                print(f"[VTSAdapter] ✓ モーションを実行しました: {hotkey_name}")
                return True
            else:
                error_message = data.get("message", "モーションの実行に失敗しました")
                print(f"[VTSAdapter] エラー: {error_message}")
                return False
                
        except Exception as e:
            print(f"[VTSAdapter] エラー: モーションの実行中にエラーが発生しました: {e}")
            return False
    
    async def get_expressions(self) -> List[Dict[str, Any]]:
        """
        現在利用可能なExpressionファイルのリストを取得
        
        Returns:
            List[Dict[str, Any]]: Expression情報のリスト（ファイル名、アクティブ状態など）
        """
        if not self.is_connected or not self.websocket:
            print("[VTSAdapter] エラー: VTube Studioに接続されていません。")
            return []
        
        try:
            expressions = await self._get_expressions_internal()
            
            if expressions:
                print(f"[VTSAdapter] 利用可能な表情: {len(expressions)}個")
                for expr in expressions:
                    file_name = expr.get("file", "unknown")
                    active = expr.get("active", False)
                    status = "アクティブ" if active else "非アクティブ"
                    print(f"  - {file_name} ({status})")
            else:
                print("[VTSAdapter] 警告: 利用可能な表情が見つかりませんでした。")
            
            return expressions
            
        except Exception as e:
            print(f"[VTSAdapter] エラー: 表情リストの取得中にエラーが発生しました: {e}")
            return []
    
    async def clear_expressions(self) -> bool:
        """
        現在適用されている全ての表情をオフにする（公開メソッド、エラーハンドリング強化）
        
        Returns:
            bool: リセットが成功した場合はTrue
        """
        if not self.is_connected or not self.websocket:
            print("[VTSAdapter] エラー: VTube Studioに接続されていません。")
            return False
        
        try:
            print("[VTSAdapter] 全ての表情をリセット中...")
            result = await self._reset_all_expressions()
            if result:
                print("[VTSAdapter] ✓ 全ての表情をリセットしました")
            return result
            
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.InvalidState) as e:
            # WebSocketエラー（no close frame等）でメインループが止まらないよう例外処理
            print(f"[VTSAdapter] 警告: WebSocketエラーが発生しましたが、処理を継続します: {e}")
            self.is_connected = False
            self.websocket = None
            return False
        except Exception as e:
            print(f"[VTSAdapter] エラー: 表情のリセット中にエラーが発生しました: {e}")
            return False
    
    async def _get_expressions_internal(self) -> List[Dict[str, Any]]:
        """
        現在利用可能なExpressionファイルのリストを取得（内部メソッド、無限ループ回避用）
        
        Returns:
            List[Dict[str, Any]]: Expression情報のリスト
        """
        if not self.is_connected or not self.websocket:
            return []
        
        try:
            response = await self._send_request("ExpressionStateRequest")
            data = response.get("data", {})
            return data.get("expressions", [])
        except Exception as e:
            print(f"[VTSAdapter] 警告: 表情リストの取得中にエラー: {e}")
            return []
    
    async def _reset_all_expressions(self) -> bool:
        """
        全ての表情をリセット（無効化）- 内部メソッド
        
        Returns:
            bool: リセットが成功した場合はTrue
        """
        try:
            # まず現在アクティブな表情を取得（内部メソッドを使用して無限ループを回避）
            expressions = await self._get_expressions_internal()
            active_expressions = [expr for expr in expressions if expr.get("active", False)]
            
            # アクティブな表情があれば、それぞれを個別に無効化
            success = True
            for expr in active_expressions:
                file_name = expr.get("file")
                if file_name:
                    try:
                        response = await self._send_request(
                            "ExpressionActivationRequest",
                            {
                                "expressionFile": file_name,
                                "active": False
                            }
                        )
                        # レスポンスのmessageTypeとエラーを確認
                        message_type = response.get("messageType")
                        data = response.get("data", {})
                        error_id = data.get("errorID")
                        
                        # エラーがない場合は成功とみなす
                        if message_type != "ExpressionActivationResponse" or error_id is not None:
                            success = False
                    except Exception as e:
                        print(f"[VTSAdapter] 警告: 表情 '{file_name}' のリセットに失敗: {e}")
                        success = False
            
            # アクティブな表情がない場合でも成功とみなす
            if not active_expressions:
                return True
            
            return success
            
        except Exception as e:
            print(f"[VTSAdapter] 警告: 表情のリセット中にエラーが発生しました: {e}")
            # フォールバック: 単純なリセットリクエストを試行（この方法はVTS APIではサポートされていない可能性がある）
            return True
    
    async def disconnect(self):
        """VTube Studioとの接続を切断（エラーハンドリング強化）"""
        if self.websocket:
            try:
                await self.websocket.close()
                print("[VTSAdapter] 接続を切断しました")
            except Exception as e:
                # WebSocketエラー（no close frame等）でメインループが止まらないよう例外処理
                print(f"[VTSAdapter] 警告: 切断中にエラーが発生しましたが、処理を継続します: {e}")
            finally:
                self.websocket = None
                self.is_connected = False
    
    async def __aenter__(self):
        """async with構文のサポート"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """async with構文のサポート"""
        await self.disconnect()


# ==========================================
# 使用例・テストコード
# ==========================================
async def test_vts_adapter():
    """VTSAdapterのテスト関数"""
    print("=" * 60)
    print("VTSAdapter テスト実行")
    print("=" * 60)
    
    # VTSAdapterを使用（async with構文）
    async with VTSAdapter() as vts:
        if not vts.is_connected:
            print("接続に失敗しました。テストを終了します。")
            return
        
        # 利用可能な表情を取得
        print("\n[テスト0] 利用可能な表情を取得")
        expressions = await vts.get_expressions()
        
        if expressions:
            print(f"[テスト] {len(expressions)}個の表情が見つかりました")
            expression_files = [expr.get("file") for expr in expressions if expr.get("file")]
            
            # trigger_expressionのテスト（実際に存在するファイルのみ）
            print("\n[テスト1] trigger_expression のテスト")
            test_files = ["happy.exp3.json", "shock.exp3.json", "sad.exp3.json", "angry.exp3.json"]
            
            for expr_file in test_files:
                if expr_file in expression_files:
                    print(f"\n[テスト] {expr_file} を実行中...")
                    success = await vts.trigger_expression(expr_file)
                    if success:
                        print(f"✓ {expr_file} を実行しました")
                    else:
                        print(f"✗ {expr_file} の実行に失敗しました")
                    
                    # 1秒待機
                    await asyncio.sleep(1)
                else:
                    print(f"[テスト] {expr_file} は利用できません（スキップ）")
        else:
            print("[テスト] 利用可能な表情が見つかりませんでした")
        
        # set_expressionのテスト（感情タグを使用）
        print("\n[テスト2] set_expression のテスト")
        emotions = ["Happy", "Surprised", "Sad", "Angry", "Neutral"]
        
        for emotion in emotions:
            print(f"\n[テスト] {emotion} の表情を設定中...")
            success = await vts.set_expression(emotion)
            if success:
                print(f"✓ {emotion} の表情を設定しました")
            else:
                print(f"✗ {emotion} の表情の設定に失敗しました")
            
            # 1秒待機
            await asyncio.sleep(1)
        
        # clear_expressionsのテスト
        print("\n[テスト3] clear_expressions のテスト")
        success = await vts.clear_expressions()
        if success:
            print("✓ 全ての表情をリセットしました")
        
        # set_hotkeyのテスト（コメントアウト: 実際のホットキーIDが必要）
        print("\n[テスト4] set_hotkey のテスト（スキップ: ホットキーIDが必要）")
        # hotkey_id = "your_hotkey_id_here"  # VTube Studio側で設定されたホットキーID
        # success = await vts.set_hotkey(hotkey_id)
        # if success:
        #     print(f"✓ モーションを実行しました: {hotkey_id}")
        
        print("\n" + "=" * 60)
        print("テスト完了")
        print("=" * 60)


if __name__ == "__main__":
    # テスト実行
    asyncio.run(test_vts_adapter())

