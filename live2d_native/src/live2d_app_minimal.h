/**
 * Live2D Native アプリケーション（最小構成版）
 * Live2D SDKなしでもビルドできるバージョン
 * 
 * 注意: このバージョンではLive2Dモデルは表示できません。
 * 基本的なウィンドウ表示のみをテストするために使用してください。
 */

#ifndef LIVE2D_APP_MINIMAL_H
#define LIVE2D_APP_MINIMAL_H

#include <string>
#include <memory>
#include <atomic>

// Windows API
#ifdef _WIN32
// winsock2.hをwindows.hの前にインクルードする必要がある
#define WIN32_LEAN_AND_MEAN  // winsock.hのインクルードを防ぐ
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#pragma comment(lib, "ws2_32.lib")
#endif

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
    
    // モデルを読み込む（SDKなしでは動作しない）
    bool LoadModel(const std::string& modelPath);
    
    // 表情を設定（SDKなしでは動作しない）
    void SetExpression(const std::string& expressionName);
    
    // WebSocket接続
    bool ConnectWebSocket(const std::string& url = "ws://localhost:8765");
    
private:
    // ウィンドウハンドル
    HWND m_hWnd;
    
    // 実行フラグ
    std::atomic<bool> m_running;
    
    // WebSocket接続（簡易版）
    SOCKET m_wsSocket;
    
    // ウィンドウプロシージャ
    static LRESULT CALLBACK WindowProc(HWND hWnd, UINT uMsg, WPARAM wParam, LPARAM lParam);
    
    // メッセージループ
    void MessageLoop();
    
    // 描画
    void Render();
};

#endif // LIVE2D_APP_MINIMAL_H
