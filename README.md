# Lightroom MCP

Bridge between [Adobe Lightroom Classic](https://www.adobe.com/products/photoshop-lightroom-classic.html) and AI agents via the [Model Context Protocol](https://modelcontextprotocol.io/) (MCP). Enables automated photo management, metadata editing, and catalog operations from Cursor and other MCP-capable clients.

## Architecture

- **Lightroom Plugin** (`lightroom-plugin.lrplugin/`) — Lua plugin running inside Lightroom Classic. Listens on `localhost:54321` and handles commands over a TCP socket (JSON-RPC 2.0).
- **MCP Server** (`mcp-server/`) — Python [FastMCP](https://github.com/jlowin/fastmcp) server that exposes Lightroom as MCP tools and connects to the plugin.

```
┌─────────────────┐     MCP      ┌──────────────┐  TCP :54321  ┌─────────────────────┐
│ Cursor / Agent  │ ◄──────────► │ MCP Server   │ ◄──────────► │ Lightroom + Plugin  │
└─────────────────┘              └──────────────┘              └─────────────────────┘
```

## Prerequisites

- **Adobe Lightroom Classic** (LrSdk 10.0+)
- **Python 3.10+** (for the MCP server)
- **Lightroom** and **MCP server** both running, with the plugin loaded

## Setup

### 1. Install the Lightroom plugin

1. Copy `lightroom-plugin.lrplugin` into your Lightroom plugins folder:
   - **macOS:** `~/Library/Application Support/Adobe/Lightroom/Modules/`
   - **Windows:** `%APPDATA%\Adobe\Lightroom\Modules\`
2. In Lightroom: **File → Plug-in Manager → Add** and select the plugin folder, or place it in **Modules** and restart Lightroom.
3. Ensure the plugin is **Enabled**. It starts a TCP server on port **54321** when Lightroom launches.

### 2. MCP server (Python)

```bash
cd mcp-server
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
```

### 3. Configure Cursor to use the MCP server

Add the Lightroom MCP server to your Cursor MCP config (e.g. **Settings → MCP** or project `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "lightroom": {
      "command": "d:/Projects/lightroom-mcp/mcp-server/.venv/Scripts/python.exe",
      "args": ["d:/Projects/lightroom-mcp/mcp-server/server.py"]
    }
  }
}
```

Use **absolute paths** to the venv Python and `server.py` (Cursor may ignore `cwd`). Adjust if you cloned the repo elsewhere.

## Usage

With the plugin loaded in Lightroom and the MCP server configured in Cursor:

1. Open a catalog in Lightroom Classic.
2. Select one or more photos.
3. In Cursor, use natural language or MCP tools to:
   - **Get catalog info** — `get_studio_info`
   - **Inspect selection** — `get_selection` (filenames, paths, rating, label, title, caption, pickFlag, keywords)
   - **Set rating** — `set_rating(0–5)`
   - **Set color label** — `set_label("Red"|"Yellow"|"Green"|"Blue"|"Purple"|"None")`
   - **Set caption** — `set_caption("your text")`
   - **Set title** — `set_title("your title")`
   - **Set pick flag** — `set_pick_flag("pick"|"reject"|"none")`
   - **Manage keywords** — `add_keywords(["keyword1", "Location > Europe"]), remove_keywords(), get_keywords()`
   - **Collections** — `list_collections(), add_to_collection("collection name")`
   - **Search photos** — `search_photos("query")`
   - **Metadata** — `set_metadata(field, value), get_metadata([fields])`

See **[agents.md](./agents.md)** for detailed tool semantics, example workflows, and best practices for AI agents.

## Project layout

```
lightroom-mcp/
├── README.md           # This file
├── agents.md           # MCP tools & agent workflows
├── SDK_INTEGRATION.md  # Lightroom SDK integration details
├── CHANGELOG.md        # Version history
├── CONTRIBUTING.md     # Contribution guidelines
├── .cursorrules        # Cursor project rules
├── lightroom_SDK/      # Adobe Lightroom SDK 15.0 (reference)
├── lightroom-plugin.lrplugin/   # Lua plugin for Lightroom
│   ├── Info.lua
│   ├── Init.lua
│   ├── Shutdown.lua
│   ├── Server.lua
│   ├── CommandHandlers.lua
│   └── JSON.lua
└── mcp-server/         # Python MCP server
    ├── server.py
    ├── lrc_client.py
    ├── test_connection.py
    └── requirements.txt
```

## SDK Integration

The plugin is built against **Lightroom SDK 15.0** and follows SDK best practices. 

**Download the SDK**: [Adobe Lightroom Classic SDK](https://developer.adobe.com/console/4061681/servicesandapis)

See **[SDK_INTEGRATION.md](./SDK_INTEGRATION.md)** for:
- SDK version requirements
- Implementation patterns used
- Reference examples
- Testing and debugging

## Troubleshooting

- **"No response from Lightroom"** — Lightroom must be running, plugin enabled, and nothing else using port **54321**. Restart Lightroom and try again.
- **MCP server fails to start** — Check Python version, venv, and `pip install -r requirements.txt`. Run from `mcp-server` or set `cwd` correctly in MCP config.
- **"can't open file 'server.py'" / "No such file or directory"** — Cursor may run the MCP server from your home directory and ignore `cwd`. Use **absolute paths** for both `command` (venv Python) and `args` (path to `server.py`), e.g. `"command": "d:/Projects/lightroom-mcp/mcp-server/.venv/Scripts/python.exe"` and `"args": ["d:/Projects/lightroom-mcp/mcp-server/server.py"]`. Adjust paths if you cloned the repo elsewhere.
- **Tools fail** — Ensure photos are selected when using `set_rating`, `set_label`, or `set_caption`. Call `get_selection` first to verify.

## License

See repository license file.
