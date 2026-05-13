import requests
import os

url = "https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js"
save_path = "live2d_app/lib/live2dcubismcore.min.js"

os.makedirs(os.path.dirname(save_path), exist_ok=True)

print(f"Downloading Cubism Core from {url}...")
try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    
    with open(save_path, "wb") as f:
        f.write(response.content)
    
    print(f"Successfully saved to {save_path}")
    print(f"File size: {len(response.content)} bytes")
except Exception as e:
    print(f"Error downloading file: {e}")
