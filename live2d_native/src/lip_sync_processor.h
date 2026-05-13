/**
 * リアルタイム日本語リップシンク処理
 * LPCフォルマント + スペクトル比による母音推定
 */

#pragma once

#include <vector>
#include <complex>
#include <cmath>

class LipSyncProcessor {
public:
    LipSyncProcessor(int sampleRate = 48000);
    ~LipSyncProcessor();
    
    // 音声フレームを処理して mouthOpen と mouthForm を計算
    void ProcessFrame(const float* samples, size_t sampleCount, 
                     float& mouthOpen, float& mouthForm);
    
private:
    // 定数
    static constexpr int SAMPLE_RATE = 48000;
    static constexpr int FRAME_SIZE = 960;   // 20ms @ 48kHz
    static constexpr int HOP_SIZE = 480;     // 10ms @ 48kHz
    static constexpr int LPC_ORDER = 18;
    static constexpr int FFT_SIZE = 1024;
    
    // パラメータ
    static constexpr float NOISE_FLOOR_INIT = 0.015f;
    static constexpr float NOISE_FLOOR_ATTACK = 0.06f;
    static constexpr float NOISE_FLOOR_RELEASE = 0.0035f;
    static constexpr float PEAK_DECAY = 0.985f;
    static constexpr float PEAK_DECAY_SILENCE = 0.006f;
    static constexpr float OPEN_GAIN = 1.15f;
    static constexpr float ATTACK_OPEN = 0.55f;
    static constexpr float RELEASE_OPEN = 0.35f;
    static constexpr float SILENCE_RELEASE = 0.65f;
    static constexpr float VOICE_THRESHOLD = 0.08f;
    static constexpr float MIN_MOUTH_OPEN_FOR_VOWEL = 0.08f;
    static constexpr int VOWEL_SWITCH_FRAMES = 3;
    static constexpr int SILENCE_FRAMES_TO_CLOSE = 2;
    
    // リングバッファ
    std::vector<float> m_frameBuffer;
    size_t m_bufferPos;
    
    // 状態
    float m_mouthOpen;
    float m_mouthForm;
    int m_lastVowel;  // 0=a, 1=i, 2=u, 3=e, 4=o
    float m_lastMouthForm;
    int m_sameVowelCount;
    float m_lastRawLoudness;
    float m_noiseFloor;
    float m_peakLevel;
    int m_silenceFrames;
    int m_candidateVowel;
    int m_candidateCount;
    
    // FFT用バッファ
    std::vector<std::complex<float>> m_fftBuffer;
    
    // ヘルパー関数
    float CalculateRMS(const float* samples, size_t count);
    void PreEmphasis(std::vector<float>& samples, float alpha = 0.97f);
    void ApplyHammingWindow(std::vector<float>& samples);
    bool CalculateLPC(const std::vector<float>& samples, std::vector<float>& lpcCoeffs);
    bool ExtractFormants(const std::vector<float>& lpcCoeffs, float& f1, float& f2);
    int ClassifyVowelByFormant(float f1, float f2);
    void CalculateSpectrum(const std::vector<float>& samples, std::vector<float>& magnitude);
    int ClassifyVowelBySpectrum(const std::vector<float>& magnitude);
    float SmoothStep(float edge0, float edge1, float x);
    void FFT(std::vector<std::complex<float>>& x);
    float CalculateSpectralCentroid(const std::vector<float>& magnitude, float lowHz, float highHz);
    void CalculateBandEnergies(const std::vector<float>& magnitude, float& low, float& mid, float& high);
    int ClassifyVowelByBands(float low, float mid, float high);
};
