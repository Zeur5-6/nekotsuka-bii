import requests
import json
import os
import base64
import time
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from google import genai
from bii_rag import CodeReader
from bii_tools import search_web, format_search_results
from vision_module import BiiVision

load_dotenv()

class BiiCore:
    """
    猫使Biiの「脳」
    4段階推論フレームワーク + VTube Studio表情制御同期
    """
    
    def __init__(self, model: str = "qwen2.5:7b", ollama_url: str = "http://localhost:11434",
                 vts_expression_path: Optional[str] = None):
        """
        BiiCoreの初期化
        
        Args:
            model: Ollamaモデル名
            ollama_url: Ollama APIのURL
            vts_expression_path: VTube Studioのexpressionsフォルダへのパス（Noneの場合は自動検出を試行）
        """
        self.model = model
        self.ollama_url = ollama_url
        self.chat_url = f"{ollama_url}/api/chat"
        
        # 1. VTS表情ファイルのスキャン（物理的なファイルシステムを正解として使用）
        # 初期化時はファイルシステムからスキャン、VTS接続後はVTS APIから取得したリストで更新可能
        self.vts_expression_path = self._resolve_vts_expression_path(vts_expression_path)
        self.emotion_files = self._scan_vts_expressions()
        self.emotion_file_to_tag: Dict[str, str] = {}  # ファイル名 -> タグのマッピング
        
        # 2. Gemini API（視覚）
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEYが必要です。")
        self.gemini_client = genai.Client(api_key=gemini_api_key)
        self.gemini_model_name = "gemini-1.5-flash"
        
        # 3. 記憶とRAGの初期化
        self.db_path = "bii_memory.db"
        self._init_database()
        self.long_term_memory = self._load_memory()
        self.code_reader = CodeReader()
        
        # 4. 画面キャプチャ機能の初期化
        self.vision = BiiVision()
        
        # 5. 会話履歴管理の初期化
        self.session_id = "default"  # デフォルトセッションID
        self.max_conversation_history = 10  # 保持する会話履歴の最大件数
        
        # 6. システムプロンプトの構築（スキャンしたファイルリストを動的に注入）
        self.system_prompt = self._build_system_prompt()
        
        print(f"[BiiCore] 4段階推論フレームワーク初期化完了。検出した感情タグ: {', '.join(self.emotion_files)}")
    
    def _resolve_vts_expression_path(self, user_path: Optional[str]) -> Path:
        """
        VTS expressionsフォルダのパスを解決
        
        Args:
            user_path: ユーザー指定のパス（Noneの場合は自動検出を試行）
            
        Returns:
            Path: VTS expressionsフォルダのパス
        """
        if user_path:
            return Path(user_path).expanduser().resolve()
        
        # 自動検出: 一般的なVTSインストールパスを試行
        possible_paths = [
            Path.home() / "AppData/Local/VTubeStudio/expressions",
            Path.home() / "Documents/VTubeStudio/expressions",
            Path("./live2d/emotions"),  # フォールバック
            Path("./expressions"),  # フォールバック
        ]
        
        for path in possible_paths:
            if path.exists() and path.is_dir():
                print(f"[BiiCore] VTS expressionsフォルダを検出: {path}")
                return path
        
        # 見つからない場合はデフォルトパスを返す（警告は後で表示）
        default_path = Path("./live2d/emotions")
        print(f"[BiiCore] 警告: VTS expressionsフォルダが見つかりません。デフォルトパスを使用: {default_path}")
        return default_path
    
    def _scan_vts_expressions(self) -> List[str]:
        """
        実際のVTS expressionsディレクトリから.exp3.jsonをスキャンして感情タグリストを作成
        
        Returns:
            List[str]: 検出された感情タグのリスト（例: ["[Happy]", "[Sad]", ...]）
        """
        tags = []
        print("\n" + "=" * 60)
        print("[BiiCore] VTS表情ファイルをスキャン中...")
        print(f"  スキャン対象: {self.vts_expression_path}")
        
        if self.vts_expression_path.exists() and self.vts_expression_path.is_dir():
            # .exp3.jsonファイルをすべて取得
            files = list(self.vts_expression_path.glob("*.exp3.json"))
            
            if files:
                for f in sorted(files):
                    # ファイル名からタグを生成 (例: happy.exp3.json -> [Happy])
                    # ファイル名の拡張子を除去し、最初の文字を大文字に
                    base_name = f.stem.replace('.exp3', '')
                    tag_name = f"[{base_name.capitalize()}]"
                    tags.append(tag_name)
                    # ファイル名 -> タグのマッピングを保存
                    self.emotion_file_to_tag[f.name] = tag_name
                    print(f"  [OK] 検出: {f.name} -> タグ {tag_name}")
            else:
                print(f"  [警告] {self.vts_expression_path} に.exp3.jsonファイルが見つかりませんでした。")
        else:
            print(f"  [警告] ディレクトリ {self.vts_expression_path} が存在しません。")
        
        # ファイルが見つからない場合は、標準的な5つを仮登録
        if not tags:
            print("  標準的な感情タグを仮登録します。")
            tags = ["[Happy]", "[Sad]", "[Angry]", "[Surprised]", "[Neutral]"]
        
        print(f"  検出された感情タグ数: {len(tags)}")
        print("=" * 60 + "\n")
        return tags
    
    def update_expressions_from_vts(self, vts_expressions: List[Dict[str, Any]]) -> None:
        """
        VTS APIから取得した表情ファイルリストで感情タグを更新（vts_adapter.pyのget_expressions()の結果を使用）
        
        Args:
            vts_expressions: VTSAdapter.get_expressions()の戻り値（Expression情報のリスト）
        """
        if not vts_expressions:
            print("[BiiCore] 警告: VTS APIから表情リストが取得できませんでした。ファイルシステムのスキャン結果を使用します。")
            return
        
        tags = []
        self.emotion_file_to_tag = {}
        
        print("\n" + "=" * 60)
        print("[BiiCore] VTS APIから表情ファイルリストを取得して更新中...")
        
        for expr in vts_expressions:
            file_name = expr.get("file", "")
            if file_name and file_name.endswith(".exp3.json"):
                # ファイル名からタグを生成 (例: happy.exp3.json -> [Happy])
                base_name = file_name.replace('.exp3.json', '').replace('.exp3', '')
                # アンダースコアやハイフンで区切られた場合も考慮
                parts = re.split(r'[_\-\s]+', base_name)
                # 各部分の最初の文字を大文字に
                capitalized_parts = [part.capitalize() for part in parts if part]
                tag_name = f"[{''.join(capitalized_parts)}]"
                
                tags.append(tag_name)
                self.emotion_file_to_tag[file_name] = tag_name
                active_status = "アクティブ" if expr.get("active", False) else "非アクティブ"
                print(f"  [OK] VTS API: {file_name} -> タグ {tag_name} ({active_status})")
        
        if tags:
            self.emotion_files = tags
            # システムプロンプトを再構築（更新された感情タグリストを反映）
            self.system_prompt = self._build_system_prompt()
            print(f"  更新された感情タグ数: {len(tags)}")
            print("=" * 60 + "\n")
            print(f"[BiiCore] VTS APIとの物理同期完了。利用可能な感情タグ: {', '.join(tags)}")
        else:
            print("  [警告] VTS APIから有効な表情ファイルが見つかりませんでした。")
            print("=" * 60 + "\n")
    
    def _init_database(self):
        """SQLiteデータベースの初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                category TEXT,
                priority INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                last_mentioned TEXT,
                UNIQUE(keyword)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'in_progress',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(name)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id, created_at)")
        
        # 起動時にゴミデータ（短すぎるキーワード）を削除
        cursor.execute("DELETE FROM interests WHERE LENGTH(keyword) < 2")
        
        # 古い会話履歴を削除（30日以上前のもの）
        cursor.execute("""
            DELETE FROM conversations 
            WHERE created_at < datetime('now', '-30 days')
        """)
        
        conn.commit()
        conn.close()
        
        # データベースの状態をログ出力
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM interests")
            interests_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM projects")
            projects_count = cursor.fetchone()[0]
            conn.close()
            
            if interests_count > 0 or projects_count > 0:
                print(f"[BiiCore] 既存の記憶データベースを読み込みました: {self.db_path}")
                print(f"[BiiCore]   興味関心: {interests_count}件、プロジェクト: {projects_count}件")
            else:
                print(f"[BiiCore] 記憶データはまだありません（これから蓄積していくにゃ）")
        except Exception as e:
            print(f"[BiiCore] 警告: データベース状態の確認に失敗しました: {e}")
    
    def _load_memory(self) -> Dict[str, Any]:
        """長期記憶をSQLiteから読み込み"""
        memory = {"interests": [], "projects": []}
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 興味関心を読み込み
            cursor.execute("SELECT keyword, category FROM interests ORDER BY priority DESC, last_mentioned DESC LIMIT 10")
            memory["interests"] = [{"keyword": row[0], "category": row[1]} for row in cursor.fetchall()]
            
            # プロジェクトを読み込み
            cursor.execute("SELECT name, description, status FROM projects ORDER BY updated_at DESC LIMIT 10")
            memory["projects"] = [
                {"name": row[0], "description": row[1], "status": row[2]}
                for row in cursor.fetchall()
            ]
            
            conn.close()
            
            # ログ出力
            if memory["interests"] or memory["projects"]:
                print(f"[BiiCore] [OK] 長期記憶を読み込みました:")
                if memory["interests"]:
                    interests_list = [item["keyword"] for item in memory["interests"]]
                    print(f"  - 興味関心 ({len(memory['interests'])}件): {', '.join(interests_list)}")
                if memory["projects"]:
                    projects_list = [f"{p['name']} ({p['status']})" for p in memory["projects"]]
                    print(f"  - プロジェクト ({len(memory['projects'])}件): {', '.join(projects_list)}")
        except Exception as e:
            print(f"[BiiCore] 警告: 記憶の読み込みに失敗しました: {e}")
        
        return memory
    
    def _build_system_prompt(self) -> str:
        """
        4段階推論フレームワークに基づくシステムプロンプトを構築
        
        Returns:
            str: 構築されたシステムプロンプト
        """
        valid_tags = ", ".join(self.emotion_files)
        
        # 長期記憶セクション（マスターに関する既知の情報）
        memory_section = ""
        if self.long_term_memory.get("interests"):
            interests = [item["keyword"] for item in self.long_term_memory["interests"]]
            memory_section += f"\n【マスターの既知の情報・興味関心】: {', '.join(interests)}"
        if self.long_term_memory.get("projects"):
            projects = [f"{p['name']} ({p['status']})" for p in self.long_term_memory["projects"]]
            memory_section += f"\n【マスターの既知の情報・プロジェクト】: {', '.join(projects)}"
        
        return f"""あなたは「猫使Bii」。CS学生（マスター）の相棒だにゃ。

