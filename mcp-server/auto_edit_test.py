import base64
import requests
import json
import os
import sys

BROKER_URL = "http://127.0.0.1:8085/auto_edit"
TEST_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "auto_settings", "tests", "test_images", "sample.jpg")

if not os.path.exists(TEST_IMAGE_PATH):
    print(f"Error: test image not found at {TEST_IMAGE_PATH}")
    # Try finding any jpg
    import glob
    jpgs = glob.glob(os.path.join(os.path.dirname(__file__), "..", "**", "*.jpg"), recursive=True)
    if not jpgs:
        print("No jpgs found to test with.")
        sys.exit(1)
    TEST_IMAGE_PATH = jpgs[0]

print(f"Using test image: {TEST_IMAGE_PATH}")

with open(TEST_IMAGE_PATH, "rb") as f:
    image_bytes = f.read()

encoded = base64.b64encode(image_bytes).decode('utf-8')

payload = {
    "image": encoded,
    "localId": "test_id",
    "provider": "gemini"
}

print("Sending request to broker...")
try:
    response = requests.post(BROKER_URL, json=payload, timeout=60)
    print(f"Status Code: {response.status_code}")
    print("Response JSON:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")
