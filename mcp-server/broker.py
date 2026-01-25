"""
Lightroom MCP Broker Server

HTTP broker that relays messages between the Lightroom plugin and MCP server.
Features:
- REST API for request/response relay
- WebSocket for real-time dashboard updates
- System tray icon with status
- Web UI dashboard
"""

import json
import logging
import os
import sys
import threading
import time
import uuid
import webbrowser
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request, Response
from flask_sock import Sock

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

BROKER_PORT = 54321
BROKER_HOST = '127.0.0.1'
SOCKET_PORT = 54322  # Fallback socket port for plugin
REQUEST_TIMEOUT = 30  # seconds
POLL_TIMEOUT = 0.5  # seconds for long-polling
LR_CONNECTION_TIMEOUT = 5  # seconds before considering LR disconnected
WS_PING_INTERVAL = 30  # seconds

# ============================================================================
# Global State
# ============================================================================

# Pending requests waiting for Lightroom response
pending_requests: Dict[str, Dict[str, Any]] = {}
pending_requests_lock = threading.Lock()

# Request queue for Lightroom to poll
request_queue: deque = deque()
request_queue_lock = threading.Lock()
request_queue_event = threading.Event()

# Connected WebSocket clients
ws_clients: list = []
ws_clients_lock = threading.Lock()

# Broker statistics
broker_stats = {
    "started_at": None,
    "lightroom_connected": False,
    "lightroom_last_poll": None,
    "requests_total": 0,
    "requests_success": 0,
    "requests_failed": 0,
    "requests_timeout": 0,
    "avg_latency_ms": 0,
    "total_latency_ms": 0,
    "recent_requests": deque(maxlen=100),
    "recent_logs": deque(maxlen=500),
}
stats_lock = threading.Lock()

# History file path
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "broker_history.json")
HISTORY_AUTO_SAVE = True  # Auto-save history after each request

# ============================================================================
# History Save/Load Functions
# ============================================================================

def save_history():
    """Save request history to JSON file."""
    try:
        with stats_lock:
            history_data = {
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "requests": list(broker_stats["recent_requests"]),
            }

        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=2, default=str)

        return True
    except Exception as e:
        logger.error(f"Failed to save history: {e}")
        return False


def load_history():
    """Load request history from JSON file."""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history_data = json.load(f)

            with stats_lock:
                broker_stats["recent_requests"].clear()
                for req in history_data.get("requests", []):
                    broker_stats["recent_requests"].append(req)

            logger.info(f"Loaded {len(history_data.get('requests', []))} requests from history")
            return True
    except Exception as e:
        logger.error(f"Failed to load history: {e}")
    return False


# ============================================================================
# Flask App Setup
# ============================================================================

app = Flask(__name__)
sock = Sock(app)

# Disable Flask's default logging for cleaner output
log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)

# ============================================================================
# Logging Helper
# ============================================================================

def broker_log(level: str, message: str):
    """Log a message and store it for the dashboard."""
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = {"timestamp": timestamp, "level": level, "message": message}

    with stats_lock:
        broker_stats["recent_logs"].append(entry)

    # Also log to console
    if level == "ERROR":
        logger.error(message)
    elif level == "WARNING":
        logger.warning(message)
    elif level == "DEBUG":
        logger.debug(message)
    else:
        logger.info(message)

    # Broadcast to WebSocket clients (outside any lock to prevent contention)
    # Use a thread to avoid blocking the caller
    def _broadcast():
        try:
            broadcast_ws({"type": "log_entry", "timestamp": timestamp, "data": entry})
        except Exception:
            pass  # Don't let broadcast failures affect logging

    threading.Thread(target=_broadcast, daemon=True).start()

# ============================================================================
# WebSocket Broadcasting
# ============================================================================

def broadcast_ws(message: dict):
    """Broadcast a message to all connected WebSocket clients."""
    msg_str = json.dumps(message)

    # Get a snapshot of clients to avoid holding lock during send
    with ws_clients_lock:
        clients_snapshot = list(ws_clients)

    if not clients_snapshot:
        return

    dead_clients = []
    for ws in clients_snapshot:
        try:
            ws.send(msg_str)
        except Exception:
            dead_clients.append(ws)

    # Remove dead clients
    if dead_clients:
        with ws_clients_lock:
            for ws in dead_clients:
                if ws in ws_clients:
                    ws_clients.remove(ws)

def update_lr_connection_status():
    """Check if Lightroom is still connected based on last poll time."""
    broadcast_msg = None
    status_changed = False
    is_connected = False

    with stats_lock:
        last_poll = broker_stats["lightroom_last_poll"]
        if last_poll:
            elapsed = (datetime.now(timezone.utc) - last_poll).total_seconds()
            was_connected = broker_stats["lightroom_connected"]
            is_connected = elapsed < LR_CONNECTION_TIMEOUT
            broker_stats["lightroom_connected"] = is_connected

            if was_connected != is_connected:
                status_changed = True
                broadcast_msg = {
                    "type": "status_update",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": {"lightroom_connected": is_connected}
                }

    # Broadcast OUTSIDE the lock to prevent contention
    if status_changed:
        status = "connected" if is_connected else "disconnected"
        broker_log("INFO", f"Lightroom {status}")
        if broadcast_msg:
            broadcast_ws(broadcast_msg)

