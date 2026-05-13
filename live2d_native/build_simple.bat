@echo off
REM 簡易ビルドスクリプト
REM Visual Studioの開発者コマンドプロンプトで実行してください

echo ========================================
echo 猫使ビィ・Live2D Native App ビルドスクリプト
echo ========================================

REM ビルドディレクトリを作成
if not exist build mkdir build
cd build

REM CMake設定を生成
echo.
echo [1/2] CMake設定を生成中...
cmake .. -G "Visual Studio 16 2019" -A x64
if errorlevel 1 (
    echo.
    echo エラー: CMake設定の生成に失敗しました
    echo.
    echo 解決方法:
    echo 1. Visual Studioの開発者コマンドプロンプトを使用してください
    echo 2. または、Visual StudioでCMakeLists.txtを直接開いてください
    pause
    exit /b 1
)

REM ビルド
echo.
echo [2/2] ビルド中...
cmake --build . --config Release
if errorlevel 1 (
    echo.
    echo エラー: ビルドに失敗しました
    echo.
    echo 確認事項:
    echo 1. live2d_native/sdk/CubismSdk/にLive2D SDKが配置されているか
    echo 2. Visual Studioの出力ウィンドウでエラーメッセージを確認
    pause
    exit /b 1
)

echo.
echo ========================================
echo ビルド完了！
echo ========================================
echo.
echo 実行ファイル: build\Release\bii_live2d_native.exe
echo.
pause
