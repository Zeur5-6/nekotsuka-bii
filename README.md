# Bii

デスクトップ常駐型 AI アシスタント。ローカル LLM とクラウド Vision API のハイブリッド構成で、
画面認識・音声合成・Live2D モデルの表情制御をリアルタイムに連携させます。

---

## 概要

「Bii」は、次の要素を 1 つのシステムに統合した個人用 AI デスクトップアシスタントです。

- **ローカル推論** — Ollama 上の `qwen2.5` によるオフライン対話
- **クラウド Vision** — Gemini API によるスクリーンショット解析
- **Live2D キャラクター** — VTube Studio API / Electron 直接レンダリング
- **音声合成** — VOICEVOX によるリップシンク付き読み上げ
- **長期記憶** — SQLite + Sentence Transformers によるセマンティック検索

---

## アーキテクチャ

```
┌─────────────────────────────────────────────┐
│                  bii_core.py                │
│  ツール自律選択 (tool calling) → 応答生成    │
│  長期記憶 (SQLite/WAL)  /  RAG (SBERT)      │
│  画面分析 (Gemini Vision API)               │
└────┬──────────┬──────────┬──────────────────┘
     │          │          │
     ▼          ▼          ▼
bii_chat.py  bii_web.py  bii_observer.py   bii_desktop.py
 CLI 対話     Streamlit   自動画面観察       Tkinter UI
                 │
                 ▼
        live2d_server.py  ─── WebSocket ───▶  live2d_app/
         (Python WS サーバー)                  (Electron + Live2D)
                 │
          VoicevoxAdapter ──▶ VOICEVOX (localhost:50021)
          VTSAdapter      ──▶ VTube Studio (localhost:8001)
```

---

## 主な機能

| 機能 | 実装 |
|------|------|
| **ツール自律選択** | Web検索・コード検索の要否を LLM 自身が判断（Ollama tool calling、非対応モデルは自動フォールバック） |
| **画面認識** | 全画面キャプチャ（長辺 1024px）→ Gemini 2.5 Flash 系で解析（モデル自動フォールバック付き） |
| **長期記憶** | SQLite (WAL) に興味・プロジェクトを永続化、起動時に自動読み込み |
| **セマンティック検索** | コードを 40 行チャンクで埋め込みベクトル化して検索（埋め込みはディスクにキャッシュ） |
| **Live2D 表情制御** | 応答内の感情タグ `[Happy]` `[Sad]` 等を VTS API / Electron に送信 |
| **音声合成** | VOICEVOX REST API → pygame で再生（VB-Audio 仮想デバイス対応） |
| **自動観察モード** | 指定間隔で画面をキャプチャし、変化を音声でコメント |
| **Web UI** | Streamlit による画面キャプチャ＋チャット統合インターフェース |

---

## 技術スタック

- **言語**: Python 3.11+, JavaScript (Node.js)
- **AI/ML**: Ollama (qwen2.5), Google Gemini API, Sentence Transformers
- **フロントエンド**: Electron, Streamlit, Tkinter
- **通信**: WebSocket (`websockets`, VTube Studio API)
- **音声**: VOICEVOX, pygame, PyAudio
- **データ**: SQLite3, numpy

---

## 必要な環境

