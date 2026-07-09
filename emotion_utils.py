"""
感情タグの解析・正規化・表情ファイル名との相互変換

bii_core / live2d_server / bii_desktop / vts_adapter に重複していたタグ処理を
一箇所に集約する。タグとファイル名の対応はここのロジックだけが真実。
"""
import re
from typing import Dict, List, Optional

# 別名タグ → 正規タグ
TAG_ALIASES = {
    "Shock": "Surprised",
}

# 表情ファイルが1つも見つからないときに使う標準タグ
DEFAULT_TAGS = ["Happy", "Sad", "Angry", "Surprised", "Neutral"]


def normalize_tag_name(raw: str) -> str:
    """'happy' / 'HAPPY' / 'Shock' などを正規タグ名（'Happy', 'Surprised' 等）に揃える"""
    name = (raw or "").strip()
    if not name:
        return name
    if name.islower() or name.isupper():
        name = name.capitalize()
    return TAG_ALIASES.get(name, name)


def tag_from_filename(file_name: str) -> str:
    """表情ファイル名からタグ名を生成する

    例: 'happy.exp3.json' → 'Happy'
        'shock.exp3.json' → 'Surprised'（別名解決）
        'angry_face.exp3.json' → 'AngryFace'
    """
    base = file_name
    for suffix in (".exp3.json", ".exp3"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    parts = [p for p in re.split(r"[_\-\s]+", base) if p]
    if not parts:
        return normalize_tag_name(base)
    name = "".join(p[:1].upper() + p[1:] for p in parts)
    return TAG_ALIASES.get(name, name)


def extract_emotion_tag(text: str) -> Optional[str]:
    """応答テキスト先頭の [タグ] から感情名を抽出する

    例: '[Happy] やったにゃ' → 'Happy'
        '[shock] びっくり' → 'Surprised'
        タグが無ければ None
    """
    m = re.match(r"\s*\[([^\]\n]+)\]", text or "")
    if not m:
        return None
    return normalize_tag_name(m.group(1))


def strip_leading_tag(text: str) -> str:
    """テキスト先頭の感情タグだけを除去する（本文中の [] は温存する）"""
    return re.sub(r"^\s*\[[^\]\n]+\]\s*", "", text or "").strip()


def build_emotion_to_file_map(expression_files: List[str]) -> Dict[str, Optional[str]]:
    """表情ファイル名のリストから 感情タグ → ファイル名 のマッピングを構築する

    'shock.exp3.json' しか無いモデルでも 'Surprised' タグで表情が出せるように
    別名解決込みで対応付ける。Neutral は「全表情リセット」の意味で None。
    """
    mapping: Dict[str, Optional[str]] = {}
    for file_name in expression_files:
        if not file_name or not file_name.endswith(".exp3.json"):
            continue
        tag = tag_from_filename(file_name)
        mapping.setdefault(tag, file_name)
    mapping.setdefault("Neutral", None)
    return mapping
