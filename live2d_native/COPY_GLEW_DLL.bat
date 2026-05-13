@echo off
REM GLEW DLLをビルド出力ディレクトリにコピーするスクリプト

set "GLEW_DLL_PATH=C:\glew\bin\Release\x64\glew32.dll"
set "TARGET_DIR=BiiLive2dNative\x64\Debug\"

echo ========================================
echo GLEW DLLをコピー中...
echo ========================================

if not exist "%TARGET_DIR%" (
    echo ターゲットディレクトリが存在しません: %TARGET_DIR%
    echo 作成します...
    mkdir "%TARGET_DIR%"
)

if exist "%GLEW_DLL_PATH%" (
    copy "%GLEW_DLL_PATH%" "%TARGET_DIR%"
    if %errorlevel% equ 0 (
        echo.
        echo [OK] DLLのコピーが完了しました。
        echo   ソース: %GLEW_DLL_PATH%
        echo   宛先: %TARGET_DIR%
    ) else (
        echo.
        echo [エラー] DLLのコピーに失敗しました。
        echo   エラーコード: %errorlevel%
    )
) else (
    echo.
    echo [エラー] ソースDLLファイルが見つかりません: %GLEW_DLL_PATH%
    echo   GLEWが正しくインストールされているか確認してください。
    echo   インストール場所が異なる場合は、このスクリプトのパスを修正してください。
)

echo.
echo 続行するには何かキーを押してください . . .
pause > nul
