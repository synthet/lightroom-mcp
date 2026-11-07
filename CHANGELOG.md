# Changelog

## [Unreleased]

### Added
- `lr_save` (Grid-trip save that only reports success when a new settings file appears), `lr_render_preview`, and `lr_get_photo_state`.
- Current photo is read from the Lightroom window title, since the controller API has no getter for it (confirmed against LrControllerAPI 9.5.1 and live).
- Unit-mismatch guard: values far outside the controller range (for example `Temperature` 5350 against 0..100) are refused instead of clamped.
- Lightroom Desktop MCP server over the Lightroom Controller API, with stored-GUID registration and reconnect.
- Tools: `lr_get_status`, `lr_connect`, `lr_list_parameters`, `lr_get_values`, `lr_set_values` (clamp and read-back), `lr_select_mask`, `lr_read_saved_settings`, `lr_verify_saved` (XMP plus catalog proof), `lr_call`, `lr_capture`.
- Scenario runner tools `lr_run_scenario`, `lr_resume_scenario`, `lr_validate_scenario`, `lr_list_scenarios` and the `scenario` CLI, on WinGuiMcp.Core with `lr.*` steps.
- Bundled scenarios `apply-and-verify` (two approval checkpoints) and `saved-state-report`.
- Write guard: `confirmed`, `expectedPhoto`, refusal while TourBox Console runs, and a block after a write with an unknown outcome.
