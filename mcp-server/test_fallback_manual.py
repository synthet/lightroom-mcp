
import os
import sys
import logging

# Add current dir to path so we can import server
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock dependencies to avoid side effects during test
import unittest.mock as mock

# Mock mcp.tool decorator
mock_mcp = mock.MagicMock()
mock_mcp.tool = lambda: lambda x: x

# Mock FastMCP
with mock.patch('mcp.server.fastmcp.FastMCP', return_value=mock_mcp):
    import server

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_fallback():
    print("Testing metadata fallback...")

    # Create a dummy file to find
    test_filename = "test_fallback_dummy.txt"
    with open(test_filename, "w") as f:
        f.write("dummy content")

    try:
        # Mock search_photos to simulate LrC failure/not found
        with mock.patch('server.search_photos', return_value='[]'):

            # Mock read_file_metadata to avoid Pillow requirements and just verify path was found
            with mock.patch('server.read_file_metadata') as mock_read:
                mock_read.return_value = "Success: Metadata Read"

                # Test finding the local file
                print(f"Searching for {test_filename}...")
                result = server.get_metadata_by_filename(test_filename, ".")

                print(f"Result: {result}")

                # Verify it called read_file_metadata with the absolute path
                if mock_read.called:
                    args, _ = mock_read.call_args
                    found_path = args[0]
                    print(f"Called read_file_metadata with: {found_path}")
                    if os.path.basename(found_path) == test_filename:
                        print("SUCCESS: File was found via fallback!")
                    else:
                        print("FAILURE: Wrong file found.")
                else:
                    print("FAILURE: read_file_metadata was not called.")

    finally:
        # Cleanup
        if os.path.exists(test_filename):
            os.remove(test_filename)

if __name__ == "__main__":
    test_fallback()
