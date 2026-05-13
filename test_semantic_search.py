"""
セマンティック検索の動作確認用テストスクリプト
ビフォー・アフターの違いを確認できます
"""
from bii_rag import CodeReader

def test_search_comparison():
    """検索の違いを確認"""
    print("=" * 60)
    print("セマンティック検索の動作確認")
    print("=" * 60)
    
    # CodeReaderの初期化（セマンティック検索有効）
    code_reader = CodeReader(enable_semantic=True)
    
    # テストクエリ
    test_queries = [
        "エラーを処理する関数",
        "データベースに接続する処理",
        "VTSの表情を設定する関数"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"【検索クエリ】: {query}")
        print(f"{'='*60}")
        
        # セマンティック検索の結果
        print("\n[セマンティック検索結果]")
        results_semantic = code_reader.search_code(query, max_results=3, use_semantic=True)
        for i, result in enumerate(results_semantic, 1):
            method = result.get("method", "unknown")
            score = result.get("score", 0)
            print(f"  {i}. {result['file']} (スコア: {score:.2f}, 方法: {method})")
            print(f"     {result['content'][:100]}...")
        
        # キーワード検索のみの結果（比較用）
        print("\n[キーワード検索のみの結果（比較用）]")
        results_keyword = code_reader.search_code(query, max_results=3, use_semantic=False)
        for i, result in enumerate(results_keyword, 1):
            score = result.get("score", 0)
            print(f"  {i}. {result['file']} (スコア: {score:.2f})")
    
    print(f"\n{'='*60}")
    print("テスト完了")
    print("=" * 60)

if __name__ == "__main__":
    test_search_comparison()