"""
Web検索ツール: DuckDuckGoを使用したWeb検索機能
"""
try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        raise ImportError("ddgsまたはduckduckgo_searchパッケージが必要です。`pip install ddgs`を実行してください。")

from typing import List, Dict, Optional


def search_web(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """
    DuckDuckGoを使用してWeb検索を実行し、上位N件の結果を返す
    
    Args:
        query: 検索クエリ
        max_results: 取得する結果の最大数（デフォルト: 3）
        
    Returns:
        List[Dict[str, str]]: [{"title": "タイトル", "url": "URL", "snippet": "スニペット"}] のリスト
    """
    try:
        with DDGS() as ddgs:
            results = []
            # DuckDuckGoで検索を実行
            for result in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("href", ""),
                    "snippet": result.get("body", "")
                })
            return results
    except Exception as e:
        print(f"[WebSearch] エラー: Web検索に失敗しました: {e}")
        return []


def format_search_results(results: List[Dict[str, str]]) -> str:
    """
    検索結果をプロンプト用のテキスト形式にフォーマット
    
    Args:
        results: search_web()の戻り値
        
    Returns:
        str: フォーマットされた検索結果テキスト
    """
    if not results:
        return "（検索結果が見つかりませんでした）"
    
    formatted = []
    for i, result in enumerate(results, 1):
        formatted.append(f"{i}. **{result['title']}**\n   URL: {result['url']}\n   説明: {result['snippet']}")
    
    return "\n\n".join(formatted)
