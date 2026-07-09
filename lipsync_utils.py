"""
VOICEVOX の audio_query から Live2D 用の口パクシーケンスを生成する純粋関数群

live2d_server.py から分離。副作用が無いのでユニットテスト可能。
"""
from typing import List, Tuple


def map_vowel_to_viseme(vowel: str) -> Tuple[float, float]:
    """母音 → (口の開き ParamMouthOpenY 0..1, 口の形 ParamMouthForm -1..1)"""
    v = (vowel or "").lower()
    if v == "a":
        return 1.0, 0.0
    if v == "i":
        return 0.35, -1.0
    if v == "u":
        return 0.45, 0.4
    if v == "e":
        return 0.6, -0.5
    if v == "o":
        return 0.8, 0.8
    if v in {"n", "cl", "pau", "sil"}:
        return 0.0, 0.0
    return 0.2, 0.0


def build_viseme_sequence(query: dict, fps: int = 60) -> List[Tuple[float, float]]:
    """audio_query のモーラ情報からフレームごとの (開き, 形) のリストを作る"""
    sequence: List[Tuple[float, float]] = []
    frame_time = 1.0 / fps

    def add_frames(duration, open_val, form_val):
        if not duration or duration <= 0.0:
            return
        frames = max(1, int(round(duration / frame_time)))
        sequence.extend([(open_val, form_val)] * frames)

    add_frames(query.get("prePhonemeLength", 0.0), 0.0, 0.0)

    for phrase in query.get("accent_phrases", []):
        for mora in phrase.get("moras", []):
            cons_len = mora.get("consonant_length", 0.0)
            if cons_len:
                add_frames(cons_len, 0.1, 0.0)
            vowel = mora.get("vowel", "")
            vowel_len = mora.get("vowel_length", 0.0)
            open_val, form_val = map_vowel_to_viseme(vowel)
            add_frames(vowel_len, open_val, form_val)

        pause = phrase.get("pause_mora")
        if pause:
            add_frames(pause.get("vowel_length", 0.0), 0.0, 0.0)

    add_frames(query.get("postPhonemeLength", 0.0), 0.0, 0.0)

    return sequence