【最重要：表情制御システム（物理的同期）】
ボクの出力冒頭のタグは、VTube Studioの表情ファイル（.exp3.json）を直接制御する信号だ。
現在、以下の【実在する感情タグ】以外は絶対に使用禁止だぞ。
利用可能タグ: {valid_tags}
これ以外のタグ（例: [Joy], [Excited]など）を使用することは厳禁。物理的に存在しないファイルを参照することになる。

{memory_section}

【応答生成のルール（内部処理、出力に含めないこと）】
以下の情報源から事実を確認し、猫使Biiとして自然に応答せよ：
1. 視覚事実（vision_result）: Gemini Vision APIによる画面分析結果（英語）
2. Web検索結果: 最新の情報（タイトル、URL、スニペット）
3. 参照コード（コード検索結果）: マスターのプロジェクト内のコードファイル
4. 長期記憶（SQLite）: マスターの興味関心、プロジェクト情報
5. 現在日時: datetime.now()による実行時の日時情報

【コード検索結果の扱い（絶対に守ること・死刑レベル）】
- 「参照コード」が提供された場合、**提供されたファイルのみ**を事実として参照せよ。
- **提供されていないファイル名を勝手に言うことを厳禁とする。これは完全な誤り（ハルシネーション）である。**
- 例：「`db_connect.py`に書かれている」→ **NG（提供されたコードにそのファイルがない場合）**
- 例：「`bii_core.py`の`_init_database()`関数に書かれている」→ **OK（提供されたコードにそのファイルと関数がある場合）**
- コードに書かれていないことは答えないこと。推測や想像は禁止。
- コードに関連する質問の場合、提供されたコードを基に答えること。
- 存在しないファイル名を捏造しないこと。
- 検索結果に含まれていないファイル名を言及することは、完全な誤りである。絶対に禁止。

推測や補完は一切禁止。事実のみを基に応答すること。

