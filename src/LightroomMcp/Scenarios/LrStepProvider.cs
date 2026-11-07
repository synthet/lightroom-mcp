using System.Text.Json.Nodes;
using LightroomMcp.Safety;
using LightroomMcp.Tools;
using WinGuiMcp.Common;
using WinGuiMcp.Platform;
using WinGuiMcp.Scenarios;

namespace LightroomMcp.Scenarios;

/// <summary>
/// "lr.*" scenario steps. Each maps to the lr_* tool of the same name (docs/tools.md), with the same arguments.
/// In a dry run no step talks to Lightroom: it echoes the arguments it would send.
/// Write steps (ReadOnly = false) only run when the scenario is started with allowWrites, and still pass
/// the WriteGuard (confirmed, expectedPhoto, TourBox) like the tools do.
/// </summary>
public sealed class LrStepProvider : IScenarioStepProvider
{
    private static readonly Dictionary<string, StepDescriptor> Steps = new[]
    {
        new StepDescriptor("get_status", "Lightroom process, controller, current photo, external controllers", true),
        new StepDescriptor("connect", "Connect and register with the controller API", true),
        new StepDescriptor("list_parameters", "Develop parameter ids and panels", true),
        new StepDescriptor("get_values", "Current values and ranges: { parameters: [..] }", true),
        new StepDescriptor("set_values", "Set values: { values: {..}, expectedPhoto, confirmed, delta? }", false),
        new StepDescriptor("select_mask", "Select a mask group/component: { selector, component? }", false),
        new StepDescriptor("read_saved_settings", "Parse the newest saved settings XMP: { file?, requireMasks?, sinceUtc? }", true),
        new StepDescriptor("verify_saved", "Prove persistence: { expect: {..}, sinceUtc, photo?, tolerance? }", true),
        new StepDescriptor("call", "Raw controller message: { message, args?, expectedPhoto?, confirmed? }", false),
        new StepDescriptor("capture", "Capture the Lightroom window to a PNG: { outputPath, x?, y?, width?, height? }", true),
        new StepDescriptor("now", "Current UTC time (ISO-8601) for sinceUtc", true),
        new StepDescriptor("save", "Make Lightroom save (Grid trip) and wait for the settings file: { returnView?, timeoutMs? }", false),
        new StepDescriptor("render_preview", "JPEG of the active image: { copyTo? } (relative to the run folder)", true),
        new StepDescriptor("get_photo_state", "Rating, colour label, flag, selected tool and mask", true),
    }.ToDictionary(d => d.Name, StringComparer.Ordinal);

    private readonly LrToolService _svc;
    private readonly UiaDispatcher _dispatcher;

    public LrStepProvider(LrToolService svc, UiaDispatcher dispatcher)
    {
        _svc = svc;
        _dispatcher = dispatcher;
    }

    public string Namespace => "lr";
    public StepDescriptor? Describe(string name) => Steps.GetValueOrDefault(name);
    public IEnumerable<StepDescriptor> List() => Steps.Values;

