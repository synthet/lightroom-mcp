using System.Diagnostics;
using System.Text.Json.Nodes;
using LightroomMcp.Controller;
using LightroomMcp.Safety;
using LightroomMcp.Saved;
using WinGuiMcp.Capture;
using WinGuiMcp.Common;
using WinGuiMcp.Platform;

namespace LightroomMcp.Tools;

/// <summary>
/// lr_* tool logic, free of MCP types so it can be tested against a fake controller.
/// Channel order: Controller API (values and masks) → saved-settings XMP + catalog (persistence proof) →
/// WinGuiMcp.Core (window state and captures). Method names marked "observed" are confirmed against a live
/// Lightroom 9.5.1 (TourBox traffic); the rest come from lightroom.exe strings and are probed defensively.
/// </summary>
public sealed class LrToolService
{
    /// <summary>
    /// Getters tried in order to identify the current photo. None is in the documented API (LrControllerAPI 9.5.1):
    /// they are internal Lua names and probably unreachable, so the photo check usually needs an on-screen
    /// confirmation (skipPhotoCheck after a capture + checkpoint). Kept so a live run can prove otherwise.
    /// </summary>
    public static readonly string[] PhotoIdentityProbes = ["getActiveImageName", "getActivePhotoId", "getLibraryImageId"];

    /// <summary>Messages lr_call may send without confirmed: true. Documented read-only getters from LrControllerAPI 9.5.1.</summary>
    public static readonly HashSet<string> ReadOnlyMessages = new(StringComparer.Ordinal)
    {
        "appVersionString", "appVersionTable", "getWhiteBalanceModel", "isHDROn", "isBlackAndWhiteOn",
        "getParameterNames", "getParameterType", "getPanelNames", "getRange", "getDefault", "getLabel", "getValue",
        "isConstrainAspectRatioOn", "getCropAspectRatio", "getPresetIDs", "getPresetName", "getProfileIDs", "getProfileName",
        "getSelectedTool", "isClippingShowing", "getMaskTypes", "getMaskTypeName", "getMaskGroupVisibility",
        "getMaskComponentVisibility", "getMaskGroupName", "getMaskComponentName", "canExportWithPrevious",
        "canPasteEditSettings", "getFlag", "getRating", "getColorLabel",
        // undocumented probes (harmless getters)
        "getActiveImageName", "getActivePhotoId", "getLibraryImageId"
    };

    /// <summary>View names accepted by showView (documented).</summary>
    public static readonly string[] Views = ["loupe", "square_grid", "compare", "dynamic_grid"];

    private readonly LrSession _session;
    private readonly ParamCatalog _params;
    private readonly WriteGuard _guard;
    private readonly SettingsFolder _settings;
    private readonly WindowEnumerator _windows;
    private readonly WindowCapture _capture;
    private readonly Func<IEnumerable<string>> _windowTitles;

    public LrToolService(LrSession session, ParamCatalog parameters, WriteGuard guard, SettingsFolder settings,
        WindowEnumerator windows, WindowCapture capture, Func<IEnumerable<string>>? windowTitles = null)
    {
        _windowTitles = windowTitles ?? LightroomWindowTitles;
        _session = session;
        _params = parameters;
        _guard = guard;
        _settings = settings;
        _windows = windows;
        _capture = capture;
    }

    // ---------------------------------------------------------------- status / connect

