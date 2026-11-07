using System.Text.Json.Nodes;
using LightroomMcp.Controller;
using WinGuiMcp.Common;

namespace LightroomMcp.Tests;

public sealed class ControllerTests : IAsyncLifetime
{
    private FakeLightroomServer _server = null!;
    private string _dir = null!;

    public async Task InitializeAsync()
    {
        _server = await FakeLightroomServer.StartAsync();
        _dir = Directory.CreateTempSubdirectory("lrmcp-").FullName;
    }

    public async Task DisposeAsync()
    {
        await _server.DisposeAsync();
        Directory.Delete(_dir, true);
    }

    private LrSession NewSession(TimeSpan? approval = null) => new(new LrSessionOptions
    {
        ConnectionFilePath = _server.WriteConnectionFile(_dir),
        IdentityPath = Path.Combine(_dir, "client.json"),
        ApprovalTimeout = approval ?? TimeSpan.FromSeconds(5)
    });

    [Fact]
    public async Task Register_StoresGuid_AndReusesItOnReconnect()
    {
        await using (var first = NewSession())
        {
            await first.EnsureConnectedAsync(CancellationToken.None);
            Assert.Equal("9.5.1", first.LightroomVersion);
        }

        var register1 = _server.Received.First(r => r["message"]!.GetValue<string>() == "register");
        Assert.Equal(2, register1["params"]!.AsArray().Count);           // no GUID the first time
        Assert.True(register1.ContainsKey("object"));                    // documented explicit null object
        Assert.Contains(_server.GrantedGuid, File.ReadAllText(Path.Combine(_dir, "client.json")));

        await using (var second = NewSession())
            await second.EnsureConnectedAsync(CancellationToken.None);

        var register2 = _server.Received.Where(r => r["message"]!.GetValue<string>() == "register").Last();
        Assert.Equal(_server.GrantedGuid, register2["params"]![2]!.GetValue<string>());
    }

    [Fact]
    public async Task Register_WithoutApproval_ReportsApprovalPending()
    {
        _server.ApproveRegistration = false;
        await using var session = NewSession(TimeSpan.FromMilliseconds(300));
        var ex = await Assert.ThrowsAsync<ToolException>(() => session.EnsureConnectedAsync(CancellationToken.None));
        Assert.Equal(LrErrorCodes.ApprovalPending, ex.Error.Code);
        Assert.False(File.Exists(Path.Combine(_dir, "client.json")));
    }

    [Fact]
    public async Task MissingConnectionFile_ReportsControllerUnavailable()
    {
        await using var session = new LrSession(new LrSessionOptions
        {
            ConnectionFilePath = Path.Combine(_dir, "absent.json"),
            IdentityPath = Path.Combine(_dir, "client.json")
        });
        var ex = await Assert.ThrowsAsync<ToolException>(() => session.EnsureConnectedAsync(CancellationToken.None));
        Assert.Equal(LrErrorCodes.ControllerUnavailable, ex.Error.Code);
    }

    [Fact]
    public async Task ExtraResponsesForOneRequest_ArePushedNotDropped()
    {
        await using var session = NewSession();
        var pushes = new List<ControllerPush>();
        var got = new TaskCompletionSource();
        session.Pushed += (_, p) => { lock (pushes) pushes.Add(p); got.TrySetResult(); };

        var reply = await session.CallAsync("addAdjustmentChangeObserver", new JsonArray("Exposure2012"));
        Assert.True(reply.Success);
        await _server.PushAsync(reply.RequestId, new JsonObject { ["adjustments.Exposure2012"] = new JsonObject { ["newValue"] = 0.5 } });

        await got.Task.WaitAsync(TimeSpan.FromSeconds(5));
        Assert.Equal(reply.RequestId, Assert.Single(pushes).RequestId);
    }

    [Theory]
    [InlineData(-10.000000149011612, 0, 0.01, -10.0)]
    [InlineData(0.8500000238418579, 2, 0.025, 0.85)]
    [InlineData(0.0125, 2, 0.025, 0.0125)]
    public void ParamRange_RoundsFloatReadbacks(double raw, int precision, double small, double expected)
    {
        var range = new ParamRange(-100, 100, precision, small, 1);
        Assert.Equal(expected, range.Round(raw), 6);
    }

    [Fact]
    public void ParamRange_ParsesObservedGetRangeReply()
    {
        var r = ParamRange.TryParse(JsonNode.Parse("[-4,4,2,0.025,0.0825]"))!;
        Assert.Equal((-4d, 4d, 2, 0.025, 0.0825), (r.Min, r.Max, r.Precision, r.SmallIncrement, r.LargeIncrement));
        Assert.Equal(4, r.Clamp(9));
    }
}
