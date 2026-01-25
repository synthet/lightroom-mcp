import subprocess
import sys
import json
import threading
import time

def reader(process):
    """Reads lines from stdout and prints them."""
    for line in iter(process.stdout.readline, ''):
        if not line:
            break
        print(f"SERVER: {line.strip()}")
    process.stdout.close()

def test_mcp_server():
    server_script = "d:/Projects/lightroom-mcp/mcp-server/server.py"
    cmd = [sys.executable, server_script]

    print(f"Starting server: {cmd}")
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    # Start reader thread
    t = threading.Thread(target=reader, args=(process,))
    t.start()

    try:
        # 1. Initialize
        print("\n--- Sending Initialize ---")
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05", # Updated protocol version
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            }
        }
        process.stdin.write(json.dumps(init_req) + "\n")
        process.stdin.flush()
        time.sleep(1)

        # 2. List Tools
        print("\n--- Sending tools/list ---")
        list_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        process.stdin.write(json.dumps(list_req) + "\n")
        process.stdin.flush()
        time.sleep(1)

        # 3. Call get_studio_info
        print("\n--- Sending tools/call (get_studio_info) ---")
        call_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_studio_info",
                "arguments": {}
            }
        }
        process.stdin.write(json.dumps(call_req) + "\n")
        process.stdin.flush()
        time.sleep(2)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("\nClosing server...")
        try:
            process.terminate()
            process.wait(timeout=2)
        except:
            process.kill()
        t.join(timeout=2)

if __name__ == "__main__":
    test_mcp_server()
