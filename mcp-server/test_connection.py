#!/usr/bin/env python3
"""
Test connection to Lightroom Classic MCP Bridge plugin via the HTTP broker.
"""

import sys
import logging
import unittest
from lrc_client import LrCClient, check_plugin_status, BROKER_URL

# Enable verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def show_status():
    """Show plugin connection status"""
    print("\n" + "="*60)
    print("MCP Bridge Plugin Status")
    print("="*60)

    status = check_plugin_status()

    print(f"\nBroker URL: {BROKER_URL}")
    print(f"  Running: {'Yes' if status['broker_running'] else 'No'}")
    print(f"  Lightroom connected: {'Yes' if status.get('lightroom_connected') else 'No'}")

    if status['broker_running']:
        print(f"  Requests handled: {status.get('requests_total', 0)}")
        print(f"  Avg latency: {status.get('avg_latency_ms', 0):.1f}ms")

    if not status['broker_running']:
        print("\n*** Broker not running ***")
        print("Start the broker with: python broker.py")
    elif not status.get('lightroom_connected'):
        print("\n*** Lightroom not connected ***")
        print("Possible issues:")
        print("  1. Lightroom is not running")
        print("  2. Plugin is not enabled in Plug-in Manager")
        print("  3. Check plugin_debug.log for errors")


class TestLrcConnection(unittest.TestCase):
    def test_connection_and_info(self):
        print("\n" + "="*60)
        print("Testing MCP Bridge Connection")
        print("="*60)

        print("\nStep 1: Checking broker status...")
        status = check_plugin_status()

        print(f"  Broker URL: {BROKER_URL}")
        print(f"  Broker running: {status['broker_running']}")
        print(f"  Lightroom connected: {status.get('lightroom_connected', False)}")

        if not status['broker_running']:
            self.skipTest("Broker not running - start with: python broker.py")
            return

        if not status.get('lightroom_connected'):
            self.skipTest("Lightroom not connected - ensure plugin is enabled")
            return

        print("\nStep 2: Creating client...")
        client = LrCClient()

        print("\nStep 3: Sending get_studio_info...")
        try:
            response = client.send_command("get_studio_info")
            print(f"  Response: {response}")

            self.assertIsNotNone(response, "Response should not be None")

            if "error" in response:
                print(f"\n*** ERROR: {response['error']} ***")
                self.fail(f"Server returned error: {response['error']}")

            if "result" in response:
                result = response["result"]
                print(f"\n*** SUCCESS ***")
                if isinstance(result, dict):
                    print(f"  Catalog: {result.get('catalogName', 'N/A')}")
                    print(f"  Path: {result.get('catalogPath', 'N/A')}")
                    print(f"  Plugin: {result.get('pluginVersion', 'N/A')}")

        except Exception as e:
            print(f"\n*** ERROR: {e} ***")
            raise


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--status':
        show_status()
    else:
        print("Usage:")
        print("  python test_connection.py          # Run connection test")
        print("  python test_connection.py --status # Show plugin status")
        print()
        unittest.main(argv=[''], exit=False, verbosity=2)
