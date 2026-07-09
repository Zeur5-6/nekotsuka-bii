"""
Bii の「脳」

- 応答生成は Ollama の tool calling ベース。Web検索・コード検索を使うかどうかは
  キーワードリストではなく LLM 自身が判断する
- 長期記憶（SQLite, WALモード）と会話履歴を保持
- 画面分析は Gemini Vision API（成功したモデルを記憶して次回優先）
"""
import base64
import json
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from google import genai

import emotion_utils
from bii_rag import CodeReader
from bii_tools import format_search_results, search_web
from config import (DB_PATH, GEMINI_API_KEY, OLLAMA_MODEL, OLLAMA_URL,
                    get_logger)
from vision_module import BiiVision

log = get_logger("BiiCore")

# 画面分析に使う Gemini モデルの候補（先頭から順に試す）
GEMINI_CANDIDATES = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-2.5-flash-preview-09-2025",
    "gemini-3-flash-preview",
    "gemini-2.0-flash-lite-preview",
    "gemini-2.0-flash-001",
]

# 「明日」「来週」などが含まれる場合だけ現在日時をプロンプトに注入する
RELATIVE_DATE_KEYWORDS = [
    "明日", "来週", "昨日", "先週", "来月", "先月", "来年", "去年",
    "今年", "今週", "今月", "今日", "何時", "何日", "何曜日",
]

WEEKDAY_NAMES = ["月", "火", "水", "木", "金", "土", "日"]


