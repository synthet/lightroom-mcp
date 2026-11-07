# Lightroom Controller API (Lightroom Desktop 9.x)

Adobe's live-control channel for **Lightroom Desktop (cloud)**. TourBox Console uses it to read and write sliders, and its HUD reads values through it. This is not Lightroom Classic's Lua SDK; that is `lightroom-classic-mcp`.

**Authority:** Adobe's exported `LrControllerAPI_9.5.1.html` (saved locally in [vendor/](vendor/README.md) on 2026-11-07; gitignored). Where this page and that file disagree, the file wins. Evidence labels:

- **[D]** documented in LrControllerAPI_9.5.1.html
- **[L]** observed live through lightroom-mcp on 2026-11-07 (Lightroom 9.5.1, DSC_8750 open)

- **[E]** text embedded in `lightroom.exe` 9.5.1
- **[T]** observed in TourBox's log (`%APPDATA%\TourBox Console\tourbox.log`)
- **[I]** inferred, unconfirmed

## Enabling it

- **Turn it on:** Preferences > Interface > **Enable external controllers**, then restart Lightroom. The pref key is `ExternalControllers_enabled` in `%APPDATA%\Adobe\Lightroom CC\Preferences\Lightroom CC Preferences.agprefs` [E].
- **Find the port:** it's written to `%LOCALAPPDATA%\Adobe\Lightroom CC\Connections\connections.json`, e.g. `{"port":7682}`. 7682 is the default; another port is used when it's taken [E][T].
- **Export the full docs:** Preferences > Interface shows "Developers: hold … to access API documentation", which writes `LrControllerAPI_<ver>.html` to temp [E].

## Protocol [E]

```json
{ "requestId": "<guid>", "object": "<object handle>", "message": "<operation>", "params": [ ... ] }
{ "requestId": "<request guid>", "success": true, "response": ... }
```

- **Object handle:** messages go to the root object when `object` is omitted. TourBox sends `setValue` with no `object` [T].
- **Several responses per request:** "Each request can be served by one or many responses". `ControllerClient` completes a call on the first response and raises later ones as `Pushed` events, which is how observer notifications arrive [I].
- **Register first:** `{"object": null, "message": "register", "params": ["<appName>", "<appVersion>", "<optional clientGUID>"]}`. The first time, Lightroom shows an approval dialog, then replies `[clientGUID, lightroomVersion]`, e.g. `["<client guid>","9.5.1"]` [E][T]. Sending the same GUID later skips the dialog. lightroom-mcp stores it in `%LOCALAPPDATA%\LightroomMcp\client.json` and never returns it from tools.
- **Close:** `{"object": "<handle>", "message": "close", "params": []}` closes an object [E].

## Messages

| Message | Params → response | Status |
|---|---|---|
| `getRange` | `[param]` → `[min, max, precision, smallIncrement, largeIncrement]`, e.g. Exposure `[-4,4,2,0.025,0.0825]` | [T] |
| `getValue` | `[param]` → `[value]` as a float, e.g. `-10.000000149011612`; round it | [T] |
| `setValue` | `[param, value]` | [T] |
| `addAdjustmentChangeObserver` | `[param?]` → `{}` | [T] |
| `getParameterNames`, `getPanelNames`, `getParameterType`, `getLabel`, `getDefault`, `increment`, `decrement`, `resetToDefault`, `resetAllDevelopAdjustments`, `setImageSettingsXMP`, `setAutoTone`, `setWhiteBalance`, `setUpright`, `toggleHDR`, `runEnhance`, `getPresetIDs`, `applyPreset`, `getProfileIDs`, `applyProfile`, `selectTool`, `getSelectedTool`, `startTracking`, `stopTracking`, `setMultipleAdjustmentThreshold`, `undo`, `redo`, `renderImage`, `nextPhoto`, `previousPhoto` | — | [E] names only |
| Masking: `getMaskTypes`, `createMaskGroup`, `addMaskComponent`, `subtractMaskComponent`, `intersectMaskComponent`, `selectMaskGroup`, `selectMaskComponent` (1-based, or `"-1"`/`"+1"`), `renameMaskGroup`, `duplicateMaskGroup`, `invertMaskGroup`, `deleteMaskGroup`, `getMaskGroupName` | — | [E] names only |
| Current photo: `getActiveImageName`, `getActivePhotoId`, `getLibraryImageId` | — | [E] names only; lr-mcp probes them in order |

