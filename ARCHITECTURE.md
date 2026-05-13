# Bii プロジェクト - 技術者向けアーキテクチャ説明書

初めてこのプロジェクトを見る技術者が、**どこで何がどのように使われて動いているか**を理解できるよう、詳細にまとめたドキュメントです。

---

## 1. プロジェクト概要

**Bii**は、AIアシスタント「Bii」をLive2Dキャラクターとしてデスクトップ上に表示し、チャット・画面認識・音声合成・表情制御を行うシステムです。

### 主な構成要素

| 要素 | 技術 | 役割 |
|------|------|------|
| **Pythonバックエンド** | Python 3.x | AI推論、WebSocketサーバー、音声合成、画面キャプチャ |
| **Live2Dクライアント（Electron）** | Node.js / Electron / PixiJS | デスクトップ常駐のLive2D表示、UI、WebSocketクライアント |
| **Live2Dクライアント（Native）** | C++ / Cubism SDK | ネイティブ版Live2D表示（オプション） |
| **外部サービス** | VOICEVOX, Ollama, Gemini, VTube Studio | TTS、LLM、視覚API、表情制御 |

---

## 2. ディレクトリ構造と役割

```
modelfile/
├── live2d_server.py          # ★ メインサーバー（WebSocket、AI連携のハブ）
├── bii_core.py               # ★ AIの「脳」（4段階推論、会話、記憶、視覚）
├── voicevox_adapter.py       # VOICEVOX連携（TTS・リップシンク用）
├── vts_adapter.py            # VTube Studio連携（表情制御）
├── vision_module.py          # 画面キャプチャ（BiiVision）
├── bii_rag.py                # コード検索RAG（CodeReader）
├── bii_tools.py              # Web検索ツール
├── bii_chat.py               # 対話型CLI
├── bii_web.py                # Streamlit Web UI
├── bii_desktop.py            # Tkinter デスクトップUI
├── bii_observer.py           # 定期画面監視
├── requirements.txt          # Python依存関係
├── .env                      # 環境変数（GEMINI_API_KEY等）
├── bii_memory.db             # SQLite長期記憶（自動生成）
├── vts_token.json            # VTS認証トークン（自動生成）
│
├── live2d_app/               # ★ Electron版Live2Dクライアント
│   ├── main.js               # Electronメインプロセス（ウィンドウ作成）
│   ├── index.html            # HTMLシェル、PIXI/Live2D読み込み
│   ├── renderer.js           # レンダラープロセス（Live2D表示、WebSocket、UI）
│   ├── package.json          # Node.js依存関係
│   └── models/bii/           # Live2Dモデルファイル
│       └── Usa Maid/         # 例: Usa Maid.model3.json, *.exp3.json
│
├── live2d_native/            # C++版Live2Dクライアント（オプション）
│   ├── src/
│   │   ├── main.cpp          # エントリーポイント
│   │   ├── live2d_app.cpp/h  # Live2D表示ロジック
│   │   ├── websocket_client.cpp/h
│   │   ├── audio_capture.cpp/h
│   │   └── lip_sync_processor.cpp/h
│   └── sdk/CubismSdk/        # Live2D Cubism SDK
│
└── old_assets/               # 旧・実験用スクリプト（参考用）
```

---

## 3. システムアーキテクチャ図

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          クライアント層（表示・入力）                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   live2d_app (Electron)                    live2d_native (C++)                   │
│   ┌─────────────────────────────┐         ┌─────────────────────────────┐      │
│   │ main.js                      │         │ main.cpp                     │      │
│   │ ・透明ウィンドウ作成          │         │ ・Live2DApp初期化             │      │
│   │ ・IPC (minimize/close等)     │         │ ・モデル読み込み              │      │
│   └─────────────────────────────┘         └─────────────────────────────┘      │
│   ┌─────────────────────────────┐         ┌─────────────────────────────┐      │
│   │ index.html                  │         │ live2d_app.cpp               │      │
│   │ ・PIXI.js / pixi-live2d     │         │ ・Cubism SDK描画             │      │
│   │ ・Live2D Cubism Core        │         │ ・WebSocketClient            │      │
│   └─────────────────────────────┘         │ ・LipSyncProcessor            │      │
│   ┌─────────────────────────────┐         └─────────────────────────────┘      │
│   │ renderer.js                 │                                               │
│   │ ・Live2Dモデル表示           │                                               │
│   │ ・WebSocket接続(ws)         │                                               │
│   │ ・表情/リップシンク/字幕     │                                               │
│   │ ・チャット入力/視覚ボタン   │                                               │
│   └─────────────────────────────┘                                               │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                    │                                        │
                    │  WebSocket ws://localhost:8765         │
                    ▼                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    live2d_server.py（WebSocketサーバー）                           │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ handle_client() → handle_message()                                         │  │
