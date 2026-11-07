using System.Diagnostics;
using LightroomMcp.Controller;
using WinGuiMcp.Common;

namespace LightroomMcp.Safety;

/// <summary>
/// Every lr_* write passes through here:
/// 1. <c>confirmed: true</c> is required (the caller has shown the change to the user or a checkpoint approved it).
/// 2. <c>expectedPhoto</c> must match the photo Lightroom reports, unless the caller explicitly skips the check.
/// 3. Refuse while TourBox Console runs (it polls and writes the same controller API) unless allowed.
/// 4. After a write whose outcome is unknown (timeout, dropped connection), block writes until a read succeeds.
/// </summary>
public sealed class WriteGuard
{
    public static readonly string[] ExternalControllerProcesses = ["TourBox Console", "TourBox"];

    private readonly Func<IReadOnlyList<string>> _runningControllers;
    private volatile string? _needsReadbackReason;

    public WriteGuard(Func<IReadOnlyList<string>>? runningControllers = null) =>
        _runningControllers = runningControllers ?? DetectExternalControllers;

    public string? NeedsReadbackReason => _needsReadbackReason;

    public void MarkOutcomeUnknown(string reason) => _needsReadbackReason = reason;
    public void MarkReadbackDone() => _needsReadbackReason = null;

    public IReadOnlyList<string> RunningExternalControllers() => _runningControllers();

    public void Check(WriteRequest req, string? currentPhoto)
    {
        if (!req.Confirmed)
            throw new ToolException(LrErrorCodes.ConfirmationRequired,
                "Writes need confirmed: true. Show the planned change (use dryRun: true) and get approval first.");

        if (_needsReadbackReason is { } why)
            throw new ToolException(LrErrorCodes.ReadbackRequired,
                $"A previous write may or may not have applied ({why}). Call lr_get_values for the affected parameters before writing again.");

        if (!req.SkipPhotoCheck)
        {
            if (string.IsNullOrWhiteSpace(req.ExpectedPhoto))
                throw new ToolException(LrErrorCodes.PhotoMismatch,
                    "expectedPhoto is required for writes (the file name Lightroom shows, e.g. DSC_8750). lr_get_status reports the current photo.");
            if (currentPhoto is null)
                throw new ToolException(LrErrorCodes.PhotoMismatch,
                    "Lightroom did not report the current photo, so expectedPhoto cannot be verified. Pass skipPhotoCheck: true only after confirming the photo on screen.",
                    new Dictionary<string, object?> { ["expectedPhoto"] = req.ExpectedPhoto });
            if (!PhotoMatches(req.ExpectedPhoto, currentPhoto))
                throw new ToolException(LrErrorCodes.PhotoMismatch,
                    $"The current photo is '{currentPhoto}', not '{req.ExpectedPhoto}'. Nothing was written.",
                    new Dictionary<string, object?> { ["expectedPhoto"] = req.ExpectedPhoto, ["currentPhoto"] = currentPhoto });
        }

        if (!req.AllowExternalControllers && _runningControllers() is { Count: > 0 } running)
            throw new ToolException(LrErrorCodes.ExternalControllerActive,
                $"{string.Join(", ", running)} is running and also writes Lightroom sliders through the same API. Close it, or pass allowExternalControllers: true and leave the device untouched.",
                new Dictionary<string, object?> { ["processes"] = running });
    }

    /// <summary>Case-insensitive match on the base name, so "DSC_8750" matches "DSC_8750-DxO_DeepPRIME XD3.dng".</summary>
    public static bool PhotoMatches(string expected, string current)
    {
        static string Norm(string s) => Path.GetFileNameWithoutExtension(s.Trim()).ToLowerInvariant();
        var e = Norm(expected);
        var c = Norm(current);
        return c == e || c.StartsWith(e + "-", StringComparison.Ordinal) || c.StartsWith(e + "_", StringComparison.Ordinal) ||
               c.StartsWith(e + " ", StringComparison.Ordinal) || current.Trim().Equals(expected.Trim(), StringComparison.OrdinalIgnoreCase);
    }

    private static IReadOnlyList<string> DetectExternalControllers()
    {
        var found = new List<string>();
        foreach (var name in ExternalControllerProcesses)
        {
            var procs = Process.GetProcessesByName(name);
            if (procs.Length > 0)
                found.Add(name + ".exe");
            foreach (var p in procs)
                p.Dispose();
        }
        return found;
    }
}

public sealed record WriteRequest(
    bool Confirmed,
    string? ExpectedPhoto,
    bool SkipPhotoCheck = false,
    bool AllowExternalControllers = false);
