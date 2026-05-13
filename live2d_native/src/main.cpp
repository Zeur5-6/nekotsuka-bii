/**
 * Live2D Native アプリケーション - メインエントリーポイント
 * C++初心者向けのシンプルな実装
 */

#include "live2d_app.h"
#include <iostream>

int main() {
    std::cout << "Bii Live2D Native App" << std::endl;
    std::cout << "================================" << std::endl;
    
    // アプリケーションを作成
    Live2DApp app;
    
    // 初期化
    if (!app.Initialize()) {
        std::cerr << "Initialization failed" << std::endl;
        return 1;
    }
    
    // モデルを読み込む（実行ファイルのディレクトリから見た相対パス）
    // 実行ファイルは live2d_native/BiiLive2dNative/x64/Debug/ にある
    // モデルファイルは live2d_app/models/bii/Usa Maid/ にある
    std::string modelPath = "../../../live2d_app/models/bii/Usa Maid/Usa Maid.model3.json";
    
    // 絶対パスも試す（開発環境用）
    std::string absPath = "C:/Users/user/Downloads/sousaku/modelfile/live2d_app/models/bii/Usa Maid/Usa Maid.model3.json";
    
    if (!app.LoadModel(modelPath)) {
        std::cerr << "[Live2DApp] Relative path failed, trying absolute path..." << std::endl;
        if (!app.LoadModel(absPath)) {
            std::cerr << "Failed to load model with both paths" << std::endl;
            std::cerr << "  Relative: " << modelPath << std::endl;
            std::cerr << "  Absolute: " << absPath << std::endl;
        }
    }
    
    // 実行
    std::cout << "Starting application..." << std::endl;
    app.Run();
    
    // 終了
    app.Shutdown();
    std::cout << "Application terminated" << std::endl;
    
    return 0;
}
