using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using LightroomMcp.Controller;
using LightroomMcp.Safety;
using LightroomMcp.Saved;
using LightroomMcp.Tools;
using Microsoft.Data.Sqlite;
using WinGuiMcp.Capture;
using WinGuiMcp.Common;
using WinGuiMcp.Platform;

namespace LightroomMcp.Tests;

public sealed class ToolServiceTests : IAsyncLifetime
{
    private FakeLightroomServer _server = null!;
    private string _dir = null!;
    private LrSession _session = null!;
    private List<string> _externalControllers = null!;
    private LrToolService _svc = null!;
    private string _catalogDir = null!;
    private readonly List<string> _titles = [];   // never the real desktop

    public async Task InitializeAsync()
    {
        _server = await FakeLightroomServer.StartAsync();
        _dir = Directory.CreateTempSubdirectory("lrmcp-").FullName;
        _session = new LrSession(new LrSessionOptions
        {
            ConnectionFilePath = _server.WriteConnectionFile(_dir),
            IdentityPath = Path.Combine(_dir, "client.json")
        });
        _externalControllers = [];
        _catalogDir = Path.Combine(_dir, "Data", "0123456789abcdef0123456789abcdef");
        Directory.CreateDirectory(Path.Combine(_catalogDir, "settings"));
        _svc = new LrToolService(_session, new ParamCatalog(_session), new WriteGuard(() => _externalControllers),
            new SettingsFolder(Path.Combine(_dir, "Data")), new WindowEnumerator(), new WindowCapture(),
            windowTitles: () => _titles);
    }

    public async Task DisposeAsync()
    {
        await _session.DisposeAsync();
        await _server.DisposeAsync();
        SqliteConnection.ClearAllPools();
        Directory.Delete(_dir, true);
    }

    private static WriteRequest Ok(string photo = "DSC_8750") => new(Confirmed: true, ExpectedPhoto: photo);

    private static JsonObject J(object o) => JsonSerializer.SerializeToNode(o)!.AsObject();

    [Fact]
    public async Task SetValues_ClampsWritesAndReadsBack()
    {
        var result = J(await _svc.SetValuesAsync(new JsonObject { ["Exposure2012"] = 7.0, ["Shadows2012"] = 30 }, false, Ok(), false, default));

        Assert.True(result["ok"]!.GetValue<bool>());
        Assert.Equal(5.0, _server.Values["Exposure2012"]);              // clamped to getRange max
        Assert.Equal(30.0, _server.Values["Shadows2012"]);
        var exposure = result["results"]!.AsArray().First(r => r!["parameter"]!.GetValue<string>() == "Exposure2012")!;
        Assert.True(exposure["clamped"]!.GetValue<bool>());
        Assert.True(exposure["readbackOk"]!.GetValue<bool>());
        Assert.False(result["persisted"]!.GetValue<bool>());
    }

    [Fact]
    public async Task SetValues_DeltaAddsToCurrentValue()
    {
        _server.Values["LocalShadows2012"] = 10;
        await _svc.SetValuesAsync(new JsonObject { ["LocalShadows2012"] = -15 }, true, Ok(), false, default);
        Assert.Equal(-5.0, _server.Values["LocalShadows2012"]);
    }

    [Fact]
    public async Task SetValues_DryRunSendsNoSetValue()
    {
        var result = J(await _svc.SetValuesAsync(new JsonObject { ["Exposure2012"] = 0.3 }, false, new WriteRequest(false, null), true, default));
        Assert.True(result["dryRun"]!.GetValue<bool>());
        Assert.DoesNotContain("setValue", _server.Messages);
    }

    [Theory]
    [InlineData(false, "DSC_8750", LrErrorCodes.ConfirmationRequired)]
    [InlineData(true, null, LrErrorCodes.PhotoMismatch)]
    [InlineData(true, "DSC_9999", LrErrorCodes.PhotoMismatch)]
    public async Task SetValues_GuardsRefuseBeforeWriting(bool confirmed, string? photo, string code)
    {
        var ex = await Assert.ThrowsAsync<ToolException>(() =>
            _svc.SetValuesAsync(new JsonObject { ["Exposure2012"] = 0.3 }, false, new WriteRequest(confirmed, photo), false, default));
        Assert.Equal(code, ex.Error.Code);
        Assert.DoesNotContain("setValue", _server.Messages);
    }

