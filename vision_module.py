"""
画面キャプチャモジュール

- 全画面を撮影し、Gemini へ渡す JPEG(base64) を生成する
- アクティブウィンドウのタイトルはメタ情報として取得のみ行う（撮影範囲は全画面）
- 解像度は長辺 config.VISION_MAX_PX（既定 1024px）。画面上の文字を
  Gemini が読み取れる解像度と転送量のバランスを取る
"""
import base64
from io import BytesIO

import pygetwindow as gw
from PIL import Image, ImageGrab

from config import VISION_MAX_PX, get_logger

log = get_logger("Vision")


class BiiVision:
    def capture_screen(self, max_px: int = None, save_debug: bool = True):
        """全画面をキャプチャして Base64 文字列で返す

        Args:
            max_px: 長辺の最大ピクセル数（None なら config.VISION_MAX_PX）
            save_debug: デバッグ画像 debug_vision.png を保存するか

        Returns:
            tuple: (Base64エンコードされたJPEG, アクティブウィンドウのタイトル)
        """
        max_px = max_px or VISION_MAX_PX

        # アクティブウィンドウのタイトルはメタ情報として取るだけ（最小化などはしない）
        window_title = "Full Screen"
        try:
            active = gw.getActiveWindow()
            if active and active.title:
                window_title = active.title
        except Exception:
            pass

        screenshot = ImageGrab.grab()

        original_size = screenshot.size
        scale = min(1.0, max_px / max(original_size))
        if scale < 1.0:
            new_size = (int(original_size[0] * scale), int(original_size[1] * scale))
            screenshot = screenshot.resize(new_size, Image.LANCZOS)
        log.info(f"画面キャプチャ: {original_size[0]}x{original_size[1]} → "
                 f"{screenshot.size[0]}x{screenshot.size[1]} (window: {window_title})")

        if save_debug:
            try:
                screenshot.save("debug_vision.png", format="PNG")
            except Exception as e:
                log.warning(f"デバッグ画像の保存に失敗: {e}")

        buffered = BytesIO()
        screenshot.convert("RGB").save(buffered, format="JPEG", quality=80)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        return img_str, window_title


# テスト実行用
if __name__ == "__main__":
    vision = BiiVision()
    img_base64, title = vision.capture_screen()
    print(f"キャプチャ完了！(Base64長さ: {len(img_base64)}, ウィンドウ: {title})")
