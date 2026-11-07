using LightroomMcp.Controller;
using LightroomMcp.Safety;
using LightroomMcp.Saved;
using LightroomMcp.Scenarios;
using LightroomMcp.Tools;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using ModelContextProtocol.Server;
using WinGuiMcp;
using WinGuiMcp.Scenarios;

static void AddLightroom(IServiceCollection services, bool warnDpi)
{
    services.AddWinGuiCore(o => o.WarnIfNotPerMonitorV2 = warnDpi);
    services.AddScenarioEngine(o =>
    {
        if (Environment.GetEnvironmentVariable("WINGUI_SCENARIO_RUNS") is null)
            o.RunsDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "LightroomMcp", "runs");
        // Repo checkout: <repo>/src/LightroomMcp/bin/... → <repo>/scenarios
        var repoScenarios = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "scenarios"));
        if (Directory.Exists(repoScenarios))
            o.ScenarioRoots.Add(repoScenarios);
        if (Environment.GetEnvironmentVariable("LIGHTROOM_MCP_SCENARIOS") is { Length: > 0 } extra)
            o.ScenarioRoots.Insert(0, extra);
    });
    services.AddScenarioStepProvider<LrStepProvider>();
    services.AddSingleton(new LrSessionOptions());
    services.AddSingleton(sp => new LrSession(sp.GetRequiredService<LrSessionOptions>()));
    services.AddSingleton<ParamCatalog>();
    services.AddSingleton(_ => new WriteGuard());
    services.AddSingleton(_ => new SettingsFolder());
    services.AddSingleton<LrToolService>();
    services.AddSingleton<LrTools>();
    services.AddSingleton<LrScenarioTools>();
}

// CLI: `LightroomMcp scenario run|resume|validate|list ...` — same engine as lr_run_scenario.
if (args.Length > 0 && args[0] == "scenario")
{
    var cli = new ServiceCollection();
    AddLightroom(cli, warnDpi: false);
    await using var provider = cli.BuildServiceProvider();
    return await ScenarioCommands.RunCliAsync(provider.GetRequiredService<ScenarioEngine>(), args[1..], Console.Out, CancellationToken.None);
}

var builder = Host.CreateApplicationBuilder(args);
builder.Logging.AddConsole(o => o.LogToStandardErrorThreshold = LogLevel.Trace);
AddLightroom(builder.Services, warnDpi: true);

builder.Services
    .AddMcpServer(options =>
    {
        options.ServerInfo = new()
        {
            Name = "lightroom-mcp",
            Version = typeof(LrTools).Assembly.GetName().Version?.ToString(3) ?? "0.1.0"
        };
    })
    .WithStdioServerTransport()
    .WithTools<LrTools>()
    .WithTools<LrScenarioTools>();

await builder.Build().RunAsync();
return 0;