    public async Task<object> GetStatusAsync(CancellationToken ct)
    {
        var procs = Process.GetProcessesByName("lightroom");
        var pids = procs.Select(p => p.Id).ToArray();
        foreach (var p in procs) p.Dispose();

        var windows = pids.Length == 0 ? [] : _windows.ListWindows(null, includeMinimized: true)
            .Where(w => pids.Contains(w.Pid)).Select(w => new { w.Handle, w.Title, w.IsForeground, w.IsMinimized }).ToArray();

        string? connectError = null;
        string? photo = null;
        string? photoSource = null;
        if (pids.Length > 0)
        {
            try
            {
                await _session.EnsureConnectedAsync(ct).ConfigureAwait(false);
                (photo, photoSource) = await ProbeCurrentPhotoAsync(ct).ConfigureAwait(false);
            }
            catch (ToolException ex)
            {
                connectError = $"{ex.Error.Code}: {ex.Error.Message}";
            }
        }

        var settingsDir = _settings.FindSettingsDir();
        return new
        {
            ok = true,
            lightroomRunning = pids.Length > 0,
            pids,
            windows,
            controller = new
            {
                port = ConnectionFile.TryReadPort(),
                registered = _session.IsRegistered,
                lightroomVersion = _session.LightroomVersion,
                error = connectError
            },
            currentPhoto = photo,
            currentPhotoSource = photoSource ?? (photo is null && pids.Length > 0 ? "unavailable: no window title names a photo and the controller API has no current-photo getter; confirm on screen (lr_capture) and use skipPhotoCheck" : null),
            externalControllers = _guard.RunningExternalControllers(),
            needsReadback = _guard.NeedsReadbackReason,
            settingsDir,
            newestSettingsUtc = settingsDir is null ? null : SettingsFolder.ListNewestFirst(settingsDir).Select(f => (DateTime?)File.GetLastWriteTimeUtc(f)).FirstOrDefault()
        };
    }

    public async Task<object> ConnectAsync(CancellationToken ct)
    {
        await _session.EnsureConnectedAsync(ct).ConfigureAwait(false);
        return new { ok = true, registered = true, lightroomVersion = _session.LightroomVersion, port = _session.Port };
    }

    // ---------------------------------------------------------------- parameters and values

    public async Task<object> ListParametersAsync(string? panel, CancellationToken ct)
    {
        var args = panel is null ? null : new JsonArray(panel);
        var names = await _session.CallAsync("getParameterNames", args, ct: ct).ConfigureAwait(false);
        var panels = await _session.CallAsync("getPanelNames", ct: ct).ConfigureAwait(false);
        return new
        {
            ok = names.Success,
            parameters = names.Response,
            panels = panels.Success ? panels.Response : null,
            note = names.Success ? null : "getParameterNames was rejected; Camera Raw ids such as Exposure2012 or LocalExposure2012 still work with lr_get_values."
        };
    }

    public async Task<object> GetValuesAsync(IReadOnlyList<string> parameters, CancellationToken ct)
    {
        if (parameters.Count == 0)
            throw new ToolException(ErrorCodes.InvalidArgument, "Pass at least one parameter id, e.g. [\"Exposure2012\"].");

        var values = new JsonObject();
        foreach (var p in parameters)
        {
            var range = await _params.GetRangeAsync(p, ct).ConfigureAwait(false);
            var raw = await _params.GetValueAsync(p, ct).ConfigureAwait(false);
            values[p] = new JsonObject
            {
                ["value"] = raw is null ? null : range.Round(raw.Value),
                ["min"] = range.Min,
                ["max"] = range.Max,
                ["step"] = range.SmallIncrement
            };
        }
        _guard.MarkReadbackDone();
        return new { ok = true, values };
    }

