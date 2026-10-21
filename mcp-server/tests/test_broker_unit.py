import unittest
import json
import threading
import time
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path to import broker
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import broker

class TestBrokerUnit(unittest.TestCase):

    def setUp(self):
        # Reset broker state before each test
        broker.pending_requests.clear()
        broker.request_queue.clear()
        broker.request_queue_event.clear()
        broker.broker_stats["requests_total"] = 0
        broker.broker_stats["requests_success"] = 0
        broker.broker_stats["requests_failed"] = 0
        broker.broker_stats["requests_timeout"] = 0

    def test_update_lr_connection_status(self):
        # Test connection status update logic
        with patch('broker.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.timezone = timezone

            # Case 1: No last poll (initially disconnected)
            broker.broker_stats["lightroom_last_poll"] = None
            broker.broker_stats["lightroom_connected"] = False
            broker.update_lr_connection_status()
            self.assertFalse(broker.broker_stats["lightroom_connected"])

            # Case 2: Recent poll (should be connected)
            broker.broker_stats["lightroom_last_poll"] = mock_datetime.now(timezone.utc)
            broker.update_lr_connection_status()
            self.assertTrue(broker.broker_stats["lightroom_connected"])

            # Case 3: Old poll (should be disconnected)
            from datetime import timedelta
            broker.broker_stats["lightroom_last_poll"] = mock_datetime.now(timezone.utc) - timedelta(seconds=broker.LR_CONNECTION_TIMEOUT + 1)
            broker.update_lr_connection_status()
            self.assertFalse(broker.broker_stats["lightroom_connected"])

    @patch('broker.broadcast_ws')
    def test_broker_log(self, mock_broadcast):
        # Test logging functionality
        broker.broker_log("INFO", "Test log message")

        # Verify log storage
        with broker.stats_lock:
            found_log = False
            for log in reversed(broker.broker_stats["recent_logs"]):
                if log["message"] == "Test log message":
                    self.assertEqual(log["level"], "INFO")
                    found_log = True
                    break
            self.assertTrue(found_log, "Test log message not found in recent_logs")

        # Verify broadcast (might be called in a thread, so we wait a bit or just check call count if synchronous enough)
        # Since it's threaded, we might not catch it immediately, but let's assume for unit test we can check logic
        # For strict unit testing with threads, we'd mock threading.Thread too.
        pass

    def test_request_queueing(self):
        # Test that requests are correctly added to the queue
        request_data = {"method": "test_method", "id": 1, "params": {}}

        # Simulate request handling part (adding to queue)
        request_uuid = "test-uuid"

        with broker.request_queue_lock:
            broker.request_queue.append(request_data)
            broker.request_queue_event.set()

        self.assertEqual(len(broker.request_queue), 1)
        self.assertTrue(broker.request_queue_event.is_set())

        # Verify pop works
        popped = broker.request_queue.popleft()
        self.assertEqual(popped, request_data)

    def test_response_matching(self):
        # Test matching a response to a pending request
        request_uuid = "test-uuid"
        event = threading.Event()

        # Setup pending request
        with broker.pending_requests_lock:
            broker.pending_requests[request_uuid] = {
                "request": {},
                "event": event,
                "response": None,
                "started_at": datetime.now(timezone.utc),
            }

        # Simulate receiving response
        response_data = {"_broker_uuid": request_uuid, "result": "success"}

        # Logic from handle_response
        with broker.pending_requests_lock:
            if request_uuid in broker.pending_requests:
                broker.pending_requests[request_uuid]["response"] = response_data
                broker.pending_requests[request_uuid]["event"].set()

        self.assertTrue(event.is_set())
        self.assertEqual(broker.pending_requests[request_uuid]["response"], response_data)

    def test_auto_edit_missing_image(self):
        client = broker.app.test_client()
        res = client.post('/auto_edit', json={})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertIn("error", data)

    def test_auto_edit_invalid_base64(self):
        client = broker.app.test_client()
        res = client.post('/auto_edit', json={"image": 12345})
        self.assertEqual(res.status_code, 400)

    @patch('broker.GeminiAPIProvider')
    def test_auto_edit_success(self, mock_provider_cls):
        import asyncio
        from unittest.mock import AsyncMock
        mock_provider_instance = MagicMock()
        mock_provider_cls.return_value = mock_provider_instance
        mock_settings = MagicMock()
        mock_settings.model_dump.return_value = {
            "exposure": 0.5,
            "contrast": 15,
            "highlights": -20,
            "shadows": 25
        }
        mock_provider_instance.process = AsyncMock(return_value=mock_settings)

        import base64
        test_img_b64 = base64.b64encode(b"fake-jpeg-data").decode('utf-8')

        client = broker.app.test_client()
        res = client.post('/auto_edit', json={
            "image": test_img_b64,
            "localId": "123",
            "intent": "clean_commercial"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("settings", {}).get("exposure"), 0.5)


from datetime import datetime, timezone

if __name__ == '__main__':
    unittest.main()
