# 次の実装ステップ

## 現在の状態

✅ **ビルド成功**
✅ **アプリケーション起動成功**
✅ **ウィンドウ表示成功**

❌ **Live2Dモデルが表示されない**
- モデル読み込み機能が未実装
- 描画機能が未実装

## コンソール出力

```
Bii Live2D Native App
================================
[Live2DApp] Initialization complete
[Live2DApp] Loading model: models/bii/Usa Maid/Usa Maid.model3.json
Starting application...
[Live2DApp] WebSocket connection: ws://localhost:8765
```

初期化は成功していますが、モデルの読み込みと描画がまだ実装されていません。

## 次の実装ステップ

### ステップ1: Live2Dモデルの読み込み機能を実装

`LoadModel()`関数を実装する必要があります：

1. **Live2D Cubism SDKの初期化**
   - `CubismFramework::Initialize()`

2. **モデルファイルの読み込み**
   - `.model3.json`ファイルを読み込む
   - テクスチャファイルを読み込む
   - モデルデータを解析

3. **モデルの作成**
   - `CubismUserModel`を使用してモデルを作成

### ステップ2: 描画機能を実装

`Render()`関数を実装する必要があります：

1. **DirectXまたはOpenGLの初期化**
   - 現在はWindows APIのみを使用
   - DirectX 11またはOpenGLの初期化が必要

2. **Live2Dモデルの描画**
   - モデルを描画コンテキストに描画
   - 60FPSで更新

### ステップ3: WebSocket通信を実装

`ConnectWebSocket()`関数を実装する必要があります：

1. **WebSocketライブラリの統合**
   - `websocketpp`などのライブラリを使用
   - または、簡易的な実装

2. **Pythonサーバーとの通信**
   - `ws://localhost:8765`に接続
   - メッセージの送受信

## 実装の難易度

- **Live2Dモデルの読み込み**: 中程度（SDKのサンプルコードを参考に）
- **描画機能**: 高（DirectX/OpenGLの知識が必要）
- **WebSocket通信**: 中程度（ライブラリを使用すれば比較的簡単）

## 推奨される実装順序

1. **まず、基本的な描画を実装**
   - ウィンドウに何か表示する（例: 背景色、テキスト）
   - これで描画パイプラインが動作することを確認

2. **次に、Live2Dモデルの読み込み**
   - SDKのサンプルコードを参考に実装

3. **最後に、WebSocket通信**
   - 表情制御と音声合成の指示を受け取る

## 参考資料

- Live2D Cubism SDK for Nativeのサンプルコード:
  ```
  sdk/CubismSdk/CubismSdkForNative-5-r.4.1/Samples/
  ```
  - `OpenGL/Demo/` - OpenGLを使用したサンプル
  - `D3D11/Demo/` - DirectX 11を使用したサンプル

- Live2D公式ドキュメント:
  - https://docs.live2d.com/cubism-sdk-manual/

## 現在の状態の確認

✅ **アプリケーションは正常に動作しています**

真っ白なウィンドウが表示されているのは、描画機能が未実装のためです。これは正常な状態です。

次のステップとして、Live2Dモデルの読み込みと描画機能を実装する必要があります。
