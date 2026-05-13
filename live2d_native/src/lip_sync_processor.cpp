/**
 * リアルタイム日本語リップシンク処理実装
 */

#include "lip_sync_processor.h"
#include <algorithm>
#include <numeric>
#include <cmath>

LipSyncProcessor::LipSyncProcessor(int sampleRate)
    : m_frameBuffer(FRAME_SIZE, 0.0f)
    , m_bufferPos(0)
    , m_mouthOpen(0.0f)
    , m_mouthForm(0.0f)
    , m_lastVowel(0)  // 'a'
    , m_lastMouthForm(0.0f)
    , m_sameVowelCount(0)
    , m_lastRawLoudness(0.0f)
    , m_noiseFloor(NOISE_FLOOR_INIT)
    , m_peakLevel(NOISE_FLOOR_INIT)
    , m_silenceFrames(0)
    , m_candidateVowel(0)
    , m_candidateCount(0)
    , m_fftBuffer(FFT_SIZE)
{
}

LipSyncProcessor::~LipSyncProcessor() {
}

float LipSyncProcessor::CalculateRMS(const float* samples, size_t count) {
    float sumSquared = 0.0f;
    for (size_t i = 0; i < count; i++) {
        sumSquared += samples[i] * samples[i];
    }
    return std::sqrt(sumSquared / count);
}

void LipSyncProcessor::PreEmphasis(std::vector<float>& samples, float alpha) {
    if (samples.size() < 2) return;
    for (size_t i = samples.size() - 1; i > 0; i--) {
        samples[i] -= alpha * samples[i - 1];
    }
}

void LipSyncProcessor::ApplyHammingWindow(std::vector<float>& samples) {
    const size_t N = samples.size();
    for (size_t i = 0; i < N; i++) {
        float window = 0.54f - 0.46f * std::cos(2.0f * 3.14159265359f * i / (N - 1));
        samples[i] *= window;
    }
}

bool LipSyncProcessor::CalculateLPC(const std::vector<float>& samples, std::vector<float>& lpcCoeffs) {
    const int order = LPC_ORDER;
    const int N = static_cast<int>(samples.size());
    
    if (N < order + 1) return false;
    
    // 自己相関を計算
    std::vector<float> autocorr(order + 1, 0.0f);
    for (int i = 0; i <= order; i++) {
        for (size_t j = 0; j < N - i; j++) {
            autocorr[i] += samples[j] * samples[j + i];
        }
        if (i > 0) autocorr[i] /= (N - i);
    }
    
    // Levinson-Durbinアルゴリズム
    std::vector<float> a(order + 1, 0.0f);
    std::vector<float> k(order, 0.0f);
    std::vector<float> e(order + 1, 0.0f);
    
    e[0] = autocorr[0];
    if (e[0] < 1e-10f) return false;
    
    for (int i = 1; i <= order; i++) {
        float sum = 0.0f;
        for (int j = 1; j < i; j++) {
            sum += a[j] * autocorr[i - j];
        }
        k[i - 1] = (autocorr[i] - sum) / e[i - 1];
        
        a[i] = k[i - 1];
        for (int j = 1; j < i; j++) {
            a[j] = a[j] - k[i - 1] * a[i - j];
        }
        
        e[i] = (1.0f - k[i - 1] * k[i - 1]) * e[i - 1];
        if (e[i] < 1e-10f) return false;
    }
    
    lpcCoeffs.resize(order + 1);
    lpcCoeffs[0] = 1.0f;
    for (int i = 1; i <= order; i++) {
        lpcCoeffs[i] = -a[i];
    }
    
    return true;
}