    [Fact]
    public async Task SetValues_RefusesWhileTourBoxRuns_UnlessAllowed()
    {
        _externalControllers.Add("TourBox Console.exe");
        var ex = await Assert.ThrowsAsync<ToolException>(() =>
            _svc.SetValuesAsync(new JsonObject { ["Exposure2012"] = 0.3 }, false, Ok(), false, default));
        Assert.Equal(LrErrorCodes.ExternalControllerActive, ex.Error.Code);

        await _svc.SetValuesAsync(new JsonObject { ["Exposure2012"] = 0.3 }, false,
            new WriteRequest(true, "DSC_8750", AllowExternalControllers: true), false, default);
        Assert.Equal(0.3, _server.Values["Exposure2012"]);
    }

    [Fact]
    public async Task SetValues_ReportsReadbackMismatchWhenValueDoesNotStick()
    {
        _server.IgnoreWrites = true;
        var ex = await Assert.ThrowsAsync<ToolException>(() =>
            _svc.SetValuesAsync(new JsonObject { ["Contrast2012"] = 12 }, false, Ok(), false, default));
        Assert.Equal(LrErrorCodes.ReadbackMismatch, ex.Error.Code);
    }

    [Fact]
    public async Task SetValues_UnknownPhotoIdentity_NeedsExplicitSkip()
    {
        _server.CurrentPhoto = null;
        var ex = await Assert.ThrowsAsync<ToolException>(() =>
            _svc.SetValuesAsync(new JsonObject { ["Exposure2012"] = 0.3 }, false, Ok(), false, default));
        Assert.Equal(LrErrorCodes.PhotoMismatch, ex.Error.Code);

        await _svc.SetValuesAsync(new JsonObject { ["Exposure2012"] = 0.3 }, false,
            new WriteRequest(true, null, SkipPhotoCheck: true), false, default);
        Assert.Equal(0.3, _server.Values["Exposure2012"]);
    }

    [Fact]
    public async Task CallRaw_WriteMessagesNeedConfirmation_ReadsDoNot()
    {
        var read = J(await _svc.CallRawAsync("getRange", new JsonArray("Exposure2012"), null, new WriteRequest(false, null), default));
        Assert.True(read["readOnly"]!.GetValue<bool>());

        var ex = await Assert.ThrowsAsync<ToolException>(() =>
            _svc.CallRawAsync("resetAllDevelopAdjustments", null, null, new WriteRequest(false, null), default));
        Assert.Equal(LrErrorCodes.ConfirmationRequired, ex.Error.Code);
        Assert.DoesNotContain("resetAllDevelopAdjustments", _server.Messages);
    }

    [Fact]
    public async Task SetValues_FarOutsideRange_IsAUnitErrorNotAClamp()
    {
        _server.Ranges["Temperature"] = new JsonArray(0, 100, 1, 1, 5);   // observed live: 0..100, not Kelvin
        _server.Values["Temperature"] = 33.5;
        var ex = await Assert.ThrowsAsync<ToolException>(() =>
            _svc.SetValuesAsync(new JsonObject { ["Temperature"] = 5350 }, false, Ok(), false, default));
        Assert.Equal(ErrorCodes.InvalidArgument, ex.Error.Code);
        Assert.Contains("not Kelvin", ex.Error.Message);
        Assert.DoesNotContain("setValue", _server.Messages);
    }

    [Theory]
    [InlineData(new[] { "PreferencesDialog", "Lightroom", "Lightroom - DSC_8750-DxO_DeepPRIME XD3.dng" }, "DSC_8750-DxO_DeepPRIME XD3.dng")]
    [InlineData(new[] { "Lightroom", "Lightroom" }, null)]
    [InlineData(new[] { "Lightroom - A.dng", "Lightroom - B.dng" }, null)]
    public void PhotoFromWindowTitles_UsesTheSinglePhotoTitle(string[] titles, string? expected) =>
        Assert.Equal(expected, LrToolService.PhotoFromWindowTitles(titles));

    [Theory]
    [InlineData("DSC_8750", "DSC_8750-DxO_DeepPRIME XD3.dng", true)]
    [InlineData("dsc_8750.nef", "DSC_8750.NEF", true)]
    [InlineData("DSC_875", "DSC_8750.NEF", false)]
    [InlineData("DSC_8750", "DSC_87501.NEF", false)]
    public void PhotoMatches_UsesBaseNameNotPrefix(string expected, string current, bool match) =>
        Assert.Equal(match, WriteGuard.PhotoMatches(expected, current));

