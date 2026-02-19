import asyncio
import os
import sys
import base64
import json
from unittest.mock import MagicMock

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server import get_photo_preview
from lrc_client import LrCClient

async def run_test():
    print("--- Starting get_photo_preview Tool Verification ---")

    # Setup LRC client
    lrc = LrCClient()
    if not lrc.start_broker():
        print("FAILED: Could not start Lightroom client")
        return

    # Mock context
    ctx = MagicMock()
    ctx.request_context = MagicMock()
    ctx.request_context.lifespan_context = MagicMock()
    ctx.request_context.lifespan_context.lrc = lrc

    # 1. Test base64 preview (current selection)
    print("\n1. Testing base64 preview for selection...")
    try:
        response = await get_photo_preview(ctx, width=100, height=100)
        if response and 'photos' in response:
            content = response['photos']
            print(f"  - Result contains {len(content)} items")
            found_image = False
            for item in content:
                if 'jpegBase64' in item:
                    found_image = True
                    print(f"  - OK: Found image data (length: {len(item['jpegBase64'])})")
                    if item['jpegBase64'].startswith('/9j/'): # JPEG base64 header
                        print("  - OK: Valid JPEG header found")
            if not found_image:
                print("  - FAILED: No image found in response")
        else:
            print(f"  - FAILED: Unexpected response: {response}")
    except Exception as e:
        print(f"  - FAILED: Error during base64 test: {e}")

    # 2. Test saving to path
    print("\n2. Testing preview save to path...")
    temp_dir = os.path.join(os.getcwd(), "test_previews")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    try:
        response = await get_photo_preview(ctx, save_path=temp_dir, width=200, height=200)
        if response and 'savedPaths' in response:
            saved_paths = response['savedPaths']
            print(f"  - Result saved paths: {saved_paths}")
            # Check if file exists
            if saved_paths and len(saved_paths) > 0:
                p = saved_paths[0]
                if os.path.exists(p):
                    print(f"  - OK: Verified file exists: {os.path.basename(p)}")
                else:
                    print(f"  - FAILED: File missing: {p}")
            else:
                print("  - FAILED: savedPaths list is empty")
        else:
            print(f"  - FAILED: Unexpected response: {response}")
    except Exception as e:
        print(f"  - FAILED: Error during save_path test: {e}")

    # 3. Test with specific photo_id
    print("\n3. Testing preview for specific photo_id...")
    try:
        # Get current selection to find an ID
        status_resp = lrc.send_command("get_selection")
        print(f"  - Raw get_selection response: {str(status_resp)[:200]}")

        target_id = None
        if status_resp and "result" in status_resp:
            result_data = status_resp["result"]
            if isinstance(result_data, str):
                result_data = json.loads(result_data)

            # result_data should be a list of photo dicts
            if isinstance(result_data, list) and len(result_data) > 0:
                target_id = result_data[0].get('localId')
            elif isinstance(result_data, dict):
                # Could be wrapped with a "photos" key
                photos = result_data.get("photos") or result_data.get("selection", [])
                if photos:
                    target_id = photos[0].get('localId')

        if target_id is not None:
            print(f"  - Using target_id: {target_id}")
            response = await get_photo_preview(ctx, photo_id=target_id, width=150, height=150)
            if response and 'photos' in response:
                photos = response['photos']
                if photos and str(photos[0].get('localId')) == str(target_id) and 'jpegBase64' in photos[0]:
                    print(f"  - SUCCESS: Got preview for photo_id {target_id}")
                else:
                     print(f"  - FAILED: incorrect or missing photo in response for {target_id}: {response}")
            else:
                print(f"  - FAILED: Could not get preview for {target_id}: {response}")
        else:
            print("  - SKIP: No selection found to get a valid photo_id")
    except Exception as e:
        print(f"  - FAILED: Error during photo_id test: {e}")

    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(run_test())
