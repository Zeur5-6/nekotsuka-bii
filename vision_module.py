import pyautogui
import pygetwindow as gw
from PIL import Image, ImageGrab
import base64
from io import BytesIO
import os

class BiiVision:
    def capture_screen(self, scale=0.7, save_debug=True):
        """
        アクティブなウィンドウ（一番手前の窓）だけをキャプチャしてBase64文字列で返すんだぞ
        
        Args:
            scale: 画像のスケール（デフォルト: 0.7、Gemini用には384x384に縮小されるため使用されない）
            save_debug: デバッグ画像を保存するか（デフォルト: True）
            
        Returns:
            tuple: (Base64エンコードされた画像文字列, ウィンドウタイトル)
        """
        window_title = "Full Screen"
        
        try:
            # ユーザーの要望により、アクティブウィンドウ取得をやめ、常に全画面撮影に変更
            # これにより「最小化する時間」が不要になり、即応性が向上する
            # （キャラクターが映り込むが、それはプロンプト側で無視するようにする）
            
            # 全画面キャプチャ（全モニターを含む場合があるが、メインモニターを想定）
            # ImageGrab.grab() はメインモニターを撮る
            screenshot = ImageGrab.grab()
            bbox = None
            print(f"[Vision] 全画面キャプチャを実行しました: {screenshot.size}")
            
            # --- 以下、旧アクティブウィンドウ取得ロジック（コメントアウト）---
            # import time
            # active_window = None
            # for i in range(3): ...

        except Exception as e:
            print(f"[Vision] 警告: ウィンドウキャプチャに失敗しました ({e})。全画面をキャプチャします。")
            # エラー時はフォールバック: 全画面キャプチャ
            screenshot = pyautogui.screenshot()
            bbox = None
            window_title = "Unknown"
        
        # サイズを小さくして処理速度とVRAM使用量を削減
        original_width, original_height = screenshot.size
        
        # Gemini用：384x384に超軽量化（API転送時間を最小限に）
        target_size = 384
        # アスペクト比を維持しながら384x384の範囲内に収める
        if original_width > original_height:
            scale_factor = target_size / original_width
        else:
            scale_factor = target_size / original_height
        
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)
        new_size = (new_width, new_height)
        screenshot = screenshot.resize(new_size, Image.LANCZOS)
        print(f"[Vision] 画像を超軽量化: {original_width}x{original_height} → {new_width}x{new_height} (Gemini用: 最大384px)")
        
        # デバッグ画像を保存
        if save_debug:
            try:
                screenshot.save("debug_vision.png", format="PNG")
                print(f"[Vision] デバッグ画像を保存: debug_vision.png ({new_size[0]}x{new_size[1]})")
            except Exception as e:
                print(f"[Vision] 警告: デバッグ画像の保存に失敗しました: {e}")
        
        # Base64に変換（Ollama APIに送るため）
        buffered = BytesIO()
        screenshot.save(buffered, format="JPEG", quality=75)  # 品質を少し上げて文字認識精度を維持
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        return img_str, window_title  # ウィンドウタイトルも返す（メタ情報として活用）

# テスト実行用
if __name__ == "__main__":
    vision = BiiVision()
    img_base64, window_title = vision.capture_screen()
    print(f"キャプチャ完了！(Base64長さ: {len(img_base64)}, ウィンドウ: {window_title})")