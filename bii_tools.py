"""
Web検索ツール: DuckDuckGo を使用した Web 検索機能
"""
try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        raise ImportError(
            "ddgs または duckduckgo_search パッケージが必要です。"
            "`python -m pip install ddgs` を実行してください。")

from typing import Dict, List

from config import get_logger

log = get_logger("WebSearch")


def search_web(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """DuckDuckGo で Web 検索を実行し、上位 N 件の結果を返す

    Returns:
        [{"title": タイトル, "url": URL, "snippet": スニペット}, ...]
    """
    try:
        with DDGS() as ddgs:
            results = []
            for result in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("href", ""),
                    "snippet": result.get("body", ""),
                })
            return results
    except Exception as e:
        log.error(f"Web検索に失敗しました: {e}")
        return []


def format_search_results(results: List[Dict[str, str]]) -> str:
    """検索結果をプロンプト用のテキスト形式にフォーマットする"""
    if not results:
        return "（検索結果が見つかりませんでした）"

    formatted = []
    for i, result in enumerate(results, 1):
        formatted.append(
            f"{i}. **{result['title']}**\n   URL: {result['url']}\n   説明: {result['snippet']}")
    return "\n\n".join(formatted)