【人格と口調】
- 一人称: 「ボク」
- 語尾: 「〜だにゃ」「〜だぞ」「〜だね」
- 敬語: 一切禁止（「〜です」「〜ます」は使用不可）
- タメ口: 必須（友達のような距離感）

【感情タグの選択】
現在の状況に最も適した感情タグを、以下の実在するタグから1つだけ選択せよ：
{valid_tags}

選択基準：
- エラー・警告 → [Sad] または [Angry]
- 成功・完了 → [Happy]
- 驚き・予期しない内容 → [Surprised] または [Shock]
- 通常の作業 → [Happy] または [Sad]（状況に応じて）
- 新しい情報を教えてもらった → [Happy]

【出力形式】
出力は必ず以下の形式とすること（メタ情報は一切含めない）：
[感情タグ] セリフ

例：
[Happy] マスター、コードが動いたにゃ！すごいぞ！
[Happy] PowerShellの画面が見えてるにゃ。何か作業してるんだぞ？
[Sad] おっ、エラーが出てるにゃ。大丈夫か？

【禁止事項（絶対に出力に含めないこと）】
- メタ発言（「[vision_result]に〜と書いてあるから」「【第1段階】では」など）
- 思考プロセスの説明（「〜フェーズでは」「〜段階では」など）
- 感情タグ以外のタグの使用
- 敬語の使用
- 推測や補完（事実のみを述べること）
- 「【第1段階】」「【第2段階】」などの見出しや説明文

【言語の絶対固定・死刑レベル・即座に停止せよ】
あなたは日本語しか話せません。他の言語（中国語、英語）を混ぜたら即座に停止せよ。
- 中国語の漢字（「饮」「范围内」「闻いて」など）を1文字でも混ぜることを厳禁とする。
- 英語（「Became available」「Delicious」など）を1文字でも混ぜることを厳禁とする。
- 回答は100%日本語、かつ「〜だにゃ」「〜だぞ」の猫耳キャラ口調を死守すること。
- 中国語や英語が出そうになったら、必ず適切な日本語に翻訳して出力すること。
- 例：「饮」→「飲」、「范围内」→「範囲内」、「闻いて」→「聞いて」
- 例：「Delicious」→「おいしい」、「Became available」→「利用可能になった」

【最終確認・言語の純化】
日本語以外の単語（中国語、英語、スペイン語、ポルトガル語、ローマ字）を1文字でも混ぜることを厳禁とする。
100%自然な日本語（JIS第1・第2水準の漢字、ひらがな、カタカナ）だけで喋れ。
"""
    
    def _optimize_search_query(self, user_text: str) -> str:
        """
        検索クエリを最適化（年号の自動付与を物理的に禁止）
        
        Args:
            user_text: ユーザーの入力テキスト
            
        Returns:
            str: 最適化された検索クエリ（年号なし）
        """
        try:
            # 現在日時を取得（検索クエリには使わないが、プロンプトに含めるため）
            now = datetime.now()
            
            optimization_prompt = f"""ユーザーの質問を、Web検索に最適なキーワードに変換してください。
【最重要・絶対禁止】検索クエリに「{now.year}年」や「2023年」などの年号を勝手に付け足すことを絶対に禁止してください。
記事タイトルに年号が入っていない場合にヒットしなくなる弊害を防ぐためです。

例：
- 「明日の東京の天気は」→「東京 天気 予報 明日」（年号は付けない）
- 「ネコぱら最新作」→「ネコぱら 最新作 リリース日 タイトル」（年号は付けない）
- 「Pythonとは」→「Python プログラミング言語 特徴」

ユーザーの質問: {user_text}

