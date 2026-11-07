using System.Collections.Concurrent;
using System.Text.Json.Nodes;
using WinGuiMcp.Common;

namespace LightroomMcp.Controller;

/// <summary>getRange reply: [min, max, precision, smallIncrement, largeIncrement].</summary>
public sealed record ParamRange(double Min, double Max, int Precision, double SmallIncrement, double LargeIncrement)
{
    public static ParamRange? TryParse(JsonNode? node)
    {
        if (node is not JsonArray { Count: >= 2 } a)
            return null;
        static double D(JsonNode? n, double fallback) => n is null ? fallback : n.GetValue<double>();
        return new ParamRange(D(a[0], 0), D(a[1], 0), (int)D(a.Count > 2 ? a[2] : null, 2),
            D(a.Count > 3 ? a[3] : null, 0), D(a.Count > 4 ? a[4] : null, 0));
    }

    public double Clamp(double v) => Math.Min(Max, Math.Max(Min, v));

    /// <summary>
    /// Removes float32 noise from a read-back (-10.000000149011612 → -10, 0.8500000238 → 0.85) without
    /// coarsening a value that was set deliberately: at least 4 decimals are kept, more when the reported
    /// precision or small increment needs them. (Rounding to display precision would turn 0.0125 into 0.013.)
    /// </summary>
    public double Round(double v)
    {
        var digits = Math.Max(4, Math.Max(Precision, DecimalsOf(SmallIncrement)));
        return Math.Round(v, Math.Clamp(digits, 0, 6), MidpointRounding.AwayFromZero);
    }

    public double Tolerance => Math.Max(Math.Pow(10, -Math.Max(Precision, DecimalsOf(SmallIncrement))) / 2, 1e-6);

    private static int DecimalsOf(double v)
    {
        if (v <= 0) return 0;
        for (var d = 0; d <= 6; d++)
            if (Math.Abs(v * Math.Pow(10, d) - Math.Round(v * Math.Pow(10, d))) < 1e-9)
                return d;
        return 6;
    }
}

/// <summary>Caches parameter ranges for the life of the connection (they do not change per photo).</summary>
public sealed class ParamCatalog
{
    private readonly LrSession _session;
    private readonly ConcurrentDictionary<string, ParamRange> _ranges = new(StringComparer.Ordinal);

    public ParamCatalog(LrSession session) => _session = session;

    public async Task<ParamRange> GetRangeAsync(string parameter, CancellationToken ct)
    {
        if (_ranges.TryGetValue(parameter, out var cached))
            return cached;
        var reply = await _session.CallAsync("getRange", new JsonArray(parameter), ct: ct).ConfigureAwait(false);
        var range = reply.Success ? ParamRange.TryParse(reply.Response) : null;
        if (range is null)
            throw new ToolException(LrErrorCodes.UnknownParameter,
                $"Lightroom has no range for '{parameter}'. Use lr_list_parameters for valid Camera Raw ids (e.g. Exposure2012, LocalExposure2012).",
                new Dictionary<string, object?> { ["parameter"] = parameter, ["response"] = reply.Response?.ToJsonString() });
        _ranges[parameter] = range;
        return range;
    }

    public async Task<double?> GetValueAsync(string parameter, CancellationToken ct)
    {
        var reply = await _session.CallAsync("getValue", new JsonArray(parameter), ct: ct).ConfigureAwait(false);
        if (!reply.Success)
            return null;
        var node = reply.Response is JsonArray { Count: > 0 } a ? a[0] : reply.Response;
        if (node is null)
            return null;
        try
        {
            return node.GetValue<double>();
        }
        catch (Exception)
        {
            return double.TryParse(node.ToString(), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var d) ? d : null;
        }
    }

    public void Invalidate() => _ranges.Clear();
}
