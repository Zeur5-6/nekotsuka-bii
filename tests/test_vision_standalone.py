
import os
import sys
import time
from dotenv import load_dotenv
import traceback

# Load env variables
load_dotenv()

print("=== Vision Feature Diagnostic Tool ===")

# 1. Check API Key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ ERROR: GEMINI_API_KEY not found in .env")
    sys.exit(1)
print(f"✓ GEMINI_API_KEY found: {api_key[:5]}...{api_key[-5:]}")

# 2. Check Dependencies
print("\nChecking dependencies...")
try:
    import pyautogui
    import pygetwindow as gw
    from PIL import Image, ImageGrab
    from google import genai
    print("✓ All dependencies imported successfully")
except ImportError as e:
    print(f"❌ ERROR: Missing dependency: {e}")
    sys.exit(1)

# 3. Test Screen Capture
print("\nTesting Screen Capture...")
try:
    from vision_module import BiiVision
    vision = BiiVision()
    print("Minimizing this window in 2 seconds...")
    time.sleep(2)
    
    img_base64, window_title = vision.capture_screen(save_debug=True)
    print(f"✓ Capture successful!")
    print(f"  - Window Title: {window_title}")
    print(f"  - Image Data Length: {len(img_base64)}")
    print(f"  - Debug image saved to: {os.path.abspath('debug_vision.png')}")
except Exception as e:
    print(f"❌ ERROR: Screen capture failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# 4. Test Gemini API
print("\nTesting Gemini API Connection...")
try:
    client = genai.Client(api_key=api_key)
    print("Sending image to Gemini API...")
    
    import base64
    image_data = base64.b64decode(img_base64)
    
    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=[
            "Describe this screen in Japanese. What do you see?",
            genai.types.Part.from_bytes(
                data=image_data,
                mime_type="image/jpeg"
            )
        ]
    )
    print("✓ Gemini API Responded!")
    print(f"Response: {response.text}")

except Exception as e:
    print(f"❌ ERROR: Gemini API failed: {e}")
    traceback.print_exc()
    # Try fallback model
    print("\nTrying fallback model 'gemini-1.5-flash'...")
    try:
         response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=[
                "Describe this screen.",
                genai.types.Part.from_bytes(
                    data=image_data,
                    mime_type="image/jpeg"
                )
            ]
        )
         print("✓ Gemini API (Fallback) Responded!")
         print(f"Response: {response.text}")
    except Exception as e2:
         print(f"❌ ERROR: Fallback model also failed: {e2}")

print("\n=== Diagnosis Complete ===")
input("Press Enter to close...")
