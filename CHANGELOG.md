# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.2] - 2026-02-18

### Added
- New memory management workflow in `.agent/workflows/memory.md`.

## [0.3.1] - 2026-02-18

### Changed
- Updated `test_preview_tool.py` to return structured response with `savedPaths`.

## [0.3.0] - 2026-02-18

### Added
- New release automation workflow in `.agent/workflows/release.md`.
- Documentation for the release workflow in `agents.md`.

## [0.2.0] - 2026-02-18

### Added
- New broker management and diagnostic scripts: `run_broker.bat`, `start_broker.py`, `diag_port.py`, `debug_server_start.py`, `test_broker_start.py`.
- New debugging scripts: `broker.py`, `check_settings.py`, `debug_mcp_handshake.py`, `get_preview.py`.
- Automated test scripts: `run_get_studio_info.py`, `test_fallback_manual.py`.

### Changed
- Updated default broker ports to 8085 (HTTP) and 8086 (Socket) to avoid conflicts.
- Increased request and LR connection timeouts for better stability.
- Improved error handling in MCP server connection.
- Refactored `mcp_bridge_port.txt` handling.

---


## [0.1.0] — YYYY-MM-DD

### Added

- First release: Lightroom Classic plugin and MCP server for Cursor / MCP clients.
