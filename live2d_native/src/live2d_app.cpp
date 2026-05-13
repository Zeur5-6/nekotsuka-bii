/**
 * Live2D Native アプリケーション実装
 * C++初心者向けのシンプルな実装
 */

#include "live2d_app.h"
#include "websocket_client.h"
#include "audio_capture.h"
#include "simple_json.h"
#include "lip_sync_processor.h"
#include <cmath>
#include <iostream>
#include <sstream>
#include <fstream>
#include <algorithm>
#include <vector>
#include <cstring>
#include <sys/stat.h>
#include <io.h>
#include <cstdlib>
#include <malloc.h>
#include <ctime>
// GLEWを最初にインクルード（gl.hの前に）
#include <GL/glew.h>
#include <Rendering/OpenGL/CubismRenderer_OpenGLES2.hpp>
#include <Math/CubismMatrix44.hpp>
#include <Effect/CubismEyeBlink.hpp>
#include <Effect/CubismBreath.hpp>
#include <Motion/CubismMotionManager.hpp>
#include <Motion/CubismExpressionMotionManager.hpp>
#include <Id/CubismId.hpp>

// stb_image.h for PNG loading
#define STBI_NO_STDIO
#define STBI_ONLY_PNG
#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"

// グローバルインスタンス（ウィンドウプロシージャ用）
Live2DApp* g_app = nullptr;

// CubismFramework用のファイル読み込み関数（フレンド関数）
csmByte* LoadFileAsBytesForCubism(const std::string filePath, csmSizeInt* outSize) {
    if (g_app) {
        return g_app->LoadFileAsBytes(filePath, outSize);
    }
    return nullptr;
}

// CubismFramework用のメモリ解放関数（フレンド関数）
void ReleaseBytesForCubism(csmByte* byteData) {
    if (g_app) {
        g_app->ReleaseBytes(byteData);
    }
}

Live2DApp::Live2DApp() 
    : m_hWnd(nullptr)
    , m_running(false)
    , m_model(nullptr)
    , m_wsClient(nullptr)
    , m_modelSetting(nullptr)
    , m_modelLoaded(false)
    , m_allocator(nullptr)
    , m_cubismOption()
    , m_eyeBlink(nullptr)
    , m_breath(nullptr)
    , m_motionManager(nullptr)
    , m_expressionManager(nullptr)
    , m_userTimeSeconds(0.0f)
    , m_lastFrameTime(0.0f)
    , m_modelMatrix(nullptr)
    , m_modelScale(1.0f)
    , m_modelX(0.0f)
    , m_modelY(0.0f)
    , m_dragging(false)
    , m_windowDragging(false)
    , m_lastMouseX(0)
    , m_lastMouseY(0)
    , m_windowDragStartX(0)
    , m_windowDragStartY(0)
    , m_lipSyncValue(0.0f)
    , m_mouthSmileId(nullptr)
    , m_mouthOpenId(nullptr)
    , m_mouthFormId(nullptr)
    , m_mouthSmileValue(0.0f)
    , m_mouthOpenValue(0.0f)
    , m_lastLipSyncValue(0.0f)
    , m_lastMouthOpenValue(0.0f)
    , m_lastMouthSmileValue(0.0f)
    , m_mouthFormValue(0.0f)
    , m_externalLipSyncActive(false)
    , m_lastExternalLipSyncMs(0)
    , m_lipSyncProcessor(nullptr)
    , m_audioCapture(nullptr)
    , m_hDC(nullptr)
    , m_hGLRC(nullptr)
    , m_glInitialized(false)
{
    g_app = this;
    m_allocator = new BiiAllocator();
}

Live2DApp::~Live2DApp() {
    Shutdown();
}

bool Live2DApp::Initialize() {
    // Windows APIの初期化
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
        std::cerr << "WSAStartup failed" << std::endl;
        return false;
    }
    
    // 作業ディレクトリを実行ファイルのディレクトリに設定
    // シェーダーファイルは FrameworkShaders/ という相対パスで探されるため、
    // 実行ファイルのディレクトリに FrameworkShaders フォルダを作成する必要があります
    char exePath[MAX_PATH];
    GetModuleFileNameA(nullptr, exePath, MAX_PATH);
    std::string exeDir = exePath;
    size_t lastSlash = exeDir.find_last_of("\\/");
    if (lastSlash != std::string::npos) {
        exeDir = exeDir.substr(0, lastSlash + 1);
    }
    
    // 作業ディレクトリを実行ファイルのディレクトリに設定
    SetCurrentDirectoryA(exeDir.c_str());
    std::cout << "[Live2DApp] Working directory set to: " << exeDir << std::endl;
    
    // Live2D Cubism Frameworkの初期化
    // オプションを設定
    m_cubismOption.LogFunction = nullptr;  // ログ関数（必要に応じて設定）
    m_cubismOption.LoggingLevel = Csm::CubismFramework::Option::LogLevel_Off;  // ログレベル
    m_cubismOption.LoadFileFunction = LoadFileAsBytesForCubism;  // ファイル読み込み関数
    m_cubismOption.ReleaseBytesFunction = ReleaseBytesForCubism;  // メモリ解放関数
    
    CubismFramework::StartUp(m_allocator, &m_cubismOption);
    CubismFramework::Initialize();
    
    std::cout << "[Live2DApp] CubismFramework initialized" << std::endl;
    
    // ウィンドウクラスの登録
    WNDCLASSEX wc = {};
    wc.cbSize = sizeof(WNDCLASSEX);
    wc.style = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc = WindowProc;
    wc.hInstance = GetModuleHandle(nullptr);
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wc.lpszClassName = L"BiiLive2DWindow";
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    
    if (!RegisterClassEx(&wc)) {
        std::cerr << "Window class registration failed" << std::endl;
        return false;
    }
    
    // ウィンドウの作成
    m_hWnd = CreateWindowEx(
        WS_EX_LAYERED | WS_EX_TOPMOST,  // 透明背景、常に最前面
        L"BiiLive2DWindow",
        L"Bii Live2D",
        WS_POPUP,  // フレームレス
        100, 100, 400, 600,
        nullptr, nullptr, GetModuleHandle(nullptr), nullptr
    );
    
    if (!m_hWnd) {
        std::cerr << "Window creation failed" << std::endl;
        return false;
    }
    
    // 透明背景を設定
    SetLayeredWindowAttributes(m_hWnd, 0, 255, LWA_ALPHA);
    
    // ウィンドウを表示
    ShowWindow(m_hWnd, SW_SHOW);
    UpdateWindow(m_hWnd);
    
    // OpenGLの初期化（ウィンドウ作成後に必要）
    if (!InitializeOpenGL()) {
        std::cerr << "[Live2DApp] OpenGL initialization failed" << std::endl;
        return false;
    }
    
    std::cout << "[Live2DApp] Initialization complete" << std::endl;
    return true;
}

