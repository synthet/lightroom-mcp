# lightroom-mcp errors

lightroom-mcp returns the WinGuiMcp error envelope ([win-gui-mcp/docs/errors.md](../../win-gui-mcp/docs/errors.md)) and uses its codes (`InvalidArgument`, `Timeout`, `WindowGone`, `CaptureFailed`, `InternalError`, plus the scenario codes), with these additions:

| Code | When | Recovery |
|---|---|---|
| `ControllerUnavailable` | No `connections.json`, nothing listening on the port, or the connection dropped | Start Lightroom Desktop and enable Preferences > Interface > Enable external controllers, then restart it |
| `ApprovalPending` | `register` got no answer: Lightroom is showing its Allow dialog | Click Allow in Lightroom, then call `lr_connect` again |
| `ApprovalDenied` | Lightroom refused the registration | Re-run `lr_connect` and allow it |
| `ControllerCallFailed` | Lightroom answered `success: false` | Check the message name and params (`lr_call`); is a photo open in Edit? |
| `UnknownParameter` | `getRange` failed for an id | Use Camera Raw ids (`Exposure2012`, `LocalShadows2012`); see `lr_list_parameters` |
| `ConfirmationRequired` | A write without `confirmed: true` | Preview with `dryRun`, get approval, then resend |
| `PhotoMismatch` | `expectedPhoto` missing or different from the current photo, or Lightroom didn't report the photo | Check `lr_get_status`. Use `skipPhotoCheck` only after confirming the photo on screen |
| `ExternalControllerActive` | TourBox Console is running | Close it, or pass `allowExternalControllers: true` and leave the device alone |
| `ReadbackRequired` | An earlier write's outcome is unknown | Call `lr_get_values` for the affected ids |
| `ReadbackMismatch` | A value didn't read back as written | Check the selected mask and other controllers; read the values and retry |
| `SettingsNotFound` | No settings folder or file | Has Lightroom saved anything yet? Leave the photo to make it save |
| `SaveUnverified` | No file saved since `sinceUtc`, a value differs, or the catalog doesn't reference the file | Make Lightroom save (leave the photo), then verify again |
