"""
Simple Coding RAG: プロジェクト内のコードを読み込んで検索するモジュール

設計方針:
- チャンクは 40 行（10 行オーバーラップ）。埋め込みモデル
  (paraphrase-multilingual-MiniLM-L12-v2) の入力上限が約 128 トークンのため、
  大きいチャンクは先頭しか埋め込まれず検索精度が壊れる。
- 埋め込みは全ファイルのコンテンツハッシュをキーにディスクへキャッシュし、
  毎起動の再計算を回避する。
- キーワード検索はセマンティック検索の補完。特定ドメイン（DB や VTS）への
  ハードコードされたスコア補正は行わない。
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Set

import numpy as np

from config import RAG_CACHE_PATH, get_logger

log = get_logger("CodeReader")

EMBED_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_LINES = 40
CHUNK_OVERLAP = 10
SIMILARITY_THRESHOLD = 0.25


def chunk_text(text: str, chunk_lines: int = CHUNK_LINES, overlap: int = CHUNK_OVERLAP) -> List[Dict]:
    """テキストを行単位のチャンクに分割する

    Returns:
        [{"start": 開始行番号(1始まり), "text": チャンク本文}, ...]
    """
    lines = text.split("\n")
    step = max(1, chunk_lines - overlap)
    chunks: List[Dict] = []
    for start in range(0, max(len(lines), 1), step):
        part = lines[start:start + chunk_lines]
        body = "\n".join(part)
        if len(body.strip()) > 30:
            chunks.append({"start": start + 1, "text": body})
        if start + chunk_lines >= len(lines):
            break
    return chunks


class CodeReader:
    """コードファイルを読み込んで検索するクラス"""

    ALLOWED_EXTENSIONS = {'.py', '.json', '.md', '.txt', '.yaml', '.yml'}

    EXCLUDED_DIRS = {'.git', '__pycache__', 'venv', 'env', '.venv', 'node_modules',
                     '.idea', '.vscode', 'sdk', 'live2d_native', 'build', 'target', 'dist',
                     '.ruff_cache', 'old_assets', '.claude', '.cursor'}
    EXCLUDED_FILES = {'.env', '.env.local', '.gitignore', 'package-lock.json', 'yarn.lock',
                      'vts_token.json', 'available_models.txt',
                      # 自分自身のキャッシュを対象にするとダイジェストが毎回変わり
                      # キャッシュが永久にミスするため必ず除外する
                      '.rag_cache.json', '.rag_cache.npz'}

    def __init__(self, root_dir: str = ".", enable_semantic: bool = True):
        """
        Args:
            root_dir: 読み込むルートディレクトリ
            enable_semantic: セマンティック検索を有効にするか
        """
        self.root_dir = Path(root_dir).resolve()
        self.code_files: Dict[str, str] = {}
        self._load_all_files()

        self.semantic_enabled = enable_semantic
        self.embedding_model = None
        self.code_embeddings: Optional[np.ndarray] = None
        self._chunks: List[Dict] = []

        if self.semantic_enabled:
            try:
                from sentence_transformers import SentenceTransformer
                log.info("セマンティック検索モデルを読み込み中...")
                self.embedding_model = SentenceTransformer(EMBED_MODEL_NAME, device="cpu")
                self._chunks = self._build_chunks()
                if not self._load_embedding_cache():
                    self._build_embeddings()
                    self._save_embedding_cache()
            except ImportError:
                log.warning("sentence-transformers 未インストールのためキーワード検索のみ使用")
                self.semantic_enabled = False
            except Exception as e:
                log.warning(f"セマンティック検索の初期化に失敗（キーワード検索のみ使用）: {e}")
                self.semantic_enabled = False

    # ------------------------------------------------------------------
    # ファイル読み込み
    # ------------------------------------------------------------------

    def _should_exclude(self, path: Path) -> bool:
        if path.is_dir():
            return path.name in self.EXCLUDED_DIRS
        if path.name in self.EXCLUDED_FILES:
            return True
        if path.suffix not in self.ALLOWED_EXTENSIONS:
            return True
        return any(part in self.EXCLUDED_DIRS for part in path.parts)

    def _load_all_files(self):
        loaded = 0
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
            for file in files:
                file_path = Path(root) / file
                if self._should_exclude(file_path):
                    continue
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    rel_path = file_path.relative_to(self.root_dir)
                    self.code_files[str(rel_path)] = content
                    loaded += 1
                except Exception as e:
                    log.warning(f"{file_path} の読み込みに失敗: {e}")
        log.info(f"{loaded}個のファイルを読み込みました: {self.root_dir}")

    # ------------------------------------------------------------------
    # 埋め込み（チャンク化 + ディスクキャッシュ）
    # ------------------------------------------------------------------

    def _build_chunks(self) -> List[Dict]:
        chunks = []
        for file_path, content in self.code_files.items():
            for ch in chunk_text(content):
                chunks.append({"file": file_path, "start": ch["start"], "text": ch["text"]})
        return chunks

    def _content_digest(self) -> str:
        h = hashlib.sha256()
        h.update(EMBED_MODEL_NAME.encode())
        h.update(f"{CHUNK_LINES}:{CHUNK_OVERLAP}".encode())
        for path in sorted(self.code_files):
            h.update(path.encode())
            h.update(hashlib.sha256(
                self.code_files[path].encode("utf-8", "ignore")).digest())
        return h.hexdigest()

    def _cache_paths(self):
        base = self.root_dir / RAG_CACHE_PATH
        return Path(f"{base}.npz"), Path(f"{base}.json")

    def _load_embedding_cache(self) -> bool:
        npz_path, meta_path = self._cache_paths()
        try:
            if not (npz_path.exists() and meta_path.exists()):
                return False
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("digest") != self._content_digest():
                return False
            data = np.load(npz_path)
            embeddings = data["embeddings"]
            if len(embeddings) != len(self._chunks):
                return False
            self.code_embeddings = embeddings
            log.info(f"埋め込みキャッシュを使用（{len(embeddings)}チャンク、再計算スキップ）")
            return True
        except Exception as e:
            log.warning(f"埋め込みキャッシュの読み込みに失敗（再計算します）: {e}")
            return False

    def _save_embedding_cache(self):
        if self.code_embeddings is None:
            return
        npz_path, meta_path = self._cache_paths()
        try:
            np.savez_compressed(npz_path, embeddings=self.code_embeddings)
            meta_path.write_text(
                json.dumps({"digest": self._content_digest(),
                            "model": EMBED_MODEL_NAME,
                            "chunks": len(self._chunks)}),
                encoding="utf-8")
            log.info(f"埋め込みキャッシュを保存: {npz_path.name}")
        except Exception as e:
            log.warning(f"埋め込みキャッシュの保存に失敗: {e}")

    def _build_embeddings(self):
        if not self.semantic_enabled or not self.embedding_model:
            return
        if not self._chunks:
            log.warning("ベクトル化するコードが見つかりませんでした")
            return
        texts = [f"{c['file']}\n{c['text']}" for c in self._chunks]
        try:
            self.code_embeddings = self.embedding_model.encode(
                texts,
                batch_size=32,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            log.info(f"{len(texts)}個のコードチャンクをベクトル化しました")
        except Exception as e:
            log.warning(f"ベクトル化に失敗: {e}")
            self.semantic_enabled = False

    # ------------------------------------------------------------------
    # 検索
    # ------------------------------------------------------------------

    def search_code(self, query: str, max_results: int = 5,
                    use_semantic: bool = True) -> List[Dict]:
        """クエリに関連するコードを検索する（セマンティック優先 + キーワード補完）

        Returns:
            [{"file", "content", "score", "method", ...}, ...]
        """
        results: List[Dict] = []
        seen_files: Set[str] = set()

        if use_semantic and self.semantic_enabled and self.code_embeddings is not None:
            try:
                query_vec = self.embedding_model.encode(
                    query, convert_to_numpy=True, normalize_embeddings=True)
                sims = self.code_embeddings @ query_vec
                for idx in np.argsort(sims)[::-1]:
                    if sims[idx] < SIMILARITY_THRESHOLD or len(results) >= max_results:
                        break
                    chunk = self._chunks[idx]
                    if chunk["file"] in seen_files:
                        continue
                    seen_files.add(chunk["file"])
                    results.append({
                        "file": chunk["file"],
                        "content": chunk["text"],
                        "start_line": chunk["start"],
                        "score": float(sims[idx]) * 100,
                        "method": "semantic",
                    })
            except Exception as e:
                log.warning(f"セマンティック検索中にエラー（キーワード検索へ）: {e}")

        if len(results) < max_results:
            for r in self._keyword_search(query, exclude=seen_files):
                if len(results) >= max_results:
                    break
                results.append(r)
                seen_files.add(r["file"])

        return results

    def _keyword_search(self, query: str, exclude: Set[str]) -> List[Dict]:
        """素朴なキーワード検索（ファイル名一致 + 出現頻度）"""
        terms = [t for t in query.lower().split() if len(t) >= 2]
        if not terms:
            terms = [query.lower().strip()] if query.strip() else []
        scored: List[Dict] = []
        for file_path, content in self.code_files.items():
            if file_path in exclude:
                continue
            content_lower = content.lower()
            path_lower = file_path.lower()
            score = sum(10 for t in terms if t in path_lower)
            score += sum(min(content_lower.count(t), 20) for t in terms)
            if score <= 0:
                continue
            scored.append({
                "file": file_path,
                "content": self._excerpt_around_match(content, terms),
                "score": float(score),
                "method": "keyword",
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    @staticmethod
    def _excerpt_around_match(content: str, terms: List[str],
                              context_lines: int = 20, max_chars: int = 2000) -> str:
        """最初にキーワードが出現する行の前後を抜粋する"""
        lines = content.split("\n")
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(t in line_lower for t in terms):
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines)
                return "\n".join(lines[start:end])[:max_chars]
        return content[:max_chars]

    # ------------------------------------------------------------------
    # ユーティリティ
    # ------------------------------------------------------------------

    def get_file_content(self, file_path: str) -> Optional[str]:
        """指定されたファイルの内容を取得する"""
        try:
            rel_path_str = str(Path(file_path).relative_to(self.root_dir))
        except ValueError:
            rel_path_str = str(Path(file_path).name)

        if rel_path_str in self.code_files:
            return self.code_files[rel_path_str]

        for path, content in self.code_files.items():
            if Path(path).name == Path(file_path).name:
                return content
        return None

    def get_all_files(self) -> List[str]:
        """読み込んだすべてのファイルパスのリストを返す"""
        return list(self.code_files.keys())