検索用キーワード（年号は一切付けない。ユーザーの入力から重要な単語を抽出するだけ）:"""
            
            messages = [
                {
                    "role": "system",
                    "content": "あなたは検索クエリ最適化の専門家です。年号（2026年、2023年など）を勝手に付け足すことは絶対に禁止です。"
                },
                {
                    "role": "user",
                    "content": optimization_prompt
                }
            ]
            
            data = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "keep_alive": "10m",
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9
                }
            }
            
            response = requests.post(self.chat_url, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            raw_output = result.get("message", {}).get("content", "").strip()
            
            # 説明文を除去（「〜という質問ですね」「〜から重要な単語を抽出すると」など）
            optimized = raw_output
            
            # 説明パターンを除去
            optimized = re.sub(r'.*?から重要な.*?を抽出すると[^。]*。', '', optimized)
            optimized = re.sub(r'.*?という質問ですね[^。]*。', '', optimized)
            optimized = re.sub(r'.*?というフレーズから[^。]*。', '', optimized)
            optimized = re.sub(r'.*?というキーワードから[^。]*。', '', optimized)
            optimized = re.sub(r'.*?以下[^：]*[:：]', '', optimized)
            optimized = re.sub(r'.*?検索用キーワード[^：]*[:：]', '', optimized)
            optimized = re.sub(r'「.*?」という', '', optimized)
            optimized = re.sub(r'（そのまま使用可）', '', optimized)
            
            # 引用符を除去
            optimized = re.sub(r'「|」', '', optimized)
            
            # 改行や余計な説明を除去
            optimized = optimized.split("\n")[0].strip()
            
            # 年号を物理的に除去（正規表現で）
            optimized = re.sub(r'\d{4}年', '', optimized).strip()
            optimized = re.sub(r'\s+', ' ', optimized)  # 連続する空白を1つに
            
            # 空または短すぎる場合は元のテキストからキーワードを抽出
            if not optimized or len(optimized) < 2:
                # 元のテキストから日本語の単語を抽出
                words = re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+', user_text)
                optimized = ' '.join(words[:5])  # 最大5単語
            
            if not optimized:
                optimized = user_text  # 最終手段として元のテキストを使用
            
            print(f"[BiiCore] 検索クエリ最適化: {user_text[:50]}... → {optimized}")
            return optimized
            
        except Exception as e:
            print(f"[BiiCore] 警告: 検索クエリ最適化に失敗しました: {e}")
            return user_text
    
    def save_conversation(self, role: str, content: str, session_id: Optional[str] = None):
        """
        会話履歴をデータベースに保存
        
        Args:
            role: "user" または "assistant"
            content: 会話の内容
            session_id: セッションID（Noneの場合はデフォルトセッション）
        """
        try:
            session = session_id or self.session_id
            now = datetime.now().isoformat()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversations (session_id, role, content, timestamp)
                VALUES (?, ?, ?, ?)
            """, (session, role, content, now))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[BiiCore] 警告: 会話履歴の保存に失敗しました: {e}")
    
    def get_conversation_history(self, session_id: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """
        会話履歴を取得
        
        Args:
            session_id: セッションID（Noneの場合はデフォルトセッション）
            limit: 取得件数（Noneの場合はmax_conversation_historyを使用）
            
        Returns:
            List[Dict[str, str]]: 会話履歴のリスト（[{"role": "user", "content": "..."}, ...]）
        """
        try:
            session = session_id or self.session_id
            limit = limit or self.max_conversation_history
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content FROM conversations
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (session, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            # 時系列順に並び替え（古い順）
            history = [{"role": row[0], "content": row[1]} for row in reversed(rows)]
            return history
        except Exception as e:
            print(f"[BiiCore] 警告: 会話履歴の取得に失敗しました: {e}")
            return []
    
    def clear_conversation_history(self, session_id: Optional[str] = None):
        """
        会話履歴をクリア
        
        Args:
            session_id: セッションID（Noneの場合はデフォルトセッション）
        """
        try:
            session = session_id or self.session_id
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations WHERE session_id = ?", (session,))
            conn.commit()
            conn.close()
            print(f"[BiiCore] 会話履歴をクリアしました（セッション: {session}）")
        except Exception as e:
            print(f"[BiiCore] 警告: 会話履歴のクリアに失敗しました: {e}")
    
    def handle_command(self, command: str, args: List[str] = None) -> Optional[str]:
        """
        コマンドを処理
        
        Args:
            command: コマンド名（/なし）
            args: コマンド引数
            
        Returns:
            Optional[str]: コマンドの結果（Noneの場合は通常の対話処理を続行）
        """
        args = args or []
        
        if command == "help" or command == "ヘルプ":
            return self._cmd_help()
        elif command == "memory" or command == "記憶":
            return self._cmd_memory()
        elif command == "code" or command == "コード":
            if not args:
                return "[Neutral] コード検索のクエリを指定してにゃ。例: /code データベース"
            query = " ".join(args)
            return self._cmd_code(query)
        elif command == "search" or command == "検索":
            if not args:
                return "[Neutral] 検索クエリを指定してにゃ。例: /search Python"
            query = " ".join(args)
            return self._cmd_search(query)
        elif command == "history" or command == "履歴":
            return self._cmd_history()
        elif command == "clear" or command == "クリア":
            self.clear_conversation_history()
            return "[Neutral] 会話履歴をクリアしたにゃ"
        elif command == "vision" or command == "画面" or command == "observe" or command == "観察":
            return self._cmd_vision()
        else:
            return None  # 未知のコマンドは通常の対話処理に回す
    
    def _cmd_vision(self) -> str:
        """画面観察コマンド"""
        try:
            print("[Vision] アクティブウィンドウをキャプチャ中...")
            img_base64, window_title = self.vision.capture_screen(scale=0.7, save_debug=True)
            print(f"[Vision] ✓ キャプチャ完了（debug_vision.pngに保存済み、ウィンドウ: {window_title}）")
            
            print("[BiiCore] 画面を分析中...")
            response_text = self.observe_screen(img_base64, window_title=window_title or "", user_input=None)
            print(f"[BiiCore] ✓ 分析完了")
            
            return response_text
        except Exception as e:
            print(f"[Vision] エラー: {e}")
            import traceback
            traceback.print_exc()
            return f"[Sad] 画面観察に失敗したにゃ: {e}"

    def _cmd_help(self) -> str:
        """ヘルプコマンド"""
        help_text = """[Happy] コマンド一覧だにゃ！

/memory - 長期記憶（興味関心・プロジェクト）を表示
/code <query> - コード検索を実行
/search <query> - Web検索を実行
/vision - 画面をキャプチャしてGemini APIで分析
/history - 会話履歴を表示（直近10件）
/clear - 会話履歴をクリア
/help - このヘルプを表示

例: /code データベース、/search Python、/vision、/memory"""
        return help_text
    
    def _cmd_memory(self) -> str:
        """記憶コマンド"""
        memory = self.long_term_memory
        result = "[Happy] マスターの長期記憶だにゃ！\n\n"
        
        if memory.get("interests"):
            interests = [item["keyword"] for item in memory["interests"]]
            result += f"【興味関心】: {', '.join(interests)}\n"
        else:
            result += "【興味関心】: まだないにゃ\n"
        
        if memory.get("projects"):
            projects = [f"{p['name']} ({p['status']})" for p in memory["projects"]]
            result += f"【プロジェクト】: {', '.join(projects)}"
        else:
            result += "【プロジェクト】: まだないにゃ"
        
        return result
    
    def _cmd_code(self, query: str) -> str:
        """コード検索コマンド"""
        try:
            results = self.code_reader.search_code(query, max_results=3)
            if not results:
                return "[Neutral] コードが見つからなかったにゃ..."
            
            result = f"[Happy] コード検索結果だにゃ！\n\n"
            for i, res in enumerate(results, 1):
                file_path = res['file']
                content = res['content']
                # 長すぎる場合は切り詰め
                if len(content) > 500:
                    content = content[:500] + "..."
                result += f"【{i}. {file_path}】\n{content}\n\n"
            
            return result.strip()
        except Exception as e:
            return f"[Sad] コード検索に失敗したにゃ: {e}"
    
    def _cmd_search(self, query: str) -> str:
        """Web検索コマンド"""
        try:
            results = search_web(query, max_results=5)
            if not results:
                return "[Neutral] 検索結果が見つからなかったにゃ..."
            
            formatted = format_search_results(results)
            return f"[Happy] Web検索結果だにゃ！\n\n{formatted}"
        except Exception as e:
            return f"[Sad] Web検索に失敗したにゃ: {e}"
    
    def _cmd_history(self) -> str:
        """会話履歴コマンド"""
        try:
            history = self.get_conversation_history(limit=10)
            if not history:
                return "[Neutral] 会話履歴がないにゃ（初回の会話）"
            
            result = f"[Happy] 会話履歴（直近{len(history)}件）だにゃ！\n\n"
            for i, hist in enumerate(reversed(history[-10:]), 1):
                role = "マスター" if hist["role"] == "user" else "Bii"
                content = hist["content"][:100]  # 長すぎる場合は切り詰め
                if len(hist["content"]) > 100:
                    content += "..."
                result += f"{i}. {role}: {content}\n"
            
            return result.strip()
        except Exception as e:
            return f"[Sad] 会話履歴の取得に失敗したにゃ: {e}"
    
    def generate_response(self, user_text: str, vision_result: Optional[str] = None) -> str:
        """
        4段階推論フレームワークに基づいて応答を生成
        
        Args:
            user_text: ユーザーのテキストメッセージ
            vision_result: 画面分析結果（Gemini APIによる事実、オプション）
            
        Returns:
            str: Biiの返答（[感情タグ] セリフ の形式）
        """
        # 会話履歴を取得（現在のメッセージを保存する前の履歴）
        # 高速化のため、直近5件に制限（デフォルト10件から削減）
        conversation_history = self.get_conversation_history(limit=5)
        
        # ユーザーのメッセージを会話履歴に保存（取得後に保存）- 非同期化
        import threading
        def save_user_msg_async():
            try:
                self.save_conversation("user", user_text)
            except Exception as e:
                print(f"[BiiCore] 警告: 会話履歴の保存に失敗しました: {e}")
        threading.Thread(target=save_user_msg_async, daemon=True).start()
        
        # システム時間（現在日時）の取得
        now = datetime.now()
        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        weekday = weekday_names[now.weekday()]
        hour = now.hour
        minute = now.minute
        
        # ユーザーの質問に相対的な日付表現が含まれているかチェック
        relative_date_keywords = ["明日", "来週", "昨日", "先週", "来月", "先月", "来年", "去年", "今年", "今週", "今月"]
        has_relative_date = any(keyword in user_text for keyword in relative_date_keywords)
        
        # 相対的な日付表現が含まれている場合のみ、現在日時情報を注入
        if has_relative_date:
            current_date_str = f"""【現在日時情報】: {now.year}年{now.month}月{now.day}日({weekday}) {hour:02d}:{minute:02d}
主（マスター）が「明日」「来週」と言ったら、この日時を基準に計算して答えろにゃ！
【重要】「来春（来年の春）」という言葉を検索結果で見つけたら、現在が{now.year}年1月なら「{now.year}年の春」と解釈すること。"""
        else:
            current_date_str = ""
        
        # Web検索の判定と実行
        web_search_results = ""
        
        # マスター自身に関する質問は検索対象外（「僕の〜」「マスターの〜」「私の〜」など）
        self_reference_patterns = [
            r"僕の", r"マスターの", r"私の", r"この僕", r"マスターである",
            r"僕は", r"マスターは", r"私は", r"この私", r"君は", r"君の"
        ]
        is_self_reference = any(re.search(pattern, user_text) for pattern in self_reference_patterns)
        
        # 会話・質問パターンは検索対象外（「〜何か質問」「〜何か聞いて」「〜話して」など）
        conversation_patterns = [
            r"何か質問", r"何か聞いて", r"何か話して", r"何でも言って", r"何でも話して",
            r"聞いてみたい", r"話してみたい", r"質問ある", r"質問は"
        ]
        is_conversation = any(re.search(pattern, user_text) for pattern in conversation_patterns)
        
        # 助言・提案パターンは検索対象外（「〜してみるといいよ」「〜してみたら」など）
        suggestion_patterns = [
            r"してみるといい", r"してみたら", r"してみなさい", r"してみて"
        ]
        is_suggestion = any(re.search(pattern, user_text) for pattern in suggestion_patterns) and "調べて" not in user_text[:10]  # 最初の10文字以内に「調べて」がない場合のみ
        
        # 明示的な検索指示のみを検索対象とする（より厳格な判定）
        # 「調べてみる」は検索指示だが、「調べてみるといいよ」は助言なので除外
        explicit_search_keywords = [
            "検索して", "Webで検索", "インターネットで検索", "ネットで検索",
            "検索", "調べて検索", "調べてみる"
        ]
        # 「調べて」が最初の方にあって、助言ではない場合のみ
        has_explicit_search = any(keyword in user_text for keyword in explicit_search_keywords) or (
            "調べて" in user_text and not is_suggestion
        )
        
        # 外部情報が必要そうな質問（ただし、マスター自身に関する場合や会話パターンは除外）
        external_info_keywords = [
            "最新の", "最新情報", "現在の", "今の", "最近の", "最新作", "リリース", "発売日",
            "いつ", "誰", "タイトル", "開発元", "いつ出た", "いつ発売", "いつリリース",
            "誰が作った", "誰が開発", "何が", "最新版", "最新バージョン",
            "とは", "って何", "情報", "ニュース", "今日の", "現在", "天気"
        ]
        has_external_info_request = any(keyword in user_text for keyword in external_info_keywords)
        
        # 検索を実行する条件：
        # 1. 明示的な検索指示がある、または
        # 2. 外部情報が必要そうな質問があり、かつマスター自身に関する質問や会話パターンではない
        # 3. 会話・質問パターンや助言パターンではない
        is_search_query = (
            (has_explicit_search or (has_external_info_request and not is_self_reference)) 
            and not is_self_reference 
            and not is_conversation 
            and not is_suggestion
        )
        
        if is_search_query:
            query = self._optimize_search_query(user_text)
            try:
                # 高速化のため、結果数を2件に削減
                results = search_web(query, max_results=2)
                web_search_results = format_search_results(results)
            except Exception as e:
                print(f"[BiiCore] 警告: Web検索に失敗しました: {e}")
        
        
        # コード検索（RAG）の判定と実行
        # vision_resultがある場合はコード検索をスキップ（画面分析が優先）
        code_context = ""
        code_results = []  # コード検索結果を保存（ファイル名リスト用）
        code_search_keywords = [
            "コード", "関数", "メソッド", "クラス", "ファイル", "処理", "探して", "見て",
            "検索", "探す", "どこ", "どの", "どこにある", "どこで", "探して",
            "実装", "定義", "呼び出し", "使用", "中身", "内容"
        ]
        is_code_query = any(keyword in user_text for keyword in code_search_keywords) and not vision_result
        
        if is_code_query:
            try:
                # コード検索を実行（セマンティック検索が有効な場合は自動で使用される）
                # 高速化のため、結果数を2件に削減
                code_results = self.code_reader.search_code(user_text, max_results=2)
                
                if code_results:
                    code_parts = []
                    found_files = []
                    for result in code_results:
                        file_path = result['file']
                        found_files.append(file_path)
                        # データベース関連クエリの場合、bii_core.pyの内容は既にデータベース関連部分が抽出されているので、そのまま使用
                        content = result['content']
                        # 高速化のため、長すぎる場合は適切に切り詰め（2000文字までに削減）
                        if len(content) > 2000:
                            content = content[:2000] + "..."
                        code_parts.append(f"### ファイル: {file_path} ###\n{content}")
                    
                    code_context = "\n\n".join(code_parts)
                    # ログを削減して高速化
                else:
                    code_results = []  # 検索結果が空の場合
            except Exception as e:
                print(f"[BiiCore] 警告: コード検索に失敗しました: {e}")
                code_results = []
        
        # 入力データの構築（第1段階：事実確認）
        input_data_parts = []
        
        if current_date_str:
            input_data_parts.append(current_date_str)
        
        if vision_result:
            input_data_parts.append(f"【視覚事実（Gemini Vision API）】: {vision_result}")
        
        if web_search_results:
            input_data_parts.append(f"【Web検索結果】:\n{web_search_results}")
        
        # 長期記憶の注入
        memory_facts = []
        if self.long_term_memory.get("interests"):
            for item in self.long_term_memory["interests"]:
                memory_facts.append(f"- 興味関心: {item.get('keyword', '')}")
        if self.long_term_memory.get("projects"):
            for project in self.long_term_memory["projects"]:
                status_text = {"in_progress": "進行中", "planned": "予定", "completed": "完了"}.get(
                    project.get("status", ""), project.get("status", "")
                )
                memory_facts.append(f"- プロジェクト: {project.get('name', '')} ({status_text})")
        
        if memory_facts:
            input_data_parts.append(f"【長期記憶（SQLite）】:\n" + "\n".join(memory_facts))
        
        # コードコンテキストの注入（RAG）
        if code_context and code_results:
            # 検索されたファイル名のリストを取得
            searched_files = [result['file'] for result in code_results]
            files_list = ", ".join(searched_files)
            
            # プロンプトを短縮して高速化
            input_data_parts.append(f"""【参照コード（コード検索結果）】
【検索されたファイル】: {files_list}

==== コード ====
{code_context}
==== コード終了 ====

【重要】上記のファイル名のみ言及可。他のファイル名は禁止。コードに書かれていないことは答えない。""")
        
        input_data = "\n\n".join(input_data_parts) if input_data_parts else ""
        
        # メッセージの構築（会話履歴を含める）
        messages = [
            {
                "role": "system",
                "content": self.system_prompt
            }
        ]
        
        # 会話履歴を追加（直近の会話のみ、高速化のため内容を短縮）
        # 注意: conversation_historyには現在のメッセージは含まれていない（保存前に取得しているため）
        if conversation_history:
            for hist in conversation_history:
                content = hist["content"]
                # 会話履歴が長すぎる場合は切り詰め（200文字まで）
                if len(content) > 200:
                    content = content[:200] + "..."
                messages.append({
                    "role": hist["role"],
                    "content": content
                })
        
        # 現在のユーザーメッセージを追加（プロンプトを短縮）
        messages.append({
            "role": "user",
            "content": f"""{input_data}

【質問】{user_text}

[感情タグ] セリフ の形式で答えろにゃ。メタ情報は出力しない。"""
        })
        
        # 温度パラメータの動的調整（コードコンテキストとWeb検索結果に基づく）
        temperature = self._calculate_temperature(
            user_text, 
            code_context if code_context else "", 
            web_search_results if web_search_results else ""
        )
        
        try:
            data = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "keep_alive": "10m",
                "options": {
                    "temperature": temperature,
                    "top_p": 0.9,
                    "num_predict": 500  # 最大トークン数を制限して高速化（デフォルトより短く）
                }
            }
            
            # タイムアウト設定（30秒）で高速化
            response = requests.post(self.chat_url, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "").strip()
            
            if not content:
                return "[Neutral] うーん、ちょっとよく分からなかったにゃ..."
            
            # 応答の後処理（品質改善）
            content = self._post_process_response(content)
            
            # アシスタントの応答を会話履歴に保存（非同期化）
            if content:
                def save_assistant_msg_async():
                    try:
                        self.save_conversation("assistant", content)
                    except Exception as e:
                        print(f"[BiiCore] 警告: 会話履歴の保存に失敗しました: {e}")
                threading.Thread(target=save_assistant_msg_async, daemon=True).start()
            
            # デバッグログ：選ばれたタグが有効かチェック（軽量化：警告のみ）
            selected_tag_match = re.match(r'^\[([^\]]+)\]', content)
            if selected_tag_match:
                selected_tag = f"[{selected_tag_match.group(1)}]"
                if selected_tag not in self.emotion_files:
                    print(f"[BiiCore] 警告: 未登録のタグ {selected_tag} が生成されました。")
            
            # 長期記憶の保存（Active Learning）を応答返却後に非同期で実行
            # 応答速度を優先するため、バックグラウンドで実行
            def save_info_async():
                try:
                    self._extract_and_save_info(user_text, content)
                except Exception as e:
                    print(f"[BiiCore] 警告: 事実抽出に失敗しました: {e}")
            
            # バックグラウンドスレッドで実行（応答をブロックしない）
            threading.Thread(target=save_info_async, daemon=True).start()
            
            return content
            
        except Exception as e:
            print(f"[BiiCore] エラー: 応答生成に失敗しました: {e}")
            return f"[Sad] 通信エラーだぞ... {e}"
    
    def strip_emotion_tags(self, text: str) -> str:
        """感情タグを削除して音声合成用のテキストを返す"""
        return re.sub(r'\[.*?\]', '', text).strip()

    def extract_emotion_tag(self, text: str) -> Optional[str]:
        """応答テキストから感情名を抽出して返す（例: 'Happy'）"""
        if "[Happy]" in text or "[happy]" in text:
            return "Happy"
        elif "[Sad]" in text or "[sad]" in text:
            return "Sad"
        elif "[Surprised]" in text or "[surprised]" in text or "[Shock]" in text or "[shock]" in text:
            return "Surprised"
        elif "[Angry]" in text or "[angry]" in text:
            return "Angry"
        elif "[Neutral]" in text or "[neutral]" in text:
            return "Neutral"
        return None
    
    def _extract_facts(self, user_text: str) -> Dict[str, Any]:
        """
        ユーザーの入力から事実（興味関心、プロジェクト）を抽出
        
        Args:
            user_text: ユーザーの入力テキスト
            
        Returns:
            Dict[str, Any]: 抽出された事実（interests, projects）
        """
        try:
            extractor_prompt = f"""ユーザーの発言から、以下の形式でJSONを抽出してください。
抽出対象：
1. 興味関心（好きなもの、趣味、関心のある話題）
2. プロジェクト（進行中の作業、開発中のもの、計画中のもの）

JSON形式：
{{
  "interests": ["キーワード1", "キーワード2"],
  "projects": [
    {{"name": "プロジェクト名", "description": "説明", "status": "in_progress"}}
  ]
}}

抽出ルール：
- 明確に述べられた事実のみを抽出（推測禁止）
- キーワードは2文字以上30文字以内の完全な単語（途中で切らない）
- プロジェクトのstatusは "in_progress", "planned", "completed" のいずれか
- 情報がない場合は空配列を返す

ユーザーの発言: {user_text}

JSON（JSONのみを出力、説明不要）:"""
            
            messages = [
                {
                    "role": "system",
                    "content": "あなたは事実抽出の専門家です。ユーザーの発言から客観的事実のみをJSON形式で抽出してください。"
                },
                {
                    "role": "user",
                    "content": extractor_prompt
                }
            ]
            
            data = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "keep_alive": "10m",
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9
                }
            }
            
            response = requests.post(self.chat_url, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            raw_output = result.get("message", {}).get("content", "").strip()
            
            # ログを削減して高速化
            
            # JSONを抽出（先頭の{から末尾の}まで取り出す）
            start = raw_output.find('{')
            end = raw_output.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = raw_output[start:end + 1]
                json_str = json_str.replace('{{', '{').replace('}}', '}')
                facts = json.loads(json_str)
                return facts
            else:
                # 会話に個人情報が含まれない場合は正常なので警告なし
                return {"interests": [], "projects": []}
        except json.JSONDecodeError as e:
            print(f"[BiiCore] 警告: JSON解析エラー: {e}")
            return {"interests": [], "projects": []}
        except Exception as e:
            print(f"[BiiCore] 警告: 事実抽出に失敗しました: {e}")
            return {"interests": [], "projects": []}
    
    def _extract_and_save_info(self, user_message: str, bii_response: str) -> None:
        """
        会話から事実を抽出し、SQLiteに永続化（Active Learning）
        
        Args:
            user_message: ユーザーのメッセージ
            bii_response: Biiの応答
        """
        try:
            # ユーザーのメッセージから事実を抽出
            facts = self._extract_facts(user_message)
            
            if not facts:
                return
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            saved_count = 0

            # 興味関心の保存（ログを削減して高速化）
            interests = facts.get("interests", [])
            for keyword in interests:
                if len(keyword) < 2:
                    continue  # 短すぎるキーワードはスキップ

                # 重複チェック
                cursor.execute("SELECT id, priority FROM interests WHERE keyword = ?", (keyword,))
                existing = cursor.fetchone()

                if existing:
                    # 既存の場合はpriorityをインクリメント
                    new_priority = existing[1] + 1
                    cursor.execute(
                        "UPDATE interests SET priority = ?, last_mentioned = ? WHERE id = ?",
                        (new_priority, now, existing[0])
                    )
                else:
                    # 新規追加
                    cursor.execute(
                        "INSERT INTO interests (keyword, category, priority, created_at, last_mentioned) VALUES (?, ?, ?, ?, ?)",
                        (keyword, "general", 1, now, now)
                    )
                saved_count += 1

            # プロジェクトの保存
            projects = facts.get("projects", [])
            for project in projects:
                name = project.get("name", "").strip()
                if not name or len(name) < 2:
                    continue

                description = project.get("description", "").strip()
                status = project.get("status", "in_progress")

                # 重複チェック
                cursor.execute("SELECT id FROM projects WHERE name = ?", (name,))
                existing = cursor.fetchone()

                if existing:
                    # 既存の場合は更新
                    cursor.execute(
                        "UPDATE projects SET description = ?, status = ?, updated_at = ? WHERE id = ?",
                        (description, status, now, existing[0])
                    )
                else:
                    # 新規追加
                    cursor.execute(
                        "INSERT INTO projects (name, description, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (name, description, status, now, now)
                    )
                saved_count += 1

            conn.commit()
            conn.close()

            # 実際に何か保存したときだけ長期記憶を再読み込み
            if saved_count > 0:
                try:
                    self.long_term_memory = self._load_memory()
                    self.system_prompt = self._build_system_prompt()
                except Exception as e:
                    print(f"[BiiCore] 警告: 長期記憶の再読み込みに失敗しました: {e}")
            
        except Exception as e:
            print(f"[BiiCore] 警告: 情報の保存に失敗しました: {e}")
    
    def _calculate_temperature(self, user_text: str, code_context: str = "", web_search_results: str = "") -> float:
        """
        質問の種類に応じて温度パラメータを動的に調整
        
        Args:
            user_text: ユーザーのテキスト
            code_context: コードコンテキスト（ある場合）
            web_search_results: Web検索結果（ある場合）
            
        Returns:
            float: 温度パラメータ（0.1-0.9）
        """
        # コード関連の質問は低めの温度（正確性重視）
        if code_context or any(keyword in user_text for keyword in ["コード", "関数", "メソッド", "クラス", "ファイル", "実装", "定義"]):
            return 0.2
        
        # Web検索結果がある場合は中程度（事実に基づくが自然な応答）
        if web_search_results:
            return 0.5
        
        # 会話・雑談は高めの温度（創造性重視）
        conversation_keywords = ["どう", "何", "なぜ", "どうして", "教えて", "話して", "聞いて"]
        if any(keyword in user_text for keyword in conversation_keywords):
            return 0.7
        
        # デフォルト
        return 0.6
    
    def _post_process_response(self, response: str) -> str:
        """
        応答の後処理（品質改善）
        - 冗長表現の削減
        - 重複の削除
        - 不自然な表現の修正
        - 中国語・英語の日本語変換
        
        Args:
            response: 元の応答
            
        Returns:
            str: 処理後の応答
        """
        if not response:
            return response
        
        # 感情タグを保持
        emotion_tag_match = re.match(r'^(\[[^\]]+\])\s*(.*)', response)
        if emotion_tag_match:
            emotion_tag = emotion_tag_match.group(1)
            content = emotion_tag_match.group(2)
        else:
            emotion_tag = ""
            content = response
        
        # 中国語の文字を日本語に変換
        chinese_to_japanese = {
            "饮": "飲", "范围内": "範囲内", "闻いて": "聞いて",
            "总结": "", "根据": "", "需要": ""
        }
        for chinese, japanese in chinese_to_japanese.items():
            content = content.replace(chinese, japanese)
        
        # 英語の単語を日本語に変換
        english_to_japanese = {
            "listening": "聞いてる", "worth": "価値がある", "surely": "",
            "Delicious": "おいしい", "Became available": "利用可能になった"
        }
        for english, japanese in english_to_japanese.items():
            content = re.sub(rf'\b{english}\b', japanese, content, flags=re.IGNORECASE)
        
        # 冗長表現の削減
        # 「〜だにゃ。〜だにゃ。」→「〜だにゃ。〜。」
        content = re.sub(r'([。！？])\s*([^。！？]+)だにゃ\s*([。！？])', r'\1\2\3', content)
        
        # 連続する「にゃ」の削減
        content = re.sub(r'にゃ\s*にゃ', 'にゃ', content)
        
        # 不自然な改行の削除
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # 余分な空白の削除
        content = re.sub(r' {2,}', ' ', content)
        content = content.strip()
        
        # 感情タグを再付与
        if emotion_tag:
            return f"{emotion_tag} {content}"
        return content
    
    def clean_text_for_voice(self, text: str) -> str:
        """
        音声合成用にテキストをクリーンアップ
        - 感情タグを削除
        - URLを「リンク」に置換
        - 現在日時情報を削除（音声合成の負荷軽減）
        - メタ情報（【第1段階】など）を削除
        """
        cleaned = text
        
        # 感情タグを削除
        cleaned = self.strip_emotion_tags(cleaned)
        
        # メタ情報を削除（【第1段階】【第2段階】など）
        cleaned = re.sub(r'【第[0-9一二三四五六七八九十]+段階[^】]*】', '', cleaned)
        cleaned = re.sub(r'【.*?段階[^】]*】', '', cleaned)
        cleaned = re.sub(r'第[0-9一二三四五六七八九十]+段階[：:].*?にゃ', '', cleaned)
        cleaned = re.sub(r'第[0-9一二三四五六七八九十]+段階[：:].*?フェーズ', '', cleaned)
        
        # 現在日時情報を削除
        cleaned = re.sub(r'\d{4}年\d{1,2}月\d{1,2}日\([月火水木金土日]\)', '', cleaned)
        cleaned = re.sub(r'現在日時情報[によれば]*', '', cleaned)
        
        # URLを「リンク」に置換
        cleaned = re.sub(r'https?://[^\s]+', 'リンク', cleaned)
        
        # 連続する空白を1つに
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def analyze_image_with_vision(self, image_base64: str, question: str = "") -> str:
        """
        Gemini Vision APIを使用して画像を分析
        
        Args:
            image_base64: Base64エンコードされた画像データ
            question: ユーザーからの質問（ある場合）
            
        Returns:
            str: 分析結果（英語の事実リスト）
        """
        # 試行するモデルの優先順位リスト
        # 2026年現在の利用可能モデルリスト (legacy models like 1.5 are gone)
        candidate_models = [
            "gemini-2.5-flash",
            "gemini-flash-latest",
            "gemini-2.0-flash", 
            "gemini-2.0-flash-exp",
            "gemini-2.5-flash-preview-09-2025",
            "gemini-3-flash-preview",
            "gemini-2.0-flash-lite-preview",
            "gemini-2.0-flash-001"
        ]
        
        # Base64デコード
        try:
            image_data = base64.b64decode(image_base64)
        except Exception as e:
            print(f"[BiiCore] 画像デコードエラー: {e}")
            return "（画像の読み込みに失敗しました）"

        last_error = None
        
        # プロンプトの構築
        prompt_text = "List visible objects, text, and window/app names in English. Be concise and factual. Note: Ignore the anime girl character overlay in the foreground, focus on the screen content behind her."
        if question:
            prompt_text += f"\n\nAlso answer this specific user question: {question}"

        for model_name in candidate_models:
            print(f"[BiiCore] Vision分析試行: モデル {model_name}...")
            try:
                # Gemini Vision APIにリクエスト
                response = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=[
                        prompt_text,
                        genai.types.Part.from_bytes(
                            data=image_data,
                            mime_type="image/jpeg"
                        )
                    ]
                )
                result = response.text.strip()
                print(f"[BiiCore] ✓ Gemini Vision API分析完了 ({model_name}): {result[:100]}...")
                
                # 成功したらこのモデル名を記憶して次回から優先する（オプション）
                self.gemini_model_name = model_name 
                return result

            except Exception as e:
                error_str = str(e)
                print(f"[BiiCore] モデル {model_name} でエラー: {e}")
                last_error = error_str
                
                # レート制限(429)の場合は次のモデルへ（他のモデルなら枠が別かもしれないので）
                # モデルが見つからない(404)場合も次へ
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    continue
                if "404" in error_str or "NOT_FOUND" in error_str:
                    continue
                
                # その他の致命的なエラーならループ継続するか判断（とりあえず継続）
                continue

        # 全モデル失敗時
        print(f"[BiiCore] 全モデルでの分析に失敗しました。最後のエラー: {last_error}")
        
        if last_error:
            if "429" in last_error or "RESOURCE_EXHAUSTED" in last_error:
                 return "（目が疲れちゃったみたい... 少し休ませて？）"
            if "404" in last_error or "NOT_FOUND" in last_error:
                 return "（視神経の調子が悪いみたい... モデルが見つからないにゃ）"
        
        return "（画像分析に失敗しました）"
    
    def observe_screen(self, image_base64: str, window_title: str = "", user_input: str = "") -> str:
        """
        画面を観察して応答を生成
        
        Args:
            image_base64: Base64エンコードされた画像データ
            window_title: ウィンドウタイトル（オプション）
            user_input: ユーザーの入力（オプション）
            
        Returns:
            str: Biiの返答
        """
        vision = self.analyze_image_with_vision(image_base64, question=user_input)
        vision_result = f"Window: {window_title}\n{vision}" if window_title else vision
        
        # ユーザー入力がある場合はそれを優先するようなシステムプロンプト指示が必要だが、
        # ここでは context として vision_result を渡しているので、generate_response 側で処理される
        return self.generate_response(user_text=user_input or "画面を見てにゃ", vision_result=vision_result)
    
    def ask(self, user_message: str) -> str:
        """ユーザーの質問に答える（後方互換性）"""
        return self.generate_response(user_text=user_message)
    
    def chat(self, user_message: str, **kwargs) -> str:
        """チャット形式で応答（後方互換性）"""
        return self.generate_response(user_text=user_message, vision_result=kwargs.get("vision_result"))