# ============================================================================
# API Endpoints - Core Relay
# ============================================================================

@app.route('/request', methods=['POST'])
def handle_request():
    """
    MCP server posts a JSON-RPC request here.
    Blocks until Lightroom responds or timeout.
    """
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({"error": "Invalid JSON"}), 400

        # Generate UUID for this request
        request_uuid = str(uuid.uuid4())
        request_data["_broker_uuid"] = request_uuid

        broker_log("DEBUG", f"Request {request_uuid[:8]}: {request_data.get('method', 'unknown')}")

        # Create event for waiting
        response_event = threading.Event()

        with pending_requests_lock:
            pending_requests[request_uuid] = {
                "request": request_data,
                "event": response_event,
                "response": None,
                "started_at": datetime.now(timezone.utc),
            }

        # Add to queue for Lightroom to poll
        with request_queue_lock:
            request_queue.append(request_data)
            request_queue_event.set()

        # Update stats
        with stats_lock:
            broker_stats["requests_total"] += 1

        # Broadcast request start
        broadcast_ws({
            "type": "request_start",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "uuid": request_uuid,
                "method": request_data.get("method", "unknown"),
            }
        })

        # Wait for response
        got_response = response_event.wait(timeout=REQUEST_TIMEOUT)

        with pending_requests_lock:
            pending_data = pending_requests.pop(request_uuid, None)

        if not got_response or not pending_data or not pending_data.get("response"):
            # Prepare request payload for storage
            display_request = {k: v for k, v in request_data.items() if k != "_broker_uuid"}
            error_response = {
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": "Request timeout - Lightroom not responding"},
                "id": request_data.get("id")
            }

            with stats_lock:
                broker_stats["requests_timeout"] += 1
                broker_stats["recent_requests"].append({
                    "uuid": request_uuid,
                    "method": request_data.get("method", "unknown"),
                    "latency_ms": REQUEST_TIMEOUT * 1000,
                    "success": False,
                    "error": "timeout",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "request_payload": display_request,
                    "response_payload": error_response,
                })

            # Auto-save history
            if HISTORY_AUTO_SAVE:
                threading.Thread(target=save_history, daemon=True).start()

            # Broadcast timeout with payloads
            broadcast_ws({
                "type": "request_complete",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "uuid": request_uuid,
                    "method": request_data.get("method", "unknown"),
                    "latency_ms": REQUEST_TIMEOUT * 1000,
                    "success": False,
                    "error": "timeout",
                    "request_payload": display_request,
                    "response_payload": error_response,
                }
            })

            broker_log("WARNING", f"Request {request_uuid[:8]} timed out")
            return jsonify(error_response), 504

        # Calculate latency
        latency_ms = (datetime.now(timezone.utc) - pending_data["started_at"]).total_seconds() * 1000

        # Prepare request payload (remove internal broker uuid for display)
        display_request = {k: v for k, v in request_data.items() if k != "_broker_uuid"}
        response_payload = pending_data["response"]

        with stats_lock:
            broker_stats["requests_success"] += 1
            broker_stats["total_latency_ms"] += latency_ms
            broker_stats["avg_latency_ms"] = broker_stats["total_latency_ms"] / broker_stats["requests_success"]
            broker_stats["recent_requests"].append({
                "uuid": request_uuid,
                "method": request_data.get("method", "unknown"),
                "latency_ms": round(latency_ms, 2),
                "success": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_payload": display_request,
                "response_payload": response_payload,
            })

        # Auto-save history
        if HISTORY_AUTO_SAVE:
            threading.Thread(target=save_history, daemon=True).start()

        broker_log("DEBUG", f"Request {request_uuid[:8]} completed in {latency_ms:.0f}ms")

        # Broadcast completion with payloads
        broadcast_ws({
            "type": "request_complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "uuid": request_uuid,
                "method": request_data.get("method", "unknown"),
                "latency_ms": round(latency_ms, 2),
                "success": True,
                "request_payload": display_request,
                "response_payload": response_payload,
            }
        })

        return jsonify(pending_data["response"])

    except Exception as e:
        broker_log("ERROR", f"Error handling request: {e}")
        with stats_lock:
            broker_stats["requests_failed"] += 1
        return jsonify({"error": str(e)}), 500


@app.route('/poll', methods=['POST'])
def handle_poll():
    """
    Lightroom plugin polls for pending requests.
    Returns immediately with a request or empty response.
    """
    # Update last poll time and check if we need to broadcast connection
    should_broadcast = False
    with stats_lock:
        broker_stats["lightroom_last_poll"] = datetime.now(timezone.utc)
        if not broker_stats["lightroom_connected"]:
            broker_stats["lightroom_connected"] = True
            should_broadcast = True

    # Broadcast OUTSIDE the lock
    if should_broadcast:
        broker_log("INFO", "Lightroom connected")
        broadcast_ws({
            "type": "status_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {"lightroom_connected": True}
        })

    # Wait briefly for a request (long-polling)
    request_queue_event.wait(timeout=POLL_TIMEOUT)

    with request_queue_lock:
        if request_queue:
            request_data = request_queue.popleft()
            if not request_queue:
                request_queue_event.clear()
            return jsonify(request_data)

    return Response("", status=204)