    /// <summary>
    /// Sets develop values on the current photo. Local* ids apply to the selected mask in Lightroom.
    /// Each value is clamped to getRange, written with setValue, and read back with getValue.
    /// </summary>
    public async Task<object> SetValuesAsync(JsonObject values, bool delta, WriteRequest req, bool dryRun, CancellationToken ct)
    {
        if (values.Count == 0)
            throw new ToolException(ErrorCodes.InvalidArgument, "values must contain at least one parameter, e.g. {\"Exposure2012\": 0.3}.");

        var plan = new List<(string Param, double Before, double Target, bool Clamped, ParamRange Range)>();
        foreach (var (param, node) in values)
        {
            if (node is null || !TryNumber(node, out var requested))
                throw new ToolException(ErrorCodes.InvalidArgument, $"Value for '{param}' must be a number.");
            var range = await _params.GetRangeAsync(param, ct).ConfigureAwait(false);
            var before = await _params.GetValueAsync(param, ct).ConfigureAwait(false)
                ?? throw new ToolException(LrErrorCodes.ControllerCallFailed, $"Could not read the current value of '{param}'. Is a photo open in Edit?");
            var wanted = delta ? before + requested : requested;
            // Far outside the range means a unit mismatch, not an overshoot: the API's Temperature is 0..100
            // (it read 33.5 for a photo saved at 5350 K). Refuse instead of clamping silently.
            if (Math.Abs(wanted - range.Clamp(wanted)) > range.Max - range.Min)
                throw new ToolException(ErrorCodes.InvalidArgument,
                    $"{param}={wanted} is far outside its controller range [{range.Min}, {range.Max}] (current {range.Round(before)}). The API uses its own scale for some sliders (Temperature is 0..100, not Kelvin); use lr_get_values and a delta.",
                    new Dictionary<string, object?> { ["parameter"] = param, ["requested"] = wanted, ["min"] = range.Min, ["max"] = range.Max, ["current"] = before });
            var target = range.Round(range.Clamp(wanted));
            plan.Add((param, range.Round(before), target, Math.Abs(target - range.Round(wanted)) > range.Tolerance, range));
        }

        var (photo, _) = await ProbeCurrentPhotoAsync(ct).ConfigureAwait(false);
        var planned = plan.Select(p => new { parameter = p.Param, before = p.Before, target = p.Target, clamped = p.Clamped }).ToArray();
        if (dryRun)
            return new { ok = true, dryRun = true, currentPhoto = photo, planned };

        _guard.Check(req, photo);

        var results = new JsonArray();
        var mismatches = 0;
        foreach (var p in plan)
        {
            ControllerReply reply;
            try
            {
                reply = await _session.CallAsync("setValue", new JsonArray(p.Param, p.Target), ct: ct).ConfigureAwait(false);
            }
            catch (ToolException ex) when (ex.Error.Code is ErrorCodes.Timeout or LrErrorCodes.ControllerUnavailable)
            {
                _guard.MarkOutcomeUnknown($"setValue {p.Param}={p.Target} got {ex.Error.Code}");
                throw;
            }

            var after = await _params.GetValueAsync(p.Param, ct).ConfigureAwait(false);
            var actual = after is null ? (double?)null : p.Range.Round(after.Value);
            var matched = actual is not null && Math.Abs(actual.Value - p.Target) <= p.Range.Tolerance;
            if (!matched) mismatches++;
            results.Add(new JsonObject
            {
                ["parameter"] = p.Param,
                ["before"] = p.Before,
                ["requested"] = p.Target,
                ["actual"] = actual,
                ["clamped"] = p.Clamped,
                ["accepted"] = reply.Success,
                ["readbackOk"] = matched
            });
        }

        if (mismatches > 0)
            throw new ToolException(LrErrorCodes.ReadbackMismatch,
                $"{mismatches} value(s) did not read back as written. Another controller (TourBox) or a wrong mask selection may have interfered.",
                new Dictionary<string, object?> { ["results"] = results.ToJsonString() });

        return new
        {
            ok = true,
            currentPhoto = photo,
            results,
            persisted = false,
            note = "Values are live in Lightroom but not yet saved. Lightroom Desktop writes edits when you leave the photo; then call lr_verify_saved."
        };
    }

    // ---------------------------------------------------------------- masks

    public async Task<object> SelectMaskAsync(string selector, bool component, CancellationToken ct)
    {
        // selectMaskGroup / selectMaskComponent take a 1-based index or "-1"/"+1" (relative). Unconfirmed live.
        var message = component ? "selectMaskComponent" : "selectMaskGroup";
        JsonNode arg = int.TryParse(selector, out var idx) && !selector.StartsWith('+') && !selector.StartsWith('-')
            ? JsonValue.Create(idx)
            : JsonValue.Create(selector);
        var reply = await _session.CallAsync(message, new JsonArray(arg), ct: ct).ConfigureAwait(false);
        var name = await TryCallAsync(component ? "getMaskComponentName" : "getMaskGroupName", ct).ConfigureAwait(false);
        return new
        {
            ok = reply.Success,
            message,
            response = reply.Response,
            selectedName = name,
            verified = name is not null,
            note = name is null ? "Lightroom did not report the selected mask name; confirm the selection on screen (lr_capture) before writing Local* values." : null
        };
    }

    // ---------------------------------------------------------------- persistence proof

    public object ReadSavedSettings(string? file, bool requireMasks, DateTimeOffset? sinceUtc)
    {
        var path = file ?? PickSettingsFile(requireMasks, sinceUtc);
        var saved = XmpCrsParser.Parse(path);
        return new { ok = true, settings = saved };
    }

