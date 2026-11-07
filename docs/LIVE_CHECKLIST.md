# Live checklist (needs Lightroom Desktop and you)

Results so far, 2026-11-07, Lightroom 9.5.1: checks 0–3 done read-only (marked ✅). Checks 4 onwards need writes or a view change, so they wait for your go-ahead. Use a **duplicate photo**, never DSC_8750. Record each result in this file with the date and Lightroom version.

| # | Check | How | Pass when |
|---|---|---|---|
| 0 ✅ | Export the API docs | Preferences > Interface, hold the key shown; save `LrControllerAPI_<ver>.html` to `docs/vendor/` | The file exists; update `controller-api.md` from it |
| 1 ✅ | Registration | `lr_connect`, then click Allow; reconnect | The second connect shows no dialog; `%LOCALAPPDATA%\LightroomMcp\client.json` exists |
| 2 ✅ | Photo identity | `lr_get_status` with a photo open | No API getter answers; the window title `Lightroom - <file>` does (`currentPhotoSource: windowTitle`) |
| 3 ✅ | Read | `lr_get_values ["Exposure2012","Shadows2012"]` | Values match the panel |
| 4 | Write and read-back | `lr_set_values {"Exposure2012":0.1}` with `expectedPhoto` and `confirmed` | `readbackOk`; the panel moves |
| 5 | **Persistence** | `lr.now`, a write, then `lr_save` (Grid trip); if it fails, leave the photo by hand | `lr_save` returns a file and `lr_verify_saved` passes. Also try the write alone, wait 60 s, and verify: does Lightroom save without the trip? |
| 6 | Masks | Duplicate with 2 masks: `lr_select_mask "1"`, set `LocalShadows2012`, select `"2"`, read | Values land on the right mask; `lr_verify_saved` with `"Mask 1.Shadows2012"` passes |
| 7 (partly ✅) | TourBox coexistence | Run 3 with TourBox Console running and `allowExternalControllers: true`, for 10 minutes | 2026-11-07: connecting and reading worked while TourBox Console was running, so two clients can be connected at once. Still open: does a long session disconnect either client, and do foreign writes show up as `Pushed` events? |
| 8 | Scenario end to end | `LightroomMcp scenario run apply-and-verify --allow-writes --param ...` | Pauses twice, then `passed`; the receipt and XMP agree |
| 9 | Undo history | Several `lr_set_values` calls | Count the history steps; decide whether to use `setMultipleAdjustmentThreshold` / tracking |