@app.route('/response', methods=['POST'])
def handle_response():
    """
    Lightroom plugin posts response here.
    Matches response to pending request via UUID.
    """
    try:
        response_data = request.get_json()
        if not response_data:
            return jsonify({"error": "Invalid JSON"}), 400

        request_uuid = response_data.pop("_broker_uuid", None)
        if not request_uuid:
            broker_log("WARNING", "Response missing _broker_uuid")
            return jsonify({"error": "Missing _broker_uuid"}), 400

        with pending_requests_lock:
            if request_uuid in pending_requests:
                pending_requests[request_uuid]["response"] = response_data
                pending_requests[request_uuid]["event"].set()
                broker_log("DEBUG", f"Response received for {request_uuid[:8]}")
                return jsonify({"status": "ok"})
            else:
                broker_log("WARNING", f"No pending request for UUID {request_uuid[:8]}")
                return jsonify({"error": "Unknown request UUID"}), 404

    except Exception as e:
        broker_log("ERROR", f"Error handling response: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# API Endpoints - Debug/Status
# ============================================================================

@app.route('/api/status', methods=['GET'])
def api_status():
    """Get full broker status."""
    update_lr_connection_status()

    with stats_lock:
        uptime = None
        if broker_stats["started_at"]:
            uptime = (datetime.now(timezone.utc) - broker_stats["started_at"]).total_seconds()

        return jsonify({
            "uptime_seconds": uptime,
            "lightroom_connected": broker_stats["lightroom_connected"],
            "lightroom_last_poll": broker_stats["lightroom_last_poll"].isoformat() if broker_stats["lightroom_last_poll"] else None,
            "requests_total": broker_stats["requests_total"],
            "requests_success": broker_stats["requests_success"],
            "requests_failed": broker_stats["requests_failed"],
            "requests_timeout": broker_stats["requests_timeout"],
            "avg_latency_ms": round(broker_stats["avg_latency_ms"], 2),
            "pending_requests": len(pending_requests),
            "queue_depth": len(request_queue),
        })


@app.route('/api/requests', methods=['GET'])
def api_requests():
    """Get recent requests."""
    with stats_lock:
        return jsonify(list(broker_stats["recent_requests"]))


@app.route('/api/requests/<request_uuid>', methods=['GET'])
def api_request_detail(request_uuid):
    """Get details of a specific request including payloads."""
    with stats_lock:
        for req in broker_stats["recent_requests"]:
            if req["uuid"] == request_uuid:
                return jsonify(req)
    return jsonify({"error": "Request not found"}), 404


@app.route('/api/history/save', methods=['POST'])
def api_history_save():
    """Save request history to JSON file."""
    if save_history():
        return jsonify({"status": "ok", "file": HISTORY_FILE})
    return jsonify({"error": "Failed to save history"}), 500


@app.route('/api/history/load', methods=['POST'])
def api_history_load():
    """Load request history from JSON file."""
    if load_history():
        with stats_lock:
            count = len(broker_stats["recent_requests"])
        return jsonify({"status": "ok", "loaded": count})
    return jsonify({"error": "Failed to load history"}), 500


@app.route('/api/history/export', methods=['GET'])
def api_history_export():
    """Export request history as downloadable JSON file."""
    with stats_lock:
        history_data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "requests": list(broker_stats["recent_requests"]),
        }

    response = Response(
        json.dumps(history_data, indent=2, default=str),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename=broker_history.json'}
    )
    return response


@app.route('/api/history/clear', methods=['POST'])
def api_history_clear():
    """Clear request history."""
    with stats_lock:
        broker_stats["recent_requests"].clear()

    # Also clear the file
    if os.path.exists(HISTORY_FILE):
        try:
            os.remove(HISTORY_FILE)
        except Exception:
            pass

    return jsonify({"status": "ok"})


@app.route('/api/logs', methods=['GET'])
def api_logs():
    """Get recent log entries."""
    level = request.args.get('level', None)
    limit = int(request.args.get('limit', 100))

    with stats_lock:
        logs = list(broker_stats["recent_logs"])

    if level:
        logs = [l for l in logs if l["level"] == level.upper()]

    return jsonify(logs[-limit:])


@app.route('/api/test', methods=['POST'])
def api_test():
    """Send a test ping to Lightroom."""
    update_lr_connection_status()

    with stats_lock:
        connected = broker_stats["lightroom_connected"]

    return jsonify({
        "lightroom_connected": connected,
        "message": "Lightroom is connected" if connected else "Lightroom not connected"
    })


@app.route('/api/config', methods=['GET'])
def api_config():
    """Get current configuration."""
    return jsonify({
        "broker_port": BROKER_PORT,
        "broker_host": BROKER_HOST,
        "socket_port": SOCKET_PORT,
        "request_timeout": REQUEST_TIMEOUT,
        "poll_timeout": POLL_TIMEOUT,
        "lr_connection_timeout": LR_CONNECTION_TIMEOUT,
        "ws_ping_interval": WS_PING_INTERVAL,
    })


