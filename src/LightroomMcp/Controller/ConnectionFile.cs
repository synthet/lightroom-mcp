using System.Text.Json.Nodes;

namespace LightroomMcp.Controller;

/// <summary>
/// Lightroom Desktop writes its controller WebSocket port to
/// %LOCALAPPDATA%\Adobe\Lightroom CC\Connections\connections.json, e.g. {"port":7682}.
/// The default is 7682; Lightroom picks another port when that one is taken.
/// </summary>
public static class ConnectionFile
{
    public const int DefaultPort = 7682;

    public static string DefaultPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "Adobe", "Lightroom CC", "Connections", "connections.json");

    public static int? TryReadPort(string? path = null)
    {
        path ??= DefaultPath;
        try
        {
            if (!File.Exists(path))
                return null;
            var node = JsonNode.Parse(File.ReadAllText(path));
            var port = node?["port"]?.GetValue<int>();
            return port is > 0 and < 65536 ? port : null;
        }
        catch (Exception)
        {
            return null;
        }
    }
}
