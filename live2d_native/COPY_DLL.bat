@echo off
REM DLLファイルを実行ファイルと同じディレクトリにコピーするスクリプト

echo ========================================
echo Live2D DLLファイルをコピー
echo ========================================
echo.

cd /d "%~dp0"

set DLL_SOURCE=sdk\CubismSdk\CubismSdkForNative-5-r.4.1\Core\dll\windows\x86_64\Live2DCubismCore.dll
set DLL_DEST_DEBUG=BiiLive2dNative\x64\Debug\Live2DCubismCore.dll
set DLL_DEST_RELEASE=BiiLive2dNative\x64\Release\Live2DCubismCore.dll

REM プロジェクトの出力ディレクトリが異なる場合の代替パス
set DLL_DEST_DEBUG_ALT=x64\Debug\Live2DCubismCore.dll
set DLL_DEST_RELEASE_ALT=x64\Release\Live2DCubismCore.dll

REM DLLファイルが存在するか確認
if not exist "%DLL_SOURCE%" (
    echo [エラー] DLLファイルが見つかりません: %DLL_SOURCE%
    pause
    exit /b 1
)

echo [OK] DLLファイルが見つかりました
echo.

REM Debugディレクトリにコピー
if exist "BiiLive2dNative\x64\Debug\" (
    copy /Y "%DLL_SOURCE%" "%DLL_DEST_DEBUG%"
    if errorlevel 1 (
        echo [エラー] Debugディレクトリへのコピーに失敗しました
    ) else (
        echo [OK] Debugディレクトリにコピーしました: %DLL_DEST_DEBUG%
    )
) else if exist "x64\Debug\" (
    copy /Y "%DLL_SOURCE%" "%DLL_DEST_DEBUG_ALT%"
    if errorlevel 1 (
        echo [エラー] Debugディレクトリへのコピーに失敗しました
    ) else (
        echo [OK] Debugディレクトリにコピーしました: %DLL_DEST_DEBUG_ALT%
    )
) else (
    echo [警告] Debugディレクトリが存在しません（ビルド後に作成されます）
)

echo.

REM Releaseディレクトリにコピー
if exist "BiiLive2dNative\x64\Release\" (
    copy /Y "%DLL_SOURCE%" "%DLL_DEST_RELEASE%"
    if errorlevel 1 (
        echo [エラー] Releaseディレクトリへのコピーに失敗しました
    ) else (
        echo [OK] Releaseディレクトリにコピーしました: %DLL_DEST_RELEASE%
    )
) else if exist "x64\Release\" (
    copy /Y "%DLL_SOURCE%" "%DLL_DEST_RELEASE_ALT%"
    if errorlevel 1 (
        echo [エラー] Releaseディレクトリへのコピーに失敗しました
    ) else (
        echo [OK] Releaseディレクトリにコピーしました: %DLL_DEST_RELEASE_ALT%
    )
) else (
    echo [警告] Releaseディレクトリが存在しません（ビルド後に作成されます）
)

echo.
echo ========================================
echo 完了
echo ========================================
echo.
pause