@app.route('/api/exit', methods=['POST'])
def api_exit():
    """Exit the broker server."""
    broker_log("INFO", "Exit requested via API")
    # Return response first, then shutdown
    def delayed_exit():
        time.sleep(0.5)
        os._exit(0)
    threading.Thread(target=delayed_exit, daemon=True).start()
    return jsonify({"status": "ok", "message": "Broker shutting down"})


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@sock.route('/ws')
def websocket(ws):
    """WebSocket endpoint for real-time dashboard updates."""
    with ws_clients_lock:
        ws_clients.append(ws)

    broker_log("DEBUG", "WebSocket client connected")

    # Send initial status
    update_lr_connection_status()
    with stats_lock:
        ws.send(json.dumps({
            "type": "status_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "lightroom_connected": broker_stats["lightroom_connected"],
                "requests_total": broker_stats["requests_total"],
                "requests_success": broker_stats["requests_success"],
                "avg_latency_ms": round(broker_stats["avg_latency_ms"], 2),
            }
        }))

    try:
        while True:
            # Receive ping from client (or any message to keep alive)
            try:
                msg = ws.receive(timeout=WS_PING_INTERVAL + 5)
                if msg is None:
                    break
            except Exception:
                break
    finally:
        with ws_clients_lock:
            if ws in ws_clients:
                ws_clients.remove(ws)
        broker_log("DEBUG", "WebSocket client disconnected")


# ============================================================================
# Fallback Socket Server (for Lightroom plugin)
# ============================================================================

import socket
import select

# Socket client connection (only one at a time for simplicity)
socket_client = None
socket_client_lock = threading.Lock()

def handle_socket_client(client_socket, client_address):
    """Handle a connected socket client (Lightroom plugin)."""
    global socket_client

    broker_log("INFO", f"Socket client connected from {client_address}")

    with socket_client_lock:
        socket_client = client_socket

    # Update connection status
    should_broadcast = False
    with stats_lock:
        broker_stats["lightroom_last_poll"] = datetime.now(timezone.utc)
        if not broker_stats["lightroom_connected"]:
            broker_stats["lightroom_connected"] = True
            should_broadcast = True

    # Broadcast OUTSIDE the lock
    if should_broadcast:
        broker_log("INFO", "Lightroom connected (socket)")
        broadcast_ws({
            "type": "status_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {"lightroom_connected": True}
        })

    buffer = b""

    try:
        while True:
            # Check for incoming data or outgoing requests
            ready_to_read, _, _ = select.select([client_socket], [], [], 0.1)

            if ready_to_read:
                data = client_socket.recv(4096)
                if not data:
                    break

                buffer += data

                # Process complete messages (newline-delimited JSON)
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line:
                        try:
                            message = json.loads(line.decode('utf-8'))
                            handle_socket_message(client_socket, message)
                        except json.JSONDecodeError as e:
                            broker_log("WARNING", f"Invalid JSON from socket: {e}")

            # Update last poll time periodically
            with stats_lock:
                broker_stats["lightroom_last_poll"] = datetime.now(timezone.utc)

            # Check if there's a pending request to send
            with request_queue_lock:
                if request_queue:
                    request_data = request_queue.popleft()
                    if not request_queue:
                        request_queue_event.clear()

                    # Send request to socket client
                    try:
                        msg = json.dumps(request_data) + "\n"
                        client_socket.sendall(msg.encode('utf-8'))
                        broker_log("DEBUG", f"Sent request via socket: {request_data.get('method', 'unknown')}")
                    except Exception as e:
                        broker_log("ERROR", f"Failed to send via socket: {e}")
                        # Put request back in queue
                        request_queue.appendleft(request_data)
                        request_queue_event.set()
                        break

    except Exception as e:
        broker_log("WARNING", f"Socket client error: {e}")

    finally:
        with socket_client_lock:
            socket_client = None

        try:
            client_socket.close()
        except:
            pass

        broker_log("INFO", "Socket client disconnected")


def handle_socket_message(client_socket, message):
    """Handle a message received from the socket client."""
    # This is a response from Lightroom
    if "_broker_uuid" in message:
        request_uuid = message.pop("_broker_uuid")

        with pending_requests_lock:
            if request_uuid in pending_requests:
                pending_requests[request_uuid]["response"] = message
                pending_requests[request_uuid]["event"].set()
                broker_log("DEBUG", f"Socket response received for {request_uuid[:8]}")
            else:
                broker_log("WARNING", f"Socket: No pending request for UUID {request_uuid[:8]}")
    else:
        broker_log("WARNING", "Socket message missing _broker_uuid")


