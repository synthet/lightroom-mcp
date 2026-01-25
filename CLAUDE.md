# Claude AI Guide for Lightroom MCP

This document provides context and guidelines for Claude AI when working with the Lightroom MCP project.

## Project Overview

**Lightroom MCP** is a bridge between Adobe Lightroom Classic and AI agents (like Claude) via the Model Context Protocol (MCP). It enables automated photo management, metadata editing, and catalog operations.

### Architecture

```
┌─────────────────┐     MCP      ┌──────────────┐  TCP :54321  ┌─────────────────────┐
│ Cursor / Agent  │ ◄──────────► │ MCP Server   │ ◄──────────► │ Lightroom + Plugin  │
└─────────────────┘              └──────────────┘              └─────────────────────┘
```

- **Lightroom Plugin** (`lightroom-plugin.lrplugin/`): Lua plugin running inside Lightroom Classic, listening on `localhost:54321` (JSON-RPC 2.0)
- **MCP Server** (`mcp-server/`): Python FastMCP server that exposes Lightroom functionality as MCP tools

## Key Files and Their Purposes

### Plugin Files (Lua)
- `Info.lua` - Plugin metadata and entry point
- `Init.lua` - Plugin initialization, starts TCP server
- `Shutdown.lua` - Cleanup on plugin shutdown
- `Server.lua` - TCP server implementation (port 54321)
- `CommandHandlers.lua` - Handles JSON-RPC commands from MCP server
- `JSON.lua` - JSON encoding/decoding utilities

### MCP Server Files (Python)
- `server.py` - FastMCP server entry point, defines MCP tools
- `lrc_client.py` - Client that communicates with Lightroom plugin over TCP
- `test_connection.py` - Utility for testing plugin connection
- `requirements.txt` - Python dependencies

### Documentation
- `README.md` - Setup, usage, troubleshooting
- `agents.md` - Detailed MCP tool documentation and agent workflows
- `.cursorrules` - Cursor project rules and conventions
- `CHANGELOG.md` - Version history
- `CONTRIBUTING.md` - Contribution guidelines

## Available MCP Tools

When working as an MCP agent, Claude has access to these tools:

1. **`get_studio_info()`** - Get catalog information (name, path, plugin version)
2. **`get_selection()`** - Get details about currently selected photos
3. **`set_rating(rating: int)`** - Set star rating (0-5) for selected photos
4. **`set_label(label: str)`** - Set color label (Red/Yellow/Green/Blue/Purple/None)
5. **`set_caption(caption: str)`** - Set caption text for selected photos

See `agents.md` for detailed tool semantics, parameters, return values, and example workflows.

## Development Guidelines

### When Editing Plugin Code (Lua)

- **Language**: Lua 5.1-compatible, uses Lightroom SDK
- **Key SDK Modules**: `LrTasks`, `LrSocket`, `LrHttp`, `LrApplication`, `LrCatalog`, `LrLogger`
- **Restart Required**: Changes to `Info.lua`, `Init.lua`, or `Shutdown.lua` require Lightroom restart
- **Testing**: Plugin runs inside Lightroom; use `test_connection.py` to verify connectivity
- **JSON**: Use `JSON.lua` for encoding/decoding; avoid external dependencies

### When Editing MCP Server Code (Python)

- **Language**: Python 3.10+
- **Framework**: FastMCP for tool definitions
- **Communication**: `lrc_client.py` handles TCP communication with plugin
- **Error Handling**: Tools return `"Error: ..."` prefix for errors
- **Restart Required**: Restart MCP server (or Cursor's MCP client) after changes
- **Dependencies**: Manage via `requirements.txt`

### Code Style

- Follow existing patterns in the codebase
- Maintain consistency with current error handling approach
- Update `agents.md` when adding/removing tools or changing semantics
- Add appropriate logging for debugging

## Common Tasks Claude Might Be Asked To Do

### 1. Add New MCP Tools
- Add tool definition in `server.py` (FastMCP decorator)
- Implement handler in `lrc_client.py` if needed
- Add corresponding command handler in `CommandHandlers.lua`
- Update `agents.md` with tool documentation
- Test end-to-end workflow

### 2. Fix Bugs
- Check `lrc_client.py` for connection/communication issues
- Verify plugin is running (port 54321)
- Check error messages returned from tools
- Review JSON-RPC 2.0 protocol compliance
- Test with `test_connection.py`

### 3. Enhance Existing Features
- Review current implementation in both plugin and server
- Maintain backward compatibility
- Update documentation as needed
- Consider error cases and edge conditions

### 4. Improve Error Handling
- Add validation in both Lua and Python layers
- Provide clear error messages to users
- Handle connection failures gracefully
- Log errors appropriately

### 5. Add Documentation
- Update relevant sections in `README.md`, `agents.md`, or this file
- Add code comments for complex logic
- Document new workflows or use cases

## Testing and Debugging

### Testing Plugin Connection
```bash
cd mcp-server
python test_connection.py
```

### Verifying MCP Server
- Ensure Python venv is activated
- Check that `requirements.txt` dependencies are installed
- Verify `cwd` path in Cursor MCP config matches project location
- Check Cursor MCP logs for connection errors

### Debugging Tips

1. **Plugin not responding**: 
   - Verify Lightroom is running
   - Check plugin is enabled in Plug-in Manager
   - Ensure port 54321 is not in use by another process
   - Restart Lightroom

2. **MCP server fails to start**:
   - Check Python version (3.10+)
   - Verify venv activation
   - Ensure dependencies installed: `pip install -r requirements.txt`
   - Check `cwd` path in MCP config

3. **Tools fail**:
   - Ensure photos are selected in Lightroom
   - Call `get_selection()` first to verify selection
   - Check error messages returned from tools
   - Verify catalog has write access

## Workflow Best Practices

1. **Before making changes**: Read relevant files, understand current implementation
2. **When adding features**: Update both plugin and server code, maintain protocol compatibility
3. **After changes**: Update documentation, test end-to-end, verify error handling
4. **For user requests**: Check `agents.md` for tool capabilities, suggest appropriate workflows

## Protocol Details

- **Transport**: TCP socket on `localhost:54321`
- **Protocol**: JSON-RPC 2.0
- **Encoding**: UTF-8 JSON
- **Threading**: Synchronous operations (wait for responses)
- **Selection-based**: Metadata operations work on currently selected photos

## References

- **Lightroom SDK**: Adobe Lightroom SDK documentation
- **FastMCP**: https://github.com/jlowin/fastmcp
- **MCP Protocol**: https://modelcontextprotocol.io/
- **JSON-RPC 2.0**: https://www.jsonrpc.org/specification

## Notes for Claude

- Always verify connection with `get_studio_info()` before operations
- Check selection with `get_selection()` before modifying photos
- Handle errors gracefully and provide user-friendly feedback
- Remember that operations affect ALL selected photos (batch operations)
- When in doubt, refer to `agents.md` for tool semantics and examples
