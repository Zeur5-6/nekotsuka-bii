@echo off
REM コマンドラインからビルドするスクリプト
REM Visual Studioの開発者コマンドプロンプトで実行してください

echo ========================================
echo 猫使ビィ・Live2D Native App ビルド（コマンドライン）
echo ========================================
echo.

REM 現在のディレクトリを確認
cd /d "%~dp0"
echo 作業ディレクトリ: %CD%
echo.

REM CMakeのバージョンを確認
echo [1/5] CMakeのバージョンを確認中...
cmake --version
if errorlevel 1 (
    echo.
    echo エラー: CMakeが見つかりません
    echo.
    echo 解決方法:
    echo 1. Visual Studioの開発者コマンドプロンプトを使用してください
    echo 2. または、CMakeをインストールしてPATHに追加してください
    pause
    exit /b 1
)
echo.

REM SDKの配置を確認
echo [2/5] Live2D SDKの配置を確認中...
if not exist "sdk\CubismSdk" (
    echo [警告] Live2D SDKが見つかりません
    echo SDKを sdk\CubismSdk\ に配置してください
    echo.
    pause
    exit /b 1
)
echo [OK] Live2D SDKが見つかりました
echo.

REM ビルドディレクトリを作成
echo [3/5] ビルドディレクトリを作成中...
if exist build rmdir /s /q build
mkdir build
cd build
echo.

REM CMake設定を生成
echo [4/5] CMake設定を生成中...
cmake .. -G "Visual Studio 16 2019" -A x64
if errorlevel 1 (
    echo.
    echo エラー: CMake設定の生成に失敗しました
    echo.
    echo 解決方法:
    echo 1. Visual Studioのバージョンを確認してください
    echo 2. -G オプションを変更してください:
    echo    Visual Studio 2019: "Visual Studio 16 2019"
    echo    Visual Studio 2022: "Visual Studio 17 2022"
    echo.
    pause
    exit /b 1
)
echo.

REM ビルド
echo [5/5] ビルド中...
cmake --build . --config Release
if errorlevel 1 (
    echo.
    echo エラー: ビルドに失敗しました
    echo.
    echo 確認事項:
    echo 1. live2d_native/sdk/CubismSdk/にLive2D SDKが配置されているか
    echo 2. Visual Studioの出力ウィンドウでエラーメッセージを確認
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo ビルド完了！
echo ========================================
echo.
echo 実行ファイル: build\x64-Release\BiiLive2DNative.exe
echo.
echo Visual Studioで開く場合は:
echo   start BiiLive2DNative.sln
echo.
pause
