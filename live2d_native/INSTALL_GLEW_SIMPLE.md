# GLEWの簡単インストール手順（手動）

vcpkgが使えない場合の、最も簡単な方法です。

## 手順

### 1. GLEWをダウンロード

以下のURLからGLEWをダウンロードしてください：
- **推奨**: https://sourceforge.net/projects/glew/files/glew/2.2.0/glew-2.2.0-win32.zip/download
- または最新版: https://github.com/nigels-com/glew/releases

### 2. 解凍して配置

1. ダウンロードしたZIPファイルを解凍
2. `glew-2.2.0`フォルダを `C:\glew` に移動（または任意の場所）

### 3. Visual Studioプロジェクトの設定

1. **Visual Studioでプロジェクトを開く**
   - `BiiLive2dNative.sln` を開く

2. **プロジェクトのプロパティを開く**
   - ソリューションエクスプローラーで `BiiLive2dNative` を右クリック
   - 「プロパティ」を選択

3. **インクルードディレクトリを追加**
   - 「構成プロパティ」→「C/C++」→「全般」を選択
   - 「追加のインクルード ディレクトリ」に以下を追加：
     ```
     C:\glew\include
     ```
   - または、GLEWを配置した場所に合わせて調整

4. **ライブラリディレクトリを追加**
   - 「構成プロパティ」→「リンカー」→「全般」を選択
   - 「追加のライブラリ ディレクトリ」に以下を追加：
     ```
     C:\glew\lib\Release\x64
     ```
   - **Debug構成の場合**:
     ```
     C:\glew\lib\Debug\x64
     ```

5. **ライブラリファイルを追加**
   - 「構成プロパティ」→「リンカー」→「入力」を選択
   - 「追加の依存ファイル」に以下を追加：
     ```
     glew32.lib
     ```

6. **DLLをコピー**
   - `C:\glew\bin\Release\x64\glew32.dll` を実行ファイルのディレクトリにコピー
   - 実行ファイルは `live2d_native\BiiLive2dNative\x64\Debug\` にあります

### 4. 確認

設定が完了したら、ビルドしてエラーがないか確認してください。

## 注意

- GLEWのバージョンは2.2.0以上を推奨
- x64版を使用してください（x86版ではありません）
- DebugとReleaseで異なるライブラリが必要な場合があります
