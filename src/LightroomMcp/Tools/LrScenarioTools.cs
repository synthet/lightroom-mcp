using System.ComponentModel;
using System.Text.Json.Nodes;
using ModelContextProtocol.Protocol;
using ModelContextProtocol.Server;
using WinGuiMcp.Common;
using WinGuiMcp.Scenarios;

namespace LightroomMcp.Tools;

/// <summary>
/// Scenario runner over lr.* and win-gui steps, using WinGuiMcp.Core's engine. Names carry the lr_ prefix so they
/// never shadow win-gui-mcp's run_scenario family (LIGHTROOM_BOUNDARIES_CONSTITUTION §4).
/// </summary>
[McpServerToolType]
public sealed class LrScenarioTools
{
    private readonly ScenarioEngine _engine;

    public LrScenarioTools(ScenarioEngine engine) => _engine = engine;

    [McpServerTool(Name = "lr_run_scenario", ReadOnly = false, Destructive = true, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Runs a Lightroom scenario (*.scenario.yaml) by path or name under scenarios/. Write steps need allowWrites; dryRun never contacts Lightroom. Stops at checkpoints with a resumeToken.")]
    public Task<CallToolResult> RunScenario(string scenario, JsonObject? @params = null, bool dryRun = false, bool allowWrites = false,
        CancellationToken cancellationToken = default) =>
        Run(() => ScenarioCommands.RunAsync(_engine, scenario, @params, dryRun, allowWrites, cancellationToken));

    [McpServerTool(Name = "lr_resume_scenario", ReadOnly = false, Destructive = true, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Continues (approve: true) or stops (approve: false) a Lightroom scenario paused at a checkpoint. Tokens are single-use.")]
    public Task<CallToolResult> ResumeScenario(string resumeToken, bool approve = true, JsonObject? secretParams = null,
        CancellationToken cancellationToken = default) =>
        Run(() => ScenarioCommands.ResumeAsync(_engine, resumeToken, approve, secretParams, cancellationToken));

    [McpServerTool(Name = "lr_validate_scenario", ReadOnly = true, Destructive = false, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Checks a Lightroom scenario's structure, params and steps without contacting Lightroom.")]
    public Task<CallToolResult> ValidateScenario(string scenario, JsonObject? @params = null) =>
        Run(() => Task.FromResult(ScenarioCommands.Validate(_engine, scenario, @params)));

    [McpServerTool(Name = "lr_list_scenarios", ReadOnly = true, Destructive = false, OpenWorld = false, UseStructuredContent = true, OutputSchemaType = typeof(JsonObject))]
    [Description("Lists the bundled and local Lightroom scenarios with their params.")]
    public Task<CallToolResult> ListScenarios() =>
        Run(() => Task.FromResult(ScenarioCommands.List(_engine)));

    private static async Task<CallToolResult> Run(Func<Task<object>> action)
    {
        try
        {
            return LrTools.Result(await action());
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (ScenarioException ex)
        {
            return LrTools.Result(ToolError.Create(ex.Code, ex.Message, ex.Details));
        }
        catch (ToolException ex)
        {
            return LrTools.Result(ex.Error);
        }
        catch (Exception ex)
        {
            return LrTools.Result(ToolError.Create(ErrorCodes.InternalError, ex.Message));
        }
    }
}