void Live2DApp::Run() {
    m_running = true;
    
    // WebSocket接続
    ConnectWebSocket();
    
    // 仮想マイクから音声を取得（リップシンク用）
    InitializeAudioCapture();
    
    // メッセージループ
    MessageLoop();
}

void Live2DApp::Shutdown() {
    m_running = false;
    
    // アニメーション関連を解放
    if (m_eyeBlink) {
        CubismEyeBlink::Delete(m_eyeBlink);
        m_eyeBlink = nullptr;
    }
    if (m_breath) {
        CubismBreath::Delete(m_breath);
        m_breath = nullptr;
    }
    if (m_motionManager) {
        delete m_motionManager;
        m_motionManager = nullptr;
    }
        if (m_expressionManager) {
            delete m_expressionManager;
            m_expressionManager = nullptr;
        }
        
        // モーションを解放
        for (csmMap<csmString, ACubismMotion*>::const_iterator iter = m_motions.Begin(); iter != m_motions.End(); ++iter) {
            ACubismMotion::Delete(iter->Second);
        }
        m_motions.Clear();
        
        // モデルマトリックスを解放
        if (m_modelMatrix) {
            delete m_modelMatrix;
            m_modelMatrix = nullptr;
        }
        
        // モデルを解放
    if (m_model) {
        delete m_model;
        m_model = nullptr;
    }
    if (m_modelSetting) {
        delete m_modelSetting;
        m_modelSetting = nullptr;
    }
    
    // OpenGLコンテキストを破棄
    if (m_hGLRC) {
        wglMakeCurrent(nullptr, nullptr);
        wglDeleteContext(m_hGLRC);
        m_hGLRC = nullptr;
    }
    if (m_hDC) {
        ReleaseDC(m_hWnd, m_hDC);
        m_hDC = nullptr;
    }
    
    // CubismFrameworkを終了
    CubismFramework::Dispose();
    
    // アロケーターを解放
    if (m_allocator) {
        delete m_allocator;
        m_allocator = nullptr;
    }
    
    // WebSocketを閉じる
    if (m_wsClient) {
        m_wsClient->Disconnect();
        delete m_wsClient;
        m_wsClient = nullptr;
    }
    
    // 音声キャプチャを終了
    if (m_audioCapture) {
        m_audioCapture->Shutdown();
        delete m_audioCapture;
        m_audioCapture = nullptr;
    }
    
    if (m_lipSyncProcessor) {
        delete m_lipSyncProcessor;
        m_lipSyncProcessor = nullptr;
    }
    
    // ウィンドウを破棄
    if (m_hWnd) {
        DestroyWindow(m_hWnd);
        m_hWnd = nullptr;
    }
    
    WSACleanup();
}

bool Live2DApp::LoadModel(const std::string& modelPath) {
    if (m_modelLoaded) {
        std::cerr << "[Live2DApp] Model already loaded" << std::endl;
        return false;
    }
    
    std::cout << "[Live2DApp] Loading model: " << modelPath << std::endl;
    
    // モデルファイルのパスからディレクトリを取得
    size_t lastSlash = modelPath.find_last_of("/\\");
    if (lastSlash == std::string::npos) {
        m_modelHomeDir = "./";
    } else {
        m_modelHomeDir = modelPath.substr(0, lastSlash + 1);
    }
    
    // モデル設定ファイル（.model3.json）を読み込む
    csmSizeInt size;
    csmByte* buffer = LoadFileAsBytes(modelPath, &size);
    if (!buffer) {
        std::cerr << "[Live2DApp] Failed to load model setting file: " << modelPath << std::endl;
        return false;
    }
    
    // JSONからモデル設定を読み込む
    m_modelSetting = new CubismModelSettingJson(buffer, size);
    ReleaseBytes(buffer);
    
    if (!m_modelSetting) {
        std::cerr << "[Live2DApp] Failed to parse model setting" << std::endl;
        return false;
    }
    
    // モデルをセットアップ
    if (!SetupModel(m_modelSetting)) {
        std::cerr << "[Live2DApp] Failed to setup model" << std::endl;
        return false;
    }
    
    m_modelLoaded = true;
    std::cout << "[Live2DApp] Model loaded successfully" << std::endl;
    return true;
}

void Live2DApp::SetExpression(const std::string& expressionName) {
    if (!m_model || !m_modelLoaded || !m_expressionManager) {
        return;
    }
    
    // 表情名をcsmStringに変換
    csmString exprName(expressionName.c_str());
    
    // 表情マップから取得（[]演算子を使用）
    ACubismMotion* motion = m_expressions[exprName];
    if (motion) {
        m_expressionManager->StartMotion(motion, false);
        std::cout << "[Live2DApp] Expression set: " << expressionName << std::endl;
    } else {
        std::cout << "[Live2DApp] Expression not found: " << expressionName << std::endl;
    }
}

void Live2DApp::SetLipSyncValue(float value) {
    // リップシンク値を設定（0.0～1.0）
    m_lipSyncValue = value;
    if (m_lipSyncValue < 0.0f) m_lipSyncValue = 0.0f;
    if (m_lipSyncValue > 1.0f) m_lipSyncValue = 1.0f;
}

void Live2DApp::SetMouthOpenValue(float value) {
    // 口の開き値を設定（0.0～1.0）
    m_mouthOpenValue = value;
    if (m_mouthOpenValue < 0.0f) m_mouthOpenValue = 0.0f;
    if (m_mouthOpenValue > 1.0f) m_mouthOpenValue = 1.0f;
}

void Live2DApp::SetMouthSmileValue(float value) {
    // 口の笑顔値を設定（0.0～1.0）
    m_mouthSmileValue = value;
    if (m_mouthSmileValue < 0.0f) m_mouthSmileValue = 0.0f;
    if (m_mouthSmileValue > 1.0f) m_mouthSmileValue = 1.0f;
}

void Live2DApp::SetMouthFormValue(float value) {
    // 口の横の値を設定（-1.0～1.0）
    m_mouthFormValue = value;
    if (m_mouthFormValue < -1.0f) m_mouthFormValue = -1.0f;
    if (m_mouthFormValue > 1.0f) m_mouthFormValue = 1.0f;
}

