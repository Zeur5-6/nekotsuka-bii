#include "websocket_client.h"
#include <winsock2.h>
#include <ws2tcpip.h>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <algorithm>
#include <random>
#include <iomanip>
#include <sstream>

#pragma comment(lib, "ws2_32.lib")

WebSocketClient::WebSocketClient() : m_connected(false), m_socket(nullptr) {
}

WebSocketClient::~WebSocketClient() {
    Disconnect();
}

bool WebSocketClient::Connect(const std::string& url) {
    // URLを解析: ws://localhost:8765
    std::string host = "localhost";
    int port = 8765;
    
    if (url.find("ws://") == 0) {
        std::string rest = url.substr(5);
        size_t colon = rest.find(':');
        if (colon != std::string::npos) {
            host = rest.substr(0, colon);
            port = std::stoi(rest.substr(colon + 1));
        } else {
            host = rest;
        }
    }
    
    // TCP接続
    SOCKET sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (sock == INVALID_SOCKET) {
        std::cerr << "[WebSocket] Failed to create socket" << std::endl;
        return false;
    }
    
    sockaddr_in addr = {};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    
    // ホスト名を解決
    addrinfo hints = {};
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    addrinfo* result = nullptr;
    
    if (getaddrinfo(host.c_str(), nullptr, &hints, &result) != 0) {
        std::cerr << "[WebSocket] Failed to resolve host: " << host << std::endl;
        closesocket(sock);
        return false;
    }
    
    addr.sin_addr = ((sockaddr_in*)result->ai_addr)->sin_addr;
    freeaddrinfo(result);
    
    if (connect(sock, (sockaddr*)&addr, sizeof(addr)) != 0) {
        std::cerr << "[WebSocket] Failed to connect to " << host << ":" << port << std::endl;
        closesocket(sock);
        return false;
    }
    
    // WebSocketハンドシェイク
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, 255);
    
    std::vector<unsigned char> key_bytes(16);
    for (int i = 0; i < 16; i++) {
        key_bytes[i] = dis(gen);
    }
    
    std::string key_base64;
    const char base64_chars[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    for (int i = 0; i < 16; i += 3) {
        unsigned int b1 = key_bytes[i];
        unsigned int b2 = (i + 1 < 16) ? key_bytes[i + 1] : 0;
        unsigned int b3 = (i + 2 < 16) ? key_bytes[i + 2] : 0;
        
        unsigned int combined = (b1 << 16) | (b2 << 8) | b3;
        
        key_base64 += base64_chars[(combined >> 18) & 0x3F];
        key_base64 += base64_chars[(combined >> 12) & 0x3F];
        if (i + 1 < 16) {
            key_base64 += base64_chars[(combined >> 6) & 0x3F];
        } else {
            key_base64 += '=';
        }
        if (i + 2 < 16) {
            key_base64 += base64_chars[combined & 0x3F];
        } else {
            key_base64 += '=';
        }
    }
    
    std::ostringstream handshake;
    handshake << "GET / HTTP/1.1\r\n";
    handshake << "Host: " << host << ":" << port << "\r\n";
    handshake << "Upgrade: websocket\r\n";
    handshake << "Connection: Upgrade\r\n";
    handshake << "Sec-WebSocket-Key: " << key_base64 << "\r\n";
    handshake << "Sec-WebSocket-Version: 13\r\n";
    handshake << "\r\n";
    
    std::string handshake_str = handshake.str();
    if (send(sock, handshake_str.c_str(), handshake_str.length(), 0) == SOCKET_ERROR) {
        std::cerr << "[WebSocket] Failed to send handshake" << std::endl;
        closesocket(sock);
        return false;
    }
    
    // ハンドシェイク応答を受信
    char buffer[4096];
    int received = recv(sock, buffer, sizeof(buffer) - 1, 0);
    if (received <= 0) {
        std::cerr << "[WebSocket] Failed to receive handshake response" << std::endl;
        closesocket(sock);
        return false;
    }
    
    buffer[received] = '\0';
    std::string response(buffer);
    
    if (response.find("HTTP/1.1 101") == std::string::npos) {
        std::cerr << "[WebSocket] Handshake failed: " << response << std::endl;
        closesocket(sock);
        return false;
    }
    
    m_socket = (void*)sock;
    m_connected = true;
    std::cout << "[WebSocket] Connected to " << host << ":" << port << std::endl;
    return true;
}

