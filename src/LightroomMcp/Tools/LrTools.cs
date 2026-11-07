using System.ComponentModel;
using System.Text.Json;
using System.Text.Json.Nodes;
using LightroomMcp.Safety;
using ModelContextProtocol.Protocol;
using ModelContextProtocol.Server;
using WinGuiMcp.Common;
using WinGuiMcp.Platform;

namespace LightroomMcp.Tools;

/// <summary>MCP surface. Names and arguments are specified in docs/tools.md; keep the two in step.</summary>
[McpServerToolType]
public sealed class LrTools
{
    private readonly LrToolService _svc;
    private readonly UiaDispatcher _dispatcher;

    public LrTools(LrToolService svc, UiaDispatcher dispatcher)
    {
        _svc = svc;
        _dispatcher = dispatcher;
    }

    [McpServerTool(Name = "lr_get_status", ReadOnly = true, Destructive = false, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Lightroom Desktop status: process and windows, controller connection, current photo, running external controllers (TourBox), and the newest saved-settings time.")]
    public Task<CallToolResult> GetStatus(CancellationToken cancellationToken = default) =>
        Run(() => _svc.GetStatusAsync(cancellationToken));

    [McpServerTool(Name = "lr_connect", ReadOnly = false, Destructive = false, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Connects to Lightroom's controller API and registers. The first time, Lightroom shows an Allow dialog; returns ApprovalPending until the user clicks Allow.")]
    public Task<CallToolResult> Connect(CancellationToken cancellationToken = default) =>
        Run(() => _svc.ConnectAsync(cancellationToken));

    [McpServerTool(Name = "lr_list_parameters", ReadOnly = true, Destructive = false, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Lists develop parameter ids (Camera Raw names such as Exposure2012, LocalExposure2012) and panel names, optionally for one panel.")]
    public Task<CallToolResult> ListParameters(string? panel = null, CancellationToken cancellationToken = default) =>
        Run(() => _svc.ListParametersAsync(panel, cancellationToken));

    [McpServerTool(Name = "lr_get_values", ReadOnly = true, Destructive = false, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Reads current values and ranges for develop parameters on the current photo. Local* ids read the selected mask. Clears a pending read-back block.")]
    public Task<CallToolResult> GetValues(string[] parameters, CancellationToken cancellationToken = default) =>
        Run(() => _svc.GetValuesAsync(parameters, cancellationToken));

    [McpServerTool(Name = "lr_set_values", ReadOnly = false, Destructive = true, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Sets develop values on the current photo through the controller API, clamped to range and read back. Local* ids apply to the selected mask. Requires confirmed and expectedPhoto; use dryRun to preview. Not persisted until Lightroom saves; then use lr_verify_saved.")]
    public Task<CallToolResult> SetValues(
        JsonObject values,
        string? expectedPhoto = null,
        bool confirmed = false,
        bool delta = false,
        bool dryRun = false,
        bool skipPhotoCheck = false,
        bool allowExternalControllers = false,
        CancellationToken cancellationToken = default) =>
        Run(() => _svc.SetValuesAsync(values, delta,
            new WriteRequest(confirmed, expectedPhoto, skipPhotoCheck, allowExternalControllers), dryRun, cancellationToken));

    [McpServerTool(Name = "lr_select_mask", ReadOnly = false, Destructive = false, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Selects a mask group (or component) by 1-based index, or '+1'/'-1' relative. Reports the selected name when Lightroom provides it; otherwise verify on screen before writing Local* values.")]
    public Task<CallToolResult> SelectMask(string selector, bool component = false, CancellationToken cancellationToken = default) =>
        Run(() => _svc.SelectMaskAsync(selector, component, cancellationToken));

    [McpServerTool(Name = "lr_read_saved_settings", ReadOnly = true, Destructive = false, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Parses the newest saved develop-settings XMP (or a given file) into global values and masks in slider units. sinceUtc limits it to files saved after that time.")]
    public Task<CallToolResult> ReadSavedSettings(string? file = null, bool requireMasks = false, string? sinceUtc = null) =>
        Run(() => Task.FromResult(_svc.ReadSavedSettings(file, requireMasks, ParseTime(sinceUtc))));

    [McpServerTool(Name = "lr_verify_saved", ReadOnly = true, Destructive = false, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Proves an edit was persisted: a settings XMP saved since sinceUtc holds the expected values ('global.Exposure2012' or '<mask name>.Shadows2012', slider units) and a current catalog revision references it. Fails with SaveUnverified otherwise.")]
    public Task<CallToolResult> VerifySaved(JsonObject expect, string sinceUtc, string? photo = null, double tolerance = 0.011) =>
        Run(() => Task.FromResult(_svc.VerifySaved(expect,
            ParseTime(sinceUtc) ?? throw new ToolException(ErrorCodes.InvalidArgument, "sinceUtc is required (ISO-8601), the time just before you made Lightroom save."),
            photo, tolerance)));

    [McpServerTool(Name = "lr_save", ReadOnly = false, Destructive = false, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Makes Lightroom save the current edit by switching to Grid (showView square_grid), waits for a new settings XMP, then returns to returnView (default loupe; null stays in Grid). SaveUnverified if no file appears.")]
    public Task<CallToolResult> Save(string? returnView = "loupe", int timeoutMs = 10000, CancellationToken cancellationToken = default) =>
        Run(() => _svc.SaveAsync(returnView, timeoutMs, cancellationToken));

    [McpServerTool(Name = "lr_render_preview", ReadOnly = true, Destructive = false, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Renders the active image with its current settings to a JPEG (renderImage filepath) and returns the path; copyTo saves a copy.")]
    public Task<CallToolResult> RenderPreview(string? copyTo = null, CancellationToken cancellationToken = default) =>
        Run(() => _svc.RenderPreviewAsync(copyTo, cancellationToken));

    [McpServerTool(Name = "lr_get_photo_state", ReadOnly = true, Destructive = false, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Rating, colour label, flag, selected tool and selected mask name. Compare before and after GUI steps to catch stray single-key shortcuts.")]
    public Task<CallToolResult> GetPhotoState(CancellationToken cancellationToken = default) =>
        Run(() => _svc.GetPhotoStateAsync(cancellationToken));

    [McpServerTool(Name = "lr_call", ReadOnly = false, Destructive = true, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Sends one raw controller API message (for discovery). Known read-only messages run freely; anything else is treated as a write and needs confirmed and expectedPhoto.")]
    public Task<CallToolResult> Call(
        string message,
        JsonArray? args = null,
        string? objectHandle = null,
        string? expectedPhoto = null,
        bool confirmed = false,
        bool skipPhotoCheck = false,
        bool allowExternalControllers = false,
        CancellationToken cancellationToken = default) =>
        Run(() => _svc.CallRawAsync(message, args, objectHandle,
            new WriteRequest(confirmed, expectedPhoto, skipPhotoCheck, allowExternalControllers), cancellationToken));

    [McpServerTool(Name = "lr_capture", ReadOnly = true, Destructive = false, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Captures the Lightroom window (or a region of it) to a PNG file and returns its path, size and SHA-256. Never returns image data inline.")]
    public Task<CallToolResult> Capture(
        string outputPath,
        int? handle = null,
        int? x = null,
        int? y = null,
        int? width = null,
        int? height = null,
        double scale = 1.0) =>
        Run(() => _dispatcher.InvokeAsync(() => _svc.Capture(outputPath, handle, x, y, width, height, scale)));

    private static DateTimeOffset? ParseTime(string? iso) =>
        string.IsNullOrWhiteSpace(iso) ? null
        : DateTimeOffset.TryParse(iso, System.Globalization.CultureInfo.InvariantCulture, System.Globalization.DateTimeStyles.AssumeUniversal, out var t)
            ? t.ToUniversalTime()
            : throw new ToolException(ErrorCodes.InvalidArgument, $"'{iso}' is not an ISO-8601 time.");

    private static async Task<CallToolResult> Run(Func<Task<object>> action)
    {
        try
        {
            return Result(await action().ConfigureAwait(false));
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (ToolException ex)
        {
            return Result(ex.Error);
        }
        catch (Exception ex)
        {
            return Result(ToolError.Create(ErrorCodes.InternalError, ex.Message));
        }
    }

    internal static CallToolResult Result(object payload)
    {
        var json = ToolResponse.Serialize(payload);
        return new CallToolResult
        {
            IsError = payload is ToolError,
            Content = [new TextContentBlock { Text = json }],
            StructuredContent = JsonSerializer.Deserialize<JsonElement>(json)
        };
    }
}