bool Live2DApp::ConnectWebSocket(const std::string& url) {
    if (m_wsClient) {
        m_wsClient->Disconnect();
        delete m_wsClient;
    }
    
    m_wsClient = new WebSocketClient();
    
    // メッセージのコールバックを設定
    m_wsClient->SetMessageCallback([this](const std::string& message) {
        // JSONを解析: {"type":"lipsync","value":0.5} または {"type":"expression","name":"Happy"}
        size_t typePos = message.find("\"type\":\"");
        size_t typeTokenLen = 8;  // "type":" の長さ
        if (typePos == std::string::npos) {
            typePos = message.find("\"type\": \"");
            typeTokenLen = 9;  // "type": " の長さ
        }
        if (typePos != std::string::npos) {
            typePos += typeTokenLen;
            size_t typeEndPos = message.find("\"", typePos);
            if (typeEndPos != std::string::npos) {
                std::string type = message.substr(typePos, typeEndPos - typePos);
                
                if (type == "lipsync") {
                    // リップシンクメッセージ
                    size_t valuePos = message.find("\"value\":", typeEndPos);
                    if (valuePos != std::string::npos) {
                        valuePos += 8;  // "value":の長さ
                        if (valuePos < message.size() && message[valuePos] == ' ') {
                            valuePos += 1;  // "value": の後の空白
                        }
                        size_t endPos = message.find_first_of(",}", valuePos);
                        if (endPos != std::string::npos) {
                            std::string valueStr = message.substr(valuePos, endPos - valuePos);
                            try {
                                float value = std::stof(valueStr);
                                this->SetLipSyncValue(value);
                                this->SetMouthOpenValue(value);
                                m_externalLipSyncActive = true;
                                m_lastExternalLipSyncMs = GetTickCount64();
                            } catch (...) {
                                // パースエラーは無視
                            }
                        }
                    }
                } else if (type == "mouth_form") {
                    size_t valuePos = message.find("\"value\":", typeEndPos);
                    if (valuePos != std::string::npos) {
                        valuePos += 8;
                        if (valuePos < message.size() && message[valuePos] == ' ') {
                            valuePos += 1;
                        }
                        size_t endPos = message.find_first_of(",}", valuePos);
                        if (endPos != std::string::npos) {
                            std::string valueStr = message.substr(valuePos, endPos - valuePos);
                            try {
                                float value = std::stof(valueStr);
                                this->SetMouthFormValue(value);
                                m_externalLipSyncActive = true;
                                m_lastExternalLipSyncMs = GetTickCount64();
                            } catch (...) {
                            }
                        }
                    }
                } else if (type == "expression" || type == "emotion") {
                    // 表情メッセージ
                    size_t namePos = message.find("\"name\":\"", typeEndPos);
                    if (namePos == std::string::npos) {
                        namePos = message.find("\"emotion\":\"", typeEndPos);
                        if (namePos != std::string::npos) {
                            namePos += 11;  // "emotion":"の長さ
                        }
                    } else {
                        namePos += 8;  // "name":"の長さ
                    }
                    if (namePos != std::string::npos) {
                        size_t nameEndPos = message.find("\"", namePos);
                        if (nameEndPos != std::string::npos) {
                            std::string exprName = message.substr(namePos, nameEndPos - namePos);
                            this->SetExpression(exprName);
                        }
                    }
                }
            }
        }
    });
    
    if (m_wsClient->Connect(url)) {
        std::cout << "[Live2DApp] WebSocket connected: " << url << std::endl;
        return true;
    } else {
        std::cerr << "[Live2DApp] WebSocket connection failed: " << url << std::endl;
        delete m_wsClient;
        m_wsClient = nullptr;
        return false;
    }
}

LRESULT CALLBACK Live2DApp::WindowProc(HWND hWnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
    if (g_app && g_app->m_hWnd == hWnd) {
        switch (uMsg) {
            case WM_DESTROY:
                PostQuitMessage(0);
                return 0;
            case WM_PAINT: {
                PAINTSTRUCT ps;
                BeginPaint(hWnd, &ps);
                g_app->Render();
                EndPaint(hWnd, &ps);
                return 0;
            }
            case WM_NCHITTEST: {
                // 右クリック時のみウィンドウをドラッグ可能にする
                // 左クリックはキャラクター移動用に予約
                return HTCLIENT;  // 通常のクライアント領域として扱う
            }
            case WM_RBUTTONDOWN: {
                // 右クリックでウィンドウをドラッグ開始
                g_app->m_windowDragging = true;
                POINT pt;
                GetCursorPos(&pt);
                g_app->m_windowDragStartX = pt.x;
                g_app->m_windowDragStartY = pt.y;
                SetCapture(hWnd);
                return 0;
            }
            case WM_RBUTTONUP: {
                // 右クリックが離された
                if (g_app->m_windowDragging) {
                    g_app->m_windowDragging = false;
                    ReleaseCapture();
                }
                return 0;
            }
            case WM_LBUTTONDOWN: {
                // マウス左ボタンが押された（キャラクター移動用）
                g_app->m_dragging = true;
                g_app->m_lastMouseX = LOWORD(lParam);
                g_app->m_lastMouseY = HIWORD(lParam);
                SetCapture(hWnd);  // マウスキャプチャを取得
                return 0;
            }
            case WM_MOUSEMOVE: {
                if (g_app->m_windowDragging) {
                    // ウィンドウを移動
                    POINT pt;
                    GetCursorPos(&pt);
                    RECT rect;
                    GetWindowRect(hWnd, &rect);
                    int deltaX = pt.x - g_app->m_windowDragStartX;
                    int deltaY = pt.y - g_app->m_windowDragStartY;
                    MoveWindow(hWnd, rect.left + deltaX, rect.top + deltaY, 
                              rect.right - rect.left, rect.bottom - rect.top, TRUE);
                    g_app->m_windowDragStartX = pt.x;
                    g_app->m_windowDragStartY = pt.y;
                } else if (g_app->m_dragging) {
                    // キャラクターを移動
                    int currentX = LOWORD(lParam);
                    int currentY = HIWORD(lParam);
                    int deltaX = currentX - g_app->m_lastMouseX;
                    int deltaY = currentY - g_app->m_lastMouseY;
                    
                    // ウィンドウサイズを取得して正規化
                    RECT rect;
                    GetClientRect(hWnd, &rect);
                    int width = rect.right - rect.left;
                    int height = rect.bottom - rect.top;
                    
                    // モデル位置を更新（ウィンドウサイズで正規化）
                    g_app->m_modelX += static_cast<float>(deltaX) / static_cast<float>(width) * 2.0f;
                    g_app->m_modelY -= static_cast<float>(deltaY) / static_cast<float>(height) * 2.0f;
                    
                    g_app->m_lastMouseX = currentX;
                    g_app->m_lastMouseY = currentY;
                }
                return 0;
            }
            case WM_LBUTTONUP: {
                // マウス左ボタンが離された
                if (g_app->m_dragging) {
                    g_app->m_dragging = false;
                    ReleaseCapture();  // マウスキャプチャを解放
                }
                return 0;
            }
            case WM_MOUSEWHEEL: {
                // マウスホイールで拡大縮小
                short delta = HIWORD(wParam);
                float scaleDelta = delta > 0 ? 1.1f : 0.9f;
                g_app->m_modelScale *= scaleDelta;
                
                // スケールを制限（0.1 ～ 3.0）
                if (g_app->m_modelScale < 0.1f) g_app->m_modelScale = 0.1f;
                if (g_app->m_modelScale > 3.0f) g_app->m_modelScale = 3.0f;
                
                return 0;
            }
        }
    }
    return DefWindowProc(hWnd, uMsg, wParam, lParam);
}

