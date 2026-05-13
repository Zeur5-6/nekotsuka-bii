#ifndef AUDIO_CAPTURE_H
#define AUDIO_CAPTURE_H

#include <string>
#include <functional>

class AudioCapture {
public:
    using AudioCallback = std::function<void(const float* samples, size_t sampleCount, int sampleRate)>;
    
    AudioCapture();
    ~AudioCapture();
    
    bool Initialize(const std::string& deviceName = "CABLE Output (VB-Audio Virtual Cable)");
    void Shutdown();
    
    void SetCallback(AudioCallback callback) { m_callback = callback; }
    void Update();  // 音声データを取得してコールバックを呼び出す
    
    bool IsInitialized() const { return m_initialized; }
    
private:
    bool m_initialized;
    AudioCallback m_callback;
    
    // Windows WASAPI用の内部データ
    struct IAudioClient* m_audioClient;
    struct IAudioCaptureClient* m_captureClient;
    int m_sampleRate;
    int m_channels;
    size_t m_frameSize;
};

#endif // AUDIO_CAPTURE_H
