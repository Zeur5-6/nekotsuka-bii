
# 猫使Bii・Live2Dデスクトップアプリ

Live2Dモデルをデスクトップ上に常駐表示するElectronアプリケーション

## セットアップ

### 1. Node.jsとnpmをインストール
- Node.js公式サイトからインストール: https://nodejs.org/

### 2. 依存関係をインストール
```bash
cd live2d_app
npm install
```

### 3. Live2Dモデルファイルを配置
- `live2d_app/models/bii/` ディレクトリを作成
- Live2Dモデルファイルを配置

**必須ファイル:**
- `model.model3.json` - メインモデルファイル
- テクスチャファイル（`.png`など）
- モデルデータファイル（`.moc3`）

**表情ファイル（オプション）:**
表情制御機能を使用する場合は、以下の表情ファイルも配置してください：
- `happy.exp3.json` - ハッピー表情
- `sad.exp3.json` - 悲しい表情
- `angry.exp3.json` - 怒り表情
- `surprised.exp3.json` - 驚き表情
- `shock.exp3.json` - ショック表情
- `neutral.exp3.json` - ニュートラル表情

**ディレクトリ構造例:**
```
live2d_app/models/bii/
├── model.model3.json      # メインモデルファイル
├── *.png                  # テクスチャファイル
├── *.moc3                 # モデルデータファイル
├── happy.exp3.json        # 表情ファイル（オプション）
├── sad.exp3.json          # 表情ファイル（オプション）
├── angry.exp3.json        # 表情ファイル（オプション）
├── surprised.exp3.json    # 表情ファイル（オプション）
├── shock.exp3.json        # 表情ファイル（オプション）
└── neutral.exp3.json      # 表情ファイル（オプション）
```

**注意:** モデルによって表情ファイル名が異なる場合があります。その場合は`renderer.js`の`expressionMap`を編集してください。

### 4. Pythonサーバーを起動
```bash
# プロジェクトルートで実行
python live2d_server.py
```

### 5. Electronアプリを起動
```bash
cd live2d_app
npm start
```

## 使い方

1. **Pythonサーバーを起動**: `python live2d_server.py`
2. **Electronアプリを起動**: `npm start`
3. Live2Dモデルがデスクトップ上に表示されます
4. Pythonサーバー経由で表情制御が可能です

## 機能

- ✅ デスクトップ常駐表示（常に最前面）
- ✅ 透明背景
- ✅ ドラッグ可能
- ✅ WebSocketでPythonバックエンドと通信
- ✅ 表情制御（感情タグに基づいて自動制御）
- ✅ 音声合成（VOICEVOX連携）

## 注意事項

- Live2Dモデルファイルが必要です
- Pythonサーバー（`live2d_server.py`）を先に起動してください
- モデルファイルのパスは `renderer.js` で設定してください
