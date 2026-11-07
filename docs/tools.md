# lightroom-mcp tools

Canonical tool names and arguments. Change this file before changing `src/LightroomMcp/Tools/*.cs`. Errors: [errors.md](errors.md). Results use the WinGuiMcp envelope: `{ ok: true, ... }` on success, `{ ok: false, code, message, details? }` with `isError` on failure.

**Write contract.** Every write needs `confirmed: true` and `expectedPhoto` (a file name such as `DSC_8750`, matched on the base name), unless `skipPhotoCheck: true` is passed after confirming the photo on screen. The current photo comes from the window title `Lightroom - <file>`, since the API has no getter for it. Values far outside the controller range are refused as unit errors (`Temperature` is 0..100, not Kelvin); small overshoots are clamped and flagged. Writes are refused while TourBox Console runs, unless `allowExternalControllers: true`. A write whose outcome is unknown (timeout or lost connection) blocks further writes until `lr_get_values` succeeds. API writes are live but **not saved**; prove persistence with `lr_verify_saved`.

| Tool | Input | Notes |
|---|---|---|
| `lr_get_status` | `{}` | Process and windows, controller port, registration, Lightroom version, `currentPhoto` and its source getter, `externalControllers`, `needsReadback`, settings folder and newest save time |
| `lr_connect` | `{}` | Registers, reusing the stored GUID. `ApprovalPending` until you click Allow in Lightroom |
| `lr_list_parameters` | `{ panel? }` | `getParameterNames` / `getPanelNames` |
| `lr_get_values` | `{ parameters: [ids] }` | Value (rounded), min, max and step per id. `Local*` ids read the selected mask |
| `lr_set_values` | `{ values: {id: number}, expectedPhoto, confirmed, delta?, dryRun?, skipPhotoCheck?, allowExternalControllers? }` | Clamps to `getRange`, `setValue`, then reads back. `ReadbackMismatch` if a value doesn't stick. `dryRun` returns the plan (before, target, clamped) and writes nothing |
| `lr_select_mask` | `{ selector, component? }` | `selectMaskGroup` / `selectMaskComponent`. Reports `selectedName` when Lightroom provides it; otherwise verify on screen |
| `lr_read_saved_settings` | `{ file?, requireMasks?, sinceUtc? }` | Newest saved XMP: global values and every mask in slider units |
| `lr_verify_saved` | `{ expect: {"global.Exposure2012": 0.2, "Mask 1.Shadows2012": 30}, sinceUtc, photo?, tolerance? }` | Passes only if a file saved since `sinceUtc` holds every value and a current catalog revision references it; `SaveUnverified` otherwise |
| `lr_save` | `{ returnView? = "loupe", timeoutMs? = 10000 }` | `showView("square_grid")`, waits for a new settings XMP, then `showView(returnView)` (`null` stays in Grid). `SaveUnverified` if no file appears, including when nothing changed |
| `lr_render_preview` | `{ copyTo? }` | `renderImage("filepath")`: a JPEG of the active image with current settings |
| `lr_get_photo_state` | `{}` | Rating, colour label, flag, selected tool and selected mask name. Compare before and after GUI steps to catch stray single-key shortcuts |
| `lr_call` | `{ message, args?, objectHandle?, expectedPhoto?, confirmed?, ... }` | One raw controller message, for discovery. Known read-only messages run freely; others follow the write contract. `register` and `close` are refused |
| `lr_capture` | `{ outputPath, handle?, x?, y?, width?, height?, scale? }` | PNG of the Lightroom window or a region. Returns the path, size and SHA-256; never base64 |
| `lr_run_scenario` | `{ scenario, params?, dryRun?, allowWrites? }` | WinGuiMcp.Core engine with `lr.*` steps ([win-gui-mcp/docs/scenarios.md](../../win-gui-mcp/docs/scenarios.md)). Roots: `./scenarios`, the repo's `scenarios/`, `LIGHTROOM_MCP_SCENARIOS` |
| `lr_resume_scenario` | `{ resumeToken, approve?, secretParams? }` | Continue or stop at a checkpoint |
| `lr_validate_scenario` | `{ scenario, params? }` | No Lightroom contact |
| `lr_list_scenarios` | `{}` | Bundled and local scenarios |

## Scenario steps (`lr.*`)

`lr.get_status`, `lr.connect`, `lr.list_parameters`, `lr.get_values`, `lr.read_saved_settings`, `lr.verify_saved`, `lr.capture`, `lr.render_preview`, `lr.get_photo_state` and `lr.now` (returns `{utc}`, for `sinceUtc`) are read-only. `lr.set_values`, `lr.select_mask`, `lr.save` and `lr.call` are writes: they need `allowWrites` on the run, plus the write contract above in their arguments. In a dry run no `lr.*` step contacts Lightroom. win-gui tool steps (`click`, `press_key`, ...) are available too, behind `target` and `guard`.

CLI: `LightroomMcp scenario run|resume|validate|list ...`, with exit codes 0 passed, 1 failed, 2 blocked, 3 paused and 4 invalid.

## Not yet implemented

Planned in the design but not built, and not exposed:

- `lr_apply_settings`: a settings document → stacked totals → apply → save → verify (`scenarios/apply-and-verify` covers the flow for now).
- `lr_navigate`, `lr_apply_preset`, `lr_undo`, `lr_create_mask`, `lr_mask_op` (`lr_call` reaches them meanwhile).
