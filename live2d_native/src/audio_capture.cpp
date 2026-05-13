#include "audio_capture.h"
#include <iostream>
#include <windows.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <functiondiscoverykeys_devpkey.h>
#include <comdef.h>
#include <vector>

#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "uuid.lib")

// REFTIMESの定義（100ナノ秒単位）
#define REFTIMES_PER_SEC  10000000
#define REFTIMES_PER_MILLISEC  10000

// COM初期化用
struct ComInitializer {
    ComInitializer() { CoInitializeEx(nullptr, COINIT_MULTITHREADED); }
    ~ComInitializer() { CoUninitialize(); }
};

AudioCapture::AudioCapture() 
    : m_initialized(false)
    , m_audioClient(nullptr)
    , m_captureClient(nullptr)
    , m_sampleRate(0)
    , m_channels(0)
    , m_frameSize(0)
{
}

AudioCapture::~AudioCapture() {
    Shutdown();
}

bool AudioCapture::Initialize(const std::string& deviceName) {
    if (m_initialized) {
        Shutdown();
    }
    
    static ComInitializer comInit;
    
    // デバイス列挙器を取得
    IMMDeviceEnumerator* enumerator = nullptr;
    HRESULT hr = CoCreateInstance(
        __uuidof(MMDeviceEnumerator),
        nullptr,
        CLSCTX_ALL,
        __uuidof(IMMDeviceEnumerator),
        (void**)&enumerator
    );
    
    if (FAILED(hr)) {
        std::cerr << "[AudioCapture] Failed to create device enumerator" << std::endl;
        return false;
    }
    
    // 指定されたデバイス名でデバイスを検索
    IMMDevice* device = nullptr;
    IMMDeviceCollection* devices = nullptr;
    
    hr = enumerator->EnumAudioEndpoints(eCapture, DEVICE_STATE_ACTIVE, &devices);
    if (FAILED(hr)) {
        enumerator->Release();
        std::cerr << "[AudioCapture] Failed to enumerate devices" << std::endl;
        return false;
    }
    
    UINT count = 0;
    devices->GetCount(&count);
    
    std::cout << "[AudioCapture] Searching for device containing: " << deviceName << std::endl;
    std::cout << "[AudioCapture] Found " << count << " capture devices:" << std::endl;
    
    bool found = false;
    for (UINT i = 0; i < count; i++) {
        IMMDevice* dev = nullptr;
        devices->Item(i, &dev);
        
        IPropertyStore* props = nullptr;
        dev->OpenPropertyStore(STGM_READ, &props);
        
        PROPVARIANT name;
        PropVariantInit(&name);
        props->GetValue(PKEY_Device_FriendlyName, &name);
        
        std::wstring wname(name.pwszVal);
        std::string aname(wname.begin(), wname.end());
        
        // デバイス名を表示（デバッグ用）
        std::cout << "[AudioCapture]   [" << i << "] " << aname << std::endl;
        
        if (aname.find(deviceName) != std::string::npos) {
            device = dev;
            found = true;
            std::cout << "[AudioCapture] ✓ Matched device: " << aname << std::endl;
        } else {
            dev->Release();
        }
        
        PropVariantClear(&name);
        props->Release();
        
        if (found) break;
    }
    
    devices->Release();
    enumerator->Release();
    
    if (!found || !device) {
        std::cerr << "[AudioCapture] Device not found: " << deviceName << std::endl;
        return false;
    }
    
    // オーディオクライアントを取得
    hr = device->Activate(__uuidof(IAudioClient), CLSCTX_ALL, nullptr, (void**)&m_audioClient);
    device->Release();
    
    if (FAILED(hr)) {
        std::cerr << "[AudioCapture] Failed to activate audio client" << std::endl;
        return false;
    }
    
    // フォーマットを取得
    IAudioClient* audioClient = (IAudioClient*)m_audioClient;
    WAVEFORMATEX* format = nullptr;
    hr = audioClient->GetMixFormat(&format);
    if (FAILED(hr)) {
        audioClient->Release();
        m_audioClient = nullptr;
        std::cerr << "[AudioCapture] Failed to get mix format" << std::endl;
        return false;
    }
    
    m_sampleRate = format->nSamplesPerSec;
    m_channels = format->nChannels;
    m_frameSize = format->nBlockAlign;
    
    // オーディオクライアントを初期化
    REFERENCE_TIME bufferDuration = REFTIMES_PER_MILLISEC * 100;  // 100ms
    hr = audioClient->Initialize(
        AUDCLNT_SHAREMODE_SHARED,
        0,
        bufferDuration,
        0,
        format,
        nullptr
    );
    
    CoTaskMemFree(format);
    
    if (FAILED(hr)) {
        audioClient->Release();
        m_audioClient = nullptr;
        std::cerr << "[AudioCapture] Failed to initialize audio client" << std::endl;
        return false;
    }
    
    // キャプチャクライアントを取得
    IAudioCaptureClient* captureClient = nullptr;
    hr = audioClient->GetService(__uuidof(IAudioCaptureClient), (void**)&captureClient);
    if (FAILED(hr)) {
        audioClient->Release();
        m_audioClient = nullptr;
        std::cerr << "[AudioCapture] Failed to get capture client" << std::endl;
        return false;
    }
    m_captureClient = captureClient;
    
    // キャプチャを開始
    hr = audioClient->Start();
    if (FAILED(hr)) {
        captureClient->Release();
        audioClient->Release();
        m_captureClient = nullptr;
        m_audioClient = nullptr;
        std::cerr << "[AudioCapture] Failed to start capture" << std::endl;
        return false;
    }
    
    m_initialized = true;
    std::cout << "[AudioCapture] Initialized: " << deviceName 
              << " (Rate: " << m_sampleRate << ", Channels: " << m_channels << ")" << std::endl;
    return true;
}