    /// <summary>
    /// Proof of persistence: a settings XMP written at/after <paramref name="sinceUtc"/> that holds the expected values,
    /// and a current catalog revision that references its SHA-256.
    /// Expectations: "global.Exposure2012" or "&lt;mask name&gt;.Shadows2012" (mask values in slider units).
    /// </summary>
    public object VerifySaved(JsonObject expect, DateTimeOffset sinceUtc, string? photo, double tolerance)
    {
        var settingsDir = _settings.FindSettingsDir()
            ?? throw new ToolException(LrErrorCodes.SettingsNotFound, "Lightroom Desktop settings folder not found.");
        var requireMasks = expect.Select(e => e.Key).Any(k => !k.StartsWith("global.", StringComparison.OrdinalIgnoreCase));
        var path = _settings.PickNewest(settingsDir, requireMasks, sinceUtc)
            ?? throw new ToolException(LrErrorCodes.SaveUnverified,
                $"No settings file was written since {sinceUtc:O}. The edit is visible in Lightroom but not saved: leave the photo (Grid view) to make Lightroom save, then verify again.",
                new Dictionary<string, object?> { ["settingsDir"] = settingsDir });

        var saved = XmpCrsParser.Parse(path);
        var failures = new List<string>();
        foreach (var (target, node) in expect)
        {
            if (node is null || !TryNumber(node, out var want))
            {
                failures.Add($"{target}: expected value must be a number");
                continue;
            }
            var dot = target.LastIndexOf('.');
            if (dot <= 0)
            {
                failures.Add($"{target}: use 'global.<Key>' or '<mask name>.<Key>'");
                continue;
            }
            var scope = target[..dot];
            var key = target[(dot + 1)..];
            double? got;
            if (scope.Equals("global", StringComparison.OrdinalIgnoreCase))
                got = XmpCrsParser.GlobalNumber(saved, key);
            else if (saved.FindCorrection(scope) is { } corr)
                got = corr.Values.TryGetValue(key.StartsWith("Local", StringComparison.Ordinal) ? key[5..] : key, out var v) ? v : 0;
            else
            {
                failures.Add($"{target}: no mask named '{scope}' in the saved file");
                continue;
            }
            if (got is null || Math.Abs(got.Value - want) > tolerance)
                failures.Add($"{target}: saved {got?.ToString() ?? "missing"}, expected {want}");
        }

        var catalogDir = Path.GetDirectoryName(settingsDir)!;
        IReadOnlyList<CatalogReference> refs;
        try
        {
            refs = CatalogReader.FindReferences(catalogDir, saved.Sha256, photo);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or Microsoft.Data.Sqlite.SqliteException)
        {
            refs = [];
            failures.Add($"catalog: could not read a copy ({ex.Message})");
        }
        var current = refs.Where(r => r.Current && r.Winning).ToArray();
        if (current.Length == 0)
            failures.Add("catalog: no current revision references this settings file yet");

        if (failures.Count > 0)
            throw new ToolException(LrErrorCodes.SaveUnverified, "The saved state does not match: " + string.Join("; ", failures),
                new Dictionary<string, object?> { ["file"] = saved.File, ["savedUtc"] = saved.SavedUtc, ["failures"] = failures });

        return new
        {
            ok = true,
            file = saved.File,
            sha256 = saved.Sha256,
            savedUtc = saved.SavedUtc,
            catalogRevisions = current.Select(r => new { r.Sequence, r.DocId, r.MentionsPhoto }).ToArray(),
            checkedValues = expect.Count
        };
    }

    // ---------------------------------------------------------------- save, render, library state

