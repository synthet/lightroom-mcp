# Lightroom MCP Plugin

This is a Lua plugin for Adobe Lightroom Classic that enables control via the Model Context Protocol (MCP).

## Overview

The plugin connects to the **MCP Broker** (running on localhost) and executes commands issued by the AI agent.

- **Path**: `lightroom-plugin.lrplugin`
- **SDK Version**: Built for LrClassic 15.0+ (Min 10.0)

## Structure

- **`Init.lua`**: Plugin entry point. Starts the async server task.
- **`Server.lua`**: Manages the socket connection to the Broker (default port 8086).
- **`CommandHandlers.lua`**: Implementation of specific commands (e.g., `set_rating`, `get_selection`).
- **`Info.lua`**: Plugin manifest and version info.

## Installation

1. Copy this entire folder (`lightroom-plugin.lrplugin`) to your Lightroom Modules directory.
   - **Windows**: `%APPDATA%\Adobe\Lightroom\Modules\`
   - **Mac**: `~/Library/Application Support/Adobe/Lightroom/Modules/`
2. Restart Lightroom Classic.
3. Go to **File > Plug-in Manager** and verify "MCP Bridge" is **Enabled**.

## Troubleshooting

- **Plugin not loading**: Check `Info.lua` syntax or verify path.
- **Connection failed**: Ensure the Python Broker is running.
- **Logs**: Check `plugin_debug.log` in the project root (or configured path) for Lua logs.

See `../SDK_INTEGRATION.md` for deep technical details on the Lua implementation.
