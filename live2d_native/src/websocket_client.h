#ifndef WEBSOCKET_CLIENT_H
#define WEBSOCKET_CLIENT_H

#include <string>
#include <functional>

class WebSocketClient {
public:
    using MessageCallback = std::function<void(const std::string&)>;
    
    WebSocketClient();
    ~WebSocketClient();
    
    bool Connect(const std::string& url);
    void Disconnect();
    bool IsConnected() const { return m_connected; }
    
    void SetMessageCallback(MessageCallback callback) { m_messageCallback = callback; }
    void Update();  // メッセージを受信してコールバックを呼び出す
    
private:
    bool m_connected;
    void* m_socket;  // SOCKET型（前方宣言のためvoid*）
    MessageCallback m_messageCallback;
    
    bool ParseWebSocketFrame(const char* data, size_t len, std::string& outMessage);
    std::string CreateWebSocketFrame(const std::string& message);
};

#endif // WEBSOCKET_CLIENT_H
