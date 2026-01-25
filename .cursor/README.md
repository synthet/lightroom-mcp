# Cursor IDE Configuration

This folder contains Cursor-specific configuration files for the Lightroom MCP project.

## Files

### `mcp.json`
MCP (Model Context Protocol) server configuration for Cursor. This configures Cursor to connect to the Lightroom MCP server.

**Note:** This is a project-local configuration. Cursor may also use a global MCP config at:
- **Windows:** `%APPDATA%\Cursor\User\globalStorage\cursor.mcp\mcp.json`
- **macOS:** `~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp/mcp.json`

## Setup

1. Ensure the Python virtual environment is set up in `mcp-server/.venv`
2. Install dependencies: `pip install -r requirements.txt`
3. Cursor should automatically detect this MCP configuration
4. Verify connection by using MCP tools in Cursor

## Troubleshooting

- If MCP server doesn't start, check that Python venv is activated
- Verify `cwd` path matches your project location
- Check Cursor MCP logs for connection errors
- Ensure Lightroom is running with the plugin enabled