void WebSocketClient::Disconnect() {
    if (m_connected && m_socket) {
        closesocket((SOCKET)m_socket);
        m_socket = nullptr;
        m_connected = false;
        std::cout << "[WebSocket] Disconnected" << std::endl;
    }
}

void WebSocketClient::Update() {
    if (!m_connected || !m_socket) {
        return;
    }
    
    // ノンブロッキングでデータを受信
    fd_set readfds;
    FD_ZERO(&readfds);
    FD_SET((SOCKET)m_socket, &readfds);
    
    timeval timeout = {};
    timeout.tv_sec = 0;
    timeout.tv_usec = 0;
    
    if (select(0, &readfds, nullptr, nullptr, &timeout) > 0) {
        char buffer[4096];
        int received = recv((SOCKET)m_socket, buffer, sizeof(buffer), 0);
        
        if (received > 0) {
            std::string message;
            if (ParseWebSocketFrame(buffer, received, message)) {
                if (m_messageCallback) {
                    m_messageCallback(message);
                }
            }
        } else if (received == 0) {
            // 接続が閉じられた
            Disconnect();
        }
    }
}

bool WebSocketClient::ParseWebSocketFrame(const char* data, size_t len, std::string& outMessage) {
    if (len < 2) return false;
    
    unsigned char byte0 = data[0];
    unsigned char byte1 = data[1];
    
    bool fin = (byte0 & 0x80) != 0;
    int opcode = byte0 & 0x0F;
    bool masked = (byte1 & 0x80) != 0;
    size_t payloadLen = byte1 & 0x7F;
    
    size_t offset = 2;
    
    if (payloadLen == 126) {
        if (len < 4) return false;
        payloadLen = (data[2] << 8) | data[3];
        offset = 4;
    } else if (payloadLen == 127) {
        if (len < 10) return false;
        payloadLen = 0;
        for (int i = 0; i < 8; i++) {
            payloadLen = (payloadLen << 8) | data[2 + i];
        }
        offset = 10;
    }
    
    if (opcode == 0x8) {
        // クローズフレーム
        Disconnect();
        return false;
    }
    
    if (opcode != 0x1) {
        // テキストフレーム以外は無視
        return false;
    }
    
    unsigned char mask[4] = {0};
    if (masked) {
        if (len < offset + 4) return false;
        for (int i = 0; i < 4; i++) {
            mask[i] = data[offset + i];
        }
        offset += 4;
    }
    
    if (len < offset + payloadLen) return false;
    
    outMessage.resize(payloadLen);
    for (size_t i = 0; i < payloadLen; i++) {
        if (masked) {
            outMessage[i] = data[offset + i] ^ mask[i % 4];
        } else {
            outMessage[i] = data[offset + i];
        }
    }
    
    return true;
}

std::string WebSocketClient::CreateWebSocketFrame(const std::string& message) {
    std::vector<unsigned char> frame;
    
    // FIN + テキストフレーム
    frame.push_back(0x81);
    
    size_t len = message.length();
    if (len < 126) {
        frame.push_back(len);
    } else if (len < 65536) {
        frame.push_back(126);
        frame.push_back((len >> 8) & 0xFF);
        frame.push_back(len & 0xFF);
    } else {
        frame.push_back(127);
        for (int i = 7; i >= 0; i--) {
            frame.push_back((len >> (i * 8)) & 0xFF);
        }
    }
    
    frame.insert(frame.end(), message.begin(), message.end());
    
    return std::string(frame.begin(), frame.end());
}
