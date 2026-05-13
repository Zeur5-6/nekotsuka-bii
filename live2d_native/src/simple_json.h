/**
 * 簡易JSONパーサー
 * C++初心者向けのシンプルな実装
 * 
 * 注意: これは簡易的な実装です。本格的なJSON処理には
 * nlohmann/jsonなどのライブラリを使用することを推奨します。
 */

#ifndef SIMPLE_JSON_H
#define SIMPLE_JSON_H

#include <string>
#include <map>
#include <vector>

class SimpleJson {
public:
    // JSON値を表すクラス
    class Value {
    public:
        enum Type {
            NULL_TYPE,
            BOOL,
            NUMBER,
            STRING,
            ARRAY,
            OBJECT
        };
        
        Type type;
        bool boolValue;
        double numberValue;
        std::string stringValue;
        std::vector<Value> arrayValue;
        std::map<std::string, Value> objectValue;
        
        Value() : type(NULL_TYPE) {}
        
        // 文字列からJSONをパース
        static Value Parse(const std::string& json);
        
        // オブジェクトから値を取得
        Value Get(const std::string& key) const;
        
        // 配列から値を取得
        Value Get(size_t index) const;
        
        // 型チェック
        bool IsString() const { return type == STRING; }
        bool IsNumber() const { return type == NUMBER; }
        bool IsBool() const { return type == BOOL; }
        bool IsArray() const { return type == ARRAY; }
        bool IsObject() const { return type == OBJECT; }
    };
    
    // JSON文字列をパース
    static Value Parse(const std::string& json);
    
private:
    // パーサーの内部実装（簡易版）
    static size_t SkipWhitespace(const std::string& json, size_t pos);
    static Value ParseValue(const std::string& json, size_t& pos);
    static Value ParseObject(const std::string& json, size_t& pos);
    static Value ParseArray(const std::string& json, size_t& pos);
    static Value ParseString(const std::string& json, size_t& pos);
    static Value ParseNumber(const std::string& json, size_t& pos);
    static Value ParseBool(const std::string& json, size_t& pos);
};

#endif // SIMPLE_JSON_H
