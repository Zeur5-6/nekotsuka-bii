
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

print("Listing available models...")
try:
    models = client.models.list(config={"page_size": 100})
    for m in models:
        # Show only models that likely support content generation
        print(f"- {m.name} (Display: {m.display_name})")
        # print(f"  Supported: {m.supported_generation_methods}") 
except Exception as e:
    print(f"Error listing models: {e}")
    # Try older library style if the above fails logic, but we are using google-genai
    import traceback
    traceback.print_exc()
