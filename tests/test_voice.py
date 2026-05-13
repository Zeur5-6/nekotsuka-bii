# test_voice.py
from bii_core import BiiCore
from voicevox_adapter import VoicevoxAdapter

def test_bii_voice():
    # 1. 各モジュールの準備
    brain = BiiCore()
    voice = VoicevoxAdapter()

    print("--- 接続テスト開始だぞ！ ---")
    
    # 2. 脳に言葉を生成させる
    # ここでボクが「猫使ビィ」として答えれば、人格も声もバッチリだにゃ
    text = brain.ask("ボクの声、ちゃんと届いてるかな？")
    print(f"ビィのセリフ: {text}")

    # 3. 生成されたセリフをVOICEVOXで再生
    # ※事前にVOICEVOXアプリを起動しておいてにゃ！
    print("VOICEVOXで再生中...")
    voice.play_voice(text)

if __name__ == "__main__":
    test_bii_voice()