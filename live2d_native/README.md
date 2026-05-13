# Live2D Native アプリケーション（C++）

WebGLが利用できない環境向けの、Live2D Cubism SDK for Nativeを使用したC++アプリケーション

## 概要

このアプリケーションは、Live2D Cubism SDK for Nativeを使用してLive2Dモデルを表示します。
PythonバックエンドとWebSocketで通信し、表情制御や音声合成の指示を受け取ります。

## 必要な環境

1. **Visual Studio 2019以上**（またはMinGW）
2. **CMake 3.15以上**（またはVisual Studioで直接開く）
3. **Live2D Cubism SDK for Native**
   - ダウンロード: https://www.live2d.com/sdk/download/cubism-sdk/

## クイックスタート

### 方法1: Visual Studioで直接開く（推奨・最も簡単）

**詳細な手順は `VISUAL_STUDIO_BUILD_GUIDE.md` を参照してください。**

簡単な手順:
1. Visual Studio 2019/2022を起動
2. 「ファイル」→「開く」→「CMake...」を選択
3. `live2d_native/CMakeLists.txt`を選択
4. Visual Studioが自動的にCMake設定を生成します（下部の出力ウィンドウで確認）
5. 「ビルド」→「すべてビルド」を選択（`Ctrl+Shift+B`）

**CMakeLists.txtを開いた後の詳細な手順は `QUICK_STEPS.md` または `AFTER_OPENING_CMAKELISTS.md` を参照してください。**

**⚠️ CMakeがインストールされていない、または自動生成が行われない場合:**
- **`EASIEST_WAY.md`** - 最も簡単な方法（推奨）⭐
- **`STEP_BY_STEP.md`** - ステップバイステップガイド（画像なしでも分かる）
- `SIMPLE_BUILD.md` - CMakeなしでビルドする方法
- `NO_CMAKE_SOLUTION.md` - CMakeが使えない場合の解決方法
- `TROUBLESHOOTING.md` - 詳細なトラブルシューティングガイド

**重要:** ビルド前に`CHECK_SDK.bat`を実行して、Live2D SDKが正しく配置されているか確認してください。

### 方法2: Visual Studioの開発者コマンドプロンプトを使用

1. スタートメニューから「Developer Command Prompt for VS 2019」を検索
2. プロジェクトディレクトリに移動:
   ```powershell
   cd C:\Users\user\Downloads\sousaku\modelfile\live2d_native
   ```
3. ビルドスクリプトを実行:
   ```powershell
   build_simple.bat
   ```

### 方法3: CMakeコマンドを使用

```powershell
mkdir build
cd build
cmake .. -G "Visual Studio 16 2019" -A x64
cmake --build . --config Release
```

**注意**: CMakeコマンドが使えない場合は、方法1または方法2を使用してください。

## セットアップ

### 1. Live2D Cubism SDK for Nativeをダウンロード

1. https://www.live2d.com/sdk/download/cubism-sdk/ にアクセス
2. 「Cubism SDK for Native」をダウンロード
3. 解凍して`live2d_native/sdk/`に配置

**ディレクトリ構造:**
```
live2d_native/
└── sdk/
    └── CubismSdk/
        ├── Core/
        ├── Framework/
        └── ...
```

### 2. プロジェクトの構造

```
live2d_native/
├── sdk/                    # Live2D Cubism SDK（手動で配置）
│   └── CubismSdk/
├── src/                    # ソースコード
│   ├── main.cpp
│   ├── live2d_app.cpp
│   └── live2d_app.h
├── models/                 # Live2Dモデルファイル
│   └── bii/
│       └── Usa Maid/
├── CMakeLists.txt
├── build_simple.bat        # ビルドスクリプト
└── README.md
```

## 使用方法

1. Pythonサーバーを起動:
```bash
python live2d_server.py
```

2. C++アプリを起動:
```bash
build/Release/bii_live2d_native.exe
```

## 機能

- ✅ Live2Dモデルの表示（WebGL不要）
- ✅ WebSocketでPythonバックエンドと通信
- ✅ 表情制御（感情タグに基づく）
- ✅ デスクトップ常駐表示
- ✅ 透明背景
- ✅ ドラッグ可能

## トラブルシューティング

### CMakeコマンドが使えない

**解決方法**: 
- `BUILD_WITH_VS.md`を参照
- Visual Studioで直接CMakeプロジェクトを開く（方法1）

### CMakeエラー: "Could not find Cubism SDK"

**解決方法:**
1. `live2d_native/sdk/CubismSdk/`にSDKが配置されているか確認
2. `CMakeLists.txt`の`CUBISM_SDK_PATH`を確認

### リンクエラー: "unresolved external symbol"

**解決方法:**
1. Live2D Cubism SDKのライブラリファイル（`.lib`）が正しいパスにあるか確認
2. `CMakeLists.txt`の`link_directories`を確認

### 実行時エラー: "DLL not found"

**解決方法:**
1. Live2D Cubism SDKのDLLファイル（`.dll`）を実行ファイルと同じディレクトリにコピー
2. または、システムのPATHに追加

## トラブルシューティング

**自動生成が行われない、ビルドショートカットが効かない場合:**
- **`IMMEDIATE_FIX.md`** - すぐに試せる解決方法 ⚡
- **`TROUBLESHOOTING.md`** - 詳細なトラブルシューティングガイド

## 参考資料

- **`VISUAL_STUDIO_BUILD_GUIDE.md`** - Visual Studioでのビルド方法（詳細ガイド）⭐
- `QUICK_START.md` - クイックスタートガイド
- `SETUP_GUIDE.md` - 詳細なセットアップ手順
- `BUILD_WITH_VS.md` - Visual Studioでのビルド方法（簡易版）
- `IMPLEMENTATION_GUIDE.md` - 実装ガイド
- `CHECK_SDK.bat` - Live2D SDKの配置確認スクリプト
- `build_with_cmd.bat` - コマンドラインからビルドするスクリプト

## 注意事項

- C++の基本的な知識が必要です
- Visual StudioまたはMinGWのセットアップが必要です
- Live2D Cubism SDK for Nativeのライセンスに注意してください
