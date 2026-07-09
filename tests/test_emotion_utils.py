"""emotion_utils のユニットテスト"""
import emotion_utils as eu


class TestExtractEmotionTag:
    def test_leading_tag(self):
        assert eu.extract_emotion_tag("[Happy] やったにゃ！") == "Happy"

    def test_lowercase_tag(self):
        assert eu.extract_emotion_tag("[happy] やったにゃ！") == "Happy"

    def test_alias_shock(self):
        assert eu.extract_emotion_tag("[Shock] びっくりだにゃ") == "Surprised"

    def test_no_tag(self):
        assert eu.extract_emotion_tag("タグなしのテキスト") is None

    def test_empty(self):
        assert eu.extract_emotion_tag("") is None
        assert eu.extract_emotion_tag(None) is None

    def test_leading_whitespace(self):
        assert eu.extract_emotion_tag("  [Sad] しょんぼり") == "Sad"

    def test_mid_text_brackets_not_matched(self):
        # 先頭以外の [] は感情タグとして扱わない
        assert eu.extract_emotion_tag("これは [参考] 情報だにゃ") is None


class TestStripLeadingTag:
    def test_strips_only_leading(self):
        assert eu.strip_leading_tag("[Happy] これは [参考] だにゃ") == "これは [参考] だにゃ"

    def test_no_tag_passthrough(self):
        assert eu.strip_leading_tag("タグなし") == "タグなし"


class TestTagFromFilename:
    def test_simple(self):
        assert eu.tag_from_filename("happy.exp3.json") == "Happy"

    def test_alias(self):
        assert eu.tag_from_filename("shock.exp3.json") == "Surprised"

    def test_multiword(self):
        assert eu.tag_from_filename("angry_face.exp3.json") == "AngryFace"


class TestBuildEmotionToFileMap:
    def test_standard_files(self):
        files = ["happy.exp3.json", "sad.exp3.json",
                 "angry.exp3.json", "surprised.exp3.json"]
        mapping = eu.build_emotion_to_file_map(files)
        assert mapping["Happy"] == "happy.exp3.json"
        assert mapping["Surprised"] == "surprised.exp3.json"
        assert mapping["Neutral"] is None  # Neutralは常にリセット扱い

    def test_shock_named_model(self):
        # shock.exp3.json しか無いモデルでも Surprised タグで表情が出せる
        mapping = eu.build_emotion_to_file_map(["shock.exp3.json"])
        assert mapping["Surprised"] == "shock.exp3.json"

    def test_ignores_non_expression_files(self):
        mapping = eu.build_emotion_to_file_map(["texture.png", "model.moc3"])
        assert list(mapping.keys()) == ["Neutral"]
