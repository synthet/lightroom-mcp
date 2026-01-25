import time
import base64
from lrc_client import LrCClient

c = LrCClient()

# Try multiple times
for attempt in range(5):
    print(f"Attempt {attempt + 1}...")
    result = c.send_command("get_photo_preview", {"width": 800, "height": 800})
    photo = result["result"]["photos"][0]

    if "jpegBase64" in photo:
        jpeg_data = base64.b64decode(photo["jpegBase64"])
        with open(r"D:\Projects\lightroom-mcp\preview_DSC_2957_enhanced.jpg", "wb") as f:
            f.write(jpeg_data)
        print(f"Success! Saved {len(jpeg_data)} bytes")
        break
    else:
        print(f"  Waiting for render... ({photo.get('error', 'unknown')})")
        time.sleep(2)
else:
    print("Failed after 5 attempts - Lightroom may still be rendering")