void Live2DApp::MessageLoop() {
    MSG msg = {};
    while (m_running) {
        while (PeekMessage(&msg, nullptr, 0, 0, PM_REMOVE)) {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
            
            if (msg.message == WM_QUIT) {
                m_running = false;
            }
        }
        
        // WebSocketメッセージを処理
        if (m_wsClient) {
            m_wsClient->Update();
        }
        
        // 仮想マイクから音声を取得してリップシンク値を計算
        if (m_audioCapture) {
            m_audioCapture->Update();
        }
        
        // 描画
        Render();
        Sleep(16);  // 約60FPS
    }
}

void Live2DApp::Render() {
    if (!m_hWnd || !m_glInitialized) return;
    
    // OpenGLコンテキストをアクティブにする
    if (!wglMakeCurrent(m_hDC, m_hGLRC)) {
        return;
    }
    
    // ウィンドウのサイズを取得
    RECT rect;
    GetClientRect(m_hWnd, &rect);
    int width = rect.right - rect.left;
    int height = rect.bottom - rect.top;
    
    // OpenGLのビューポートを設定
    glViewport(0, 0, width, height);
    
    // 背景をクリア
    glClearColor(0.4f, 0.6f, 1.0f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    
    // モデルが読み込まれている場合
    if (m_modelLoaded && m_model) {
        // モデルを更新
        UpdateModel();
        
        // モデルを描画
        // 注意: テクスチャが読み込まれていない場合、描画できない可能性があります
        Rendering::CubismRenderer* renderer = m_model->GetRenderer<Rendering::CubismRenderer>();
        if (renderer && m_modelMatrix) {
            // モデルマトリックスを更新（位置）
            m_modelMatrix->SetX(m_modelX);
            m_modelMatrix->SetY(m_modelY);
            
            // プロジェクション行列を設定
            CubismMatrix44 projection;
            float aspect = static_cast<float>(width) / static_cast<float>(height);
            projection.Scale(1.0f, aspect);
            
            // モデルマトリックスとプロジェクション行列を結合
            CubismMatrix44 mvp;
            mvp.MultiplyByMatrix(&projection);
            mvp.MultiplyByMatrix(m_modelMatrix);
            
            // スケールを適用
            mvp.Scale(m_modelScale, m_modelScale);
            
            renderer->SetMvpMatrix(&mvp);
            
            // モデルを描画
            renderer->DrawModel();
        }
    }
    
    // バッファをスワップ
    SwapBuffers(m_hDC);
}

void Live2DApp::WebSocketLoop() {
    // WebSocketメッセージ処理はMessageLoop内でUpdate()を呼び出すことで実装
}

bool Live2DApp::InitializeAudioCapture() {
    m_audioCapture = new AudioCapture();
    
    // リップシンクプロセッサを初期化
    m_lipSyncProcessor = new LipSyncProcessor(48000);
    
    // リップシンク値計算のコールバックを設定（リアルタイム日本語リップシンク）
    m_audioCapture->SetCallback([this](const float* samples, size_t sampleCount, int sampleRate) {
        if (!m_lipSyncProcessor) return;
        if (m_externalLipSyncActive) {
            uint64_t nowMs = GetTickCount64();
            if (nowMs - m_lastExternalLipSyncMs < 200) {
                return;  // 外部リップシンクを優先
            }
        }
        
        float mouthOpen = 0.0f;
        float mouthForm = 0.0f;
        
        m_lipSyncProcessor->ProcessFrame(samples, sampleCount, mouthOpen, mouthForm);
        
        m_lastLipSyncValue = mouthOpen;
        m_lastMouthOpenValue = mouthOpen;
        m_mouthFormValue = mouthForm;
        
        // 口形から笑顔成分を推定（"i/e"ほど笑顔寄り）
        float smileValue = std::max(0.0f, -mouthForm);
        smileValue *= (0.25f + 0.75f * mouthOpen);
        smileValue = std::min(1.0f, smileValue);
        
        this->SetLipSyncValue(mouthOpen);
        this->SetMouthOpenValue(mouthOpen);
        this->SetMouthSmileValue(smileValue);
    });
    
    if (m_audioCapture->Initialize("CABLE Output (VB-Audio Virtual Cable)")) {
        std::cout << "[Live2DApp] Audio capture initialized: CABLE Output (VB-Audio Virtual Cable)" << std::endl;
        return true;
    } else {
        std::cerr << "[Live2DApp] Audio capture initialization failed" << std::endl;
        delete m_audioCapture;
        m_audioCapture = nullptr;
        return false;
    }
}

csmByte* Live2DApp::LoadFileAsBytes(const std::string& filePath, csmSizeInt* outSize) {
    // UTF-8パスをワイド文字に変換
    wchar_t wideStr[MAX_PATH];
    int result = MultiByteToWideChar(CP_UTF8, 0, filePath.c_str(), -1, wideStr, MAX_PATH);
    if (result == 0) {
        std::cerr << "[Live2DApp] Failed to convert path to wide string: " << filePath << std::endl;
        return nullptr;
    }
    
    // ファイルサイズを取得
    struct _stat statBuf;
    if (_wstat(wideStr, &statBuf) != 0) {
        // エラー詳細を取得
        int err = errno;
        std::cerr << "[Live2DApp] Failed to stat file: " << filePath << std::endl;
        std::cerr << "[Live2DApp] Error code: " << err << std::endl;
        
        // 現在の作業ディレクトリを表示（デバッグ用）
        wchar_t currentDir[MAX_PATH];
        if (GetCurrentDirectoryW(MAX_PATH, currentDir)) {
            char currentDirA[MAX_PATH];
            WideCharToMultiByte(CP_UTF8, 0, currentDir, -1, currentDirA, MAX_PATH, nullptr, nullptr);
            std::cerr << "[Live2DApp] Current directory: " << currentDirA << std::endl;
        }
        return nullptr;
    }
    
    if (statBuf.st_size == 0) {
        std::cerr << "[Live2DApp] File size is zero: " << filePath << std::endl;
        return nullptr;
    }
    
    // ファイルを開く
    std::wfstream file;
    file.open(wideStr, std::ios::in | std::ios::binary);
    if (!file.is_open()) {
        std::cerr << "[Live2DApp] Failed to open file: " << filePath << std::endl;
        return nullptr;
    }
    
    // ファイルを読み込む
    *outSize = statBuf.st_size;
    csmByte* buffer = new csmByte[*outSize];
    std::wfilebuf* fileBuf = file.rdbuf();
    for (csmSizeInt i = 0; i < *outSize; i++) {
        buffer[i] = static_cast<csmByte>(fileBuf->sbumpc());
    }
    file.close();
    
    return buffer;
}

void Live2DApp::ReleaseBytes(csmByte* byteData) {
    delete[] byteData;
}

bool Live2DApp::SetupModel(ICubismModelSetting* setting) {
    if (!setting) {
        return false;
    }
    
    m_modelSetting = setting;
    
    // モデルファイル（.moc3）を読み込む
    const csmChar* modelFileName = m_modelSetting->GetModelFileName();
    if (strcmp(modelFileName, "") != 0) {
        std::string modelPath = m_modelHomeDir + std::string(modelFileName);
        std::cout << "[Live2DApp] Loading model file: " << modelPath << std::endl;
        
        csmSizeInt size;
        csmByte* buffer = LoadFileAsBytes(modelPath, &size);
        if (!buffer) {
            std::cerr << "[Live2DApp] Failed to load model file: " << modelPath << std::endl;
            return false;
        }
        
        // モデルを作成
        m_model = new CubismUserModel();
        if (!m_model) {
            std::cerr << "[Live2DApp] Failed to create model" << std::endl;
            ReleaseBytes(buffer);
            return false;
        }
        
        // MOCファイルを読み込む
        m_model->LoadModel(buffer, size);
        ReleaseBytes(buffer);
        
        std::cout << "[Live2DApp] Model file loaded successfully" << std::endl;
    } else {
        std::cerr << "[Live2DApp] Model file name is empty" << std::endl;
        return false;
    }
    
    // 表情ファイルを読み込む
    csmInt32 expressionCount = m_modelSetting->GetExpressionCount();
    if (expressionCount > 0) {
        std::cout << "[Live2DApp] Loading " << expressionCount << " expressions" << std::endl;
        for (csmInt32 i = 0; i < expressionCount; i++) {
            csmString name = m_modelSetting->GetExpressionName(i);
            csmString path = m_modelSetting->GetExpressionFileName(i);
            std::string expressionPath = m_modelHomeDir + std::string(path.GetRawString());
            
            csmSizeInt size;
            csmByte* buffer = LoadFileAsBytes(expressionPath, &size);
            if (buffer) {
                ACubismMotion* motion = m_model->LoadExpression(buffer, size, name.GetRawString());
                if (motion) {
                    // 表情をマップに保存
                    m_expressions[name] = motion;
                    std::cout << "[Live2DApp] Expression loaded: " << name.GetRawString() << std::endl;
                }
                ReleaseBytes(buffer);
            }
        }
    }
    
    // リップシンクパラメータIDを取得
    csmInt32 lipSyncCount = m_modelSetting->GetLipSyncParameterCount();
    if (lipSyncCount > 0) {
        std::cout << "[Live2DApp] Found " << lipSyncCount << " lip sync parameters" << std::endl;
        for (csmInt32 i = 0; i < lipSyncCount; i++) {
            const CubismId* lipSyncId = m_modelSetting->GetLipSyncParameterId(i);
            if (lipSyncId) {
                m_lipSyncIds.PushBack(lipSyncId);
                std::cout << "[Live2DApp] Lip sync parameter: " << lipSyncId->GetString().GetRawString() << std::endl;
            }
        }
    } else {
        std::cout << "[Live2DApp] No lip sync parameters found in model settings, trying default parameter names..." << std::endl;
        // デフォルトのリップシンクパラメータ名を試す
        const char* defaultLipSyncParams[] = {
            "ParamMouthOpenY",
            "ParamMouthForm",
            "ParamMouthOpen",
            "ParamMouth"
        };
        
        for (int i = 0; i < sizeof(defaultLipSyncParams) / sizeof(defaultLipSyncParams[0]); i++) {
            const CubismId* paramId = CubismFramework::GetIdManager()->GetId(defaultLipSyncParams[i]);
            if (paramId && m_model->GetModel()->GetParameterIndex(paramId) >= 0) {
                if (std::strcmp(defaultLipSyncParams[i], "ParamMouthForm") == 0) {
                    m_mouthFormId = paramId;
                    std::cout << "[Live2DApp] Found ParamMouthForm parameter" << std::endl;
                } else {
                    m_lipSyncIds.PushBack(paramId);
                    std::cout << "[Live2DApp] Using default lip sync parameter: " << defaultLipSyncParams[i] << std::endl;
                }
            }
        }
        
        if (m_lipSyncIds.GetSize() == 0) {
            std::cout << "[Live2DApp] Warning: No lip sync parameters found, lip-sync will not work" << std::endl;
        }
    }
    
    // VTS用パラメータを検索
    m_mouthSmileId = CubismFramework::GetIdManager()->GetId("VoiceFrequencyPlusMouthSmile");
    m_mouthOpenId = CubismFramework::GetIdManager()->GetId("VoiceVolumePlusMouthOpen");
    
    if (m_mouthSmileId && m_model->GetModel()->GetParameterIndex(m_mouthSmileId) >= 0) {
        std::cout << "[Live2DApp] Found VTS parameter: VoiceFrequencyPlusMouthSmile" << std::endl;
    } else {
        m_mouthSmileId = nullptr;
    }
    
    if (m_mouthOpenId && m_model->GetModel()->GetParameterIndex(m_mouthOpenId) >= 0) {
        std::cout << "[Live2DApp] Found VTS parameter: VoiceVolumePlusMouthOpen" << std::endl;
    } else {
        m_mouthOpenId = nullptr;
    }
    
    // OpenGLコンテキストをアクティブにする（テクスチャ読み込みのため）
    if (!m_glInitialized || !wglMakeCurrent(m_hDC, m_hGLRC)) {
        std::cerr << "[Live2DApp] OpenGL context not available for texture loading" << std::endl;
        return false;
    }
    
    // まばたきと呼吸を初期化
    if (m_modelSetting->GetEyeBlinkParameterCount() > 0) {
        m_eyeBlink = CubismEyeBlink::Create(m_modelSetting);
        std::cout << "[Live2DApp] EyeBlink initialized" << std::endl;
    }
    
    m_breath = CubismBreath::Create();
    csmVector<CubismBreath::BreathParameterData> breathParameters;
    // 首を傾ける動きを削除し、呼吸のみを設定
    breathParameters.PushBack(CubismBreath::BreathParameterData(
        CubismFramework::GetIdManager()->GetId(ParamBreath), 0.5f, 0.5f, 3.2345f, 0.5f));
    m_breath->SetParameters(breathParameters);
    std::cout << "[Live2DApp] Breath initialized (without head movement)" << std::endl;
    
    // モーション管理を初期化
    m_motionManager = new CubismMotionManager();
    m_expressionManager = new CubismExpressionMotionManager();
    
    // 待機モーション（Idle）をプリロード
    const csmChar* idleGroup = "Idle";
    if (m_modelSetting->GetMotionCount(idleGroup) > 0) {
        std::cout << "[Live2DApp] Preloading idle motions..." << std::endl;
        PreloadMotionGroup(idleGroup);
    } else {
        std::cout << "[Live2DApp] No idle motion group found, trying 'idle'..." << std::endl;
        // "idle"（小文字）も試す
        if (m_modelSetting->GetMotionCount("idle") > 0) {
            PreloadMotionGroup("idle");
        }
    }
    
    // 時間を初期化
    m_userTimeSeconds = 0.0f;
    m_lastFrameTime = static_cast<float>(GetTickCount64()) / 1000.0f;
    
    // 最初の待機モーションを開始
    StartRandomIdleMotion();
    
    // モデルマトリックスを初期化
    if (m_model && m_model->GetModel()) {
        // モデルのサイズに基づいてマトリックスを設定
        csmFloat32 modelWidth = m_model->GetModel()->GetCanvasWidth();
        csmFloat32 modelHeight = m_model->GetModel()->GetCanvasHeight();
        m_modelMatrix = new CubismModelMatrix(modelWidth, modelHeight);
        std::cout << "[Live2DApp] Model matrix initialized: " << modelWidth << "x" << modelHeight << std::endl;
    } else {
        m_modelMatrix = new CubismModelMatrix(2.0f, 2.0f);  // デフォルトサイズ
    }
    
    // Rendererを作成（OpenGL）
    // シェーダーファイルは FrameworkShaders/ という相対パスで探されるため、
    // 作業ディレクトリを実行ファイルのディレクトリに戻す必要があります
    char exePath[MAX_PATH];
    GetModuleFileNameA(nullptr, exePath, MAX_PATH);
    std::string exeDir = exePath;
    size_t lastSlash = exeDir.find_last_of("\\/");
    if (lastSlash != std::string::npos) {
        exeDir = exeDir.substr(0, lastSlash + 1);
    }
    
    // 作業ディレクトリを実行ファイルのディレクトリに戻す
    SetCurrentDirectoryA(exeDir.c_str());
    std::cout << "[Live2DApp] Working directory reset to: " << exeDir << std::endl;
    
    // Rendererを作成（OpenGL）
    // 注意: COPY_SHADERS.bat を実行して、シェーダーファイルを実行ファイルのディレクトリにコピーしてください
    m_model->CreateRenderer();
    
    // テクスチャを読み込む
    if (!SetupTextures()) {
        std::cerr << "[Live2DApp] Failed to setup textures" << std::endl;
        return false;
    }
    
    return true;
}

bool Live2DApp::InitializeOpenGL() {
    if (!m_hWnd) {
        return false;
    }
    
    // デバイスコンテキストを取得
    m_hDC = GetDC(m_hWnd);
    if (!m_hDC) {
        std::cerr << "[Live2DApp] Failed to get device context" << std::endl;
        return false;
    }
    
    // ピクセルフォーマットを設定
    PIXELFORMATDESCRIPTOR pfd = {};
    pfd.nSize = sizeof(PIXELFORMATDESCRIPTOR);
    pfd.nVersion = 1;
    pfd.dwFlags = PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL | PFD_DOUBLEBUFFER;
    pfd.iPixelType = PFD_TYPE_RGBA;
    pfd.cColorBits = 32;
    pfd.cDepthBits = 24;
    pfd.cStencilBits = 8;
    
    int pixelFormat = ChoosePixelFormat(m_hDC, &pfd);
    if (pixelFormat == 0) {
        std::cerr << "[Live2DApp] Failed to choose pixel format" << std::endl;
        ReleaseDC(m_hWnd, m_hDC);
        m_hDC = nullptr;
        return false;
    }
    
    if (!SetPixelFormat(m_hDC, pixelFormat, &pfd)) {
        std::cerr << "[Live2DApp] Failed to set pixel format" << std::endl;
        ReleaseDC(m_hWnd, m_hDC);
        m_hDC = nullptr;
        return false;
    }
    
    // OpenGLコンテキストを作成
    m_hGLRC = wglCreateContext(m_hDC);
    if (!m_hGLRC) {
        std::cerr << "[Live2DApp] Failed to create OpenGL context" << std::endl;
        ReleaseDC(m_hWnd, m_hDC);
        m_hDC = nullptr;
        return false;
    }
    
    // コンテキストをアクティブにする
    if (!wglMakeCurrent(m_hDC, m_hGLRC)) {
        std::cerr << "[Live2DApp] Failed to make OpenGL context current" << std::endl;
        wglDeleteContext(m_hGLRC);
        m_hGLRC = nullptr;
        ReleaseDC(m_hWnd, m_hDC);
        m_hDC = nullptr;
        return false;
    }
    
    // GLEWを初期化
    GLenum err = glewInit();
    if (err != GLEW_OK) {
        std::cerr << "[Live2DApp] Failed to initialize GLEW: " << glewGetErrorString(err) << std::endl;
        wglMakeCurrent(nullptr, nullptr);
        wglDeleteContext(m_hGLRC);
        m_hGLRC = nullptr;
        ReleaseDC(m_hWnd, m_hDC);
        m_hDC = nullptr;
        return false;
    }
    
    m_glInitialized = true;
    std::cout << "[Live2DApp] OpenGL initialized (GLEW " << glewGetString(GLEW_VERSION) << ")" << std::endl;
    return true;
}

bool Live2DApp::SetupTextures() {
    if (!m_model || !m_modelSetting) {
        std::cerr << "[Live2DApp] Model or model setting is null" << std::endl;
        return false;
    }
    
    // OpenGLコンテキストがアクティブであることを確認
    if (!m_glInitialized) {
        std::cerr << "[Live2DApp] OpenGL not initialized" << std::endl;
        return false;
    }
    
    Rendering::CubismRenderer_OpenGLES2* renderer = m_model->GetRenderer<Rendering::CubismRenderer_OpenGLES2>();
    if (!renderer) {
        std::cerr << "[Live2DApp] Renderer is null" << std::endl;
        return false;
    }
    
    // テクスチャファイルを読み込む
    csmInt32 textureCount = m_modelSetting->GetTextureCount();
    std::cout << "[Live2DApp] Loading " << textureCount << " textures" << std::endl;
    
    for (csmInt32 i = 0; i < textureCount; i++) {
        const csmChar* textureFileName = m_modelSetting->GetTextureFileName(i);
        if (!textureFileName || strcmp(textureFileName, "") == 0) {
            std::cout << "[Live2DApp] Texture " << i << " filename is empty, skipping" << std::endl;
            continue;
        }
        
        std::string texturePath = m_modelHomeDir + std::string(textureFileName);
        std::cout << "[Live2DApp] Loading texture: " << texturePath << std::endl;
        
        // ファイルを読み込む
        csmSizeInt fileSize;
        csmByte* fileData = LoadFileAsBytes(texturePath, &fileSize);
        if (!fileData || fileSize == 0) {
            std::cerr << "[Live2DApp] Failed to load texture file: " << texturePath << std::endl;
            continue;
        }
        
        // PNG画像をデコード
        int width, height, channels;
        unsigned char* imageData = stbi_load_from_memory(
            fileData,
            static_cast<int>(fileSize),
            &width,
            &height,
            &channels,
            STBI_rgb_alpha  // 常にRGBAとして読み込む
        );
        
        if (!imageData) {
            std::cerr << "[Live2DApp] Failed to decode PNG: " << texturePath << std::endl;
            ReleaseBytes(fileData);
            continue;
        }
        
        // OpenGLテクスチャを生成
        GLuint textureId;
        glGenTextures(1, &textureId);
        glBindTexture(GL_TEXTURE_2D, textureId);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, imageData);
        glGenerateMipmap(GL_TEXTURE_2D);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glBindTexture(GL_TEXTURE_2D, 0);
        
        // Live2Dレンダラーにテクスチャをバインド
        renderer->BindTexture(i, textureId);
        
        std::cout << "[Live2DApp] Texture loaded: " << texturePath 
                  << " (ID: " << textureId << ", " << width << "x" << height << ")" << std::endl;
        
        // メモリを解放
        stbi_image_free(imageData);
        ReleaseBytes(fileData);
    }
    
    // 乗算済みアルファ値の設定
    renderer->IsPremultipliedAlpha(false);
    
    std::cout << "[Live2DApp] Texture setup complete" << std::endl;
    return true;
}

