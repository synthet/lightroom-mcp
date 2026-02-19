import socket
import sys

def test_port(port, host='127.0.0.1'):
    print(f"Testing port {host}:{port}...")
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        test_socket.bind((host, port))
        print("SUCCESS: Bound successfully. Port is free.")
        test_socket.close()
    except OSError as e:
        print(f"FAILED: OSError {e.errno}: {e.strerror}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"FAILED: Unexpected error: {e}")

if __name__ == "__main__":
    test_port(54321)