def run_socket_server():
    """Run the fallback socket server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((BROKER_HOST, SOCKET_PORT))
        server_socket.listen(1)
        broker_log("INFO", f"Socket server listening on {BROKER_HOST}:{SOCKET_PORT}")

        while True:
            try:
                client_socket, client_address = server_socket.accept()
                # Handle client in a thread
                client_thread = threading.Thread(
                    target=handle_socket_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
            except Exception as e:
                broker_log("ERROR", f"Socket accept error: {e}")
                time.sleep(1)

    except Exception as e:
        broker_log("ERROR", f"Socket server error: {e}")

    finally:
        server_socket.close()


# ============================================================================
# Web UI Dashboard
# ============================================================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lightroom MCP Broker</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
        h1 { color: #fff; margin-bottom: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .status-bar { display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
        .status-card { background: #16213e; padding: 15px 20px; border-radius: 8px; min-width: 150px; }
        .status-card h3 { font-size: 12px; text-transform: uppercase; color: #888; margin-bottom: 5px; }
        .status-card .value { font-size: 24px; font-weight: bold; }
        .status-card .value.connected { color: #4ade80; }
        .status-card .value.disconnected { color: #f87171; }
        .panel { background: #16213e; border-radius: 8px; margin-bottom: 20px; overflow: hidden; }
        .panel-header { padding: 15px 20px; background: #1a1a2e; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: center; }
        .panel-header h2 { font-size: 16px; }
        .panel-content { padding: 15px 20px; max-height: 400px; overflow-y: auto; }
        .log-entry { padding: 8px 0; border-bottom: 1px solid #333; font-family: monospace; font-size: 13px; }
        .log-entry:last-child { border-bottom: none; }
        .log-entry .time { color: #888; margin-right: 10px; }
        .log-entry .level { padding: 2px 6px; border-radius: 3px; margin-right: 10px; font-size: 11px; }
        .log-entry .level.INFO { background: #3b82f6; }
        .log-entry .level.DEBUG { background: #6b7280; }
        .log-entry .level.WARNING { background: #f59e0b; }
        .log-entry .level.ERROR { background: #ef4444; }
        .request-entry { padding: 10px 0; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: background 0.2s; }
        .request-entry:hover { background: rgba(59, 130, 246, 0.1); }
        .request-entry:last-child { border-bottom: none; }
        .request-entry.selected { background: rgba(59, 130, 246, 0.2); }
        .request-entry.failed { border-left: 3px solid #ef4444; padding-left: 10px; }
        .request-method { font-family: monospace; color: #60a5fa; }
        .request-latency { color: #4ade80; }
        .request-latency.failed { color: #f87171; }
        .request-uuid { color: #888; font-size: 12px; font-family: monospace; }
        .request-time { color: #888; font-size: 11px; margin-left: 10px; }
        .btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
        .btn-primary { background: #3b82f6; color: white; }
        .btn-primary:hover { background: #2563eb; }
        .btn-secondary { background: #6b7280; color: white; }
        .btn-secondary:hover { background: #4b5563; }
        .btn-danger { background: #ef4444; color: white; }
        .btn-danger:hover { background: #dc2626; }
        .btn-sm { padding: 5px 10px; font-size: 12px; }
        .filters { display: flex; gap: 10px; }
        .filters select { padding: 5px 10px; border-radius: 4px; border: 1px solid #333; background: #1a1a2e; color: #eee; }
        #ws-status { font-size: 12px; padding: 4px 8px; border-radius: 4px; }
        #ws-status.connected { background: #4ade80; color: #000; }
        #ws-status.disconnected { background: #f87171; color: #000; }

        /* Payload viewer styles */
        .main-layout { display: flex; gap: 20px; }
        .main-left { flex: 1; min-width: 0; }
        .main-right { width: 500px; flex-shrink: 0; }
        .payload-panel { position: sticky; top: 20px; }
        .payload-panel .panel-content { max-height: calc(100vh - 350px); }
        .payload-section { margin-bottom: 15px; }
        .payload-section h4 { font-size: 12px; text-transform: uppercase; color: #888; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
        .payload-box { background: #0d1117; border: 1px solid #333; border-radius: 6px; padding: 12px; font-family: monospace; font-size: 12px; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto; }
        .payload-box.request { border-left: 3px solid #3b82f6; }
        .payload-box.response { border-left: 3px solid #4ade80; }
        .payload-box.error { border-left: 3px solid #ef4444; }
        .no-selection { color: #888; text-align: center; padding: 40px 20px; }
        .copy-btn { font-size: 10px; padding: 2px 6px; background: #333; border: none; color: #888; border-radius: 3px; cursor: pointer; }
        .copy-btn:hover { background: #444; color: #fff; }

        /* Request details */
        .request-details { background: #0d1117; border-radius: 6px; padding: 12px; margin-bottom: 15px; }
        .request-details-row { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #222; }
        .request-details-row:last-child { border-bottom: none; }
        .request-details-label { color: #888; font-size: 12px; }
        .request-details-value { font-family: monospace; font-size: 12px; }
        .request-details-value.success { color: #4ade80; }
        .request-details-value.failed { color: #ef4444; }

        @media (max-width: 1200px) {
            .main-layout { flex-direction: column; }
            .main-right { width: 100%; }
            .payload-panel { position: static; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Lightroom MCP Broker <span id="ws-status" class="disconnected">WS Disconnected</span></h1>

        <div class="status-bar">
            <div class="status-card">
                <h3>Lightroom</h3>
                <div class="value" id="lr-status">--</div>
            </div>
            <div class="status-card">
                <h3>Total Requests</h3>
                <div class="value" id="requests-total">0</div>
            </div>
            <div class="status-card">
                <h3>Success</h3>
                <div class="value" id="requests-success">0</div>
            </div>
            <div class="status-card">
                <h3>Timeouts</h3>
                <div class="value" id="requests-timeout">0</div>
            </div>
            <div class="status-card">
                <h3>Avg Latency</h3>
                <div class="value" id="avg-latency">0ms</div>
            </div>
            <div class="status-card">
                <h3>Uptime</h3>
                <div class="value" id="uptime">--</div>
            </div>
        </div>

        <div class="main-layout">
            <div class="main-left">
                <div class="panel">
                    <div class="panel-header">
                        <h2>Recent Requests</h2>
                        <div style="display: flex; gap: 10px;">
                            <button class="btn btn-secondary btn-sm" onclick="exportHistory()">Export JSON</button>
                            <button class="btn btn-secondary btn-sm" onclick="clearHistory()">Clear</button>
                            <button class="btn btn-primary" onclick="testConnection()">Test Connection</button>
                            <button class="btn btn-danger" onclick="exitBroker()">Exit Broker</button>
                        </div>
                    </div>
                    <div class="panel-content" id="requests-list">
                        <div style="color: #888;">No requests yet</div>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-header">
                        <h2>Logs</h2>
                        <div class="filters">
                            <select id="log-filter" onchange="filterLogs()">
                                <option value="">All Levels</option>
                                <option value="DEBUG">DEBUG</option>
                                <option value="INFO">INFO</option>
                                <option value="WARNING">WARNING</option>
                                <option value="ERROR">ERROR</option>
                            </select>
                        </div>
                    </div>
                    <div class="panel-content" id="logs-list">
                        <div style="color: #888;">No logs yet</div>
                    </div>
                </div>
            </div>

            <div class="main-right">
                <div class="panel payload-panel">
                    <div class="panel-header">
                        <h2>Request Details</h2>
                    </div>
                    <div class="panel-content" id="payload-viewer">
                        <div class="no-selection">Click on a request to view its payload</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let ws = null;
        let requests = [];
        let logs = [];
        let selectedUuid = null;
        let startTime = Date.now();

        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

            ws.onopen = () => {
                document.getElementById('ws-status').textContent = 'WS Connected';
                document.getElementById('ws-status').className = 'connected';
                console.log('WebSocket connected');
            };

            ws.onclose = () => {
                document.getElementById('ws-status').textContent = 'WS Disconnected';
                document.getElementById('ws-status').className = 'disconnected';
                console.log('WebSocket disconnected, reconnecting...');
                setTimeout(connect, 2000);
            };

            ws.onerror = (err) => {
                console.error('WebSocket error:', err);
            };

            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                handleMessage(msg);
            };

            // Ping every 30s
            setInterval(() => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({type: 'ping'}));
                }
            }, 30000);
        }

        function handleMessage(msg) {
            switch (msg.type) {
                case 'status_update':
                    updateStatus(msg.data);
                    break;
                case 'request_start':
                case 'request_complete':
                    addRequest(msg.data);
                    break;
                case 'log_entry':
                    addLog(msg.data);
                    break;
            }
        }

        function updateStatus(data) {
            if (data.lightroom_connected !== undefined) {
                const el = document.getElementById('lr-status');
                el.textContent = data.lightroom_connected ? 'Connected' : 'Disconnected';
                el.className = 'value ' + (data.lightroom_connected ? 'connected' : 'disconnected');
            }
            if (data.requests_total !== undefined) {
                document.getElementById('requests-total').textContent = data.requests_total;
            }
            if (data.requests_success !== undefined) {
                document.getElementById('requests-success').textContent = data.requests_success;
            }
            if (data.avg_latency_ms !== undefined) {
                document.getElementById('avg-latency').textContent = data.avg_latency_ms.toFixed(0) + 'ms';
            }
        }

        function addRequest(data) {
            // Check if this is an update to an existing request (same UUID)
            const existingIndex = requests.findIndex(r => r.uuid === data.uuid);
            if (existingIndex !== -1) {
                // Update existing entry with new data (e.g., latency_ms when completed)
                requests[existingIndex] = { ...requests[existingIndex], ...data };
            } else {
                // New request, add to front
                requests.unshift(data);
                if (requests.length > 100) requests.pop();
            }
            renderRequests();

            // Update payload viewer if this request is selected
            if (selectedUuid === data.uuid) {
                showPayload(data.uuid);
            }
        }

        function addLog(data) {
            logs.unshift(data);
            if (logs.length > 200) logs.pop();
            renderLogs();
        }

        function renderRequests() {
            const container = document.getElementById('requests-list');
            if (requests.length === 0) {
                container.innerHTML = '<div style="color: #888;">No requests yet</div>';
                return;
            }
            container.innerHTML = requests.map(r => {
                const isSelected = r.uuid === selectedUuid;
                const isFailed = r.success === false;
                const time = r.timestamp ? new Date(r.timestamp).toLocaleTimeString() : '';
                return `
                <div class="request-entry ${isSelected ? 'selected' : ''} ${isFailed ? 'failed' : ''}" onclick="showPayload('${r.uuid}')">
                    <div>
                        <span class="request-method">${r.method || 'unknown'}</span>
                        <span class="request-uuid">${r.uuid ? r.uuid.substring(0, 8) : ''}</span>
                        <span class="request-time">${time}</span>
                    </div>
                    <div class="request-latency ${isFailed ? 'failed' : ''}">${r.latency_ms ? r.latency_ms.toFixed(0) + 'ms' : 'pending...'}</div>
                </div>
            `}).join('');
        }

        function renderLogs() {
            const container = document.getElementById('logs-list');
            const filter = document.getElementById('log-filter').value;
            const filtered = filter ? logs.filter(l => l.level === filter) : logs;

            if (filtered.length === 0) {
                container.innerHTML = '<div style="color: #888;">No logs yet</div>';
                return;
            }
            container.innerHTML = filtered.slice(0, 100).map(l => `
                <div class="log-entry">
                    <span class="time">${new Date(l.timestamp).toLocaleTimeString()}</span>
                    <span class="level ${l.level}">${l.level}</span>
                    <span class="message">${escapeHtml(l.message)}</span>
                </div>
            `).join('');
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function showPayload(uuid) {
            selectedUuid = uuid;
            renderRequests(); // Re-render to show selection

            // First check local requests array
            let req = requests.find(r => r.uuid === uuid);

            if (req && req.request_payload) {
                renderPayloadViewer(req);
            } else {
                // Fetch from API for full payload
                fetch(`/api/requests/${uuid}`)
                    .then(r => r.json())
                    .then(data => {
                        if (data.error) {
                            document.getElementById('payload-viewer').innerHTML =
                                '<div class="no-selection">Request not found</div>';
                        } else {
                            // Update local cache
                            const idx = requests.findIndex(r => r.uuid === uuid);
                            if (idx !== -1) {
                                requests[idx] = { ...requests[idx], ...data };
                            }
                            renderPayloadViewer(data);
                        }
                    })
                    .catch(err => {
                        document.getElementById('payload-viewer').innerHTML =
                            '<div class="no-selection">Failed to load request details</div>';
                    });
            }
        }

        function renderPayloadViewer(req) {
            const container = document.getElementById('payload-viewer');
            const isSuccess = req.success !== false;
            const time = req.timestamp ? new Date(req.timestamp).toLocaleString() : 'N/A';

            let html = `
                <div class="request-details">
                    <div class="request-details-row">
                        <span class="request-details-label">Method</span>
                        <span class="request-details-value">${req.method || 'unknown'}</span>
                    </div>
                    <div class="request-details-row">
                        <span class="request-details-label">UUID</span>
                        <span class="request-details-value">${req.uuid || 'N/A'}</span>
                    </div>
                    <div class="request-details-row">
                        <span class="request-details-label">Timestamp</span>
                        <span class="request-details-value">${time}</span>
                    </div>
                    <div class="request-details-row">
                        <span class="request-details-label">Latency</span>
                        <span class="request-details-value">${req.latency_ms ? req.latency_ms.toFixed(0) + 'ms' : 'N/A'}</span>
                    </div>
                    <div class="request-details-row">
                        <span class="request-details-label">Status</span>
                        <span class="request-details-value ${isSuccess ? 'success' : 'failed'}">${isSuccess ? 'Success' : (req.error || 'Failed')}</span>
                    </div>
                </div>
            `;

            if (req.request_payload) {
                const reqJson = JSON.stringify(req.request_payload, null, 2);
                html += `
                    <div class="payload-section">
                        <h4>
                            Request Payload
                            <button class="copy-btn" onclick="copyToClipboard(\`${escapeForJs(reqJson)}\`)">Copy</button>
                        </h4>
                        <div class="payload-box request">${escapeHtml(reqJson)}</div>
                    </div>
                `;
            }

            if (req.response_payload) {
                const respJson = JSON.stringify(req.response_payload, null, 2);
                const hasError = req.response_payload.error;
                html += `
                    <div class="payload-section">
                        <h4>
                            Response Payload
                            <button class="copy-btn" onclick="copyToClipboard(\`${escapeForJs(respJson)}\`)">Copy</button>
                        </h4>
                        <div class="payload-box ${hasError ? 'error' : 'response'}">${escapeHtml(respJson)}</div>
                    </div>
                `;
            }

            if (!req.request_payload && !req.response_payload) {
                html += '<div class="no-selection">No payload data available (request may be pending)</div>';
            }

            container.innerHTML = html;
        }

        function escapeForJs(str) {
            return str.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$');
        }

        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                // Brief visual feedback could be added here
            }).catch(err => {
                console.error('Failed to copy:', err);
            });
        }

        function filterLogs() {
            renderLogs();
        }

        function testConnection() {
            fetch('/api/test', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    alert(data.message);
                });
        }

        function exportHistory() {
            window.location.href = '/api/history/export';
        }

        function clearHistory() {
            if (confirm('Are you sure you want to clear the request history?')) {
                fetch('/api/history/clear', {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        requests = [];
                        selectedUuid = null;
                        renderRequests();
                        document.getElementById('payload-viewer').innerHTML =
                            '<div class="no-selection">Click on a request to view its payload</div>';
                    });
            }
        }

        function exitBroker() {
            if (confirm('Are you sure you want to exit the broker?')) {
                fetch('/api/exit', {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        alert(data.message);
                        document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;"><h1>Broker stopped</h1></div>';
                    })
                    .catch(() => {
                        document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;"><h1>Broker stopped</h1></div>';
                    });
            }
        }

        function updateUptime() {
            fetch('/api/status').then(r => r.json()).then(status => {
                if (status.uptime_seconds) {
                    const hours = Math.floor(status.uptime_seconds / 3600);
                    const mins = Math.floor((status.uptime_seconds % 3600) / 60);
                    const secs = Math.floor(status.uptime_seconds % 60);
                    document.getElementById('uptime').textContent =
                        hours > 0 ? `${hours}h ${mins}m` : `${mins}m ${secs}s`;
                }

                // Also update other stats
                document.getElementById('requests-total').textContent = status.requests_total;
                document.getElementById('requests-success').textContent = status.requests_success;
                document.getElementById('requests-timeout').textContent = status.requests_timeout;
                document.getElementById('avg-latency').textContent = status.avg_latency_ms.toFixed(0) + 'ms';

                const el = document.getElementById('lr-status');
                el.textContent = status.lightroom_connected ? 'Connected' : 'Disconnected';
                el.className = 'value ' + (status.lightroom_connected ? 'connected' : 'disconnected');
            });
        }

        // Initial load
        fetch('/api/requests').then(r => r.json()).then(data => {
            requests = data.reverse();
            renderRequests();
        });

        fetch('/api/logs').then(r => r.json()).then(data => {
            logs = data.reverse();
            renderLogs();
        });

        // Connect WebSocket
        connect();

        // Update uptime every 5 seconds (WebSocket provides real-time updates, this is just fallback)
        setInterval(updateUptime, 5000);
        updateUptime();
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Serve the web dashboard."""
    return DASHBOARD_HTML


