# Live2Dモデル表示の代替案

## 現在の状況

この環境では**WebGLが利用できない**ため、ElectronアプリでLive2Dモデルを直接表示することはできません。

## 代替案

### 1. VTube Studioを使用（推奨・既に実装済み）

**メリット:**
- ✅ WebGL不要（VTSが描画を担当）
- ✅ 既に`bii_desktop.py`で実装済み
- ✅ 高品質なLive2D表示
- ✅ 表情・モーション制御が容易

**使用方法:**
```bash
python bii_desktop.py
```

**VTS接続の確認:**
1. VTube Studioを起動
2. 設定 → API → 「APIを有効にする」をON
3. `bii_desktop.py`で「VTS接続」ボタンをクリック
4. VTS側で認証ダイアログが表示されたら「許可」をクリック

### 2. Live2D Cubism SDK for Native（C++）

**概要:**
- Live2D公式のC++ SDKを使用
- WebGL不要（DirectX/OpenGLを使用）
- ネイティブアプリとして動作

**メリット:**
- ✅ 高性能
- ✅ WebGL不要
- ✅ 完全な制御が可能

**デメリット:**
- ❌ C++の知識が必要
- ❌ 開発時間が長い
- ❌ Pythonとの連携が複雑

**実装方法:**
1. Live2D Cubism SDK for Nativeをダウンロード
2. C++でアプリケーションを作成
3. PythonバックエンドとIPC（名前付きパイプ、共有メモリなど）で通信

### 3. Unityを使用（Windowsビルド）

**概要:**
- UnityでLive2Dモデルを表示
- Windows用にビルド（WebGLビルドではない）

**メリット:**
- ✅ 高品質な表示
- ✅ 豊富な機能
- ✅ クロスプラットフォーム対応

**デメリット:**
- ❌ Unityの知識が必要
- ❌ 開発環境のセットアップが必要
- ❌ ファイルサイズが大きい

### 4. OBS Studio + プラグイン

**概要:**
- OBS StudioのLive2Dプラグインを使用
- 画面キャプチャで表示

**メリット:**
- ✅ 配信にも使用可能
- ✅ プラグインが豊富

**デメリット:**
- ❌ OBS Studioが必要
- ❌ 画面キャプチャのオーバーヘッド

## 推奨される解決策

### 短期的な解決策（今すぐ使用可能）

**`bii_desktop.py`を使用:**
```bash
python bii_desktop.py
```

この方法では：
- VTS画面をキャプチャして表示
- 音声入力で操作可能
- 表情制御が可能
- WebGL不要

### 長期的な解決策（将来的な改善）

**Live2D Cubism SDK for Nativeを使用したC++アプリ:**
- PythonバックエンドとIPCで通信
- 高性能なLive2D表示
- 完全な制御が可能

## Neuro-samaの技術スタック（推測）

公開情報から推測される技術：
1. **Live2Dモデル**: 無料サンプル「桃瀬ひより」→ カスタムモデル（V2、V3）
2. **LLM**: 大規模言語モデル（詳細は非公開）
3. **TTS**: テキスト読み上げソフトウェア
4. **ゲームAI**: 別のAIモデル（osu!、Minecraftなど）

**Live2D表示方法（推測）:**
- VTube Studioを使用している可能性が高い
- または、Live2D Cubism SDK for Nativeを使用したカスタムアプリ

## 次のステップ

1. **VTS接続の問題を解決**（最も現実的）
   - `bii_desktop.py`でVTS接続を確認
   - VTS接続エラーの原因を特定・修正

2. **C++アプリの開発**（将来的な選択肢）
   - Live2D Cubism SDK for Nativeを使用
   - PythonバックエンドとIPCで通信

3. **Unityアプリの開発**（別の選択肢）
   - UnityでLive2Dモデルを表示
   - Windows用にビルド

## 参考リンク

- [Live2D Cubism SDK](https://www.live2d.com/sdk/download/cubism-sdk/)
- [VTube Studio](https://store.steampowered.com/app/1926960/VTube_Studio/)
- [Neuro-sama - Wikipedia](https://en.wikipedia.org/wiki/Neuro-sama)
