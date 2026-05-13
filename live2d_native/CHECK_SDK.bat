@echo off
REM Live2D SDKの配置確認スクリプト

echo ========================================
echo Live2D SDK 配置確認
echo ========================================
echo.

set SDK_PATH=%~dp0sdk\CubismSdk

if exist "%SDK_PATH%" (
    echo [OK] SDKディレクトリが見つかりました: %SDK_PATH%
    echo.
    
    if exist "%SDK_PATH%\Core" (
        echo [OK] Core ディレクトリが見つかりました
    ) else (
        echo [エラー] Core ディレクトリが見つかりません
    )
    
    if exist "%SDK_PATH%\Framework" (
        echo [OK] Framework ディレクトリが見つかりました
    ) else (
        echo [エラー] Framework ディレクトリが見つかりません
    )
    
    if exist "%SDK_PATH%\Core\include" (
        echo [OK] Core/include ディレクトリが見つかりました
    ) else (
        echo [エラー] Core/include ディレクトリが見つかりません
    )
    
    if exist "%SDK_PATH%\Core\lib" (
        echo [OK] Core/lib ディレクトリが見つかりました
    ) else (
        echo [エラー] Core/lib ディレクトリが見つかりません
    )
    
    echo.
    echo ========================================
    echo 確認完了
    echo ========================================
) else (
    echo [エラー] SDKディレクトリが見つかりません: %SDK_PATH%
    echo.
    echo 解決方法:
    echo 1. https://www.live2d.com/sdk/download/cubism-sdk/ にアクセス
    echo 2. アカウントを作成（無料）
    echo 3. 「Cubism SDK for Native」をダウンロード
    echo 4. 解凍して %~dp0sdk\ に配置
    echo.
    echo 期待されるディレクトリ構造:
    echo   live2d_native\
    echo     sdk\
    echo       CubismSdk\
    echo         Core\
    echo         Framework\
    echo.
)

pause
