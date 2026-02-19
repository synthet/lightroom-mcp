import sys
import logging
import traceback

# Setup logging to file
logging.basicConfig(filename='mcp_debug.log', level=logging.DEBUG)
logger = logging.getLogger(__name__)

try:
    logger.info("Starting MCP server test...")
    from mcp.server.fastmcp import FastMCP
    from lrc_client import LrCClient

    logger.info("Imports successful")

    mcp = FastMCP("Lightroom MCP")
    lrc = LrCClient()
    logger.info(f"LrCClient initialized with broker URL: {lrc.broker_url}")

    # We can't easily run mcp.run() here as it blocks on stdio,
    # but we can verify initialization works.
    print("MCP Server initialization successful")
    logger.info("MCP Server initialization successful")

except Exception as e:
    logger.error(f"Failed to start: {e}")
    logger.error(traceback.format_exc())
    print(f"FAILED: {e}")
