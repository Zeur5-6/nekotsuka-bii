"""lipsync_utils のユニットテスト"""
import lipsync_utils as lu


class TestMapVowelToViseme:
    def test_a_is_fully_open(self):
        assert lu.map_vowel_to_viseme("a") == (1.0, 0.0)

    def test_i_is_wide(self):
        open_val, form_val = lu.map_vowel_to_viseme("i")
        assert open_val < 0.5
        assert form_val == -1.0

    def test_silence_is_closed(self):
        for v in ("n", "cl", "pau", "sil"):
            assert lu.map_vowel_to_viseme(v)[0] == 0.0

    def test_unknown_vowel_slightly_open(self):
        # 未知の音素は完全に閉じず、わずかに開く（元実装の仕様を維持）
        assert lu.map_vowel_to_viseme("")[0] == 0.2

    def test_case_insensitive(self):
        assert lu.map_vowel_to_viseme("A") == lu.map_vowel_to_viseme("a")


class TestBuildVisemeSequence:
    def test_empty_query(self):
        assert lu.build_viseme_sequence({}) == []

    def test_single_vowel_frame_count(self):
        # 0.1秒の「あ」→ 60fpsで約6フレーム
        query = {
            "accent_phrases": [
                {"moras": [{"vowel": "a", "vowel_length": 0.1}]}
            ]
        }
        seq = lu.build_viseme_sequence(query, fps=60)
        assert len(seq) == 6
        assert all(frame == (1.0, 0.0) for frame in seq)

    def test_pre_post_phoneme_silence(self):
        query = {
            "prePhonemeLength": 0.1,
            "postPhonemeLength": 0.1,
            "accent_phrases": [
                {"moras": [{"vowel": "a", "vowel_length": 0.1}]}
            ],
        }
        seq = lu.build_viseme_sequence(query, fps=60)
        assert len(seq) == 18  # 6 + 6 + 6
        assert seq[0] == (0.0, 0.0)   # 前無音
        assert seq[-1] == (0.0, 0.0)  # 後無音

    def test_consonant_frames(self):
        query = {
            "accent_phrases": [
                {"moras": [{"consonant_length": 0.05, "vowel": "i",
                            "vowel_length": 0.1}]}
            ]
        }
        seq = lu.build_viseme_sequence(query, fps=60)
        # 子音3フレーム（開き0.1） + 母音6フレーム
        assert len(seq) == 9
        assert seq[0] == (0.1, 0.0)
        assert seq[-1] == (0.35, -1.0)

    def test_pause_mora(self):
        query = {
            "accent_phrases": [
                {
                    "moras": [{"vowel": "a", "vowel_length": 0.1}],
                    "pause_mora": {"vowel": "pau", "vowel_length": 0.1},
                }
            ]
        }
        seq = lu.build_viseme_sequence(query, fps=60)
        assert len(seq) == 12
        assert seq[-1] == (0.0, 0.0)
