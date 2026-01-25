# Claude AI Configuration

This folder contains Claude AI-specific configuration files for the Lightroom MCP project.

## Files

### `mcp.json`
MCP (Model Context Protocol) server configuration for Claude. This configures Claude to connect to the Lightroom MCP server when working in Claude Code or other Claude environments that support MCP.

### `config.json`
Claude agent configuration with:
- Context files to reference (CLAUDE.md, agents.md, etc.)
- Agent preferences and default behaviors
- MCP tool descriptions and use cases
- Predefined workflow templates

## Usage

When Claude AI is working on this project, it should:
1. Reference the context files listed in `config.json`
2. Use the MCP tools defined in `mcp.json`
3. Follow the preferences and workflows specified
4. Respect the safety settings and confirmations

## MCP Setup

For Claude Code or other Claude environments:
1. Ensure the Python virtual environment is set up in `mcp-server/.venv`
2. Install dependencies: `pip install -r requirements.txt`
3. Configure MCP server using the settings in `mcp.json`
4. Verify connection by using MCP tools

## Best Practices

Based on the configuration, Claude should:
- Always verify connection with `get_studio_info()` before operations
- Check selection with `get_selection()` before modifying photos
- Handle errors gracefully and provide user-friendly feedback
- Remember that operations affect ALL selected photos (batch operations)
- Refer to `agents.md` for detailed tool semantics and examples