    /// <summary>
    /// Makes Lightroom Desktop write its settings by leaving the photo: showView("square_grid"), wait for a new
    /// settings XMP, then showView(returnView). The earlier GUI session saw saves only on that Detail→Grid trip.
    /// Succeeds only when a settings file newer than the call appears; nothing changed = nothing written = SaveUnverified.
    /// </summary>
    public async Task<object> SaveAsync(string? returnView, int timeoutMs, CancellationToken ct)
    {
        if (returnView is not null && !Views.Contains(returnView))
            throw new ToolException(ErrorCodes.InvalidArgument, $"returnView must be one of {string.Join(", ", Views)}, or omitted.");
        var settingsDir = _settings.FindSettingsDir()
            ?? throw new ToolException(LrErrorCodes.SettingsNotFound, "Lightroom Desktop settings folder not found.");
        var since = DateTimeOffset.UtcNow;

        await _session.CallOkAsync("showView", new JsonArray("square_grid"), ct: ct).ConfigureAwait(false);
        string? path = null;
        var deadline = DateTime.UtcNow.AddMilliseconds(Math.Clamp(timeoutMs, 500, 60000));
        while (DateTime.UtcNow < deadline && (path = _settings.PickNewest(settingsDir, false, since)) is null)
            await Task.Delay(250, ct).ConfigureAwait(false);

        string? returned = null;
        if (returnView is not null)
        {
            var back = await _session.CallAsync("showView", new JsonArray(returnView), ct: ct).ConfigureAwait(false);
            returned = back.Success ? returnView : null;
        }

        if (path is null)
            throw new ToolException(LrErrorCodes.SaveUnverified,
                $"Switched to Grid but no settings file was written within {timeoutMs} ms. Either nothing changed since the last save, or Lightroom did not save; check lr_get_values and retry.",
                new Dictionary<string, object?> { ["settingsDir"] = settingsDir, ["since"] = since, ["returnedTo"] = returned });

        var saved = XmpCrsParser.Parse(path);
        return new { ok = true, file = saved.File, sha256 = saved.Sha256, savedUtc = saved.SavedUtc, since, returnedTo = returned,
            note = "Use lr_verify_saved with this sinceUtc to check values and the catalog." };
    }

    /// <summary>renderImage("filepath"): a JPEG of the active image with current settings; returns its temp path.</summary>
    public async Task<object> RenderPreviewAsync(string? copyTo, CancellationToken ct)
    {
        var response = await _session.CallOkAsync("renderImage", new JsonArray("filepath"), timeout: TimeSpan.FromSeconds(60), ct: ct).ConfigureAwait(false);
        var path = (response is JsonArray { Count: > 0 } a ? a[0] : response)?.ToString();
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            throw new ToolException(LrErrorCodes.ControllerCallFailed, "renderImage did not return an existing file path.",
                new Dictionary<string, object?> { ["response"] = response?.ToJsonString() });
        if (copyTo is not null)
        {
            var full = Path.GetFullPath(copyTo);
            Directory.CreateDirectory(Path.GetDirectoryName(full)!);
            File.Copy(path, full, overwrite: true);
            path = full;
        }
        return new { ok = true, path, bytes = new FileInfo(path).Length };
    }

    /// <summary>Rating, colour label, flag and selected tool: used to detect stray single-key shortcuts.</summary>
    public async Task<object> GetPhotoStateAsync(CancellationToken ct) => new
    {
        ok = true,
        rating = await TryCallAsync("getRating", ct).ConfigureAwait(false),
        colorLabel = await TryCallAsync("getColorLabel", ct).ConfigureAwait(false),
        flag = await TryCallAsync("getFlag", ct).ConfigureAwait(false),
        selectedTool = await TryCallAsync("getSelectedTool", ct).ConfigureAwait(false),
        selectedMask = await TryCallAsync("getMaskGroupName", ct).ConfigureAwait(false)
    };

    // ---------------------------------------------------------------- raw call and capture

