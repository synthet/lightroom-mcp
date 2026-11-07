# lightroom-mcp

MCP server for **Adobe Lightroom Desktop (cloud)**, version 9.x. It is not for Lightroom Classic; for that, see `lightroom-classic-mcp`.

It drives develop sliders and masks through Adobe's built-in **Lightroom Controller API**, the WebSocket that TourBox uses. It proves edits were actually **saved** by reading Lightroom's settings XMP and catalog. It runs Playwright-style **scenarios** with approval checkpoints. UI the API can't reach falls back to the shared [`WinGuiMcp.Core`](../win-gui-mcp/src/WinGuiMcp.Core).

| Channel | Used for |
|---|---|
| Controller API (`ws://127.0.0.1:<port>`) | Read, write and clamp values; select masks; raw discovery calls |
| Saved settings XMP + catalog | `lr_verify_saved`: proof that an edit persisted |
| WinGuiMcp.Core | Window state, PNG captures, guarded GUI fallback steps |

## Setup

1. **Enable the API.** In Lightroom: Preferences > Interface > **Enable external controllers**, then restart Lightroom.
2. **Build** with .NET SDK 10 (pinned in `global.json`). It needs a sibling checkout at `..\win-gui-mcp` on branch `feat/core-and-scenarios` or later:
   ```
   dotnet build LightroomMcp.sln
   dotnet test LightroomMcp.sln
   ```
3. **Register** the MCP server: copy `.mcp.example.json` into your client config.
4. **Connect.** The first `lr_connect` shows an Allow dialog in Lightroom; click Allow.

## Use

- **Tools:** [docs/tools.md](docs/tools.md). **Errors:** [docs/errors.md](docs/errors.md). **Protocol:** [docs/controller-api.md](docs/controller-api.md).
- **Scenarios:** `scenarios/*.scenario.yaml`. Language reference: [win-gui-mcp/docs/scenarios.md](../win-gui-mcp/docs/scenarios.md).
  ```
  LightroomMcp scenario run saved-state-report
  LightroomMcp scenario run apply-and-verify --dry-run --param photo=DSC_8750 --param values='{"Exposure2012":0.2}' --param expect='{"global.Exposure2012":0.2}'
  ```
- **Still to do live:** [docs/LIVE_CHECKLIST.md](docs/LIVE_CHECKLIST.md). The save trigger, photo identity and mask selection names still need a live Lightroom.