│  │ ・user_input    → process_user_input()                                      │  │
│  │ ・vision_request→ process_vision_request()                                  │  │
│  │ ・speak        → audio_queue.put()                                          │  │
│  │ ・connect_vts   → connect_vts()                                              │  │
│  │ ・ping         → pong                                                       │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │ コンポーネント: BiiCore, VoicevoxAdapter, VTSAdapter                        │  │
│  │ 音声キュー: _audio_worker() → _play_voice_with_lipsync()                    │  │
│  │ ブロードキャスト: expression, lipsync, response, status, restore           │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           コア層（AI・外部連携）                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  bii_core.py (BiiCore)                                                           │
│  ├── generate_response()     … Ollama (qwen2.5:7b) で会話生成                      │
│  ├── handle_command()        … /vision, /memory 等コマンド処理                     │
│  ├── observe_screen()        … 画面画像 → Gemini Vision API で分析                 │
│  ├── clean_text_for_voice()  … 音声化用テキストのクリーニング                       │
│  ├── vision (BiiVision)     … 画面キャプチャ                                      │
│  ├── code_reader (CodeReader)… セマンティックコード検索                            │
│  ├── long_term_memory        … SQLite (bii_memory.db)                             │
│  └── emotion_files           … VTS表情ファイルとのマッピング                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│  voicevox_adapter.py                                                             │
│  └── audio_query → synthesis → pygame再生、viseme列生成                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│  vts_adapter.py                                                                   │
│  └── WebSocket(ws://localhost:8001) → 表情・モーション制御                         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 各コンポーネントの詳細

### 4.1 live2d_server.py（サーバーハブ）

**役割**: WebSocketサーバーとして、クライアントとAI・音声・表情制御を仲介する。

| メソッド/処理 | 呼び出し元 | 処理内容 |
|---------------|------------|----------|
| `init_components()` | `run()` | BiiCore, VoicevoxAdapter, VTSAdapter を初期化 |
| `handle_client()` | websockets.serve | クライアント接続時に呼ばれ、`handle_message()` でメッセージを処理 |
| `process_user_input()` | `handle_message` (user_input) | BiiCore.generate_response() → 感情抽出 → 音声キュー or 応答送信 |
| `process_vision_request()` | `handle_message` (vision_request) | 画面キャプチャ → observe_screen() → 感情・音声・応答 |
| `_audio_worker()` | 起動時 | 音声キューを処理し、VOICEVOXで合成 → リップシンク送信 → 再生 |
| `_play_voice_with_lipsync()` | _audio_worker | audio_query → synthesis → viseme列 → broadcast(lipsync) → pygame再生 |
| `extract_emotion()` | process_* | 応答テキストから [Happy], [Sad] 等のタグを抽出 |
| `send_emotion()` | process_* | broadcast({ type: "expression", name }) |
| `broadcast()` | 各種 | 全接続クライアントにJSONメッセージを送信 |

**重要**: `_send_viseme_sequence()` は VOICEVOX の `accent_phrases` から母音ごとの口の開き度を計算し、60FPSで `lipsync` メッセージを送信する。

---

### 4.2 bii_core.py（AIの脳）

**役割**: 4段階推論フレームワーク、会話、記憶、視覚、コマンド処理。

| 主なメソッド | 使用箇所 | 処理内容 |
|--------------|----------|----------|
| `generate_response()` | live2d_server.process_user_input | ユーザー入力 → Ollama API → 応答テキスト |
| `handle_command()` | live2d_server.process_user_input | `/vision`, `/memory` 等のスラッシュコマンド |
| `observe_screen()` | live2d_server.process_vision_request | Base64画像 + ウィンドウタイトル → Gemini Vision API → 分析結果 |
| `clean_text_for_voice()` | live2d_server | 感情タグ等を除去してVOICEVOX用テキストに変換 |
| `vision.capture_screen()` | live2d_server | 全画面キャプチャ → Base64 + ウィンドウタイトル |
| `code_reader.search()` | 会話中 | セマンティック検索でコードを参照 |
| `update_expressions_from_vts()` | live2d_server.connect_vts | VTSの表情リストでBiiCoreの感情マッピングを更新 |

**外部依存**:
- Ollama (http://localhost:11434) … 会話LLM
- Gemini API (GEMINI_API_KEY) … 視覚分析
- SQLite (bii_memory.db) … 長期記憶

---

### 4.3 vision_module.py（BiiVision）

**役割**: 画面キャプチャ。

| メソッド | 処理 |
|----------|------|
| `capture_screen(scale, save_debug)` | `ImageGrab.grab()` で全画面キャプチャ → 384px以内にリサイズ → Base64 JPEG → `debug_vision.png` 保存 |

**使用箇所**: `live2d_server.process_vision_request()` 内で `self.bii.vision.capture_screen()` として呼ばれる。

---

### 4.4 voicevox_adapter.py

**役割**: VOICEVOX API でテキストを音声合成。

| 設定 | デフォルト |
|------|------------|
| voicevox_url | http://localhost:50021 |
| speaker_id | 58（四国めたん ノーマル） |

**使用箇所**: `live2d_server._play_voice_with_lipsync()` 内で、`audio_query` と `synthesis` を呼び、音声再生とリップシンク用の viseme 列を生成。実際の再生は pygame で行う。

---

### 4.5 vts_adapter.py

**役割**: VTube Studio (ws://localhost:8001) とWebSocketで通信し、表情・モーションを制御。

| 主なメソッド | 処理 |
|--------------|------|
| `connect()` | 認証トークン取得・保存 (vts_token.json) |
| `get_expressions()` | 利用可能な表情リスト取得 |
| `trigger_expression()` | 指定表情ファイルを実行 |
| `set_expression()` | 感情タグ (Happy, Sad等) から表情を設定 |

**使用箇所**: `live2d_server.connect_vts()` で接続し、`connect_vts` メッセージ受信時に呼ばれる。BiiCore の表情マッピング更新にも利用。

---

### 4.6 live2d_app（Electronクライアント）

#### main.js（メインプロセス）

| 処理 | 内容 |
|------|------|
| `createWindow()` | 透明・常に最前面のフレームレスウィンドウ (400x600) |
| IPC | `minimize-window`, `close-window`, `restore-window`, `move-window` 等 |

#### index.html

- PIXI.js と pixi-live2d-display (Cubism 4) を読み込み
- Live2D Cubism Core (`live2dcubismcore.min.js`) を読み込み
- `renderer.js` を読み込み

#### renderer.js（レンダラープロセス）

| 機能 | 実装 |
|------|------|
| WebSocket接続 | `ws://localhost:8765` に接続、3秒ごとに再接続 |
| メッセージ処理 | `handleMessage()` で type に応じて分岐 |
| Live2D初期化 | `initLive2D()` で PIXI.Application 作成 → `models/bii/` からモデル検索 → `Live2DModel.from()` |
| 表情 | `setExpression()` で `expressionMap` に基づき `model.expression()` を呼び出し |
| リップシンク | `lipsync` メッセージで `model.targetMouthValue` を設定、ticker で `ParamMouthOpenY` に補間適用 |
| 字幕 | `response` で `showSubtitle()`、5秒後にフェードアウト |
| チャット入力 | Enter で `user_input` 送信 |
| 視覚ボタン | `vision_request` 送信（入力欄のテキストも送信可） |
| ドラッグ | 左: モデル移動、右: ウィンドウ移動、ホイール: スケール |

---

## 5. WebSocketプロトコル

### 5.1 クライアント → サーバー

| type | パラメータ | 説明 |
|------|------------|------|
| `user_input` | `text` | チャット入力テキスト |
| `vision_request` | `text` (任意) | 画面を見せるリクエスト、オプションで補足テキスト |
| `speak` | `text` | 指定テキストを音声合成（リップシンク付き） |
| `connect_vts` | - | VTube Studio に接続 |
| `ping` | - | 接続確認 |

### 5.2 サーバー → クライアント

| type | パラメータ | 説明 |
|------|------------|------|
| `response` | `text` | AI応答テキスト（字幕表示） |
| `expression` | `name` | 表情名 (Happy, Sad, Angry, Surprised, Neutral) |
| `emotion` | `emotion` | 同上（互換） |
| `lipsync` | `value` | 口の開き度 0.0～1.0 |
| `motion` | `motion` | モーション名 |
| `status` | `status` | ステータスメッセージ |
| `restore` | - | ウィンドウ復帰（画面キャプチャ後の表示復元） |
| `pong` | - | ping への応答 |

---

## 6. データフロー（典型シーケンス）

### 6.1 チャット入力の流れ

```
1. ユーザーがチャット欄にテキスト入力 → Enter
2. renderer.js: ws.send({ type: "user_input", text })
3. live2d_server.handle_message() → process_user_input()
4. BiiCore.generate_response(user_text) → Ollama API → 応答テキスト
5. extract_emotion() → broadcast({ type: "expression", name })
6. VoicevoxAdapter 有効時:
   - audio_queue.put((display_text, voice_text))
   - _audio_worker が audio_query → synthesis
   - 再生直前に send_response(display_text) → broadcast({ type: "response", text })
   - _send_viseme_sequence() → broadcast({ type: "lipsync", value })
   - pygame で再生
7. renderer.js: expression → setExpression(), lipsync → targetMouthValue, response → showSubtitle()
```

### 6.2 視覚リクエストの流れ

```
1. ユーザーが視覚ボタン(👁️)クリック
2. renderer.js: ws.send({ type: "vision_request", text: chatInput.value })
3. live2d_server.process_vision_request()
4. broadcast({ type: "status", status: "画面を見ています..." })
5. bii.vision.capture_screen() → 全画面キャプチャ → Base64
6. broadcast({ type: "restore" }) → ウィンドウ復帰
7. bii.observe_screen(img_base64, ...) → Gemini Vision API → 分析結果
8. extract_emotion() → send_emotion()
9. 音声キュー投入 or send_response()
10. renderer.js: 表情・字幕・リップシンクを反映
```

---

## 7. 起動手順とエントリーポイント

### 7.1 標準的な起動（Electron版）

```bash
# 1. Pythonサーバー起動（プロジェクトルート）
python live2d_server.py
# → ws://localhost:8765 で待機

# 2. Electronアプリ起動
cd live2d_app
npm install   # 初回のみ
npm start
# → 透明ウィンドウにLive2Dが表示され、WebSocketでサーバーに接続
```

### 7.2 その他のエントリーポイント

| ファイル | コマンド | 用途 |
|----------|----------|------|
| bii_chat.py | `python bii_chat.py` | 対話型CLI |
| bii_web.py | `streamlit run bii_web.py` | Streamlit Web UI |
| bii_desktop.py | `python bii_desktop.py` | Tkinter デスクトップUI |
| bii_observer.py | `python bii_observer.py` | 定期画面監視 |

---

## 8. 設定ファイルと環境変数

| ファイル/変数 | 用途 |
|---------------|------|
| `.env` | `GEMINI_API_KEY`（Gemini Vision API用、必須） |
| `requirements.txt` | Python依存関係 |
| `live2d_app/package.json` | Node.js依存関係（pixi.js, pixi-live2d-display, ws, electron） |
| `vts_token.json` | VTS認証トークン（connect_vts 時に自動生成） |
| `bii_memory.db` | SQLite長期記憶（初回実行時に自動作成） |

### 外部サービス（起動が必要）

| サービス | URL/ポート | 用途 |
|----------|-----------|------|
| Ollama | http://localhost:11434 | 会話LLM (qwen2.5:7b) |
| VOICEVOX | http://localhost:50021 | 音声合成 |
| VTube Studio | ws://localhost:8001 | 表情・モーション（オプション） |

---

## 9. Live2Dモデル配置

**Electron版** (`live2d_app`):

```
live2d_app/models/bii/
├── Usa Maid/                    # モデル名でディレクトリ
│   ├── Usa Maid.model3.json     # メインモデル
│   ├── *.moc3                   # モデルデータ
│   ├── *.png                    # テクスチャ
│   ├── happy.exp3.json          # 表情（オプション）
│   ├── sad.exp3.json
│   └── ...
```

`renderer.js` は `models/bii/` を走査し、`*.model3.json` または `{モデル名}/{モデル名}.model3.json` を探す。

**Native版**: `live2d_native/src/main.cpp` で相対パス `../../../live2d_app/models/bii/Usa Maid/Usa Maid.model3.json` を参照。

---

## 10. トラブルシューティングのヒント

| 現象 | 確認ポイント |
|------|--------------|
| 接続できない | `live2d_server.py` が先に起動しているか、ポート8765が空いているか |
| モデルが表示されない | `live2d_app/models/bii/` に `.model3.json` があるか、パスが正しいか |
| 音声が出ない | VOICEVOX が起動しているか、VoicevoxAdapter の URL/speaker_id |
| 視覚が動かない | GEMINI_API_KEY が .env に設定されているか |
| 表情が変わらない | モデルに `.exp3.json` が含まれているか、expressionMap の名前が一致しているか |

---

## 11. 依存関係サマリ

### Python (requirements.txt)

- **サーバー・AI**: requests, python-dotenv, google-genai, sentence-transformers, numpy
- **画像**: Pillow, pyautogui, pygetwindow
- **音声・通信**: websockets, pygame, pyaudio, SpeechRecognition
- **Web UI**: streamlit

### Node.js (live2d_app/package.json)

- pixi.js, pixi-live2d-display, ws（本番）
- electron（devDependencies）

### Native (live2d_native)

- Live2D Cubism SDK 5-r.4.1
- OpenGL, WinSock (ws2_32), Windows API

---

*このドキュメントはプロジェクトの現状に基づいて作成されています。実装の変更に応じて更新してください。*