void AudioCapture::Shutdown() {
    if (m_initialized) {
        IAudioClient* audioClient = (IAudioClient*)m_audioClient;
        if (audioClient) {
            audioClient->Stop();
        }
        
        IAudioCaptureClient* captureClient = (IAudioCaptureClient*)m_captureClient;
        if (captureClient) {
            captureClient->Release();
            m_captureClient = nullptr;
        }
        
        if (audioClient) {
            audioClient->Release();
            m_audioClient = nullptr;
        }
        
        m_initialized = false;
        std::cout << "[AudioCapture] Shutdown" << std::endl;
    }
}

void AudioCapture::Update() {
    if (!m_initialized || !m_captureClient) {
        return;
    }
    
    // 利用可能なデータを取得
    IAudioCaptureClient* captureClient = (IAudioCaptureClient*)m_captureClient;
    UINT32 numFramesAvailable = 0;
    DWORD flags = 0;
    BYTE* data = nullptr;
    UINT64 devicePosition = 0;
    UINT64 qpcPosition = 0;
    
    HRESULT hr = captureClient->GetBuffer(&data, &numFramesAvailable, &flags, &devicePosition, &qpcPosition);
    
    if (SUCCEEDED(hr) && numFramesAvailable > 0) {
        // データをfloat配列に変換
        size_t sampleCount = numFramesAvailable * m_channels;
        std::vector<float> samples(sampleCount);
        
        // 16bit PCMとして処理（一般的なフォーマット）
        int16_t* pcmData = (int16_t*)data;
        for (size_t i = 0; i < sampleCount; i++) {
            samples[i] = pcmData[i] / 32768.0f;  // -1.0～1.0に正規化
        }
        
        // コールバックを呼び出し
        if (m_callback) {
            m_callback(samples.data(), sampleCount, m_sampleRate);
        }
        
        // バッファを解放
        captureClient->ReleaseBuffer(numFramesAvailable);
    }
}