void Live2DApp::UpdateModel() {
    if (!m_model || !m_modelLoaded) {
        return;
    }
    
    // デルタタイムを計算
    float currentTime = static_cast<float>(GetTickCount64()) / 1000.0f;
    float deltaTime = currentTime - m_lastFrameTime;
    m_lastFrameTime = currentTime;
    
    // デルタタイムを制限（最大0.1秒）
    if (deltaTime > 0.1f) {
        deltaTime = 0.1f;
    }
    
    m_userTimeSeconds += deltaTime;
    
    // パラメータをロード
    m_model->GetModel()->LoadParameters();
    
    // モーションを更新
    csmBool motionUpdated = false;
    if (m_motionManager) {
        if (m_motionManager->IsFinished()) {
            // モーションが終了したら、待機モーションをランダムに開始
            StartRandomIdleMotion();
        } else {
            motionUpdated = m_motionManager->UpdateMotion(m_model->GetModel(), deltaTime);
        }
    }
    
    // まばたきを更新（モーション中は更新しない）
    if (m_eyeBlink && !motionUpdated) {
        m_eyeBlink->UpdateParameters(m_model->GetModel(), deltaTime);
    }
    
    // 呼吸を更新
    if (m_breath) {
        m_breath->UpdateParameters(m_model->GetModel(), deltaTime);
    }
    
    // 表情を更新
    if (m_expressionManager) {
        m_expressionManager->UpdateMotion(m_model->GetModel(), deltaTime);
    }
    
    // リップシンクを更新（より動的な動き、口を早く締める）
    if (m_lipSyncIds.GetSize() > 0 && m_model->GetModel()) {
        // リップシンク値を適用（より速く反応、より速く閉じる）
        for (csmUint32 i = 0; i < m_lipSyncIds.GetSize(); ++i) {
            // 現在のパラメータ値を取得
            csmFloat32 currentValue = m_model->GetModel()->GetParameterValue(m_lipSyncIds[i]);
            
            // リップシンク値が0.0より大きい場合、目標値に向かって補間
            csmFloat32 targetValue = m_lipSyncValue;
            
            // 目標値が現在値より小さい場合（口を閉じる方向）、適度に速く補間
            // 目標値が現在値より大きい場合（口を開く方向）、通常の補間
            float interpolationFactor;
            if (targetValue < currentValue) {
                // 口を閉じる方向：適度に速く（0.55）
                interpolationFactor = 0.55f;
            } else {
                // 口を開く方向：通常（0.35）
                interpolationFactor = 0.35f;
            }
            
            // 目標値が0.0の場合（音声がない）、少し速く閉じる
            if (targetValue <= 0.0f) {
                interpolationFactor = 0.65f;
            }
            
            csmFloat32 newValue = currentValue * (1.0f - interpolationFactor) + targetValue * interpolationFactor;
            
            // パラメータ値を設定
            m_model->GetModel()->SetParameterValue(m_lipSyncIds[i], newValue);
        }
        
        // リップシンク値を減衰させる（音声がない場合のみ、適度に減衰）
        if (m_lipSyncValue > 0.0f) {
            m_lipSyncValue *= 0.97f;  // 適度な減衰
        } else {
            m_lipSyncValue = 0.0f;
        }
    }
    
    // VTS用パラメータを更新（より速く閉じる）
    if (m_mouthOpenId && m_model->GetModel()) {
        csmFloat32 currentValue = m_model->GetModel()->GetParameterValue(m_mouthOpenId);
        
        float interpolationFactor;
        if (m_mouthOpenValue < currentValue) {
            // 口を閉じる方向：適度に速く
            interpolationFactor = 0.55f;
        } else {
            // 口を開く方向：通常
            interpolationFactor = 0.35f;
        }
        
        if (m_mouthOpenValue <= 0.0f) {
            interpolationFactor = 0.65f;
        }
        
        csmFloat32 newValue = currentValue * (1.0f - interpolationFactor) + m_mouthOpenValue * interpolationFactor;
        m_model->GetModel()->SetParameterValue(m_mouthOpenId, newValue);
        
        // 減衰
        if (m_mouthOpenValue > 0.0f) {
            m_mouthOpenValue *= 0.97f;  // 適度な減衰
        } else {
            m_mouthOpenValue = 0.0f;
        }
    }
    
    if (m_mouthSmileId && m_model->GetModel()) {
        csmFloat32 currentValue = m_model->GetModel()->GetParameterValue(m_mouthSmileId);
        
        float interpolationFactor;
        if (m_mouthSmileValue < currentValue) {
            interpolationFactor = 0.55f;  // 適度に速く
        } else {
            interpolationFactor = 0.35f;
        }
        
        if (m_mouthSmileValue <= 0.0f) {
            interpolationFactor = 0.65f;
        }
        
        csmFloat32 newValue = currentValue * (1.0f - interpolationFactor) + m_mouthSmileValue * interpolationFactor;
        m_model->GetModel()->SetParameterValue(m_mouthSmileId, newValue);
        
        // 減衰
        if (m_mouthSmileValue > 0.0f) {
            m_mouthSmileValue *= 0.97f;  // 適度な減衰
        } else {
            m_mouthSmileValue = 0.0f;
        }
    }
    
    // ParamMouthFormを設定（-1.0～1.0）
    if (m_mouthFormId && m_model->GetModel()) {
        csmFloat32 currentValue = m_model->GetModel()->GetParameterValue(m_mouthFormId);
        float interpolationFactor = (std::abs(m_mouthFormValue) > std::abs(currentValue)) ? 0.4f : 0.28f;
        csmFloat32 newValue = currentValue * (1.0f - interpolationFactor) + m_mouthFormValue * interpolationFactor;
        m_model->GetModel()->SetParameterValue(m_mouthFormId, newValue);
    }
    
    // パラメータを保存
    m_model->GetModel()->SaveParameters();
    
    // モデルを更新
    m_model->GetModel()->Update();
}

