"""
Simple Coding RAG: コードファイルを読み込んで検索するモジュール
セマンティック検索機能付き
"""
import os
import re
from typing import List, Dict, Optional
from pathlib import Path
import numpy as np

# セマンティック検索用（オプショナルインポート）
# Lazy import in __init__ to allow offline configuration

class CodeReader:
    """
    コードファイルを読み込んで検索するクラス
    """
    
    # 読み込むファイル拡張子
    ALLOWED_EXTENSIONS = {'.py', '.json', '.md', '.txt', '.yaml', '.yml'}
    
    # 除外するディレクトリ/ファイル
    EXCLUDED_DIRS = {'.git', '__pycache__', 'venv', 'env', '.venv', 'node_modules', '.idea', '.vscode', 'sdk', 'live2d_native', 'build', 'target', 'dist'}
    EXCLUDED_FILES = {'.env', '.env.local', '.gitignore', 'package-lock.json', 'yarn.lock'}
    
    def __init__(self, root_dir: str = ".", enable_semantic: bool = True):
        """
        初期化
        
        Args:
            root_dir: 読み込むルートディレクトリ（デフォルト：カレントディレクトリ）
            enable_semantic: セマンティック検索を有効にするか（デフォルト：True）
        """
        self.root_dir = Path(root_dir).resolve()
        self.code_files: Dict[str, str] = {}  # {ファイルパス: ファイル内容}
        self._load_all_files()
        
        # セマンティック検索の初期化
        self.semantic_enabled = enable_semantic
        self.embedding_model = None
        self.code_embeddings = None  # コードのベクトル埋め込み
        
        if self.semantic_enabled:
            try:
                print("[CodeReader] セマンティック検索ライブラリを読み込み中...")
                from sentence_transformers import SentenceTransformer

                print("[CodeReader] セマンティック検索モデルを読み込み中...")
                self.embedding_model = SentenceTransformer(
                    'paraphrase-multilingual-MiniLM-L12-v2',
                    device='cpu'
                )
                print("[CodeReader] [OK] セマンティック検索モデル読み込み完了（CPU推論モード）")
                self._build_embeddings()
            except ImportError:
                print("[CodeReader] 警告: sentence-transformers がインストールされていません。")
                print("[CodeReader] キーワード検索のみを使用します。")
                self.semantic_enabled = False
            except Exception as e:
                print(f"[CodeReader] 警告: セマンティック検索の初期化に失敗しました: {e}")
                print("[CodeReader] キーワード検索のみを使用します。")
                self.semantic_enabled = False
    
    def _should_exclude(self, path: Path) -> bool:
        """
        ファイル/ディレクトリを除外するかどうかを判定
        
        Args:
            path: チェックするパス
            
        Returns:
            bool: 除外する場合は True
        """
        # ディレクトリの場合
        if path.is_dir():
            return path.name in self.EXCLUDED_DIRS
        
        # ファイルの場合
        if path.name in self.EXCLUDED_FILES:
            return True
        
        # 拡張子チェック
        if path.suffix not in self.ALLOWED_EXTENSIONS:
            return True
        
        # 親ディレクトリに除外対象が含まれているかチェック
        for part in path.parts:
            if part in self.EXCLUDED_DIRS:
                return True
        
        return False
    
    def _load_all_files(self):
        """
        すべてのコードファイルを読み込む
        """
        print(f"[CodeReader] コードファイルを読み込み中: {self.root_dir}")
        loaded_count = 0
        
        for root, dirs, files in os.walk(self.root_dir):
            # 除外ディレクトリをスキップ（dirsを直接変更することで、os.walkの再帰を制御）
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
            
            for file in files:
                file_path = Path(root) / file
                
                # 除外チェック
                if self._should_exclude(file_path):
                    continue
                
                try:
                    # ファイルを読み込み
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # 相対パスで保存
                    rel_path = file_path.relative_to(self.root_dir)
                    self.code_files[str(rel_path)] = content
                    loaded_count += 1
                    
                except Exception as e:
                    print(f"[CodeReader] 警告: {file_path} の読み込みに失敗しました: {e}")
                    continue
        
        print(f"[CodeReader] {loaded_count}個のファイルを読み込みました")
    
    def _build_embeddings(self):
        """
        コードファイルのベクトル埋め込みを構築（セマンティック検索用）
        """
        if not self.semantic_enabled or not self.embedding_model:
            return
        
        print("[CodeReader] コードファイルのベクトル埋め込みを構築中...")
        code_texts = []
        code_metadata = []  # ファイルパスと対応するインデックス
        
        # コードをチャンクに分割（長すぎるファイルを分割）
        for file_path, content in self.code_files.items():
            # ファイルを関数/クラス単位で分割（簡易版：行数で分割）
            max_chunk_size = 500  # 500行ごとに分割
            lines = content.split('\n')
            
            for i in range(0, len(lines), max_chunk_size):
                chunk = '\n'.join(lines[i:i + max_chunk_size])
                if len(chunk.strip()) > 50:  # 空でないチャンクのみ
                    code_texts.append(f"{file_path}\n{chunk}")
                    code_metadata.append(file_path)
        
        if not code_texts:
            print("[CodeReader] 警告: ベクトル化するコードが見つかりませんでした。")
            return
        
        # ベクトル化（CPU推論、バッチ処理で高速化）
        try:
            self.code_embeddings = self.embedding_model.encode(
                code_texts,
                batch_size=32,
                show_progress_bar=True,
                convert_to_numpy=True
            )
            self.code_metadata = code_metadata
            print(f"[CodeReader] [OK] {len(code_texts)}個のコードチャンクをベクトル化しました")
        except Exception as e:
            print(f"[CodeReader] 警告: ベクトル化に失敗しました: {e}")
            self.semantic_enabled = False
    
    def search_code(self, query: str, max_results: int = 5, use_semantic: bool = True) -> List[Dict[str, str]]:
        """
        ユーザーの質問に関連するコードファイルを検索（ハイブリッド検索：セマンティック + キーワード）
        
        Args:
            query: 検索クエリ
            max_results: 最大結果数
            use_semantic: セマンティック検索を使用するか（デフォルト：True）
            
        Returns:
            List[Dict[str, str]]: [{"file": "ファイルパス", "content": "ファイル内容（抜粋）", "score": スコア}] のリスト
        """
        results = []
        
        # セマンティック検索を試行
        semantic_results = []
        if use_semantic and self.semantic_enabled and self.code_embeddings is not None:
            try:
                # クエリをベクトル化
                query_embedding = self.embedding_model.encode(query, convert_to_numpy=True)
                
                # コサイン類似度を計算
                similarities = np.dot(self.code_embeddings, query_embedding) / (
                    np.linalg.norm(self.code_embeddings, axis=1) * np.linalg.norm(query_embedding) + 1e-8
                )
                
                # 類似度が高い順にソート
                top_indices = np.argsort(similarities)[::-1][:max_results * 5]  # さらに多めに取得（2倍 → 5倍）
                
                for idx in top_indices:
                    if similarities[idx] > 0.2:  # 類似度の閾値を下げる（0.3 → 0.2）
                        file_path = self.code_metadata[idx]
                        content = self.code_files.get(file_path, "")
                        if content:
                            # より長い抜粋を取得（2000文字）
                            excerpt = content[:2000] + "..." if len(content) > 2000 else content
                            semantic_results.append({
                                "file": file_path,
                                "content": excerpt,
                                "score": float(similarities[idx]) * 100,  # 0-100スケールに変換
                                "method": "semantic"
                            })
            except Exception as e:
                print(f"[CodeReader] 警告: セマンティック検索中にエラーが発生しました: {e}")
                print("[CodeReader] キーワード検索にフォールバックします。")
        
        # キーワード検索（フォールバックまたは併用）
        keyword_results = []
        query_lower = query.lower()
        query_keywords = set(query_lower.split())
        
        # データベース関連のキーワードを拡張
        db_keywords = ['sqlite', 'database', 'connect', 'データベース', '接続', 'db', 'sqlite3', '_init_database', 'conn', 'cursor']
        
        # VTS/Live2D関連のキーワードを拡張
        vts_keywords = ['vts', 'vtuber', 'live2d', '表情', 'expression', 'emotion', '感情', 'set_expression', 'trigger_expression']
        
        for file_path, content in self.code_files.items():
            file_path_lower = file_path.lower()
            content_lower = content.lower()
            
            # ファイル名でマッチ
            score = 0
            if any(keyword in file_path_lower for keyword in query_keywords):
                score += 10
            
            # ファイル内容でマッチ（重要キーワードを強調）
            content_matches = sum(1 for keyword in query_keywords if keyword in content_lower)
            if content_matches > 0:
                score += content_matches * 2  # 内容マッチの重みを上げる
            
            # クエリに「データベース」「接続」が含まれている場合、sqlite3や_init_databaseなどのキーワードも検出
            if any(kw in query_lower for kw in ['データベース', '接続', 'database', 'connect', 'db']):
                # sqlite3や_init_databaseなどのキーワードが含まれている場合、大幅にスコアを上げる
                db_code_keywords = ['sqlite', 'sqlite3', '_init_database', 'conn =', 'cursor()', 'connect(']
                db_code_matches = sum(1 for kw in db_code_keywords if kw in content_lower)
                if db_code_matches > 0:
                    score += 300 * db_code_matches  # データベース関連のコードキーワードが含まれている場合、大幅に優先
            
            # データベース関連のキーワードが含まれている場合、スコアを大幅に上げる
            db_match_count = sum(1 for db_kw in db_keywords if db_kw in content_lower)
            if db_match_count > 0:
                score += 50 * db_match_count  # データベース関連のボーナスを大幅に増加（20 → 50）
            
            # クエリに「データベース」「接続」などのキーワードが含まれている場合、データベース関連ファイルを優先
            if any(kw in query_lower for kw in ['データベース', '接続', 'database', 'connect', 'db']):
                if db_match_count > 0:
                    score += 100  # クエリと内容の両方にデータベース関連キーワードがある場合、大幅に優先（30 → 100）
            
            # bii_core.py のようなコアファイルを優先（データベース関連キーワードがある場合）
            if 'core' in file_path_lower and db_match_count > 0:
                score += 50  # コアファイルのボーナス
            
            # VTS/Live2D関連のキーワードが含まれている場合、スコアを大幅に上げる
            vts_match_count = sum(1 for vts_kw in vts_keywords if vts_kw in content_lower)
            if vts_match_count > 0:
                score += 50 * vts_match_count  # VTS関連のボーナス
            
            # クエリに「Live2d」「感情」「表情」などのキーワードが含まれている場合、VTS関連ファイルを優先
            if any(kw in query_lower for kw in ['live2d', 'vts', '表情', '感情', 'emotion', 'expression']):
                if vts_match_count > 0:
                    score += 100  # クエリと内容の両方にVTS関連キーワードがある場合、大幅に優先
                
                # vts_adapter.py を特に優先
                if 'vts_adapter' in file_path_lower or 'vts' in file_path_lower:
                    score += 200  # vts_adapter.pyのボーナス
            
            # 具体的なファイル名が指定されている場合（例：「bii_core.py」）
            if any(file_path_lower.endswith(keyword.replace('.', '')) for keyword in query_keywords if '.' in keyword):
                score += 20
            
            if score > 0:
                # データベース関連のクエリの場合、データベース関連の部分を優先的に抽出
                if any(kw in query_lower for kw in ['データベース', '接続', 'database', 'connect', 'db', 'sqlite']):
                    lines = content.split('\n')
                    db_related_lines = []
                    
                    # _init_database関数やsqlite3.connectを探す
                    for i, line in enumerate(lines):
                        if 'def _init_database' in line or 'sqlite3.connect' in line:
                            start = max(0, i - 5)
                            end = min(len(lines), i + 80)
                            db_related_lines.extend(lines[start:end])
                    
                    if db_related_lines:
                        excerpt = '\n'.join(db_related_lines[:150])
                    else:
                        excerpt = content[:2000] + "..." if len(content) > 2000 else content
                else:
                    excerpt = content[:2000] + "..." if len(content) > 2000 else content
                
                keyword_results.append({
                    "file": file_path,
                    "content": excerpt,
                    "score": float(score),
                    "method": "keyword"
                })
        
        # 結果をマージ（セマンティック結果を優先、重複を除去）
        seen_files = set()
        for result in semantic_results:
            if result["file"] not in seen_files:
                # .pyファイルを優先（スコアを上げる）
                if result["file"].endswith('.py'):
                    result["score"] = result["score"] * 1.5
                # .mdファイルやrequirements.txtは優先度を下げる
                elif result["file"].endswith('.md') or result["file"] == 'requirements.txt':
                    result["score"] = result["score"] * 0.3
                results.append(result)
                seen_files.add(result["file"])
        
        # キーワード結果を追加（セマンティックで見つからなかったもの）
        for result in keyword_results:
            if result["file"] not in seen_files:
                # データベース関連ファイルは優先（スコアを下げない）
                is_db_related = any(kw in result["file"].lower() or kw in result["content"].lower() 
                                   for kw in ['sqlite', 'database', 'データベース', 'connect', '接続', 'sqlite3', '_init_database'])
                
                if not is_db_related:
                    # セマンティック結果がある場合はスコアを下げる
                    result["score"] = result["score"] * 0.5
                else:
                    # データベース関連ファイルはスコアをさらに上げる
                    result["score"] = result["score"] * 2.0
                
                # .pyファイルを優先
                if result["file"].endswith('.py'):
                    result["score"] = result["score"] * 1.5
                # .mdファイルやrequirements.txtは優先度を下げる
                elif result["file"].endswith('.md') or result["file"] == 'requirements.txt':
                    result["score"] = result["score"] * 0.3
                results.append(result)
                seen_files.add(result["file"])
        
        # スコアでソート
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # データベース関連のクエリの場合、bii_core.pyを強制的に検索結果に含める
        is_db_query = any(kw in query_lower for kw in ['データベース', '接続', 'database', 'connect', 'db', 'sqlite'])
        
        if is_db_query:
            # bii_core.pyが検索結果に含まれているか確認
            bii_core_found = any(r["file"] == "bii_core.py" for r in results)
            
            # bii_core.pyが検索結果に含まれているか確認（スコアに関係なく強制的に最上位に配置）
            bii_core_in_results = [r for r in results if r["file"] == "bii_core.py"]
            bii_core_content = self.code_files.get("bii_core.py", "")
            
            if bii_core_content:
                # データベース関連の部分を優先的に抽出
                lines = bii_core_content.split('\n')
                db_section_start = None
                
                # _init_database関数を探す
                for i, line in enumerate(lines):
                    if 'def _init_database' in line:
                        db_section_start = max(0, i - 5)  # 関数定義の5行前から
                        break
                
                if db_section_start is not None:
                    # データベース関連の部分を抽出（関数定義から80行）
                    db_related_lines = lines[db_section_start:db_section_start + 80]
                    excerpt = '\n'.join(db_related_lines)
                else:
                    # sqlite3.connectを探す
                    for i, line in enumerate(lines):
                        if 'sqlite3.connect' in line:
                            start = max(0, i - 10)
                            end = min(len(lines), i + 50)
                            excerpt = '\n'.join(lines[start:end])
                            break
                    else:
                        # フォールバック: 最初の2000文字
                        excerpt = bii_core_content[:2000] + "..."
                
                if not bii_core_in_results:
                    # bii_core.pyを強制的に追加
                    bii_core_result = {
                        "file": "bii_core.py",
                        "content": excerpt,
                        "score": 10000.0,  # 最高スコアを付与
                        "method": "forced"
                    }
                    # 最上位に挿入
                    results.insert(0, bii_core_result)
                    print(f"[CodeReader] ✓ データベース関連クエリのため、bii_core.pyを強制的に検索結果に追加しました（データベース関連部分を抽出）")
                else:
                    # 既に含まれている場合、データベース関連部分に置き換えて最上位に移動
                    existing_result = bii_core_in_results[0]
                    existing_result["score"] = 10000.0
                    existing_result["content"] = excerpt  # データベース関連部分に置き換え
                    existing_result["method"] = "forced"
                    # リストから削除して最上位に再挿入
                    results.remove(existing_result)
                    results.insert(0, existing_result)
                    print(f"[CodeReader] ✓ bii_core.pyの内容をデータベース関連部分に置き換えて最上位に移動しました")
            else:
                print(f"[CodeReader] 警告: bii_core.pyの内容が取得できませんでした")
        
        
        # .pyファイルを優先的に含める（最低1つは含める）
        py_files = [r for r in results if r["file"].endswith('.py')]
        non_py_files = [r for r in results if not r["file"].endswith('.py')]
        
        # データベース関連クエリの場合、bii_core.pyを最優先で含める
        if is_db_query:
            bii_core_in_py = [r for r in py_files if r["file"] == "bii_core.py"]
            other_py_files = [r for r in py_files if r["file"] != "bii_core.py"]
            # bii_core.pyを最上位に配置
            py_files = bii_core_in_py + other_py_files
        
        # .pyファイルを優先、その後非コードファイル
        final_results = py_files[:max_results] + non_py_files[:max(0, max_results - len(py_files))]
        
        return final_results[:max_results]
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """
        指定されたファイルの内容を取得
        
        Args:
            file_path: ファイルパス（相対パスまたは絶対パス）
            
        Returns:
            Optional[str]: ファイル内容、見つからない場合は None
        """
        # 相対パスに変換を試みる
        try:
            rel_path = Path(file_path).relative_to(self.root_dir)
            rel_path_str = str(rel_path)
        except ValueError:
            # 絶対パスの場合
            rel_path_str = str(Path(file_path).name)
        
        # 完全一致で検索
        if rel_path_str in self.code_files:
            return self.code_files[rel_path_str]
        
        # ファイル名のみで検索
        for path, content in self.code_files.items():
            if Path(path).name == Path(file_path).name:
                return content
        
        return None
    
    def get_all_files(self) -> List[str]:
        """
        読み込んだすべてのファイルパスのリストを返す
        
        Returns:
            List[str]: ファイルパスのリスト
        """
        return list(self.code_files.keys())