    public async Task<object> CallRawAsync(string message, JsonArray? args, string? obj, WriteRequest req, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(message))
            throw new ToolException(ErrorCodes.InvalidArgument, "message is required.");
        if (message is "register" or "close")
            throw new ToolException(ErrorCodes.InvalidArgument, $"'{message}' is managed by lr_connect.");
        if (!ReadOnlyMessages.Contains(message))
        {
            var (photo, _) = await ProbeCurrentPhotoAsync(ct).ConfigureAwait(false);
            _guard.Check(req, photo);
        }
        var reply = await _session.CallAsync(message, args, obj, ct: ct).ConfigureAwait(false);
        return new { ok = reply.Success, message, readOnly = ReadOnlyMessages.Contains(message), response = reply.Response };
    }

    public object Capture(string outputPath, int? handle, int? x, int? y, int? width, int? height, double scale)
    {
        var target = handle ?? FindMainWindow()
            ?? throw new ToolException(ErrorCodes.WindowGone, "No Lightroom window found. Is it running, or hidden? lr_get_status lists its windows.");
        CaptureRegion? region = x is null && y is null && width is null && height is null
            ? null
            : x is not null && y is not null && width is > 0 && height is > 0
                ? new CaptureRegion { X = x.Value, Y = y.Value, Width = width.Value, Height = height.Value }
                : throw new ToolException(ErrorCodes.InvalidArgument, "A region needs x, y, width and height together.");
        var result = _capture.CaptureToFile(target, region, scale, outputPath);
        return new { ok = true, handle = target, path = result.Path, width = result.Width, height = result.Height, sha256 = result.Sha256 };
    }

    // ---------------------------------------------------------------- helpers

    public async Task<(string? Photo, string? Source)> ProbeCurrentPhotoAsync(CancellationToken ct)
    {
        foreach (var probe in PhotoIdentityProbes)
        {
            var value = await TryCallAsync(probe, ct).ConfigureAwait(false);
            if (!string.IsNullOrWhiteSpace(value))
                return (value, probe);
        }
        // Observed live (9.5.1): the main window title is "Lightroom - <file name>" while a photo is open.
        return PhotoFromWindowTitles(_windowTitles()) is { } fromTitle ? (fromTitle, "windowTitle") : (null, null);
    }

    /// <summary>"Lightroom - DSC_8750-DxO_DeepPRIME XD3.dng" → "DSC_8750-DxO_DeepPRIME XD3.dng". Null if no title names a photo.</summary>
    public static string? PhotoFromWindowTitles(IEnumerable<string> titles)
    {
        const string prefix = "Lightroom - ";
        var names = titles.Where(t => t.StartsWith(prefix, StringComparison.Ordinal) && t.Length > prefix.Length)
            .Select(t => t[prefix.Length..].Trim()).Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
        return names.Length == 1 ? names[0] : null; // ambiguous (several photo windows) → unknown
    }

    private IEnumerable<string> LightroomWindowTitles()
    {
        var procs = Process.GetProcessesByName("lightroom");
        var pids = procs.Select(p => p.Id).ToHashSet();
        foreach (var p in procs) p.Dispose();
        return pids.Count == 0 ? [] : _windows.ListWindows(null, includeMinimized: true).Where(w => pids.Contains(w.Pid)).Select(w => w.Title).ToArray();
    }

    private async Task<string?> TryCallAsync(string message, CancellationToken ct)
    {
        try
        {
            var reply = await _session.CallAsync(message, timeout: TimeSpan.FromSeconds(3), ct: ct).ConfigureAwait(false);
            if (!reply.Success || reply.Response is null)
                return null;
            var node = reply.Response is JsonArray { Count: > 0 } a ? a[0] : reply.Response;
            var text = node is JsonValue ? node.ToString() : null;
            return string.IsNullOrWhiteSpace(text) || text == "null" ? null : text;
        }
        catch (ToolException ex) when (ex.Error.Code == ErrorCodes.Timeout)
        {
            return null;
        }
    }

    private int? FindMainWindow()
    {
        var procs = Process.GetProcessesByName("lightroom");
        var pids = procs.Select(p => p.Id).ToHashSet();
        foreach (var p in procs) p.Dispose();
        return _windows.ListWindows(null, includeMinimized: true)
            .Where(w => pids.Contains(w.Pid) && !string.IsNullOrWhiteSpace(w.Title))
            .OrderByDescending(w => w.IsForeground)
            .Select(w => (int?)w.Handle)
            .FirstOrDefault();
    }

    private string PickSettingsFile(bool requireMasks, DateTimeOffset? sinceUtc)
    {
        var dir = _settings.FindSettingsDir()
            ?? throw new ToolException(LrErrorCodes.SettingsNotFound, "Lightroom Desktop settings folder not found.");
        return _settings.PickNewest(dir, requireMasks, sinceUtc)
            ?? throw new ToolException(LrErrorCodes.SettingsNotFound, "No matching settings file. Nothing has been saved yet (leave the photo to make Lightroom save).",
                new Dictionary<string, object?> { ["settingsDir"] = dir });
    }

    internal static bool TryNumber(JsonNode node, out double value)
    {
        value = 0;
        if (node is not JsonValue v)
            return false;
        if (v.TryGetValue(out double d)) { value = d; return true; }
        if (v.TryGetValue(out int i)) { value = i; return true; }
        if (v.TryGetValue(out long l)) { value = l; return true; }
        return v.TryGetValue(out string? s) && XmpCrsParser.TryNum(s, out value);
    }
}