bool LipSyncProcessor::ExtractFormants(const std::vector<float>& lpcCoeffs, float& f1, float& f2) {
    const int order = static_cast<int>(lpcCoeffs.size()) - 1;
    if (order < 2) return false;
    
    // LPC多項式の根を求める（簡易版：実部が負の複素共役根を探す）
    // 実際の実装では多項式の根を求める必要があるが、簡易的に周波数領域でピークを探す
    
    // スペクトルを計算
    const int nfft = 512;
    std::vector<float> spectrum(nfft, 0.0f);
    
    for (int k = 0; k < nfft; k++) {
        float w = 2.0f * 3.14159265359f * k / nfft;
        std::complex<float> denom(1.0f, 0.0f);
        for (int i = 1; i <= order; i++) {
            denom += lpcCoeffs[i] * std::exp(std::complex<float>(0.0f, -w * i));
        }
        float mag = 1.0f / std::abs(denom);
        spectrum[k] = mag;
    }
    
    // ピークを探す（F1: 200-1200Hz, F2: 600-3500Hz）
    int f1Bin = -1, f2Bin = -1;
    float f1Max = 0.0f, f2Max = 0.0f;
    
    int f1Start = (int)(200.0f * nfft / SAMPLE_RATE);
    int f1End = (int)(1200.0f * nfft / SAMPLE_RATE);
    int f2Start = (int)(600.0f * nfft / SAMPLE_RATE);
    int f2End = (int)(3500.0f * nfft / SAMPLE_RATE);
    
    for (int i = f1Start; i < f1End && i < nfft; i++) {
        if (spectrum[i] > f1Max) {
            f1Max = spectrum[i];
            f1Bin = i;
        }
    }
    
    for (int i = f2Start; i < f2End && i < nfft; i++) {
        if (spectrum[i] > f2Max) {
            f2Max = spectrum[i];
            f2Bin = i;
        }
    }
    
    if (f1Bin >= 0 && f2Bin >= 0) {
        f1 = (float)f1Bin * SAMPLE_RATE / nfft;
        f2 = (float)f2Bin * SAMPLE_RATE / nfft;
        return (f1 >= 200.0f && f1 <= 1200.0f && f2 >= 600.0f && f2 <= 3500.0f);
    }
    
    return false;
}

int LipSyncProcessor::ClassifyVowelByFormant(float f1, float f2) {
    // 日本語母音のフォルマント範囲（簡易版）
    // a: F1高、F2中
    // i: F1低、F2高
    // u: F1低、F2低
    // e: F1中、F2中高
    // o: F1中、F2低
    
    if (f1 < 400.0f && f2 > 2000.0f) return 1;  // i
    if (f1 < 400.0f && f2 < 1200.0f) return 2;  // u
    if (f1 > 600.0f && f2 < 1200.0f) return 4;  // o
    if (f1 > 500.0f && f2 > 1800.0f) return 3;  // e
    return 0;  // a (default)
}

void LipSyncProcessor::FFT(std::vector<std::complex<float>>& x) {
    const size_t N = x.size();
    if (N <= 1) return;
    
    // ビットリバーサル
    for (size_t i = 1, j = 0; i < N; i++) {
        size_t bit = N >> 1;
        for (; j & bit; bit >>= 1) {
            j ^= bit;
        }
        j ^= bit;
        if (i < j) {
            std::swap(x[i], x[j]);
        }
    }
    
    // FFT
    for (size_t len = 2; len <= N; len <<= 1) {
        float angle = -2.0f * 3.14159265359f / len;
        std::complex<float> wlen(std::cos(angle), std::sin(angle));
        for (size_t i = 0; i < N; i += len) {
            std::complex<float> w(1.0f, 0.0f);
            for (size_t j = 0; j < len / 2; j++) {
                std::complex<float> u = x[i + j];
                std::complex<float> v = x[i + j + len / 2] * w;
                x[i + j] = u + v;
                x[i + j + len / 2] = u - v;
                w *= wlen;
            }
        }
    }
}

void LipSyncProcessor::CalculateSpectrum(const std::vector<float>& samples, std::vector<float>& magnitude) {
    // FFT用バッファにコピー
    for (size_t i = 0; i < FFT_SIZE; i++) {
        if (i < samples.size()) {
            m_fftBuffer[i] = std::complex<float>(samples[i], 0.0f);
        } else {
            m_fftBuffer[i] = std::complex<float>(0.0f, 0.0f);
        }
    }
    
    // FFT実行
    FFT(m_fftBuffer);
    
    // マグニチュードを計算
    magnitude.resize(FFT_SIZE / 2);
    for (size_t i = 0; i < magnitude.size(); i++) {
        magnitude[i] = std::abs(m_fftBuffer[i]);
    }
}

