/**
 * Live2D Native アプリケーション
 * C++初心者向けのシンプルな実装
 */

#ifndef LIVE2D_APP_H
#define LIVE2D_APP_H

#include <string>
#include <memory>
#include <thread>
#include <atomic>
#include <cstdint>

// Windows API
#ifdef _WIN32
// winsock2.hをwindows.hの前にインクルードする必要がある
#define WIN32_LEAN_AND_MEAN  // winsock.hのインクルードを防ぐ
#define NOMINMAX  // Windowsのmin/maxマクロを無効化
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#pragma comment(lib, "ws2_32.lib")
#endif

// Live2D Cubism SDK
#include <CubismFramework.hpp>
#include <ICubismAllocator.hpp>
#include <Model/CubismUserModel.hpp>
#include <Model/CubismMoc.hpp>
#include <ICubismModelSetting.hpp>
#include <CubismModelSettingJson.hpp>
#include <Utils/CubismString.hpp>
#include <Id/CubismIdManager.hpp>
#include <Motion/CubismMotion.hpp>
#include <Motion/CubismMotionQueueEntry.hpp>
#include <CubismDefaultParameterId.hpp>
#include <Type/csmMap.hpp>
#include <Utils/CubismString.hpp>
#include <Math/CubismModelMatrix.hpp>

using namespace Live2D::Cubism::Framework;
using namespace Live2D::Cubism::Framework::DefaultParameterId;

// 前方宣言
class WebSocketClient;
class AudioCapture;
class LipSyncProcessor;

// メモリアロケーター
class BiiAllocator : public Csm::ICubismAllocator {
public:
    void* Allocate(const Csm::csmSizeType size) override;
    void Deallocate(void* memory) override;
    void* AllocateAligned(const Csm::csmSizeType size, const Csm::csmUint32 alignment) override;
    void DeallocateAligned(void* alignedMemory) override;
};

class Live2DApp {
public:
    Live2DApp();
    ~Live2DApp();
    
    // 初期化
    bool Initialize();
    
    // 実行
    void Run();
    
    // 終了
    void Shutdown();
    
    // モデルを読み込む
    bool LoadModel(const std::string& modelPath);
    
    // 表情を設定
    void SetExpression(const std::string& expressionName);
    
    // リップシンク値を設定
    void SetLipSyncValue(float value);
    void SetMouthOpenValue(float value);
    void SetMouthSmileValue(float value);
    void SetMouthFormValue(float value);
    
    // WebSocket接続
    bool ConnectWebSocket(const std::string& url = "ws://localhost:8765");
    
private:
    // ウィンドウハンドル
    HWND m_hWnd;
    
    // 実行フラグ
    std::atomic<bool> m_running;
    
    // WebSocketクライアント
    WebSocketClient* m_wsClient;
    
    // Live2Dモデル関連
    CubismUserModel* m_model;
    ICubismModelSetting* m_modelSetting;
    std::string m_modelHomeDir;
    bool m_modelLoaded;
    BiiAllocator* m_allocator;
    Csm::CubismFramework::Option m_cubismOption;  ///< Cubism SDK Option
    
    // アニメーション関連
    CubismEyeBlink* m_eyeBlink;  ///< まばたき
    CubismBreath* m_breath;  ///< 呼吸
    CubismMotionManager* m_motionManager;  ///< モーション管理
    CubismExpressionMotionManager* m_expressionManager;  ///< 表情管理
    csmMap<csmString, ACubismMotion*> m_motions;  ///< 読み込まれているモーションのリスト
    csmMap<csmString, ACubismMotion*> m_expressions;  ///< 読み込まれている表情のリスト
    float m_userTimeSeconds;  ///< ユーザー時間（秒）
    float m_lastFrameTime;  ///< 前フレームの時間
    
    // モデル操作関連
    CubismModelMatrix* m_modelMatrix;  ///< モデルマトリックス
    float m_modelScale;  ///< モデルのスケール
    float m_modelX;  ///< モデルのX位置
    float m_modelY;  ///< モデルのY位置
    bool m_dragging;  ///< ドラッグ中かどうか（キャラクター移動用）
    bool m_windowDragging;  ///< ウィンドウドラッグ中かどうか
    int m_lastMouseX;  ///< 前回のマウスX座標
    int m_lastMouseY;  ///< 前回のマウスY座標
    int m_windowDragStartX;  ///< ウィンドウドラッグ開始時のX座標
    int m_windowDragStartY;  ///< ウィンドウドラッグ開始時のY座標
    
    // リップシンク関連
    csmVector<const CubismId*> m_lipSyncIds;  ///< リップシンクパラメータID
    float m_lipSyncValue;  ///< リップシンク値（0.0～1.0）
    const CubismId* m_mouthSmileId;  ///< VoiceFrequencyPlusMouthSmileパラメータID
    const CubismId* m_mouthOpenId;  ///< VoiceVolumePlusMouthOpenパラメータID
    const CubismId* m_mouthFormId;  ///< ParamMouthFormパラメータID
    float m_mouthSmileValue;  ///< 口の笑顔値（0.0～1.0）
    float m_mouthOpenValue;  ///< 口の開き値（0.0～1.0）
    float m_lastLipSyncValue;  ///< 前回のリップシンク値（滑らかな動き用）
    float m_lastMouthOpenValue;  ///< 前回の口の開き値（滑らかな動き用）
    float m_lastMouthSmileValue;  ///< 前回の口の笑顔値（滑らかな動き用）
    float m_mouthFormValue;  ///< 口の横の値（-1.0～1.0）
    bool m_externalLipSyncActive;  ///< 外部リップシンクが有効か
    uint64_t m_lastExternalLipSyncMs;  ///< 外部リップシンク受信時刻
    
    // リップシンクプロセッサ
    LipSyncProcessor* m_lipSyncProcessor;
    
    // 仮想マイク音声キャプチャ
    AudioCapture* m_audioCapture;
    
    // OpenGL関連
    HDC m_hDC;
    HGLRC m_hGLRC;
    bool m_glInitialized;
    
    // ウィンドウプロシージャ
    static LRESULT CALLBACK WindowProc(HWND hWnd, UINT uMsg, WPARAM wParam, LPARAM lParam);
    
    // メッセージループ
    void MessageLoop();
    
    // WebSocketメッセージ処理
    void WebSocketLoop();
    
    // 仮想マイク音声キャプチャの初期化
    bool InitializeAudioCapture();
    
    // 描画
    void Render();
    
    // ファイル読み込みヘルパー
    csmByte* LoadFileAsBytes(const std::string& filePath, csmSizeInt* outSize);
    void ReleaseBytes(csmByte* byteData);
    
    // CubismFramework用の静的ラッパー関数（フレンド関数）
    friend csmByte* LoadFileAsBytesForCubism(const std::string filePath, csmSizeInt* outSize);
    friend void ReleaseBytesForCubism(csmByte* byteData);
    
    // モデル設定
    bool SetupModel(ICubismModelSetting* setting);
    
    // モーショングループをプリロード
    void PreloadMotionGroup(const csmChar* group);
    
    // ランダムな待機モーションを開始
    void StartRandomIdleMotion();
    
    // テクスチャ設定
    bool SetupTextures();
    
    // OpenGL初期化
    bool InitializeOpenGL();
    
    // モデル更新
    void UpdateModel();
};

#endif // LIVE2D_APP_H
