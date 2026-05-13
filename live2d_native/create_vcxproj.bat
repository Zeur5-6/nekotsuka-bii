@echo off
REM Visual Studioプロジェクトファイル（.vcxproj）を作成するスクリプト
REM CMakeが使えない場合の代替方法

echo ========================================
echo Visual Studioプロジェクトファイルを作成
echo ========================================
echo.

cd /d "%~dp0"

REM SDKの配置を確認
if not exist "sdk\CubismSdk" (
    echo [エラー] Live2D SDKが見つかりません
    echo SDKを sdk\CubismSdk\ に配置してください
    pause
    exit /b 1
)

echo [OK] Live2D SDKが見つかりました
echo.

REM プロジェクトファイルを作成
echo Visual Studioプロジェクトファイルを作成中...
echo.

REM プロジェクトファイルの内容
(
echo ^<?xml version="1.0" encoding="utf-8"?^>
echo ^<Project DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003"^>
echo   ^<ItemGroup Label="ProjectConfigurations"^>
echo     ^<ProjectConfiguration Include="Debug|x64"^>
echo       ^<Configuration^>Debug^</Configuration^>
echo       ^<Platform^>x64^</Platform^>
echo     ^</ProjectConfiguration^>
echo     ^<ProjectConfiguration Include="Release|x64"^>
echo       ^<Configuration^>Release^</Configuration^>
echo       ^<Platform^>x64^</Platform^>
echo     ^</ProjectConfiguration^>
echo   ^</ItemGroup^>
echo   ^<PropertyGroup Label="Globals"^>
echo     ^<VCProjectVersion^>16.0^</VCProjectVersion^>
echo     ^<Keyword^>Win32Proj^</Keyword^>
echo     ^<ProjectGuid^>{12345678-1234-1234-1234-123456789ABC}^</ProjectGuid^>
echo     ^<RootNamespace^>BiiLive2DNative^</RootNamespace^>
echo     ^<WindowsTargetPlatformVersion^>10.0^</WindowsTargetPlatformVersion^>
echo   ^</PropertyGroup^>
echo   ^<Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" /^>
echo   ^<PropertyGroup Condition="'$(Configuration)^|$(Platform)'=='Debug^x64'" Label="Configuration"^>
echo     ^<ConfigurationType^>Application^</ConfigurationType^>
echo     ^<UseDebugLibraries^>true^</UseDebugLibraries^>
echo     ^<PlatformToolset^>v142^</PlatformToolset^>
echo     ^<CharacterSet^>Unicode^</CharacterSet^>
echo   ^</PropertyGroup^>
echo   ^<PropertyGroup Condition="'$(Configuration)^|$(Platform)'=='Release^x64'" Label="Configuration"^>
echo     ^<ConfigurationType^>Application^</ConfigurationType^>
echo     ^<UseDebugLibraries^>false^</UseDebugLibraries^>
echo     ^<PlatformToolset^>v142^</PlatformToolset^>
echo     ^<CharacterSet^>Unicode^</CharacterSet^>
echo   ^</PropertyGroup^>
echo   ^<Import Project="$(VCTargetsPath)\Microsoft.Cpp.props" /^>
echo   ^<ImportGroup Label="ExtensionSettings"^>
echo   ^</ImportGroup^>
echo   ^<ImportGroup Label="Shared"^>
echo   ^</ImportGroup^>
echo   ^<ImportGroup Label="PropertySheets" Condition="'$(Configuration)^|$(Platform)'=='Debug^x64'"^>
echo     ^<Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" Label="LocalAppDataPlatform" /^>
echo   ^</ImportGroup^>
echo   ^<ImportGroup Label="PropertySheets" Condition="'$(Configuration)^|$(Platform)'=='Release^x64'"^>
echo     ^<Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" Label="LocalAppDataPlatform" /^>
echo   ^</ImportGroup^>
echo   ^<PropertyGroup Label="UserMacros" /^>
echo   ^<PropertyGroup Condition="'$(Configuration)^|$(Platform)'=='Debug^x64'"^>
echo     ^<OutDir^>$(SolutionDir)build\$(Configuration)\^</OutDir^>
echo     ^<IntDir^>$(Configuration)\^</IntDir^>
echo   ^</PropertyGroup^>
echo   ^<PropertyGroup Condition="'$(Configuration)^|$(Platform)'=='Release^x64'"^>
echo     ^<OutDir^>$(SolutionDir)build\$(Configuration)\^</OutDir^>
echo     ^<IntDir^>$(Configuration)\^</IntDir^>
echo   ^</PropertyGroup^>
echo   ^<ItemDefinitionGroup Condition="'$(Configuration)^|$(Platform)'=='Debug^x64'"^>
echo     ^<ClCompile^>
echo       ^<WarningLevel^>Level3^</WarningLevel^>
echo       ^<SDLCheck^>true^</SDLCheck^>
echo       ^<PreprocessorDefinitions^>_DEBUG;_CONSOLE;%(PreprocessorDefinitions)^</PreprocessorDefinitions^>
echo       ^<ConformanceMode^>true^</ConformanceMode^>
echo       ^<LanguageStandard^>stdcpp17^</LanguageStandard^>
echo       ^<AdditionalIncludeDirectories^>sdk\CubismSdk\Core\include;sdk\CubismSdk\Framework\src;sdk\CubismSdk\Framework\src\Effect;sdk\CubismSdk\Framework\src\Id;sdk\CubismSdk\Framework\src\Live2DFramework;sdk\CubismSdk\Framework\src\Math;sdk\CubismSdk\Framework\src\Model;sdk\CubismSdk\Framework\src\Motion;sdk\CubismSdk\Framework\src\Physics;sdk\CubismSdk\Framework\src\Rendering;sdk\CubismSdk\Framework\src\Type;sdk\CubismSdk\Framework\src\Utils;%(AdditionalIncludeDirectories)^</AdditionalIncludeDirectories^>
echo     ^</ClCompile^>
echo     ^<Link^>
echo       ^<SubSystem^>Console^</SubSystem^>
echo       ^<GenerateDebugInformation^>true^</GenerateDebugInformation^>
echo       ^<AdditionalLibraryDirectories^>sdk\CubismSdk\Core\lib\windows\x86_64\msvc;%(AdditionalLibraryDirectories)^</AdditionalLibraryDirectories^>
echo       ^<AdditionalDependencies^>Live2DCubismCore_5.lib;user32.lib;gdi32.lib;ws2_32.lib;%(AdditionalDependencies)^</AdditionalDependencies^>
echo     ^</Link^>
echo   ^</ItemDefinitionGroup^>
echo   ^<ItemDefinitionGroup Condition="'$(Configuration)^|$(Platform)'=='Release^x64'"^>
echo     ^<ClCompile^>
echo       ^<WarningLevel^>Level3^</WarningLevel^>
echo       ^<FunctionLevelLinking^>true^</FunctionLevelLinking^>
echo       ^<IntrinsicFunctions^>true^</IntrinsicFunctions^>
echo       ^<SDLCheck^>true^</SDLCheck^>
echo       ^<PreprocessorDefinitions^>NDEBUG;_CONSOLE;%(PreprocessorDefinitions)^</PreprocessorDefinitions^>
echo       ^<ConformanceMode^>true^</ConformanceMode^>
echo       ^<LanguageStandard^>stdcpp17^</LanguageStandard^>
echo       ^<AdditionalIncludeDirectories^>sdk\CubismSdk\Core\include;sdk\CubismSdk\Framework\src;sdk\CubismSdk\Framework\src\Effect;sdk\CubismSdk\Framework\src\Id;sdk\CubismSdk\Framework\src\Live2DFramework;sdk\CubismSdk\Framework\src\Math;sdk\CubismSdk\Framework\src\Model;sdk\CubismSdk\Framework\src\Motion;sdk\CubismSdk\Framework\src\Physics;sdk\CubismSdk\Framework\src\Rendering;sdk\CubismSdk\Framework\src\Type;sdk\CubismSdk\Framework\src\Utils;%(AdditionalIncludeDirectories)^</AdditionalIncludeDirectories^>
echo     ^</ClCompile^>
echo     ^<Link^>
echo       ^<SubSystem^>Console^</SubSystem^>
echo       ^<EnableCOMDATFolding^>true^</EnableCOMDATFolding^>
echo       ^<OptimizeReferences^>true^</OptimizeReferences^>
echo       ^<GenerateDebugInformation^>true^</GenerateDebugInformation^>
echo       ^<AdditionalLibraryDirectories^>sdk\CubismSdk\Core\lib\windows\x86_64\msvc;%(AdditionalLibraryDirectories)^</AdditionalLibraryDirectories^>
echo       ^<AdditionalDependencies^>Live2DCubismCore_5.lib;user32.lib;gdi32.lib;ws2_32.lib;%(AdditionalDependencies)^</AdditionalDependencies^>
echo     ^</Link^>
echo   ^</ItemDefinitionGroup^>
echo   ^<ItemGroup^>
echo     ^<ClCompile Include="src\main.cpp" /^>
echo     ^<ClCompile Include="src\live2d_app.cpp" /^>
echo   ^</ItemGroup^>
echo   ^<ItemGroup^>
echo     ^<ClInclude Include="src\live2d_app.h" /^>
echo     ^<ClInclude Include="src\simple_json.h" /^>
echo   ^</ItemGroup^>
echo   ^<Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" /^>
echo ^</Project^>
) > BiiLive2DNative.vcxproj

