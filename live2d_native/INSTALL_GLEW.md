# GLEWのインストール手順

## 方法1: vcpkgを使用（推奨・最も簡単）

Visual Studioにvcpkgが統合されている場合：

1. **PowerShellを管理者として開く**

2. **vcpkgをインストール**（まだインストールしていない場合）:
   ```powershell
   cd C:\
   git clone https://github.com/Microsoft/vcpkg.git
   cd vcpkg
   .\bootstrap-vcpkg.bat
   ```

3. **GLEWをインストール**:
   ```powershell
   .\vcpkg install glew:x64-windows
   ```

4. **Visual Studioに統合**:
   ```powershell
   .\vcpkg integrate install
   ```

5. **Visual Studioでプロジェクトを再読み込み**

## 方法2: 手動インストール

1. **GLEWをダウンロード**:
   - https://sourceforge.net/projects/glew/files/glew/2.2.0/glew-2.2.0.zip/download
   - または最新版: https://github.com/nigels-com/glew/releases

2. **解凍して配置**:
   - `C:\glew` などに解凍

3. **Visual Studioプロジェクトの設定**:
   - 「プロジェクトのプロパティ」→「C/C++」→「全般」→「追加のインクルード ディレクトリ」に追加:
     ```
     C:\glew\include
     ```
   - 「プロジェクトのプロパティ」→「リンカー」→「全般」→「追加のライブラリ ディレクトリ」に追加:
     ```
     C:\glew\lib\Release\x64
     ```
   - 「プロジェクトのプロパティ」→「リンカー」→「入力」→「追加の依存ファイル」に追加:
     ```
     glew32.lib
     ```

## 方法3: 一時的にOpenGLのRendererを除外（開発中）

GLEWのインストールが難しい場合は、一時的にOpenGLのRendererを除外して、基本的な実装のみを使用することもできます。

ただし、この場合、モデルを描画することはできません。
