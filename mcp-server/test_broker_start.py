from broker import app, BROKER_HOST, BROKER_PORT
import threading
from broker import run_socket_server

# Start socket server in separate thread
socket_thread = threading.Thread(target=run_socket_server, daemon=True)
socket_thread.start()

# Run Flask server
try:
    print(f"Starting test broker on {BROKER_HOST}:{BROKER_PORT}...")
    app.run(host=BROKER_HOST, port=BROKER_PORT, threaded=True, debug=False)
except Exception as e:
    print(f"FAILED: {e}")