float LipSyncProcessor::CalculateSpectralCentroid(const std::vector<float>& magnitude, float lowHz, float highHz) {
    if (magnitude.empty()) {
        return lowHz;
    }
    
    int lowBin = (int)(lowHz * FFT_SIZE / SAMPLE_RATE);
    int highBin = (int)(highHz * FFT_SIZE / SAMPLE_RATE);
    lowBin = std::max(1, std::min(lowBin, (int)magnitude.size() - 1));
    highBin = std::max(lowBin + 1, std::min(highBin, (int)magnitude.size() - 1));
    
    float weightedSum = 0.0f;
    float energySum = 0.0f;
    for (int i = lowBin; i <= highBin; i++) {
        // ルート圧縮で高域の暴れを抑える
        float mag = std::sqrt(std::max(0.0f, magnitude[i]));
        float freq = (float)i * SAMPLE_RATE / FFT_SIZE;
        weightedSum += freq * mag;
        energySum += mag;
    }
    
    if (energySum <= 1e-6f) {
        return lowHz;
    }
    return weightedSum / energySum;
}

void LipSyncProcessor::CalculateBandEnergies(const std::vector<float>& magnitude, float& low, float& mid, float& high) {
    low = 0.0f;
    mid = 0.0f;
    high = 0.0f;
    
    int lowStart = (int)(300.0f * FFT_SIZE / SAMPLE_RATE);
    int lowEnd = (int)(900.0f * FFT_SIZE / SAMPLE_RATE);
    int midStart = (int)(900.0f * FFT_SIZE / SAMPLE_RATE);
    int midEnd = (int)(2000.0f * FFT_SIZE / SAMPLE_RATE);
    int highStart = (int)(2000.0f * FFT_SIZE / SAMPLE_RATE);
    int highEnd = (int)(3500.0f * FFT_SIZE / SAMPLE_RATE);
    
    for (int i = lowStart; i < lowEnd && i < (int)magnitude.size(); i++) {
        low += magnitude[i];
    }
    for (int i = midStart; i < midEnd && i < (int)magnitude.size(); i++) {
        mid += magnitude[i];
    }
    for (int i = highStart; i < highEnd && i < (int)magnitude.size(); i++) {
        high += magnitude[i];
    }
}

int LipSyncProcessor::ClassifyVowelByBands(float low, float mid, float high) {
    const float eps = 1e-9f;
    float r1 = high / (mid + eps);
    float r2 = mid / (low + eps);
    float r3 = high / (low + eps);
    
    // i: 高域優勢
    if (r1 > 1.2f && r2 > 1.0f) return 1;  // i
    // e: 中高域優勢
    if (r1 > 0.8f && r2 > 0.9f) return 3;  // e
    // u: 低域優勢で高域弱い
    if (r2 < 0.7f && r3 < 0.45f) return 2;  // u
    // o: 低域優勢で中域もそこそこ
    if (r2 < 1.0f && r1 < 0.6f) return 4;  // o
    // a: 中域強め
    if (r2 >= 1.0f && r1 < 0.7f) return 0;  // a
    
    return 0;
}

int LipSyncProcessor::ClassifyVowelBySpectrum(const std::vector<float>& magnitude) {
    const float eps = 1e-10f;
    
    // 帯域エネルギーを計算
    int lowStart = (int)(200.0f * FFT_SIZE / SAMPLE_RATE);
    int lowEnd = (int)(900.0f * FFT_SIZE / SAMPLE_RATE);
    int midStart = (int)(900.0f * FFT_SIZE / SAMPLE_RATE);
    int midEnd = (int)(2000.0f * FFT_SIZE / SAMPLE_RATE);
    int highStart = (int)(2000.0f * FFT_SIZE / SAMPLE_RATE);
    int highEnd = (int)(3500.0f * FFT_SIZE / SAMPLE_RATE);
    
    float lowEnergy = 0.0f, midEnergy = 0.0f, highEnergy = 0.0f;
    
    for (int i = lowStart; i < lowEnd && i < (int)magnitude.size(); i++) {
        lowEnergy += magnitude[i];
    }
    for (int i = midStart; i < midEnd && i < (int)magnitude.size(); i++) {
        midEnergy += magnitude[i];
    }
    for (int i = highStart; i < highEnd && i < (int)magnitude.size(); i++) {
        highEnergy += magnitude[i];
    }
    
    // 特徴量を計算
    float r1 = highEnergy / (midEnergy + eps);
    float r2 = midEnergy / (lowEnergy + eps);
    float r3 = highEnergy / (lowEnergy + eps);
    
    // 分類ルール
    if (r1 > 1.5f) return 1;  // i (High優勢)
    if (r1 > 0.8f && r2 > 1.2f) return 3;  // e
    if (r2 > 0.7f && r2 < 1.5f && lowEnergy > midEnergy * 0.8f) return 0;  // a
    if (lowEnergy > midEnergy * 1.2f && highEnergy < midEnergy * 0.6f) return 2;  // u
    if (lowEnergy > midEnergy * 1.3f && r2 < 0.8f) return 4;  // o
    
    return 0;  // デフォルトは a
}