These are Lua names in `lightroom.exe`. The exported doc [D] settles most of them:

- **Documented:** `showView` ("loupe", "square_grid", "compare", "dynamic_grid"), `renderImage` ("base64" | "filepath"), `openImage`, `setImageSettingsXMP`, `resetToOpen`, `selectTool` ("loupe", "crop", "heal", "whiteBalance", "masking", "upright"), all masking calls (`getMaskGroupName()` with no index returns the **selected** group), `getRating` / `getColorLabel` / `getFlag`, `undo` / `redo`, `startTracking` / `stopTracking`, `setMultipleAdjustmentThreshold` (default 0.5 s), and the setters for rating, labels and flags.
- **Not documented:** any current-photo getter (`getActiveImageName`, `getActivePhotoId`, `getLibraryImageId`). Live, they return nothing [L]. **The current photo comes from the main window title instead**: `Lightroom - DSC_8750-DxO_DeepPRIME XD3.dng` [L].
- **Not documented:** any save call. `lr_save` uses `showView("square_grid")`, the Grid trip that made Lightroom save in the GUI session, and succeeds only if a new settings file appears. Unverified live so far.

## Live observations [L]

- `lr_connect` registered, and returned version 9.5.1 on port 7682.
- **Ranges are the controller's own scale, not the XMP's.** `Exposure2012` is -5..5 (small step 0.1). **`Temperature` is 0..100 and read 33.5 for a photo saved at 5350 K**, so Kelvin values are refused as a unit mismatch instead of clamped. `Contrast2012` and `Shadows2012` are -100..100 (step 10 is the *large* increment Lightroom reports as small).
- `LocalExposure2012` reads null while the selected tool is `loupe`: `Local*` ids need Masking active and a mask selected.
- `getSelectedTool` → `["loupe"]`, `getWhiteBalanceModel` → `["absolute"]`, `appVersionString` → `["9.5.1"]`.

**Parameter ids** are Camera Raw names: `Exposure2012`, `Contrast2012`, `Highlights2012`, `Shadows2012`, `Whites2012`, `Blacks2012`, `Temperature`, `Tint`, `Vibrance`, `Saturation`, `Texture`, `Clarity2012`, `Dehaze`, and so on.

**Mask ids** apply to the **selected** mask: `LocalExposure2012` (-4..4), and `LocalContrast2012`, `LocalShadows2012`, `LocalTemperature`, `LocalTexture` and the rest (-100..100) [T].

## Things that bit us

- **Edits aren't saved immediately.** Lightroom Desktop writes settings when you leave the photo, for example to Grid view. API read-back only proves the live value. `lr_verify_saved` checks the saved XMP and the catalog. Whether some API call triggers a save is open; see [LIVE_CHECKLIST.md](LIVE_CHECKLIST.md).
- **TourBox writes too.** On 2026-11-07 at 13:58:27, TourBox sent `setValue LocalExposure2012 -0.25` [T]; it was the "unexplained" −0.25 in a GUI session. lr-mcp refuses writes while `TourBox Console.exe` runs, unless `allowExternalControllers: true` is passed.
- **Whether several clients can connect at once is unknown** [I].

## Saved state

- **Settings files:** `%LOCALAPPDATA%\Adobe\Lightroom CC\Data\<catalog-id>\settings\<sha256>` are plain XMP. Mask (`Correction`) values are stored as `LocalExposure2012` = EV ÷ 4, and every other `Local*` = slider ÷ 100. `XmpCrsParser` returns slider units.
- **Catalog:** `Managed Catalog.mcat` is SQLite with `docs` and `revs` tables, and revision content is a binary encoding. A current, winning revision whose content contains the settings file's SHA-256 proves the catalog points at it. `CatalogReader` byte-searches a temp copy and never opens the live file.