void Live2DApp::PreloadMotionGroup(const csmChar* group) {
    if (!m_modelSetting || !m_model) {
        return;
    }
    
    const csmInt32 count = m_modelSetting->GetMotionCount(group);
    std::cout << "[Live2DApp] Preloading " << count << " motions from group: " << group << std::endl;
    
    for (csmInt32 i = 0; i < count; i++) {
        csmString path = m_modelSetting->GetMotionFileName(group, i);
        std::string motionPath = m_modelHomeDir + std::string(path.GetRawString());
        
        csmSizeInt size;
        csmByte* buffer = LoadFileAsBytes(motionPath, &size);
        if (buffer) {
            csmString name = Utils::CubismString::GetFormatedString("%s_%d", group, i);
            ACubismMotion* motion = m_model->LoadMotion(buffer, size, name.GetRawString());
            if (motion) {
                // モーションをマップに保存
                if (m_motions[name.GetRawString()] != NULL) {
                    ACubismMotion::Delete(m_motions[name.GetRawString()]);
                }
                m_motions[name.GetRawString()] = motion;
                std::cout << "[Live2DApp] Motion loaded: " << name.GetRawString() << std::endl;
            }
            ReleaseBytes(buffer);
        } else {
            std::cerr << "[Live2DApp] Failed to load motion: " << motionPath << std::endl;
        }
    }
}

