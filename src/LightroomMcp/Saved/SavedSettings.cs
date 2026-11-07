using System.Globalization;
using System.Xml.Linq;

namespace LightroomMcp.Saved;

public sealed record SavedCorrection(
    string? Name,
    string? Active,
    double? Amount,
    IReadOnlyDictionary<string, double> Values,
    IReadOnlyList<IReadOnlyDictionary<string, string>> Masks);

public sealed record SavedSettings(
    string File,
    string Sha256,
    DateTimeOffset SavedUtc,
    IReadOnlyDictionary<string, string?> Global,
    IReadOnlyList<SavedCorrection> Corrections)
{
    public SavedCorrection? FindCorrection(string name) =>
        Corrections.FirstOrDefault(c => string.Equals(c.Name, name, StringComparison.OrdinalIgnoreCase));
}

/// <summary>
/// Parses a Lightroom Desktop develop-settings XMP (the files in Data\&lt;catalog&gt;\settings\, named by SHA-256).
/// Mask ("Correction") values are stored on a different scale from the sliders: LocalExposure2012 is EV / 4,
/// every other Local* value is slider / 100. <see cref="Parse"/> returns slider units.
/// Ported from image-scoring-skills' lr_settings_readback.py (session d606a64e, 2026-11-07).
/// </summary>
public static class XmpCrsParser
{
    public static readonly XNamespace Crs = "http://ns.adobe.com/camera-raw-settings/1.0/";
    public static readonly XNamespace Rdf = "http://www.w3.org/1999/02/22-rdf-syntax-ns#";

    public static readonly string[] GlobalKeys =
    [
        "Temperature", "Tint", "Exposure2012", "Contrast2012", "Highlights2012", "Shadows2012", "Whites2012",
        "Blacks2012", "Vibrance", "Saturation", "Texture", "Clarity2012", "Dehaze", "PostCropVignetteAmount",
        "Sharpness", "SharpenRadius", "SharpenDetail", "SharpenEdgeMasking", "LuminanceSmoothing",
        "LuminanceNoiseReductionDetail", "ColorNoiseReduction"
    ];

    private static readonly HashSet<string> SkipLocal = new(StringComparer.Ordinal)
        { "CurveRefineSaturation", "InputDigest", "InputDigestVersion" };

    private static readonly string[] MaskAttributes = ["What", "MaskName", "MaskInverted", "Feather"];

    /// <summary>Slider value → stored mask value (inverse of the read scaling).</summary>
    public static double ToStoredLocal(string localKeyWithoutPrefix, double sliderValue) =>
        localKeyWithoutPrefix == "Exposure2012" ? sliderValue / 4 : sliderValue / 100;

    public static SavedSettings Parse(string path)
    {
        var doc = XDocument.Load(path);
        var descriptions = doc.Descendants(Rdf + "Description").ToList();
        if (descriptions.Count == 0)
            throw new InvalidDataException($"{path} has no rdf:Description; not a Camera Raw settings XMP.");

        var top = descriptions[0];
        var global = new Dictionary<string, string?>(StringComparer.Ordinal);
        foreach (var key in GlobalKeys)
            global[key] = (string?)top.Attribute(Crs + key);

        var corrections = new List<SavedCorrection>();
        foreach (var desc in descriptions)
        {
            if ((string?)desc.Attribute(Crs + "What") != "Correction")
                continue;

            var values = new Dictionary<string, double>(StringComparer.Ordinal);
            foreach (var attr in desc.Attributes())
            {
                if (attr.Name.Namespace != Crs || !attr.Name.LocalName.StartsWith("Local", StringComparison.Ordinal))
                    continue;
                var key = attr.Name.LocalName["Local".Length..];
                if (SkipLocal.Contains(key) || !TryNum(attr.Value, out var raw) || raw == 0)
                    continue;
                values[key] = Math.Round(raw * (key == "Exposure2012" ? 4 : 100), 4);
            }

            var masks = new List<IReadOnlyDictionary<string, string>>();
            foreach (var li in desc.Descendants(Rdf + "li"))
            {
                var what = (string?)li.Attribute(Crs + "What");
                if (what is null || !what.StartsWith("Mask/", StringComparison.Ordinal))
                    continue;
                var m = new Dictionary<string, string>(StringComparer.Ordinal);
                foreach (var a in MaskAttributes)
                    if ((string?)li.Attribute(Crs + a) is { } v)
                        m[a] = v;
                masks.Add(m);
            }

            corrections.Add(new SavedCorrection(
                (string?)desc.Attribute(Crs + "CorrectionName"),
                (string?)desc.Attribute(Crs + "CorrectionActive"),
                TryNum((string?)desc.Attribute(Crs + "CorrectionAmount"), out var amount) ? amount : null,
                values,
                masks));
        }

        var fileName = System.IO.Path.GetFileName(path);
        var sha = IsSha256(fileName) ? fileName.ToLowerInvariant() : Sha256Of(path);
        return new SavedSettings(path, sha, new DateTimeOffset(System.IO.File.GetLastWriteTimeUtc(path), TimeSpan.Zero), global, corrections);
    }

    /// <summary>Numeric value of a global key, accepting "+0.20" style strings.</summary>
    public static double? GlobalNumber(SavedSettings s, string key) =>
        s.Global.TryGetValue(key, out var raw) && TryNum(raw, out var v) ? v : null;

    internal static bool TryNum(string? raw, out double value) =>
        double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out value);

    internal static bool IsSha256(string name) =>
        name.Length == 64 && name.All(Uri.IsHexDigit);

    internal static string Sha256Of(string path)
    {
        using var stream = System.IO.File.OpenRead(path);
        return Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(stream)).ToLowerInvariant();
    }
}
