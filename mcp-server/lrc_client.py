"""
Lightroom Classic Client - HTTP client for MCP Broker

Communicates with the Lightroom plugin via the HTTP broker server.
Much simpler than the previous socket-based implementation.
"""

import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

# Broker configuration
BROKER_URL = "http://127.0.0.1:8085"
BROKER_SCRIPT = Path(__file__).parent / "broker.py"
REQUEST_TIMEOUT = 35  # Slightly longer than broker's internal timeout


class LrCClient:
    """Client for communicating with Lightroom Classic via the MCP Broker."""

    def __init__(self, broker_url: str = BROKER_URL):
        self.broker_url = broker_url
        self._request_id = 0
        self._broker_process = None

    def _ensure_broker_running(self) -> bool:
        """Check if broker is running, optionally start it."""
        try:
            response = requests.get(f"{self.broker_url}/api/status", timeout=2)
            return response.status_code == 200
        except requests.exceptions.ConnectionError:
            return False
        except Exception as e:
            logger.warning(f"Error checking broker status: {e}")
            return False

    def start_broker(self) -> bool:
        """Start the broker server if not already running."""
        if self._ensure_broker_running():
            logger.debug("Broker already running")
            return True

        logger.info("Starting broker server...")
        try:
            # Start broker as subprocess
            self._broker_process = subprocess.Popen(
                [sys.executable, str(BROKER_SCRIPT)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )

            # Wait for broker to start
            for _ in range(10):
                time.sleep(0.5)
                if self._ensure_broker_running():
                    logger.info("Broker started successfully")
                    return True

            logger.error("Broker failed to start within timeout")
            return False

        except Exception as e:
            logger.error(f"Failed to start broker: {e}")
            return False

    def send_command(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send a JSON-RPC command to Lightroom via the broker."""

        # Ensure broker is running
        if not self._ensure_broker_running():
            if not self.start_broker():
                raise ConnectionError("Broker not running and failed to start")

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self._request_id
        }

        try:
            logger.debug(f"Sending request: {method}")
            response = requests.post(
                f"{self.broker_url}/request",
                json=request,
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code == 504:
                raise ConnectionError("Request timeout - Lightroom not responding")

            response.raise_for_status()
            result = response.json()
            logger.debug(f"Received response for: {method}")
            return result

        except requests.exceptions.Timeout:
            logger.error("Request timeout")
            raise ConnectionError("Request timeout")

        except requests.exceptions.ConnectionError:
            logger.error("Connection error - broker not available")
            raise ConnectionError("Broker not available")

        except Exception as e:
            logger.error(f"Communication error: {e}")
            raise ConnectionError(f"Communication error: {e}")

    def close(self):
        """Close the client (no-op for HTTP client)."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def check_plugin_status() -> dict:
    """Check if the broker and Lightroom plugin are running."""
    status = {
        "broker_running": False,
        "lightroom_connected": False,
        "broker_url": BROKER_URL,
    }

    try:
        response = requests.get(f"{BROKER_URL}/api/status", timeout=2)
        if response.status_code == 200:
            status["broker_running"] = True
            data = response.json()
            status["lightroom_connected"] = data.get("lightroom_connected", False)
            status["requests_total"] = data.get("requests_total", 0)
            status["avg_latency_ms"] = data.get("avg_latency_ms", 0)
    except Exception:
        pass

    return status


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("Checking plugin status...")
    status = check_plugin_status()
    print(f"Status: {status}")

    if status["broker_running"] and status["lightroom_connected"]:
        print("\nTesting get_studio_info...")
        client = LrCClient()
        try:
            result = client.send_command("get_studio_info")
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error: {e}")