    public async Task<StepResult> ExecuteAsync(StepInvocation step, CancellationToken ct)
    {
        var a = step.Args;
        if (step.Name == "now")
            return StepResult.Success(new JsonObject { ["utc"] = DateTimeOffset.UtcNow.ToString("O") });
        if (step.DryRun)
            return StepResult.Success(new JsonObject { ["ok"] = true, ["dryRun"] = true, ["step"] = "lr." + step.Name, ["args"] = a.DeepClone() });

        try
        {
            object result = step.Name switch
            {
                "get_status" => await _svc.GetStatusAsync(ct),
                "connect" => await _svc.ConnectAsync(ct),
                "list_parameters" => await _svc.ListParametersAsync(Str(a, "panel"), ct),
                "get_values" => await _svc.GetValuesAsync(
                    (a["parameters"] as JsonArray)?.Select(p => p!.ToString()).ToArray() ?? [], ct),
                "set_values" => await _svc.SetValuesAsync(
                    a["values"] as JsonObject ?? throw new ToolException(ErrorCodes.InvalidArgument, "set_values needs values: {..}"),
                    Bool(a, "delta"), Write(a), Bool(a, "dryRun"), ct),
                "select_mask" => await _svc.SelectMaskAsync(Str(a, "selector") ?? throw new ToolException(ErrorCodes.InvalidArgument, "select_mask needs selector"),
                    Bool(a, "component"), ct),
                "read_saved_settings" => _svc.ReadSavedSettings(Str(a, "file"), Bool(a, "requireMasks"), Time(a, "sinceUtc")),
                "verify_saved" => _svc.VerifySaved(
                    a["expect"] as JsonObject ?? throw new ToolException(ErrorCodes.InvalidArgument, "verify_saved needs expect: {..}"),
                    Time(a, "sinceUtc") ?? throw new ToolException(ErrorCodes.InvalidArgument, "verify_saved needs sinceUtc"),
                    Str(a, "photo"), ScenarioExpressionNum(a["tolerance"], 0.011)),
                "call" => await _svc.CallRawAsync(Str(a, "message") ?? "", a["args"] as JsonArray, Str(a, "objectHandle"), Write(a), ct),
                "capture" => await _dispatcher.InvokeAsync(() => _svc.Capture(
                    Resolve(step, Str(a, "outputPath") ?? "lightroom.png"), Int(a, "handle"), Int(a, "x"), Int(a, "y"), Int(a, "width"), Int(a, "height"),
                    ScenarioExpressionNum(a["scale"], 1.0)), ct),
                "save" => await _svc.SaveAsync(a.ContainsKey("returnView") ? Str(a, "returnView") : "loupe", Int(a, "timeoutMs") ?? 10000, ct),
                "render_preview" => await _svc.RenderPreviewAsync(Str(a, "copyTo") is { } c ? Resolve(step, c) : null, ct),
                "get_photo_state" => await _svc.GetPhotoStateAsync(ct),
                _ => throw new ToolException(ErrorCodes.InvalidArgument, $"unknown lr step '{step.Name}'")
            };
            return StepResult.Success(JsonNode.Parse(ToolResponse.Serialize(result)));
        }
        catch (ToolException ex)
        {
            var guard = ex.Error.Code is "ConfirmationRequired" or "PhotoMismatch" or "ExternalControllerActive" or "ReadbackRequired";
            return StepResult.Failure(ex.Error.Code, ex.Error.Message,
                ex.Error.Details is null ? null : JsonNode.Parse(ToolResponse.Serialize(ex.Error.Details)), guard);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            return StepResult.Failure(ErrorCodes.InternalError, $"{ex.GetType().Name}: {ex.Message}");
        }
    }

    private static WriteRequest Write(JsonObject a) =>
        new(Bool(a, "confirmed"), Str(a, "expectedPhoto"), Bool(a, "skipPhotoCheck"), Bool(a, "allowExternalControllers"));

    private static string Resolve(StepInvocation step, string path) => Path.IsPathRooted(path) ? path : Path.Combine(step.RunDir, path);
    private static string? Str(JsonObject a, string k) => a[k] is JsonValue v && v.TryGetValue(out string? s) ? s : a[k]?.ToString();
    private static bool Bool(JsonObject a, string k) => a[k] is JsonValue v && v.TryGetValue(out bool b) && b;
    private static int? Int(JsonObject a, string k) => a[k] is { } n && LrToolService.TryNumber(n, out var d) ? (int)d : null;
    private static double ScenarioExpressionNum(JsonNode? n, double fallback) => n is not null && LrToolService.TryNumber(n, out var d) ? d : fallback;

    private static DateTimeOffset? Time(JsonObject a, string k) =>
        Str(a, k) is { Length: > 0 } s
            ? DateTimeOffset.Parse(s, System.Globalization.CultureInfo.InvariantCulture, System.Globalization.DateTimeStyles.AssumeUniversal).ToUniversalTime()
            : null;
}