class BiiCore:
    """Bii のコアエンジン（応答生成・記憶・視覚・表情タグ）"""

    def __init__(self, model: str = None, ollama_url: str = None,
                 vts_expression_path: Optional[str] = None):
        """
        Args:
            model: Ollamaモデル名（None なら config.OLLAMA_MODEL）
            ollama_url: Ollama API の URL（None なら config.OLLAMA_URL）
            vts_expression_path: VTS expressions フォルダ（None なら自動検出）
        """
        self.model = model or OLLAMA_MODEL
        self.ollama_url = ollama_url or OLLAMA_URL
        self.chat_url = f"{self.ollama_url}/api/chat"

        # 1. 表情ファイルのスキャン（VTS接続後は update_expressions_from_vts で上書き）
        self.vts_expression_path = self._resolve_vts_expression_path(vts_expression_path)
        self.emotion_file_to_tag: Dict[str, str] = {}
        self.emotion_files = self._scan_vts_expressions()

        # 2. Gemini API（視覚）
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEYが必要です。.env を確認してください。")
        self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        self.gemini_model_name = GEMINI_CANDIDATES[0]

        # 3. 記憶と RAG
        self.db_path = DB_PATH
        self._init_database()
        self.long_term_memory = self._load_memory()
        self.code_reader = CodeReader()

        # 4. 画面キャプチャ
        self.vision = BiiVision()

        # 5. 会話履歴管理
        self.session_id = "default"
        self.max_conversation_history = 10

        # 6. システムプロンプト
        self.system_prompt = self._build_system_prompt()

        log.info(f"初期化完了。モデル: {self.model} / "
                 f"感情タグ: {', '.join(self.emotion_files)}")

    # ==================================================================
    # 表情タグ
    # ==================================================================

    def _resolve_vts_expression_path(self, user_path: Optional[str]) -> Path:
        """VTS expressions フォルダのパスを解決する"""
        if user_path:
            return Path(user_path).expanduser().resolve()

        possible_paths = [
            Path.home() / "AppData/Local/VTubeStudio/expressions",
            Path.home() / "Documents/VTubeStudio/expressions",
            Path("./live2d_app/models/bii"),
            Path("./live2d/emotions"),
            Path("./expressions"),
        ]
        for path in possible_paths:
            if path.exists() and path.is_dir():
                log.info(f"VTS expressionsフォルダを検出: {path}")
                return path

        default_path = Path("./live2d/emotions")
        log.warning(f"VTS expressionsフォルダが見つかりません。デフォルト: {default_path}")
        return default_path

    def _scan_vts_expressions(self) -> List[str]:
        """expressions ディレクトリの .exp3.json から感情タグリストを作成する"""
        tags: List[str] = []
        self.emotion_file_to_tag = {}

        if self.vts_expression_path.exists() and self.vts_expression_path.is_dir():
            files = sorted(self.vts_expression_path.glob("**/*.exp3.json"))
            for f in files:
                tag_name = f"[{emotion_utils.tag_from_filename(f.name)}]"
                if tag_name not in tags:
                    tags.append(tag_name)
                self.emotion_file_to_tag[f.name] = tag_name
            if files:
                log.info(f"表情ファイル {len(files)}個を検出: {', '.join(tags)}")

        if not tags:
            log.info("表情ファイルが見つからないため標準タグを仮登録します")
            tags = [f"[{t}]" for t in emotion_utils.DEFAULT_TAGS]

        if "[Neutral]" not in tags:
            tags.append("[Neutral]")  # Neutral は「表情リセット」として常に使える
        return tags

    def update_expressions_from_vts(self, vts_expressions: List[Dict[str, Any]]) -> None:
        """VTS API から取得した表情リストで感情タグを更新する"""
        if not vts_expressions:
            log.warning("VTS APIから表情リストが取得できませんでした。"
                        "ファイルスキャン結果を継続使用します。")
            return

        tags: List[str] = []
        self.emotion_file_to_tag = {}
        for expr in vts_expressions:
            file_name = expr.get("file", "")
            if file_name and file_name.endswith(".exp3.json"):
                tag_name = f"[{emotion_utils.tag_from_filename(file_name)}]"
                if tag_name not in tags:
                    tags.append(tag_name)
                self.emotion_file_to_tag[file_name] = tag_name

        if tags:
            if "[Neutral]" not in tags:
                tags.append("[Neutral]")
            self.emotion_files = tags
            self.system_prompt = self._build_system_prompt()
            log.info(f"VTS APIと同期完了。感情タグ: {', '.join(tags)}")
        else:
            log.warning("VTS APIから有効な表情ファイルが見つかりませんでした")

    def extract_emotion_tag(self, text: str) -> Optional[str]:
        """応答テキストから感情名を抽出する（例: 'Happy'）"""
        return emotion_utils.extract_emotion_tag(text)

    def strip_emotion_tags(self, text: str) -> str:
        """先頭の感情タグを除去する（本文中の [] は温存）"""
        return emotion_utils.strip_leading_tag(text)

    # ==================================================================
    # データベース（長期記憶・会話履歴）
    # ==================================================================

    def _connect_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        # WAL: 複数スレッド（メイン + 事実抽出スレッド）からの書き込みで
        # "database is locked" を避ける
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=3000")
        return conn

    def _init_database(self):
        conn = self._connect_db()
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_session "
                       "ON conversations(session_id, created_at)")

        # 起動時クリーンアップ: ゴミキーワードと30日以上前の会話を削除
        cursor.execute("DELETE FROM interests WHERE LENGTH(keyword) < 2")
        cursor.execute("DELETE FROM conversations "
                       "WHERE created_at < datetime('now', '-30 days')")
        conn.commit()

        try:
            cursor.execute("SELECT COUNT(*) FROM interests")
            interests_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM projects")
            projects_count = cursor.fetchone()[0]
            if interests_count or projects_count:
                log.info(f"記憶DB読み込み: 興味関心 {interests_count}件 / "
                         f"プロジェクト {projects_count}件")
        except Exception as e:
            log.warning(f"データベース状態の確認に失敗: {e}")
        finally:
            conn.close()

    def _load_memory(self) -> Dict[str, Any]:
        """長期記憶を SQLite から読み込む"""
        memory = {"interests": [], "projects": []}
        try:
            conn = self._connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT keyword, category FROM interests "
                           "ORDER BY priority DESC, last_mentioned DESC LIMIT 10")
            memory["interests"] = [
                {"keyword": row[0], "category": row[1]} for row in cursor.fetchall()]
            cursor.execute("SELECT name, description, status FROM projects "
                           "ORDER BY updated_at DESC LIMIT 10")
            memory["projects"] = [
                {"name": row[0], "description": row[1], "status": row[2]}
                for row in cursor.fetchall()]
            conn.close()
        except Exception as e:
            log.warning(f"記憶の読み込みに失敗: {e}")
        return memory

    def save_conversation(self, role: str, content: str,
                          session_id: Optional[str] = None):
        """会話履歴を保存する（同期・数ms なので応答遅延にはならない）"""
        try:
            conn = self._connect_db()
            conn.execute(
                "INSERT INTO conversations (session_id, role, content, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (session_id or self.session_id, role, content,
                 datetime.now().isoformat()))
            conn.commit()
            conn.close()
        except Exception as e:
            log.warning(f"会話履歴の保存に失敗: {e}")

    def get_conversation_history(self, session_id: Optional[str] = None,
                                 limit: Optional[int] = None) -> List[Dict[str, str]]:
        """会話履歴を取得する（古い順）"""
        try:
            conn = self._connect_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content FROM conversations WHERE session_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (session_id or self.session_id,
                 limit or self.max_conversation_history))
            rows = cursor.fetchall()
            conn.close()
            return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
        except Exception as e:
            log.warning(f"会話履歴の取得に失敗: {e}")
            return []

    def clear_conversation_history(self, session_id: Optional[str] = None):
        """会話履歴をクリアする"""
        try:
            conn = self._connect_db()
            conn.execute("DELETE FROM conversations WHERE session_id = ?",
                         (session_id or self.session_id,))
            conn.commit()
            conn.close()
            log.info("会話履歴をクリアしました")
        except Exception as e:
            log.warning(f"会話履歴のクリアに失敗: {e}")

    # ==================================================================
    # システムプロンプト
    # ==================================================================

    def _build_system_prompt(self) -> str:
        valid_tags = ", ".join(self.emotion_files)

        memory_section = ""
        if self.long_term_memory.get("interests"):
            interests = [i["keyword"] for i in self.long_term_memory["interests"]]
            memory_section += f"\n- マスターの興味関心: {', '.join(interests)}"
        if self.long_term_memory.get("projects"):
            projects = [f"{p['name']} ({p['status']})"
                        for p in self.long_term_memory["projects"]]
            memory_section += f"\n- マスターのプロジェクト: {', '.join(projects)}"
        if memory_section:
            memory_section = f"\n【マスターについて知っていること】{memory_section}"

        return f"""あなたは「Bii」。マスター（CS学生）の相棒の、猫耳AIアシスタントだにゃ。

【口調】
- 一人称は「ボク」。語尾は「〜だにゃ」「〜だぞ」「〜だね」。
- 敬語（です・ます）は使わない。友達のようなタメ口で話す。
- 回答は必ず自然な日本語だけで書く。

【出力形式】
必ず「[感情タグ] セリフ」の形式で、感情タグ1つから始めること。
使える感情タグ: {valid_tags}
このリスト以外のタグは存在しないので使わない。

【事実性】
- 提供された情報（画面分析・検索結果・参照コード・記憶）だけを根拠に話す。
- 提供されていないファイル名や事実をでっち上げない。分からないことは素直に「分からない」と言う。
- ツール（Web検索・コード検索）は外部の情報が本当に必要なときだけ使う。挨拶や雑談では使わない。
{memory_section}"""

    # ==================================================================
    # ツール定義と実行（Ollama tool calling）
    # ==================================================================

    @staticmethod
    def _tool_definitions() -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": ("最新ニュース・天気・リリース情報・一般知識など、"
                                    "外部のWeb情報が必要なときに使う検索ツール"),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "検索キーワード（年号は付けない）",
                            }
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "code_search",
                    "description": ("マスターのプロジェクト内のコード・ファイル・実装"
                                    "について質問されたときに使う検索ツール"),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "探したい処理や関数の説明",
                            }
                        },
                        "required": ["query"],
                    },
                },
            },
        ]

    def _execute_tool(self, name: str, args: Dict[str, Any],
                      user_text: str = "") -> str:
        """ツール呼び出しを実行して、モデルに返す文字列を作る"""
        if name == "web_search":
            query = str(args.get("query") or user_text).strip()
            # 記事タイトルに年号が無いとヒットしなくなるため年号は除去する
            query = re.sub(r"\d{4}年", "", query).strip() or user_text
            log.info(f"Web検索: {query}")
            try:
                results = search_web(query, max_results=3)
            except Exception as e:
                return f"（Web検索に失敗しました: {e}）"
            if not results:
                return "（検索結果が見つかりませんでした）"
            return f"【Web検索結果（クエリ: {query}）】\n{format_search_results(results)}"

        if name == "code_search":
            query = str(args.get("query") or user_text).strip()
            log.info(f"コード検索: {query}")
            try:
                results = self.code_reader.search_code(query, max_results=2)
            except Exception as e:
                return f"（コード検索に失敗しました: {e}）"
            if not results:
                return "（該当するコードが見つかりませんでした）"
            files = ", ".join(r["file"] for r in results)
            parts = [f"### ファイル: {r['file']} ###\n{r['content'][:2000]}"
                     for r in results]
            return ("【参照コード】検索されたファイル: " + files + "\n\n"
                    + "\n\n".join(parts)
                    + "\n\n【重要】上記のファイル名のみ言及可。"
                      "コードに書かれていないことは答えない。")

        return f"（未知のツール: {name}）"

    def _ollama_chat(self, messages: List[Dict[str, Any]],
                     tools: Optional[List[Dict]] = None,
                     temperature: float = 0.6,
                     num_predict: int = 500,
                     timeout: int = 60) -> Dict[str, Any]:
        """Ollama /api/chat を1回呼び出して message オブジェクトを返す"""
        import requests

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": num_predict,
            },
        }
        if tools:
            payload["tools"] = tools

        try:
            response = requests.post(self.chat_url, json=payload, timeout=timeout)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            if tools:
                # tool calling 非対応のモデル/バージョン向けフォールバック
                log.warning("tools付きリクエストが拒否されました。ツールなしで再試行します。")
                payload.pop("tools", None)
                response = requests.post(self.chat_url, json=payload, timeout=timeout)
                response.raise_for_status()
            else:
                raise
        return response.json().get("message", {}) or {}

    # ==================================================================
    # 応答生成
    # ==================================================================

    def generate_response(self, user_text: str,
                          vision_result: Optional[str] = None,
                          save_history: bool = True,
                          extract_facts: bool = True) -> str:
        """応答を生成する

        Args:
            user_text: ユーザーのメッセージ
            vision_result: 画面分析結果（ある場合はツールを使わない）
            save_history: 会話履歴に保存するか（オブザーバーの定期観察では False）
            extract_facts: 長期記憶の抽出を行うか（同上）

        Returns:
            "[感情タグ] セリフ" 形式の応答
        """
        conversation_history = self.get_conversation_history(limit=5)
        if save_history:
            self.save_conversation("user", user_text)

        # コンテキストの構築
        input_parts = []
        date_context = self._build_date_context(user_text)
        if date_context:
            input_parts.append(date_context)
        if vision_result:
            input_parts.append(f"【視覚事実（Gemini Vision API）】: {vision_result}")
        memory_facts = self._memory_facts()
        if memory_facts:
            input_parts.append("【長期記憶】:\n" + "\n".join(memory_facts))
        input_data = "\n\n".join(input_parts)

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}]
        for hist in conversation_history:
            content = hist["content"]
            if len(content) > 200:
                content = content[:200] + "..."
            messages.append({"role": hist["role"], "content": content})
        user_content = f"{input_data}\n\n【質問】{user_text}" if input_data else user_text
        messages.append({"role": "user", "content": user_content})

        # 画面分析結果があるときはその内容に集中させる（ツール無効）
        tools = None if vision_result else self._tool_definitions()

        try:
            message = self._ollama_chat(messages, tools=tools, temperature=0.7)

            # ツール呼び出しループ（最大2ラウンド）
            rounds = 0
            while message.get("tool_calls") and rounds < 2:
                messages.append(message)
                for call in message["tool_calls"]:
                    fn = call.get("function", {})
                    name = fn.get("name", "")
                    args = fn.get("arguments") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    result = self._execute_tool(name, args, user_text)
                    messages.append({"role": "tool", "name": name, "content": result})
                rounds += 1
                # ツール結果を根拠に最終回答（事実性重視で温度低め）
                message = self._ollama_chat(messages, tools=None, temperature=0.3)

            content = (message.get("content") or "").strip()
            if not content:
                return "[Neutral] うーん、ちょっとよく分からなかったにゃ..."

            content = self._post_process_response(content)

            if save_history and content:
                self.save_conversation("assistant", content)

            if extract_facts:
                threading.Thread(
                    target=self._extract_and_save_info_safe,
                    args=(user_text, content), daemon=True).start()

            return content

        except Exception as e:
            log.error(f"応答生成に失敗: {e}")
            return f"[Sad] 通信エラーだぞ... {e}"

    def _build_date_context(self, user_text: str) -> str:
        """相対日付表現がある場合のみ現在日時をコンテキストに入れる"""
        if not any(k in user_text for k in RELATIVE_DATE_KEYWORDS):
            return ""
        now = datetime.now()
        weekday = WEEKDAY_NAMES[now.weekday()]
        return (f"【現在日時】: {now.year}年{now.month}月{now.day}日({weekday}) "
                f"{now.hour:02d}:{now.minute:02d}\n"
                f"「明日」「来週」はこの日時を基準に計算すること。")

    def _memory_facts(self) -> List[str]:
        facts = []
        for item in self.long_term_memory.get("interests", []):
            facts.append(f"- 興味関心: {item.get('keyword', '')}")
        status_names = {"in_progress": "進行中", "planned": "予定", "completed": "完了"}
        for project in self.long_term_memory.get("projects", []):
            status = status_names.get(project.get("status", ""),
                                      project.get("status", ""))
            facts.append(f"- プロジェクト: {project.get('name', '')} ({status})")
        return facts

    def _post_process_response(self, response: str) -> str:
        """応答の後処理（感情タグの検証・軽い整形）"""
        if not response:
            return response

        m = re.match(r"^\s*\[([^\]\n]+)\]\s*(.*)", response, re.DOTALL)
        if m:
            tag_name = emotion_utils.normalize_tag_name(m.group(1))
            content = m.group(2)
        else:
            tag_name = None
            content = response

        # タグ検証: 実在しないタグは Neutral に丸める（物理的に存在するファイルだけ参照）
        valid = f"[{tag_name}]" if tag_name else None
        if valid not in self.emotion_files:
            if tag_name:
                log.warning(f"未登録のタグ [{tag_name}] を補正します")
            valid = "[Neutral]" if "[Neutral]" in self.emotion_files else (
                self.emotion_files[0] if self.emotion_files else "")

        # 軽い整形（過剰な語尾の重複・空行・空白）
        content = re.sub(r"にゃ\s*にゃ", "にゃ", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = re.sub(r" {2,}", " ", content).strip()

        return f"{valid} {content}".strip()

    def clean_text_for_voice(self, text: str) -> str:
        """音声合成用にテキストをクリーンアップする"""
        cleaned = emotion_utils.strip_leading_tag(text)
        cleaned = re.sub(r"【[^】]*】", "", cleaned)      # 見出しメタは読まない
        cleaned = re.sub(r"https?://[^\s]+", "リンク", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    # ==================================================================
    # コマンド処理
    # ==================================================================

    @staticmethod
    def parse_command(text: str):
        """'/code foo bar' → ('code', ['foo', 'bar'])。コマンドでなければ None"""
        if not text or not text.startswith("/"):
            return None
        parts = text[1:].strip().split(maxsplit=1)
        if not parts or not parts[0]:
            return None
        command = parts[0].lower()
        args = parts[1].split() if len(parts) > 1 else []
        return command, args

    def handle_command(self, command: str, args: List[str] = None) -> Optional[str]:
        """コマンドを処理する。未知のコマンドは None（通常対話に回す）"""
        args = args or []

        if command in ("help", "ヘルプ"):
            return self._cmd_help()
        if command in ("memory", "記憶"):
            return self._cmd_memory()
        if command in ("code", "コード"):
            if not args:
                return "[Neutral] コード検索のクエリを指定してにゃ。例: /code データベース"
            return self._cmd_code(" ".join(args))
        if command in ("search", "検索"):
            if not args:
                return "[Neutral] 検索クエリを指定してにゃ。例: /search Python"
            return self._cmd_search(" ".join(args))
        if command in ("history", "履歴"):
            return self._cmd_history()
        if command in ("clear", "クリア"):
            self.clear_conversation_history()
            return "[Neutral] 会話履歴をクリアしたにゃ"
        if command in ("vision", "画面", "observe", "観察"):
            return self._cmd_vision()
        return None

    def _cmd_vision(self) -> str:
        try:
            log.info("画面をキャプチャして分析します...")
            img_base64, window_title = self.vision.capture_screen(save_debug=True)
            return self.observe_screen(img_base64, window_title=window_title or "")
        except Exception as e:
            log.error(f"画面観察に失敗: {e}")
            return f"[Sad] 画面観察に失敗したにゃ: {e}"

    def _cmd_help(self) -> str:
        return """[Happy] コマンド一覧だにゃ！

/memory - 長期記憶（興味関心・プロジェクト）を表示
/code <query> - コード検索を実行
/search <query> - Web検索を実行
/vision - 画面をキャプチャしてGemini APIで分析
/history - 会話履歴を表示（直近10件）
/clear - 会話履歴をクリア
/help - このヘルプを表示

例: /code データベース、/search Python、/vision、/memory"""

    def _cmd_memory(self) -> str:
        memory = self.long_term_memory
        result = "[Happy] マスターの長期記憶だにゃ！\n\n"
        if memory.get("interests"):
            interests = [i["keyword"] for i in memory["interests"]]
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
        try:
            results = self.code_reader.search_code(query, max_results=3)
            if not results:
                return "[Neutral] コードが見つからなかったにゃ..."
            result = "[Happy] コード検索結果だにゃ！\n\n"
            for i, res in enumerate(results, 1):
                content = res["content"]
                if len(content) > 500:
                    content = content[:500] + "..."
                result += f"【{i}. {res['file']}】\n{content}\n\n"
            return result.strip()
        except Exception as e:
            return f"[Sad] コード検索に失敗したにゃ: {e}"

    def _cmd_search(self, query: str) -> str:
        try:
            results = search_web(query, max_results=5)
            if not results:
                return "[Neutral] 検索結果が見つからなかったにゃ..."
            return f"[Happy] Web検索結果だにゃ！\n\n{format_search_results(results)}"
        except Exception as e:
            return f"[Sad] Web検索に失敗したにゃ: {e}"

    def _cmd_history(self) -> str:
        try:
            history = self.get_conversation_history(limit=10)
            if not history:
                return "[Neutral] 会話履歴がないにゃ（初回の会話）"
            result = f"[Happy] 会話履歴（直近{len(history)}件）だにゃ！\n\n"
            for i, hist in enumerate(history, 1):
                role = "マスター" if hist["role"] == "user" else "Bii"
                content = hist["content"][:100]
                if len(hist["content"]) > 100:
                    content += "..."
                result += f"{i}. {role}: {content}\n"
            return result.strip()
        except Exception as e:
            return f"[Sad] 会話履歴の取得に失敗したにゃ: {e}"

    # ==================================================================
    # 長期記憶の抽出（Active Learning）
    # ==================================================================

    def _extract_and_save_info_safe(self, user_message: str, bii_response: str):
        try:
            self._extract_and_save_info(user_message, bii_response)
        except Exception as e:
            log.warning(f"事実抽出に失敗: {e}")

    def _extract_facts(self, user_text: str) -> Dict[str, Any]:
        """ユーザーの発言から興味関心・プロジェクトを抽出する"""
        extractor_prompt = f"""ユーザーの発言から、以下の形式でJSONを抽出してください。
抽出対象:
1. 興味関心（好きなもの、趣味、関心のある話題）
2. プロジェクト（進行中の作業、開発中のもの、計画中のもの）

JSON形式:
{{
  "interests": ["キーワード1", "キーワード2"],
  "projects": [
    {{"name": "プロジェクト名", "description": "説明", "status": "in_progress"}}
  ]
}}

抽出ルール:
- 明確に述べられた事実のみを抽出（推測禁止）
- キーワードは2文字以上30文字以内の完全な単語
- statusは "in_progress", "planned", "completed" のいずれか
- 情報がない場合は空配列を返す

ユーザーの発言: {user_text}

JSON（JSONのみを出力、説明不要）:"""

        try:
            message = self._ollama_chat(
                [{"role": "system",
                  "content": "あなたは事実抽出の専門家です。客観的事実のみをJSONで抽出してください。"},
                 {"role": "user", "content": extractor_prompt}],
                temperature=0.1, timeout=20)
            raw = (message.get("content") or "").strip()
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end > start:
                return json.loads(raw[start:end + 1].replace("{{", "{").replace("}}", "}"))
            return {"interests": [], "projects": []}
        except json.JSONDecodeError as e:
            log.warning(f"事実抽出のJSON解析エラー: {e}")
            return {"interests": [], "projects": []}
        except Exception as e:
            log.warning(f"事実抽出に失敗: {e}")
            return {"interests": [], "projects": []}

    def _extract_and_save_info(self, user_message: str, bii_response: str) -> None:
        """会話から事実を抽出して SQLite に永続化する"""
        facts = self._extract_facts(user_message)
        if not facts:
            return

        conn = self._connect_db()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        saved = 0

        for keyword in facts.get("interests", []):
            if not keyword or len(keyword) < 2:
                continue
            cursor.execute("SELECT id, priority FROM interests WHERE keyword = ?",
                           (keyword,))
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    "UPDATE interests SET priority = ?, last_mentioned = ? WHERE id = ?",
                    (existing[1] + 1, now, existing[0]))
            else:
                cursor.execute(
                    "INSERT INTO interests (keyword, category, priority, created_at, "
                    "last_mentioned) VALUES (?, ?, ?, ?, ?)",
                    (keyword, "general", 1, now, now))
            saved += 1

        for project in facts.get("projects", []):
            name = (project.get("name") or "").strip()
            if not name or len(name) < 2:
                continue
            description = (project.get("description") or "").strip()
            status = project.get("status", "in_progress")
            cursor.execute("SELECT id FROM projects WHERE name = ?", (name,))
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    "UPDATE projects SET description = ?, status = ?, updated_at = ? "
                    "WHERE id = ?", (description, status, now, existing[0]))
            else:
                cursor.execute(
                    "INSERT INTO projects (name, description, status, created_at, "
                    "updated_at) VALUES (?, ?, ?, ?, ?)",
                    (name, description, status, now, now))
            saved += 1

        conn.commit()
        conn.close()

        if saved > 0:
            self.long_term_memory = self._load_memory()
            self.system_prompt = self._build_system_prompt()
            log.info(f"長期記憶を{saved}件更新しました")

    # ==================================================================
    # 視覚（Gemini Vision）
    # ==================================================================

    def analyze_image_with_vision(self, image_base64: str, question: str = "") -> str:
        """Gemini Vision API で画像を分析する

        前回成功したモデルを先頭にして候補を順に試す（レート制限・404対策）。
        """
        try:
            image_data = base64.b64decode(image_base64)
        except Exception as e:
            log.error(f"画像デコードエラー: {e}")
            return "（画像の読み込みに失敗しました）"

        prompt_text = ("List visible objects, text, and window/app names in English. "
                       "Be concise and factual. Note: Ignore the anime girl character "
                       "overlay in the foreground, focus on the screen content behind her.")
        if question:
            prompt_text += f"\n\nAlso answer this specific user question: {question}"

        # 前回成功したモデルを優先
        candidates = [self.gemini_model_name] + [
            m for m in GEMINI_CANDIDATES if m != self.gemini_model_name]

        last_error = None
        for model_name in candidates:
            try:
                response = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=[
                        prompt_text,
                        genai.types.Part.from_bytes(
                            data=image_data, mime_type="image/jpeg"),
                    ])
                result = response.text.strip()
                log.info(f"Vision分析完了 ({model_name}): {result[:80]}...")
                self.gemini_model_name = model_name
                return result
            except Exception as e:
                last_error = str(e)
                log.warning(f"Visionモデル {model_name} でエラー: {e}")
                continue

        log.error(f"全Visionモデルで分析に失敗。最後のエラー: {last_error}")
        if last_error:
            if "429" in last_error or "RESOURCE_EXHAUSTED" in last_error:
                return "（目が疲れちゃったみたい... 少し休ませて？）"
            if "404" in last_error or "NOT_FOUND" in last_error:
                return "（視神経の調子が悪いみたい... モデルが見つからないにゃ）"
        return "（画像分析に失敗しました）"

    def observe_screen(self, image_base64: str, window_title: str = "",
                       user_input: str = "", save_history: bool = True,
                       extract_facts: bool = True) -> str:
        """画面を観察して応答を生成する

        Args:
            save_history / extract_facts: オブザーバーの定期観察では False にして
                会話履歴と長期記憶を汚さない
        """
        vision = self.analyze_image_with_vision(image_base64, question=user_input or "")
        vision_result = f"Window: {window_title}\n{vision}" if window_title else vision
        return self.generate_response(
            user_text=user_input or "画面を見てにゃ",
            vision_result=vision_result,
            save_history=save_history,
            extract_facts=extract_facts)

    # ==================================================================
    # 後方互換 API
    # ==================================================================

    def ask(self, user_message: str) -> str:
        """ユーザーの質問に答える（後方互換）"""
        return self.generate_response(user_text=user_message)

    def chat(self, user_message: str, **kwargs) -> str:
        """チャット形式で応答（後方互換）"""
        return self.generate_response(
            user_text=user_message, vision_result=kwargs.get("vision_result"))
