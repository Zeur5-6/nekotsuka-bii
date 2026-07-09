"""BiiCore のツール呼び出しループのユニットテスト（Ollamaはモック）"""
import bii_core
from bii_core import BiiCore


def make_core():
    """重い初期化（Gemini/SBERT/DB）を通さずに BiiCore を組み立てる"""
    bii = BiiCore.__new__(BiiCore)
    bii.model = "test-model"
    bii.emotion_files = ["[Happy]", "[Sad]", "[Neutral]"]
    bii.long_term_memory = {"interests": [], "projects": []}
    bii.system_prompt = "テスト用プロンプト"
    bii.session_id = "test"
    bii.max_conversation_history = 10
    bii.get_conversation_history = lambda **kw: []
    bii.save_conversation = lambda *a, **kw: None
    return bii


class TestToolLoop:
    def test_tool_call_then_final_answer(self):
        bii = make_core()
        calls = []
        executed = []

        def fake_chat(messages, tools=None, **kw):
            calls.append({"messages": list(messages), "tools": tools})
            if len(calls) == 1:
                return {"tool_calls": [
                    {"function": {"name": "web_search",
                                  "arguments": {"query": "テスト"}}}]}
            return {"content": "[Happy] 検索したにゃ"}

        bii._ollama_chat = fake_chat
        bii._execute_tool = lambda name, args, user_text="": (
            executed.append((name, args)) or "【Web検索結果】ダミー")

        result = bii.generate_response(
            "VOICEVOXの最新版は？", save_history=False, extract_facts=False)

        assert result == "[Happy] 検索したにゃ"
        assert executed == [("web_search", {"query": "テスト"})]
        # 1回目はツール付き、2回目（最終回答）はツールなし
        assert calls[0]["tools"] is not None
        assert calls[1]["tools"] is None
        # ツール結果が role=tool で渡っている
        tool_msgs = [m for m in calls[1]["messages"] if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert "ダミー" in tool_msgs[0]["content"]

    def test_string_arguments_parsed_as_json(self):
        bii = make_core()
        executed = []
        responses = iter([
            {"tool_calls": [{"function": {"name": "code_search",
                                          "arguments": '{"query": "db"}'}}]},
            {"content": "[Sad] みつからないにゃ"},
        ])
        bii._ollama_chat = lambda *a, **kw: next(responses)
        bii._execute_tool = lambda name, args, user_text="": (
            executed.append((name, args)) or "結果")

        bii.generate_response("テスト", save_history=False, extract_facts=False)
        assert executed == [("code_search", {"query": "db"})]

    def test_no_tool_call_direct_answer(self):
        bii = make_core()
        bii._ollama_chat = lambda *a, **kw: {"content": "[Happy] おはようだにゃ"}
        result = bii.generate_response(
            "おはよう", save_history=False, extract_facts=False)
        assert result == "[Happy] おはようだにゃ"

    def test_vision_result_disables_tools(self):
        bii = make_core()
        seen_tools = []

        def fake_chat(messages, tools=None, **kw):
            seen_tools.append(tools)
            return {"content": "[Happy] 画面見たにゃ"}

        bii._ollama_chat = fake_chat
        bii.generate_response("画面を見て", vision_result="A terminal window",
                              save_history=False, extract_facts=False)
        assert seen_tools == [None]


class TestPostProcess:
    def test_invalid_tag_coerced_to_neutral(self):
        bii = make_core()
        assert bii._post_process_response("[Joy] うれしい") == "[Neutral] うれしい"

    def test_valid_tag_preserved(self):
        bii = make_core()
        assert bii._post_process_response("[Happy] やった") == "[Happy] やった"

    def test_alias_tag_normalized(self):
        bii = make_core()
        bii.emotion_files = ["[Surprised]", "[Neutral]"]
        assert bii._post_process_response("[Shock] びっくり") == "[Surprised] びっくり"

    def test_missing_tag_gets_neutral(self):
        bii = make_core()
        assert bii._post_process_response("タグなし応答") == "[Neutral] タグなし応答"

    def test_lowercase_tag_normalized(self):
        bii = make_core()
        assert bii._post_process_response("[happy] やった") == "[Happy] やった"


class TestVoiceCleaning:
    def test_strips_leading_tag_and_urls(self):
        bii = make_core()
        text = "[Happy] これ見て https://example.com/page だにゃ"
        assert bii.clean_text_for_voice(text) == "これ見て リンク だにゃ"

    def test_keeps_mid_text_brackets(self):
        bii = make_core()
        # strip_emotion_tags は先頭タグのみ除去（本文中の [] は温存）
        assert bii.strip_emotion_tags("[Happy] 配列は [1, 2] だにゃ") == "配列は [1, 2] だにゃ"
