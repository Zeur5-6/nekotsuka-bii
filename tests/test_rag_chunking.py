"""bii_rag のチャンク分割のユニットテスト"""
from bii_rag import CHUNK_LINES, CHUNK_OVERLAP, chunk_text


class TestChunkText:
    def test_short_text_single_chunk(self):
        text = "\n".join(f"line {i} with some content here" for i in range(10))
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0]["start"] == 1

    def test_long_text_multiple_chunks_with_overlap(self):
        text = "\n".join(f"line {i} with some content here" for i in range(100))
        chunks = chunk_text(text)
        assert len(chunks) > 1
        # オーバーラップ分だけ開始行が近づく
        step = CHUNK_LINES - CHUNK_OVERLAP
        assert chunks[1]["start"] == chunks[0]["start"] + step

    def test_chunk_size_bounded(self):
        # 各チャンクは CHUNK_LINES 行以内（埋め込みモデルの入力上限対策）
        text = "\n".join(f"line {i} with some content here" for i in range(200))
        for chunk in chunk_text(text):
            assert len(chunk["text"].split("\n")) <= CHUNK_LINES

    def test_tiny_content_skipped(self):
        # 中身がほぼ空のテキストはチャンクにしない
        assert chunk_text("a\nb") == []

    def test_empty_text(self):
        assert chunk_text("") == []
