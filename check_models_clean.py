
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

print("--- Start Model List ---")
try:
    for m in client.models.list():
        if "gemini" in m.name:
            print(m.name)
except Exception as e:
    print(e)
print("--- End Model List ---")