@app.route('/logs')
def logs_page():
    """Redirect to dashboard (logs are shown there)."""
    return DASHBOARD_HTML


@app.route('/requests')
def requests_page():
    """Redirect to dashboard (requests are shown there)."""
    return DASHBOARD_HTML


# ============================================================================
# System Tray Icon
# ============================================================================

def create_tray_icon():
    """Create and run the system tray icon."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        broker_log("WARNING", "pystray or Pillow not installed, tray icon disabled")
        return None

    def create_icon_image(color):
        """Create a simple colored circle icon."""
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse([4, 4, size-4, size-4], fill=color)
        return image

    def on_open_dashboard(icon, item):
        webbrowser.open(f'http://localhost:{BROKER_PORT}')

    def on_exit(icon, item):
        broker_log("INFO", "Exit requested from tray")
        icon.stop()
        os._exit(0)

    def get_status_text():
        update_lr_connection_status()
        with stats_lock:
            if broker_stats["lightroom_connected"]:
                return "Lightroom: Connected"
            else:
                return "Lightroom: Disconnected"

    menu = pystray.Menu(
        pystray.MenuItem("Open Dashboard", on_open_dashboard, default=True),
        pystray.MenuItem(lambda text: get_status_text(), lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", on_exit),
    )

    icon = pystray.Icon(
        "lightroom-mcp-broker",
        create_icon_image((74, 222, 128)),  # Green
        "Lightroom MCP Broker",
        menu
    )

    def update_icon_color():
        """Update icon color based on connection status."""
        while True:
            time.sleep(2)
            update_lr_connection_status()
            with stats_lock:
                connected = broker_stats["lightroom_connected"]

            if connected:
                icon.icon = create_icon_image((74, 222, 128))  # Green
            else:
                icon.icon = create_icon_image((250, 204, 21))  # Yellow

    # Start color update thread
    threading.Thread(target=update_icon_color, daemon=True).start()

    return icon


# ============================================================================
# Main Entry Point
# ============================================================================

def is_port_in_use(port: int, host: str = '127.0.0.1') -> bool:
    """Check if a port is already in use."""
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        test_socket.bind((host, port))
        test_socket.close()
        return False
    except OSError:
        return True


def shutdown_broker():
    """Shutdown the broker gracefully."""
    broker_log("INFO", "Broker shutdown requested")
    os._exit(0)


def run_broker():
    """Run the broker server."""
    # Check if broker is already running
    if is_port_in_use(BROKER_PORT, BROKER_HOST):
        print(f"ERROR: Broker already running on port {BROKER_PORT}")
        print(f"       Another instance is already active.")
        print(f"       Use the system tray icon or dashboard to exit the existing instance.")
        sys.exit(1)

    broker_stats["started_at"] = datetime.now(timezone.utc)

    # Load history from previous session
    load_history()

    broker_log("INFO", f"Starting Lightroom MCP Broker")
    broker_log("INFO", f"  HTTP: http://{BROKER_HOST}:{BROKER_PORT}")
    broker_log("INFO", f"  Socket fallback: {BROKER_HOST}:{SOCKET_PORT}")

    # Start tray icon in separate thread
    tray_icon = create_tray_icon()
    if tray_icon:
        tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
        tray_thread.start()
        broker_log("INFO", "System tray icon started")

    # Start socket server in separate thread
    socket_thread = threading.Thread(target=run_socket_server, daemon=True)
    socket_thread.start()

    # Run Flask server (main thread)
    try:
        app.run(host=BROKER_HOST, port=BROKER_PORT, threaded=True, debug=False)
    except KeyboardInterrupt:
        broker_log("INFO", "Broker shutting down")
    except Exception as e:
        broker_log("ERROR", f"Broker error: {e}")
        raise


if __name__ == '__main__':
    run_broker()
