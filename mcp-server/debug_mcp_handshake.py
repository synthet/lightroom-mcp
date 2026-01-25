import sys
import subprocess
import json
import time
import os

SERVER_SCRIPT = r"d:\Projects\lightroom-mcp\mcp-server\server.py"
PYTHON_EXE = r"d:\Projects\lightroom-mcp\mcp-server\.venv\Scripts\python.exe"

def debug_mcp():
    print(f"Starting server: {PYTHON_EXE} {SERVER_SCRIPT}")

    # Start the server process
    process = subprocess.Popen(
        [PYTHON_EXE, SERVER_SCRIPT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0  # Unbuffered
    )

    print("Server started. Sending initialize request...")

    # MCP Initialize Request
    init_request = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "start-debugger", "version": "1.0"}
        },
        "id": 1
    }

    try:
        # Write to stdin
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        print("Request sent.")

        # Read response (with timeout simulation)
        output_buffer = ""
        start_time = time.time()
        while time.time() - start_time < 5:
            if process.poll() is not None:
                print(f"Process exited with code {process.returncode}")
                stdout, stderr = process.communicate()
                print(f"STDOUT: {stdout}")
                print(f"STDERR: {stderr}")
                return

            line = process.stdout.readline()
            if line:
                print(f"Received output: {line.strip()}")
                output_buffer += line

                try:
                    msg = json.loads(line)
                    print("Valid JSON received!")
                    print(json.dumps(msg, indent=2))
                    break
                except json.JSONDecodeError:
                    print("Invalid JSON received (could be log noise)")

            time.sleep(0.1)

        # Read any stderr
        stderr_output = process.stderr.read()
        if stderr_output:
            print(f"STDERR during execution:\n{stderr_output}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        process.terminate()

if __name__ == "__main__":
    debug_mcp()
