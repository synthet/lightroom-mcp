using System.Text;

namespace LightroomMcp.Saved;

/// <summary>
/// Locates Lightroom Desktop's develop-settings store: %LOCALAPPDATA%\Adobe\Lightroom CC\Data\&lt;catalog-id&gt;\settings.
/// The folder is shared by every photo, so "the newest file" is only yours straight after you save; callers
/// pass <c>since</c> (the moment before the save) and should confirm the hash in the catalog.
/// </summary>
public sealed class SettingsFolder
{
    public SettingsFolder(string? dataRoot = null) =>
        DataRoot = dataRoot ?? Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Adobe", "Lightroom CC", "Data");

    public string DataRoot { get; }

    /// <summary>The catalog directory (Data\&lt;id&gt;) whose settings folder changed most recently.</summary>
    public string? FindCatalogDir()
    {
        if (!Directory.Exists(DataRoot))
            return null;
        return Directory.EnumerateDirectories(DataRoot)
            .Where(d => Directory.Exists(Path.Combine(d, "settings")) && File.Exists(Path.Combine(d, "Managed Catalog.mcat")))
            .OrderByDescending(d => Directory.GetLastWriteTimeUtc(Path.Combine(d, "settings")))
            .FirstOrDefault();
    }

    public string? FindSettingsDir() => FindCatalogDir() is { } c ? Path.Combine(c, "settings") : null;

    /// <summary>Newest settings XMP, optionally only files with masks and written at or after <paramref name="sinceUtc"/>.</summary>
    public string? PickNewest(string settingsDir, bool requireMasks = false, DateTimeOffset? sinceUtc = null)
    {
        foreach (var path in ListNewestFirst(settingsDir))
        {
            var mtime = new DateTimeOffset(File.GetLastWriteTimeUtc(path), TimeSpan.Zero);
            if (sinceUtc is { } since && mtime < since)
                return null;
            if (LooksLikeSettings(path, requireMasks))
                return path;
        }
        return null;
    }

    public static IEnumerable<string> ListNewestFirst(string settingsDir) =>
        Directory.Exists(settingsDir)
            ? Directory.EnumerateFiles(settingsDir).OrderByDescending(File.GetLastWriteTimeUtc)
            : [];

    internal static bool LooksLikeSettings(string path, bool requireMasks)
    {
        var text = Encoding.UTF8.GetString(File.ReadAllBytes(path));
        if (!text.Contains("crs:", StringComparison.Ordinal) || !text.Contains("x:xmpmeta", StringComparison.Ordinal))
            return false;
        return !requireMasks || text.Contains("crs:CorrectionName=", StringComparison.Ordinal);
    }
}
