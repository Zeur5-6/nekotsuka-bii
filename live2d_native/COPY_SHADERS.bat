@echo off
REM Live2Dシェーダーファイルを実行ファイルのディレクトリにコピーするスクリプト

set "SHADER_SOURCE=sdk\CubismSdk\CubismSdkForNative-5-r.4.1\Framework\src\Rendering\OpenGL\Shaders\Standard"
set "TARGET_DIR=BiiLive2dNative\x64\Debug\FrameworkShaders\"

echo ========================================
echo Live2Dシェーダーファイルをコピー中...
echo ========================================

if not exist "%TARGET_DIR%" (
    echo ターゲットディレクトリが存在しません: %TARGET_DIR%
    echo 作成します...
    mkdir "%TARGET_DIR%"
)

if exist "%SHADER_SOURCE%" (
    echo シェーダーファイルをコピー中...
    xcopy /E /I /Y "%SHADER_SOURCE%" "%TARGET_DIR%"
    if %errorlevel% equ 0 (
        echo.
        echo [OK] シェーダーファイルのコピーが完了しました。
        echo   ソース: %SHADER_SOURCE%
        echo   宛先: %TARGET_DIR%
    ) else (
        echo.
        echo [エラー] シェーダーファイルのコピーに失敗しました。
        echo   エラーコード: %errorlevel%
    )
) else (
    echo.
    echo [エラー] ソースシェーダーディレクトリが見つかりません: %SHADER_SOURCE%
    echo   Live2D Cubism SDKが正しく配置されているか確認してください。
)

echo.
echo 続行するには何かキーを押してください . . .
pause > nul