void Live2DApp::StartRandomIdleMotion() {
    if (!m_modelSetting || !m_motionManager) {
        return;
    }
    
    // "Idle"または"idle"グループを探す
    const csmChar* idleGroup = nullptr;
    if (m_modelSetting->GetMotionCount("Idle") > 0) {
        idleGroup = "Idle";
    } else if (m_modelSetting->GetMotionCount("idle") > 0) {
        idleGroup = "idle";
    }
    
    if (!idleGroup) {
        return;  // 待機モーションがない場合は何もしない
    }
    
    const csmInt32 count = m_modelSetting->GetMotionCount(idleGroup);
    if (count == 0) {
        return;
    }
    
    // ランダムにモーションを選択
    csmInt32 motionNo = rand() % count;
    
    // モーションを開始
    csmString motionName = Utils::CubismString::GetFormatedString("%s_%d", idleGroup, motionNo);
    ACubismMotion* motion = m_motions[motionName.GetRawString()];
    
    if (motion) {
        // モーションを再生
        csmFloat32 fadeInTime = 1.0f;  // フェードイン時間
        motion->SetFadeInTime(fadeInTime);
        motion->SetFadeOutTime(0.0f);
        
        csmInt32 priority = 1;  // 優先度（低）
        if (m_motionManager->ReserveMotion(priority)) {
            m_motionManager->StartMotionPriority(motion, false, priority);
            std::cout << "[Live2DApp] Started idle motion: " << motionName.GetRawString() << std::endl;
        }
    } else {
        // モーションがプリロードされていない場合は、直接読み込む
        csmString path = m_modelSetting->GetMotionFileName(idleGroup, motionNo);
        std::string motionPath = m_modelHomeDir + std::string(path.GetRawString());
        
        csmSizeInt size;
        csmByte* buffer = LoadFileAsBytes(motionPath, &size);
        if (buffer) {
            ACubismMotion* loadedMotion = m_model->LoadMotion(buffer, size, motionName.GetRawString());
            if (loadedMotion) {
                // モーションをマップに保存
                if (m_motions[motionName.GetRawString()] != NULL) {
                    ACubismMotion::Delete(m_motions[motionName.GetRawString()]);
                }
                m_motions[motionName.GetRawString()] = loadedMotion;
                
                loadedMotion->SetFadeInTime(1.0f);
                loadedMotion->SetFadeOutTime(0.0f);
                csmInt32 priority = 1;
                if (m_motionManager->ReserveMotion(priority)) {
                    m_motionManager->StartMotionPriority(loadedMotion, false, priority);
                    std::cout << "[Live2DApp] Started idle motion (loaded on demand): " << motionName.GetRawString() << std::endl;
                }
            }
            ReleaseBytes(buffer);
        }
    }
}

// BiiAllocator実装
void* BiiAllocator::Allocate(const Csm::csmSizeType size) {
    return malloc(size);
}

void BiiAllocator::Deallocate(void* memory) {
    free(memory);
}

void* BiiAllocator::AllocateAligned(const Csm::csmSizeType size, const Csm::csmUint32 alignment) {
    size_t offset, shift, alignedAddress;
    void* allocation;
    void** preamble;

    offset = alignment - 1 + sizeof(void*);
    allocation = Allocate(size + static_cast<Csm::csmUint32>(offset));

    alignedAddress = reinterpret_cast<size_t>(allocation) + sizeof(void*);
    shift = alignedAddress % alignment;

    if (shift) {
        alignedAddress += (alignment - shift);
    }

    preamble = reinterpret_cast<void**>(alignedAddress);
    preamble[-1] = allocation;

    return reinterpret_cast<void*>(alignedAddress);
}

void BiiAllocator::DeallocateAligned(void* alignedMemory) {
    void** preamble;
    preamble = static_cast<void**>(alignedMemory);
    Deallocate(preamble[-1]);
}