    // ------------------------------------------------------------ saved settings and catalog

    private string WriteSettings(string fixture = "settings-two-masks.xmp")
    {
        var text = File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "Fixtures", fixture));
        var sha = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(Encoding.UTF8.GetBytes(text))).ToLowerInvariant();
        var path = Path.Combine(_catalogDir, "settings", sha);
        File.WriteAllText(path, text);
        return sha;
    }

    private void WriteCatalog(string? referencedSha, bool current = true)
    {
        var path = Path.Combine(_catalogDir, "Managed Catalog.mcat");
        using var conn = new SqliteConnection($"Data Source={path};Pooling=False");
        conn.Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            CREATE TABLE docs(localDocId INTEGER PRIMARY KEY, fullDocId TEXT, winningRevSequence INTEGER);
            CREATE TABLE revs(sequence INTEGER PRIMARY KEY, localDocId INTEGER, revId TEXT, current BOOLEAN, content BLOB);
            INSERT INTO docs VALUES (1, 'fedcba9876543210fedcba9876543210', 7);
            INSERT INTO revs VALUES (7, 1, '1-a', $cur, $content);
            """;
        cmd.Parameters.AddWithValue("$cur", current ? 1 : 0);
        cmd.Parameters.AddWithValue("$content", Encoding.UTF8.GetBytes($"\u0082¤type¥asset xmpCameraRaw {referencedSha ?? "none"} DSC_8750"));
        cmd.ExecuteNonQuery();
    }

    [Fact]
    public void XmpParser_ScalesMaskValuesToSliderUnits()
    {
        var sha = WriteSettings();
        var s = XmpCrsParser.Parse(Path.Combine(_catalogDir, "settings", sha));
        Assert.Equal("+0.20", s.Global["Exposure2012"]);
        Assert.Equal(sha, s.Sha256);
        var m1 = s.FindCorrection("Mask 1")!;
        Assert.Equal(new Dictionary<string, double> { ["Exposure2012"] = 0.6, ["Shadows2012"] = 30, ["Saturation"] = -4 }, m1.Values);
        Assert.Equal("Subject 1", m1.Masks[0]["MaskName"]);
        Assert.Equal(0.05, s.FindCorrection("Mask 2")!.Values["Exposure2012"]);
        Assert.Equal("65", s.FindCorrection("Mask 2")!.Masks[0]["Feather"]);
    }

    [Fact]
    public void VerifySaved_PassesWhenFileAndCatalogAgree()
    {
        var since = DateTimeOffset.UtcNow.AddSeconds(-5);
        var sha = WriteSettings();
        WriteCatalog(sha);
        var result = J(_svc.VerifySaved(new JsonObject
        {
            ["global.Exposure2012"] = 0.2,
            ["Mask 1.Shadows2012"] = 30,
            ["Mask 1.LocalExposure2012"] = 0.6,
            ["Mask 2.Blacks2012"] = 0
        }, since, "DSC_8750", 0.011));
        Assert.Equal(sha, result["sha256"]!.GetValue<string>());
        Assert.True(result["catalogRevisions"]![0]!["MentionsPhoto"]!.GetValue<bool>());
    }

    [Fact]
    public void VerifySaved_FailsWhenNothingWasSavedSince()
    {
        WriteCatalog(WriteSettings());
        var ex = Assert.Throws<ToolException>(() =>
            _svc.VerifySaved(new JsonObject { ["global.Exposure2012"] = 0.2 }, DateTimeOffset.UtcNow.AddMinutes(5), null, 0.011));
        Assert.Equal(LrErrorCodes.SaveUnverified, ex.Error.Code);
        Assert.Contains("leave the photo", ex.Error.Message);
    }

    [Fact]
    public void VerifySaved_FailsOnWrongValueOrUnreferencedFile()
    {
        var since = DateTimeOffset.UtcNow.AddSeconds(-5);
        var sha = WriteSettings();
        WriteCatalog(sha);
        var wrong = Assert.Throws<ToolException>(() =>
            _svc.VerifySaved(new JsonObject { ["Mask 1.Shadows2012"] = 31 }, since, null, 0.011));
        Assert.Contains("Mask 1.Shadows2012", wrong.Error.Message);

        WriteCatalogReplace(null);
        var unref = Assert.Throws<ToolException>(() =>
            _svc.VerifySaved(new JsonObject { ["global.Exposure2012"] = 0.2 }, since, null, 0.011));
        Assert.Contains("no current revision", unref.Error.Message);
    }

    [Fact]
    public async Task Save_SwitchesToGridWaitsForTheFileAndReturns()
    {
        WriteCatalog(null);
        var xmp = File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "Fixtures", "settings-two-masks.xmp"));
        _server.SaveOnGrid = (Path.Combine(_catalogDir, "settings"), xmp);
        var result = J(await _svc.SaveAsync("loupe", 3000, default));
        Assert.Equal(["square_grid", "loupe"], _server.Views);
        Assert.Equal("loupe", result["returnedTo"]!.GetValue<string>());
        Assert.True(File.Exists(result["file"]!.GetValue<string>()));
    }

    [Fact]
    public async Task Save_ReportsSaveUnverifiedWhenNothingIsWritten()
    {
        WriteCatalog(null);
        var ex = await Assert.ThrowsAsync<ToolException>(() => _svc.SaveAsync("loupe", 600, default));
        Assert.Equal(LrErrorCodes.SaveUnverified, ex.Error.Code);
        Assert.Equal(["square_grid", "loupe"], _server.Views);   // still returns to the photo
    }

    [Fact]
    public async Task PhotoState_ReportsRatingAndLabel()
    {
        var state = J(await _svc.GetPhotoStateAsync(default));
        Assert.Equal("5", state["rating"]!.GetValue<string>());
        Assert.Equal("blue", state["colorLabel"]!.GetValue<string>());
    }

    // ------------------------------------------------------------ scenarios over lr.* steps

    [Fact]
    public async Task Scenario_PlansPausesAppliesAndResumes()
    {
        var yaml = """
            scenario: lr-apply
            target: { processes: [lightroom.exe] }
            params:
              photo: { type: string, required: true }
              values: { type: object, required: true }
            steps:
              - lr.get_status: {}
                save: { current: $.currentPhoto }
              - lr.set_values: { values: "${params.values}", dryRun: true }
                save: { planned: $.planned }
              - checkpoint: { message: "Apply ${planned} to ${current}?" }
              - lr.set_values: { values: "${params.values}", expectedPhoto: "${params.photo}", confirmed: true }
                expect: "result.results[0].readbackOk == true"
              - lr.get_values: { parameters: [Shadows2012] }
                save: { shadows: $.values.Shadows2012.value }
              - assert: "shadows == 25"
            """;
        var path = Path.Combine(_dir, "lr-apply.scenario.yaml");
        File.WriteAllText(path, yaml);
        var options = new WinGuiMcp.Scenarios.ScenarioEngineOptions { RunsDir = Path.Combine(_dir, "runs") };
        var engine = new WinGuiMcp.Scenarios.ScenarioEngine([new LightroomMcp.Scenarios.LrStepProvider(_svc, new UiaDispatcher())], options);
        var doc = WinGuiMcp.Scenarios.ScenarioLoader.Load(path);
        var p = new Dictionary<string, JsonNode?> { ["photo"] = "DSC_8750", ["values"] = new JsonObject { ["Shadows2012"] = 25 } };

        // Without allowWrites the write step is refused before anything is sent.
        var blocked = await engine.RunAsync(doc, new() { Params = p }, default);
        Assert.Equal("blocked", blocked.Status);

        var paused = await engine.RunAsync(doc, new() { Params = p, AllowWrites = true }, default);
        Assert.True(paused.Status == "paused", paused.ErrorMessage);
        Assert.DoesNotContain("setValue", _server.Messages);                 // plan only, nothing written yet
        Assert.Contains("Shadows2012", paused.CheckpointMessage);

        var done = await engine.ResumeAsync(paused.ResumeToken!, approve: true, null, default);
        Assert.True(done.Status == "passed", done.ErrorMessage);
        Assert.Equal(25.0, _server.Values["Shadows2012"]);
    }

    private void WriteCatalogReplace(string? sha)
    {
        SqliteConnection.ClearAllPools();
        File.Delete(Path.Combine(_catalogDir, "Managed Catalog.mcat"));
        WriteCatalog(sha);
    }
}