| ソフトウェア | 用途 | 必須 |
|-------------|------|------|
| Python 3.11+ | バックエンド全体 | ✅ |
| [Ollama](https://ollama.ai/) + `qwen2.5:7b` | ローカル LLM 推論 | ✅ |
| Gemini API キー | 画面分析 | ✅ |
| [VOICEVOX](https://voicevox.hiroshiba.jp/) | 音声合成 | オプション |
| [VTube Studio](https://store.steampowered.com/app/1926960/VTube_Studio/) | Live2D 表情制御 | オプション |
| Node.js 18+ | Electron アプリ | オプション |

---

## セットアップ

### 1. Python 依存関係

```bash
python -m pip install -r requirements.txt
```

### 2. Ollama モデル

```bash
ollama pull qwen2.5:7b
```

### 3. 環境変数

```bash
cp .env.example .env
# .env を編集して GEMINI_API_KEY を設定
```

`.env` の内容:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

API キーの取得: https://aistudio.google.com/app/apikey

その他の設定（Ollama モデル、VOICEVOX 話者、各種 URL・間隔など）は
`config.py` に集約されており、`.env` の `BII_*` 変数で上書きできます
（一覧は [.env.example](./.env.example) を参照）。

### 4. 動作確認

```bash
python -c "from bii_core import BiiCore; BiiCore(); print('OK')"
```

---

## 起動方法

### CLI 対話モード

```bash
python bii_chat.py
```

### 自動観察モード（画面を定期的に観察してコメント）

```bash
python bii_observer.py
```

### Web UI (Streamlit)

```bash
streamlit run bii_web.py
# → http://localhost:8501
```

### デスクトップ常駐 (Tkinter)

```bash
python bii_desktop.py
```

### Live2D デスクトップアプリ (Electron)

```bash
# ターミナル 1: Python WebSocket サーバー
python live2d_server.py

# ターミナル 2: Electron アプリ
cd live2d_app
npm install
npm start
```

> **注意**: WebGL が必要です。GPU ドライバーを最新に保ってください。
> WebGL が利用できない場合は `bii_desktop.py` または VTube Studio を使用してください。

---

## チャットコマンド

| コマンド | 説明 |
|---------|------|
| `/vision` | 画面をキャプチャして Gemini で分析 |
| `/code <query>` | プロジェクト内をセマンティック検索 |
| `/search <query>` | Web 検索 |
| `/memory` | 長期記憶を表示 |
| `/history` | 直近の会話履歴を表示 |
| `/clear` | 会話履歴をクリア |
| `/help` | コマンド一覧 |
| `exit` / `quit` | 終了 |

---

## ファイル構成

```
.
├── bii_core.py          # コア AI エンジン（tool calling・記憶・視覚）
├── config.py            # 設定の一元管理（.env の BII_* で上書き可）
├── emotion_utils.py     # 感情タグ ⇔ 表情ファイルの共通変換ロジック
├── lipsync_utils.py     # VOICEVOX audio_query → 口パク列（純粋関数）
├── bii_chat.py          # CLI 対話インターフェース
├── bii_observer.py      # 自動画面観察ループ
├── bii_web.py           # Streamlit Web UI
├── bii_desktop.py       # Tkinter デスクトップ UI
├── bii_rag.py           # セマンティックコード検索 (RAG・埋め込みキャッシュ付き)
├── bii_tools.py         # Web 検索ツール
├── vision_module.py     # 画面キャプチャモジュール
├── voicevox_adapter.py  # VOICEVOX 音声合成アダプター
├── vts_adapter.py       # VTube Studio WebSocket アダプター
├── live2d_server.py     # Python ↔ Electron WebSocket サーバー
├── live2d_app/          # Electron Live2D アプリ
│   ├── main.js          # Electron メインプロセス
│   ├── preload.js       # contextBridge（レンダラーへの安全な API 公開）
│   ├── index.html       # Live2D Canvas
│   ├── renderer.js      # 描画・リップシンク・WebSocket クライアント
│   └── models/          # Live2D モデルファイル（※ .gitignore 推奨）
├── tests/               # pytest ユニットテスト
├── requirements.txt
└── ARCHITECTURE.md      # 詳細アーキテクチャ仕様書
```

---

## トラブルシューティング

**Ollama 接続エラー**
```bash
ollama list   # サービスが起動しているか確認
ollama serve  # 未起動の場合
```

**Gemini API エラー** — `.env` の `GEMINI_API_KEY` が正しいか確認

**VOICEVOX が動かない** — VOICEVOX アプリを起動してから再実行（デフォルト: `http://localhost:50021`）

**VTS に接続できない** — VTube Studio の設定 → API → 「API を有効にする」をオン

**画面キャプチャが失敗する** — Windows の場合、管理者権限で実行するか、プライバシー設定でスクリーンキャプチャを許可

詳細は [ARCHITECTURE.md](./ARCHITECTURE.md) を参照してください。

---

## License

MIT
