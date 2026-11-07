using System.Collections.Concurrent;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json.Nodes;

namespace LightroomMcp.Controller;

public sealed record ControllerReply(string RequestId, bool Success, JsonNode? Response);

/// <summary>A response that arrived after the first one for the same request (observer push).</summary>
public sealed record ControllerPush(string RequestId, bool Success, JsonNode? Response, DateTimeOffset ReceivedUtc);

public interface ILrController : IAsyncDisposable
{
    bool IsConnected { get; }
    Task ConnectAsync(Uri endpoint, CancellationToken ct);
    /// <summary>Sends {requestId, object?, message, params} and waits for the first response.</summary>
    Task<ControllerReply> CallAsync(string message, JsonArray? args = null, string? objectHandle = null,
        TimeSpan? timeout = null, CancellationToken ct = default);
    event EventHandler<ControllerPush>? Pushed;
}

/// <summary>
/// Client for Adobe's Lightroom Controller API (Lightroom Desktop 9.x, "Enable external controllers").
/// Protocol as embedded in lightroom.exe 9.5.1:
///   request  {"requestId":"&lt;guid&gt;","object":"&lt;handle, omitted = root&gt;","message":"&lt;op&gt;","params":[...]}
///   response {"requestId":"&lt;guid&gt;","success":bool,"response":...}  — "each request can be served by one or many responses".
/// The first response completes the call; later ones for the same id are raised as <see cref="Pushed"/>.
/// </summary>
public sealed class ControllerClient : ILrController
{
    public static readonly TimeSpan DefaultTimeout = TimeSpan.FromSeconds(10);

    private readonly ConcurrentDictionary<string, TaskCompletionSource<ControllerReply>> _pending = new();
    private readonly SemaphoreSlim _sendLock = new(1, 1);
    private ClientWebSocket? _socket;
    private CancellationTokenSource? _loopCts;
    private Task? _receiveLoop;

    public event EventHandler<ControllerPush>? Pushed;
    public bool IsConnected => _socket?.State == WebSocketState.Open;

    public async Task ConnectAsync(Uri endpoint, CancellationToken ct)
    {
        await DisposeSocketAsync().ConfigureAwait(false);
        var socket = new ClientWebSocket();
        await socket.ConnectAsync(endpoint, ct).ConfigureAwait(false);
        _socket = socket;
        _loopCts = new CancellationTokenSource();
        _receiveLoop = Task.Run(() => ReceiveLoopAsync(socket, _loopCts.Token));
    }

    public async Task<ControllerReply> CallAsync(string message, JsonArray? args = null, string? objectHandle = null,
        TimeSpan? timeout = null, CancellationToken ct = default)
    {
        var socket = _socket;
        if (socket is null || socket.State != WebSocketState.Open)
            throw new InvalidOperationException("Controller is not connected.");

        var requestId = Guid.NewGuid().ToString();
        var request = new JsonObject { ["requestId"] = requestId };
        if (objectHandle is not null)
            request["object"] = objectHandle;
        else if (message == "register")
            request["object"] = null; // the documented register call sends an explicit null object
        request["message"] = message;
        request["params"] = args ?? new JsonArray();

        var tcs = new TaskCompletionSource<ControllerReply>(TaskCreationOptions.RunContinuationsAsynchronously);
        _pending[requestId] = tcs;
        try
        {
            var bytes = Encoding.UTF8.GetBytes(request.ToJsonString());
            await _sendLock.WaitAsync(ct).ConfigureAwait(false);
            try
            {
                await socket.SendAsync(bytes, WebSocketMessageType.Text, endOfMessage: true, ct).ConfigureAwait(false);
            }
            finally
            {
                _sendLock.Release();
            }

            using var timeoutCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            timeoutCts.CancelAfter(timeout ?? DefaultTimeout);
            await using (timeoutCts.Token.Register(() => tcs.TrySetCanceled(timeoutCts.Token)))
            {
                try
                {
                    return await tcs.Task.ConfigureAwait(false);
                }
                catch (OperationCanceledException) when (!ct.IsCancellationRequested)
                {
                    throw new TimeoutException($"Lightroom did not answer '{message}' within {(timeout ?? DefaultTimeout).TotalSeconds:0.#} s.");
                }
            }
        }
        finally
        {
            _pending.TryRemove(requestId, out _);
        }
    }

    private async Task ReceiveLoopAsync(ClientWebSocket socket, CancellationToken ct)
    {
        var buffer = new byte[64 * 1024];
        using var message = new MemoryStream();
        try
        {
            while (!ct.IsCancellationRequested && socket.State == WebSocketState.Open)
            {
                var result = await socket.ReceiveAsync(buffer, ct).ConfigureAwait(false);
                if (result.MessageType == WebSocketMessageType.Close)
                    break;
                message.Write(buffer, 0, result.Count);
                if (!result.EndOfMessage)
                    continue;

                var text = Encoding.UTF8.GetString(message.GetBuffer(), 0, (int)message.Length);
                message.SetLength(0);
                Dispatch(text);
            }
        }
        catch (OperationCanceledException)
        {
        }
        catch (WebSocketException)
        {
        }
        finally
        {
            foreach (var (_, tcs) in _pending)
                tcs.TrySetException(new IOException("Lightroom controller connection closed."));
        }
    }

    internal void Dispatch(string text)
    {
        JsonObject? obj;
        try
        {
            obj = JsonNode.Parse(text) as JsonObject;
        }
        catch (System.Text.Json.JsonException)
        {
            return;
        }
        if (obj is null || obj["requestId"]?.GetValue<string>() is not { } id)
            return;

        var success = obj["success"]?.GetValue<bool>() ?? false;
        var response = obj["response"]?.DeepClone();
        if (_pending.TryRemove(id, out var tcs))
        {
            tcs.TrySetResult(new ControllerReply(id, success, response));
            return;
        }
        Pushed?.Invoke(this, new ControllerPush(id, success, response, DateTimeOffset.UtcNow));
    }

    private async Task DisposeSocketAsync()
    {
        if (_loopCts is not null)
            await _loopCts.CancelAsync().ConfigureAwait(false);
        if (_socket is { State: WebSocketState.Open } open)
        {
            try
            {
                using var closeCts = new CancellationTokenSource(TimeSpan.FromSeconds(2));
                await open.CloseAsync(WebSocketCloseStatus.NormalClosure, "bye", closeCts.Token).ConfigureAwait(false);
            }
            catch (Exception)
            {
            }
        }
        _socket?.Dispose();
        _socket = null;
        if (_receiveLoop is not null)
        {
            try { await _receiveLoop.ConfigureAwait(false); } catch (Exception) { }
        }
        _loopCts?.Dispose();
        _loopCts = null;
    }

    public async ValueTask DisposeAsync() => await DisposeSocketAsync().ConfigureAwait(false);
}
