using System.Collections.Concurrent;
using System.Net;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json.Nodes;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace LightroomMcp.Tests;

/// <summary>
/// In-process stand-in for Lightroom Desktop's controller WebSocket, speaking the protocol embedded in
/// lightroom.exe 9.5.1. Replies use the shapes observed in TourBox's log (register → [guid, "9.5.1"],
/// getRange → [min,max,precision,small,large], observers → {}).
/// </summary>
public sealed class FakeLightroomServer : IAsyncDisposable
{
    private readonly WebApplication _app;
    public ConcurrentQueue<JsonObject> Received { get; } = new();
    public ConcurrentDictionary<string, double> Values { get; } = new(StringComparer.Ordinal);
    public ConcurrentDictionary<string, JsonArray> Ranges { get; } = new(StringComparer.Ordinal);
    public string GrantedGuid { get; set; } = "11111111-2222-3333-4444-555555555555";
    public string? CurrentPhoto { get; set; } = "DSC_8750-DxO_DeepPRIME XD3.dng";
    /// <summary>When false, register gets no reply (the user hasn't clicked Allow yet).</summary>
    public bool ApproveRegistration { get; set; } = true;
    /// <summary>When true, setValue reports success but does not change the value (simulates interference).</summary>
    public bool IgnoreWrites { get; set; }
    public int Port { get; }
    /// <summary>When set, showView("square_grid") writes this settings XMP (named by its SHA-256) like Lightroom's save.</summary>
    public (string Dir, string Xmp)? SaveOnGrid { get; set; }
    public List<string> Views { get; } = [];
    private WebSocket? _socket;

    private FakeLightroomServer(WebApplication app, int port)
    {
        _app = app;
        Port = port;
    }

    public static async Task<FakeLightroomServer> StartAsync()
    {
        var builder = WebApplication.CreateSlimBuilder();
        builder.Logging.ClearProviders();
        builder.WebHost.UseKestrel(o => o.Listen(IPAddress.Loopback, 0));
        var app = builder.Build();
        app.UseWebSockets();
        FakeLightroomServer? self = null;
        app.Run(async ctx =>
        {
            if (!ctx.WebSockets.IsWebSocketRequest)
            {
                ctx.Response.StatusCode = 400;
                return;
            }
            using var ws = await ctx.WebSockets.AcceptWebSocketAsync();
            await self!.ServeAsync(ws, ctx.RequestAborted);
        });
        await app.StartAsync();
        var address = app.Services.GetRequiredService<IServer>().Features.Get<IServerAddressesFeature>()!.Addresses.First();
        self = new FakeLightroomServer(app, new Uri(address).Port);
        self.Ranges["Exposure2012"] = new JsonArray(-5, 5, 2, 0.025, 0.0825);
        self.Ranges["LocalExposure2012"] = new JsonArray(-4, 4, 2, 0.025, 0.0825);
        foreach (var p in new[] { "Contrast2012", "Highlights2012", "Shadows2012", "LocalShadows2012", "LocalTexture" })
            self.Ranges[p] = new JsonArray(-100, 100, 0, 0.01, 20);
        return self;
    }

    public string WriteConnectionFile(string dir)
    {
        var path = Path.Combine(dir, "connections.json");
        File.WriteAllText(path, $"{{\"port\":{Port}}}");
        return path;
    }

    /// <summary>Pushes an extra response for an earlier request (an adjustment observer notification).</summary>
    public Task PushAsync(string requestId, JsonNode response) =>
        SendAsync(new JsonObject { ["requestId"] = requestId, ["success"] = true, ["response"] = response });

    public IEnumerable<string> Messages => Received.Select(r => r["message"]!.GetValue<string>());

    private async Task ServeAsync(WebSocket ws, CancellationToken ct)
    {
        _socket = ws;
        var buffer = new byte[64 * 1024];
        while (ws.State == WebSocketState.Open && !ct.IsCancellationRequested)
        {
            WebSocketReceiveResult r;
            try { r = await ws.ReceiveAsync(buffer, ct); }
            catch (Exception) { break; }
            if (r.MessageType == WebSocketMessageType.Close)
                break;
            var req = JsonNode.Parse(Encoding.UTF8.GetString(buffer, 0, r.Count))!.AsObject();
            Received.Enqueue(req);
            var id = req["requestId"]!.GetValue<string>();
            var message = req["message"]!.GetValue<string>();
            var args = req["params"]?.AsArray() ?? [];
            var (ok, response, reply) = Handle(message, args);
            if (reply)
                await SendAsync(new JsonObject { ["response"] = response, ["success"] = ok, ["requestId"] = id });
        }
    }

    private (bool Ok, JsonNode? Response, bool Reply) Handle(string message, JsonArray args)
    {
        switch (message)
        {
            case "register":
                return ApproveRegistration ? (true, new JsonArray(GrantedGuid, "9.5.1"), true) : (false, null, false);
            case "getRange":
                var p = args[0]!.GetValue<string>();
                return Ranges.TryGetValue(p, out var range) ? (true, range.DeepClone(), true) : (false, null, true);
            case "getValue":
                var key = args[0]!.GetValue<string>();
                return Ranges.ContainsKey(key) ? (true, new JsonArray(Values.GetValueOrDefault(key) + 1e-9), true) : (false, null, true);
            case "setValue":
                if (!IgnoreWrites)
                    Values[args[0]!.GetValue<string>()] = args[1]!.GetValue<double>();
                return (true, new JsonObject(), true);
            case "getActiveImageName":
                return CurrentPhoto is null ? (false, null, true) : (true, new JsonArray(CurrentPhoto), true);
            case "showView":
                var view = args[0]!.GetValue<string>();
                Views.Add(view);
                if (view == "square_grid" && SaveOnGrid is { } save)
                {
                    var sha = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(Encoding.UTF8.GetBytes(save.Xmp))).ToLowerInvariant();
                    File.WriteAllText(Path.Combine(save.Dir, sha), save.Xmp);
                }
                return (true, new JsonObject(), true);
            case "getRating":
                return (true, new JsonArray(5), true);
            case "getColorLabel":
                return (true, new JsonArray("blue"), true);
            case "addAdjustmentChangeObserver":
                return (true, new JsonObject(), true);
            default:
                return (false, new JsonObject { ["error"] = "unknown message" }, true);
        }
    }

    private async Task SendAsync(JsonObject obj)
    {
        if (_socket is { State: WebSocketState.Open } ws)
            await ws.SendAsync(Encoding.UTF8.GetBytes(obj.ToJsonString()), WebSocketMessageType.Text, true, CancellationToken.None);
    }

    public async ValueTask DisposeAsync()
    {
        await _app.StopAsync();
        await _app.DisposeAsync();
    }
}
