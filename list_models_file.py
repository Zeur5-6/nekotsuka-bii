
import os
import sys
from dotenv import load_dotenv
from google import genai

# Redirect stdout to a file to avoid console interleaving issues
sys.stdout = open("available_models.txt", "w", encoding="utf-8")

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

try:
    client = genai.Client(api_key=api_key)
    print("--- Available Models ---")
    for m in client.models.list():
        print(f"Name: {m.name}")
        print(f"  Display Name: {m.display_name}")
        # print(f"  Supported Methods: {m.supported_generation_methods}")
        print("-" * 20)
    print("--- End of List ---")
except Exception as e:
    print(f"Error: {e}")
