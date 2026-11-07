using System.Text.Json.Nodes;
using WinGuiMcp.Common;

namespace LightroomMcp.Controller;

public sealed class LrSessionOptions
{
    public string AppName { get; set; } = "lightroom-mcp";
    public string AppVersion { get; set; } = typeof(LrSession).Assembly.GetName().Version?.ToString(3) ?? "0.1.0";
    public string? ConnectionFilePath { get; set; }
    public string IdentityPath { get; set; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "LightroomMcp", "client.json");
    /// <summary>How long a first-time register waits for the user to click Allow in Lightroom.</summary>
    public TimeSpan ApprovalTimeout { get; set; } = TimeSpan.FromSeconds(60);
}

/// <summary>
/// Owns the single controller connection: reads the port, connects, registers (reusing the stored
/// client GUID so Lightroom skips its approval dialog), and reconnects after Lightroom restarts.
/// The client GUID is a credential-like token: it is kept in <see cref="LrSessionOptions.IdentityPath"/>
/// and never returned by tools or written to receipts.
/// </summary>
public sealed class LrSession : IAsyncDisposable
{
    private readonly LrSessionOptions _options;
    private readonly Func<ILrController> _factory;
    private readonly SemaphoreSlim _gate = new(1, 1);
    private ILrController? _client;

    public LrSession(LrSessionOptions options, Func<ILrController>? factory = null)
    {
        _options = options;
        _factory = factory ?? (() => new ControllerClient());
    }

    public string? LightroomVersion { get; private set; }
    public int? Port { get; private set; }
    public bool IsRegistered => _client?.IsConnected == true && LightroomVersion is not null;
    public event EventHandler<ControllerPush>? Pushed;

    public async Task<ILrController> EnsureConnectedAsync(CancellationToken ct)
    {
        if (_client is { IsConnected: true } live && LightroomVersion is not null)
            return live;

        await _gate.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            if (_client is { IsConnected: true } again && LightroomVersion is not null)
                return again;

            var port = ConnectionFile.TryReadPort(_options.ConnectionFilePath);
            if (port is null)
                throw new ToolException(LrErrorCodes.ControllerUnavailable,
                    "Lightroom controller connection file not found. Start Lightroom Desktop and enable Preferences > Interface > Enable external controllers, then restart Lightroom.",
                    new Dictionary<string, object?> { ["connectionFile"] = _options.ConnectionFilePath ?? ConnectionFile.DefaultPath });

            if (_client is not null)
            {
                _client.Pushed -= OnPushed;
                await _client.DisposeAsync().ConfigureAwait(false);
            }
            _client = _factory();
            _client.Pushed += OnPushed;
            LightroomVersion = null;
            Port = port;

            try
            {
                await _client.ConnectAsync(new Uri($"ws://127.0.0.1:{port}"), ct).ConfigureAwait(false);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                throw new ToolException(LrErrorCodes.ControllerUnavailable,
                    $"Could not connect to the Lightroom controller on 127.0.0.1:{port}. Is Lightroom Desktop running with external controllers enabled?",
                    new Dictionary<string, object?> { ["port"] = port, ["reason"] = ex.Message });
            }

            var storedGuid = ClientIdentityStore.TryLoad(_options.IdentityPath);
            var args = new JsonArray(_options.AppName, _options.AppVersion);
            if (storedGuid is not null)
                args.Add(storedGuid);

            ControllerReply reply;
            try
            {
                reply = await _client.CallAsync("register", args, timeout: _options.ApprovalTimeout, ct: ct).ConfigureAwait(false);
            }
            catch (TimeoutException)
            {
                throw new ToolException(LrErrorCodes.ApprovalPending,
                    "Lightroom is showing a dialog asking whether to allow lightroom-mcp. Click Allow in Lightroom, then call lr_connect again.",
                    new Dictionary<string, object?> { ["firstRegistration"] = storedGuid is null });
            }

            if (!reply.Success || reply.Response is not JsonArray { Count: >= 2 } granted)
                throw new ToolException(LrErrorCodes.ApprovalDenied,
                    "Lightroom refused the registration. Re-run lr_connect and click Allow, or check Preferences > Interface.",
                    new Dictionary<string, object?> { ["response"] = reply.Response?.ToJsonString() });

            var guid = granted[0]?.GetValue<string>();
            if (!string.IsNullOrWhiteSpace(guid) && guid != storedGuid)
                ClientIdentityStore.Save(_options.IdentityPath, guid);
            LightroomVersion = granted[1]?.ToString();
            return _client;
        }
        finally
        {
            _gate.Release();
        }
    }

    public async Task<ControllerReply> CallAsync(string message, JsonArray? args = null, string? obj = null,
        TimeSpan? timeout = null, CancellationToken ct = default)
    {
        var client = await EnsureConnectedAsync(ct).ConfigureAwait(false);
        try
        {
            return await client.CallAsync(message, args, obj, timeout, ct).ConfigureAwait(false);
        }
        catch (TimeoutException ex)
        {
            throw new ToolException(ErrorCodes.Timeout, ex.Message, new Dictionary<string, object?> { ["message"] = message });
        }
        catch (IOException ex)
        {
            LightroomVersion = null;
            throw new ToolException(LrErrorCodes.ControllerUnavailable, ex.Message, new Dictionary<string, object?> { ["message"] = message });
        }
    }

    /// <summary>Calls and requires success, returning the response payload.</summary>
    public async Task<JsonNode?> CallOkAsync(string message, JsonArray? args = null, string? obj = null,
        TimeSpan? timeout = null, CancellationToken ct = default)
    {
        var reply = await CallAsync(message, args, obj, timeout, ct).ConfigureAwait(false);
        if (!reply.Success)
            throw new ToolException(LrErrorCodes.ControllerCallFailed, $"Lightroom rejected '{message}'.",
                new Dictionary<string, object?> { ["message"] = message, ["response"] = reply.Response?.ToJsonString() });
        return reply.Response;
    }

    private void OnPushed(object? sender, ControllerPush push) => Pushed?.Invoke(this, push);

    public async ValueTask DisposeAsync()
    {
        if (_client is not null)
            await _client.DisposeAsync().ConfigureAwait(false);
    }
}

internal static class ClientIdentityStore
{
    public static string? TryLoad(string path)
    {
        try
        {
            return File.Exists(path) ? JsonNode.Parse(File.ReadAllText(path))?["clientGuid"]?.GetValue<string>() : null;
        }
        catch (Exception)
        {
            return null;
        }
    }

    public static void Save(string path, string guid)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var tmp = path + ".tmp";
        File.WriteAllText(tmp, new JsonObject { ["clientGuid"] = guid, ["savedUtc"] = DateTimeOffset.UtcNow.ToString("O") }.ToJsonString());
        File.Move(tmp, path, overwrite: true);
    }
}
