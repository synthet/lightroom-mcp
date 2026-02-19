import logging
import threading
from broker import app, run_socket_server, BROKER_HOST, BROKER_PORT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Start socket server in separate thread
    logger.info("Starting socket server thread...")
    socket_thread = threading.Thread(target=run_socket_server, daemon=True)
    socket_thread.start()

    # Run Flask server
    try:
        logger.info(f"Starting broker server on {BROKER_HOST}:{BROKER_PORT}...")
        app.run(host=BROKER_HOST, port=BROKER_PORT, threaded=True, debug=False)
    except Exception as e:
        logger.error(f"Failed to start broker: {e}")
