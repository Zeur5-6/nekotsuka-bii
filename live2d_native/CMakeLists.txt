cmake_minimum_required(VERSION 3.15)
project(BiiLive2DNative)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Live2D Cubism SDKのパス（環境に合わせて変更してください）
set(CUBISM_SDK_PATH "${CMAKE_SOURCE_DIR}/sdk/CubismSdk")

# インクルードディレクトリ
include_directories(
    ${CUBISM_SDK_PATH}/Core/include
    ${CUBISM_SDK_PATH}/Framework/src
    ${CUBISM_SDK_PATH}/Framework/src/Effect
    ${CUBISM_SDK_PATH}/Framework/src/Id
    ${CUBISM_SDK_PATH}/Framework/src/Live2DFramework
    ${CUBISM_SDK_PATH}/Framework/src/Math
    ${CUBISM_SDK_PATH}/Framework/src/Model
    ${CUBISM_SDK_PATH}/Framework/src/Motion
    ${CUBISM_SDK_PATH}/Framework/src/Physics
    ${CUBISM_SDK_PATH}/Framework/src/Rendering
    ${CUBISM_SDK_PATH}/Framework/src/Type
    ${CUBISM_SDK_PATH}/Framework/src/Utils
)

# ソースファイル
set(SOURCES
    src/main.cpp
    src/live2d_app.cpp
)

# ライブラリファイル（Windows用）
if(WIN32)
    # Live2D Cubism Coreライブラリ
    link_directories(${CUBISM_SDK_PATH}/Core/lib/windows/x86_64/msvc)
    link_libraries(
        Live2DCubismCore_5
    )
    
    # Windows API
    set(PLATFORM_LIBS
        user32
        gdi32
        ws2_32
    )
endif()

# 実行ファイルを作成
add_executable(${PROJECT_NAME} ${SOURCES})

# ライブラリをリンク
target_link_libraries(${PROJECT_NAME} ${PLATFORM_LIBS})

# モデルファイルをコピー
file(COPY ${CMAKE_SOURCE_DIR}/models DESTINATION ${CMAKE_BINARY_DIR})