float LipSyncProcessor::SmoothStep(float edge0, float edge1, float x) {
    x = std::max(0.0f, std::min(1.0f, (x - edge0) / (edge1 - edge0)));
    return x * x * (3.0f - 2.0f * x);
}

void LipSyncProcessor::ProcessFrame(const float* samples, size_t sampleCount, 
                                   float& mouthOpen, float& mouthForm) {
    // リングバッファに追加
    for (size_t i = 0; i < sampleCount; i++) {
        m_frameBuffer[m_bufferPos] = samples[i];
        m_bufferPos = (m_bufferPos + 1) % FRAME_SIZE;
    }
    
    // フレームが満たされていない場合は処理しない
    static size_t accumulatedSamples = 0;
    accumulatedSamples += sampleCount;
    if (accumulatedSamples < HOP_SIZE) {
        mouthOpen = m_mouthOpen;
        mouthForm = m_mouthForm;
        return;
    }
    accumulatedSamples = 0;
    
    // フレームを取得（リングバッファから）
    std::vector<float> frame(FRAME_SIZE);
    for (size_t i = 0; i < FRAME_SIZE; i++) {
        size_t idx = (m_bufferPos + i) % FRAME_SIZE;
        frame[i] = m_frameBuffer[idx];
    }
    
    // 1) mouthOpen計算（ノイズフロア + ダイナミックノーマライズ）
    float raw = CalculateRMS(frame.data(), FRAME_SIZE);
    m_lastRawLoudness = raw;
    
    // ノイズフロア推定（静かなときは早く追従、音があるときはゆっくり）
    float noiseRate = (raw < m_noiseFloor) ? NOISE_FLOOR_ATTACK : NOISE_FLOOR_RELEASE;
    m_noiseFloor = (1.0f - noiseRate) * m_noiseFloor + noiseRate * raw;
    
    // 信号成分を抽出
    float signal = raw - m_noiseFloor * 1.15f;
    if (signal < 0.0f) signal = 0.0f;
    
    // ピークの緩やかな追従で正規化
    m_peakLevel = std::max(signal, m_peakLevel * PEAK_DECAY);
    if (m_peakLevel < 1e-5f) {
        m_peakLevel = signal;
    }
    
    float normalized = (m_peakLevel > 1e-6f) ? (signal / m_peakLevel) : 0.0f;
    normalized = std::max(0.0f, std::min(1.0f, normalized));
    
    // 対数圧縮で自然な口開きを作る
    float compressed = std::log1p(normalized * 6.0f) / std::log1p(6.0f);
    float targetOpen = std::max(0.0f, std::min(1.0f, compressed * OPEN_GAIN));
    
    bool voiced = (normalized > VOICE_THRESHOLD);
    if (raw < m_noiseFloor * 1.05f) {
        voiced = false;
    }
    
    if (!voiced) {
        m_silenceFrames++;
        m_peakLevel *= PEAK_DECAY_SILENCE;
    } else {
        m_silenceFrames = 0;
    }
    
    if (m_silenceFrames >= SILENCE_FRAMES_TO_CLOSE) {
        targetOpen = 0.0f;
    }
    
    float interp = (targetOpen > m_mouthOpen) ? ATTACK_OPEN : RELEASE_OPEN;
    if (!voiced && targetOpen < 0.02f) {
        interp = SILENCE_RELEASE;
    }
    
    m_mouthOpen += (targetOpen - m_mouthOpen) * interp;
    
    if (!voiced && m_mouthOpen < 0.08f) {
        m_mouthOpen *= 0.9f;
    }
    
    mouthOpen = m_mouthOpen;
    
    // 2) 口形推定フレーム条件チェック
    if (m_mouthOpen < MIN_MOUTH_OPEN_FOR_VOWEL || !voiced) {
        // mouthFormをゆっくりニュートラルへ
        m_mouthForm += (0.0f - m_mouthForm) * 0.2f;
        mouthForm = m_mouthForm;
        m_lastMouthForm = m_mouthForm;
        m_candidateCount = 0;
        return;
    }
    
    // 3) スペクトル重心で口形を推定（連続値）
    std::vector<float> processedFrame = frame;
    PreEmphasis(processedFrame, 0.97f);
    ApplyHammingWindow(processedFrame);
    
    std::vector<float> magnitude;
    CalculateSpectrum(processedFrame, magnitude);
    
    float centroidHz = CalculateSpectralCentroid(magnitude, 300.0f, 3500.0f);
    float centroidNorm = (centroidHz - 500.0f) / 2500.0f;  // 500-3000Hzを0-1へ
    centroidNorm = std::max(0.0f, std::min(1.0f, centroidNorm));
    
    // 低域ほど丸め（+）、高域ほど横（-）
    float targetForm = (0.5f - centroidNorm) * 2.0f;
    
    // バンドエネルギーで母音分類を強化
    float low = 0.0f, mid = 0.0f, high = 0.0f;
    CalculateBandEnergies(magnitude, low, mid, high);
    int candidateVowel = ClassifyVowelByBands(low, mid, high);
    
    // 短い揺れを抑えるための母音スイッチ判定
    if (candidateVowel == m_lastVowel) {
        m_candidateCount = 0;
    } else {
        if (candidateVowel == m_candidateVowel) {
            m_candidateCount++;
        } else {
            m_candidateVowel = candidateVowel;
            m_candidateCount = 1;
        }
        
        if (m_candidateCount >= VOWEL_SWITCH_FRAMES) {
            m_lastVowel = m_candidateVowel;
            m_candidateCount = 0;
        }
    }
    
    int vowel = m_lastVowel;
    
    // 母音ごとの開き量（VTS風の差を再現）
    float openByVowel = 1.0f;
    float vowelMaxOpen = 1.0f;
    switch (vowel) {
        case 1: openByVowel = 0.30f; vowelMaxOpen = 0.35f; break;  // i
        case 3: openByVowel = 0.50f; vowelMaxOpen = 0.55f; break;  // e
        case 0: openByVowel = 1.00f; vowelMaxOpen = 1.00f; break;  // a
        case 2: openByVowel = 0.40f; vowelMaxOpen = 0.45f; break;  // u
        case 4: openByVowel = 0.70f; vowelMaxOpen = 0.75f; break;  // o
        default: break;
    }
    
    // バンド比から連続的に開き量を補正（識別が外れても差が出るように）
    float totalEnergy = low + mid + high + 1e-9f;
    float lowRatio = low / totalEnergy;
    float midRatio = mid / totalEnergy;
    float highRatio = high / totalEnergy;
    float openByBands = 0.25f + 1.1f * lowRatio + 0.6f * midRatio - 0.7f * highRatio;
    openByBands = std::max(0.25f, std::min(1.0f, openByBands));
    
    float combinedOpen = std::min(openByVowel, openByBands);
    
    // 口の開き量を補正
    targetOpen = std::max(0.0f, std::min(1.0f, targetOpen * combinedOpen));
    targetOpen = std::min(targetOpen, vowelMaxOpen);
    
    // 口が小さい時は口形を弱める
    float formGain = SmoothStep(0.12f, 0.35f, m_mouthOpen);
    targetForm *= formGain;
    
    // 平滑化（口形は少し遅く追従させる）
    float formInterp = (std::abs(targetForm) > std::abs(m_mouthForm)) ? 0.22f : 0.16f;
    m_mouthForm += (targetForm - m_mouthForm) * formInterp;
    
    mouthForm = m_mouthForm;
    m_lastMouthForm = m_mouthForm;
}
