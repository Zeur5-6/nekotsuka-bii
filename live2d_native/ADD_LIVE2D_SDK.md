# Live2D SDKの設定手順

## 必要な設定

Visual StudioプロジェクトにLive2D SDKのヘッダーファイルとライブラリのパスを追加する必要があります。

## 手順

### 1. プロジェクトのプロパティを開く

1. Visual Studioで `BiiLive2dNative.sln` を開く
2. ソリューションエクスプローラーで `BiiLive2dNative` プロジェクトを右クリック
3. 「プロパティ」を選択

### 2. インクルードディレクトリを追加

1. 「構成プロパティ」→「C/C++」→「全般」を選択
2. 「追加のインクルード ディレクトリ」に以下を追加：

```
$(ProjectDir)..\..\sdk\CubismSdk\CubismSdkForNative-5-r.4.1\Framework\src
$(ProjectDir)..\..\sdk\CubismSdk\CubismSdkForNative-5-r.4.1\Core\include
```

または、絶対パス：

```
C:\Users\user\Downloads\sousaku\modelfile\live2d_native\sdk\CubismSdk\CubismSdkForNative-5-r.4.1\Framework\src
C:\Users\user\Downloads\sousaku\modelfile\live2d_native\sdk\CubismSdk\CubismSdkForNative-5-r.4.1\Core\include
```

### 3. ライブラリディレクトリを追加

1. 「構成プロパティ」→「リンカー」→「全般」を選択
2. 「追加のライブラリ ディレクトリ」に以下を追加：

```
$(ProjectDir)..\..\sdk\CubismSdk\CubismSdkForNative-5-r.4.1\Core\lib\windows\x86_64\msvc\143
```

または、絶対パス：

```
C:\Users\user\Downloads\sousaku\modelfile\live2d_native\sdk\CubismSdk\CubismSdkForNative-5-r.4.1\Core\lib\windows\x86_64\msvc\143
```

### 4. ライブラリファイルを追加

1. 「構成プロパティ」→「リンカー」→「入力」を選択
2. 「追加の依存ファイル」に以下を追加：

**Debug構成の場合：**
```
Live2DCubismCore_MDd.lib
```

**Release構成の場合：**
```
Live2DCubismCore_MD.lib
```

### 5. Frameworkライブラリの追加（必要に応じて）

Frameworkのソースコードをコンパイルする必要がある場合は、Frameworkのソースファイルをプロジェクトに追加する必要があります。

ただし、今回は最小限の実装なので、Coreライブラリのみを使用します。

## 確認

設定が完了したら、ビルドしてエラーがないか確認してください。