REM ソリューションファイルを作成
(
echo Microsoft Visual Studio Solution File, Format Version 12.00
echo # Visual Studio Version 16
echo VisualStudioVersion = 16.0.31129.1
echo MinimumVisualStudioVersion = 10.0.40219.1
echo Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}"^) = "BiiLive2DNative", "BiiLive2DNative.vcxproj", "{12345678-1234-1234-1234-123456789ABC}"
echo EndProject
echo Global
echo     GlobalSection(SolutionConfigurationPlatforms^) = preSolution
echo         Debug|x64 = Debug|x64
echo         Release|x64 = Release|x64
echo     EndGlobalSection
echo     GlobalSection(ProjectConfigurationPlatforms^) = postSolution
echo         {12345678-1234-1234-1234-123456789ABC}.Debug|x64.ActiveCfg = Debug|x64
echo         {12345678-1234-1234-1234-123456789ABC}.Debug|x64.Build.0 = Debug|x64
echo         {12345678-1234-1234-1234-123456789ABC}.Release|x64.ActiveCfg = Release|x64
echo         {12345678-1234-1234-1234-123456789ABC}.Release|x64.Build.0 = Release|x64
echo     EndGlobalSection
echo     GlobalSection(SolutionProperties^) = preSolution
echo         HideSolutionNode = FALSE
echo     EndGlobalSection
echo EndGlobal
) > BiiLive2DNative.sln

echo.
echo ========================================
echo プロジェクトファイルを作成しました！
echo ========================================
echo.
echo 次のステップ:
echo 1. Visual Studioで BiiLive2DNative.sln を開く
echo 2. 「ビルド」→「ソリューションのビルド」（Ctrl+Shift+B）
echo.
pause
