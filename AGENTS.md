# AGENTS.md — lightroom-mcp

Lightroom **Desktop (cloud)** domain MCP server. C#, .NET 10, ModelContextProtocol SDK, stdio.

## Commands

```
dotnet build LightroomMcp.sln
dotnet test LightroomMcp.sln                                   # fake controller + fixtures; no Lightroom needed
dotnet run --project src/LightroomMcp -- scenario list
dotnet run --project src/LightroomMcp -- scenario run <name> --dry-run
```

Builds need `..\win-gui-mcp` checked out beside this repo, because Core is a ProjectReference.

## Rules

- **Specs first.** Tool names and arguments come from [docs/tools.md](docs/tools.md), errors from [docs/errors.md](docs/errors.md). Update them before the code.
- **Prefixes.** Tools are `lr_*` and scenario steps are `lr.*`. Never reuse win-gui-mcp tool names ([LIGHTROOM_BOUNDARIES_CONSTITUTION](../win-gui-mcp/docs/cross-project/LIGHTROOM_BOUNDARIES_CONSTITUTION.md)).
- **Core.** Consume `WinGuiMcp.Core` by reference; never copy its source here.
- **On-screen is not saved.** Never report an edit as applied until `lr_verify_saved` passes. API read-back only proves the live value.
- **Writes** go through `WriteGuard` (`confirmed`, `expectedPhoto`, TourBox check, read-back block). Do not add a write path around it.
- **Typing.** GUI fallback typing must carry `guard: { process: lightroom.exe, class: NonActivateWindow }`. A missed field turns digits into rating shortcuts (0–5) and colour-label shortcuts (6–9).
- **Catalog.** Read it only from a temp copy (`CatalogReader`); never open the live `Managed Catalog.mcat`.
- **Secrets.** The client GUID in `%LOCALAPPDATA%\LightroomMcp\client.json` is a credential. Never print it, return it, or commit it.
- **Live checks** go on a duplicate photo; log the results in [docs/LIVE_CHECKLIST.md](docs/LIVE_CHECKLIST.md).

## Layout

| Path | What |
|---|---|
| `src/LightroomMcp/Controller/` | `ConnectionFile`, `ControllerClient` (WebSocket), `LrSession` (register and reconnect), `ParamCatalog` (ranges, rounding) |
| `src/LightroomMcp/Saved/` | `XmpCrsParser`, `SettingsFolder`, `CatalogReader` |
| `src/LightroomMcp/Safety/WriteGuard.cs` | Write contract |
| `src/LightroomMcp/Tools/` | `LrToolService` (logic), `LrTools` / `LrScenarioTools` (MCP surface) |
| `src/LightroomMcp/Scenarios/LrStepProvider.cs` | `lr.*` steps |
| `scenarios/` | Bundled scenarios |
| `tests/LightroomMcp.Tests/` | `FakeLightroomServer` (Kestrel WebSocket), XMP fixture, SQLite catalog fakes |

## Provenance

- The XMP read-back logic was ported from `win-gui-mcp/scripts/apps/lightroom-desktop/lr_settings_readback.py`, written by the image-scoring-skills session on 2026-11-07. Its fixture is `tests/LightroomMcp.Tests/Fixtures/settings-two-masks.xmp`.
- The GUI traps are documented in `image-scoring-skills/docs/lightroom-desktop-gui-automation.md`.
