--[[----------------------------------------------------------------------------
Info.lua - MCP Bridge Plugin Metadata
Based on Lightroom SDK 15.0 and remote_control_socket SDK patterns
------------------------------------------------------------------------------]]

return {
    -- SDK version requirements (SDK 15.0 = Lightroom Classic 15.1)
    LrSdkVersion = 15.0,
    LrSdkMinimumVersion = 3.0,

    -- Plugin identification
    LrToolkitIdentifier = 'com.antigravity.mcp',
    LrPluginName = 'MCP Bridge',
    LrPluginInfoUrl = 'https://github.com/synthet/lightroom-mcp',

    -- Socket server initialization (writes port to file for discovery)
    LrInitPlugin = 'Init.lua',
    LrForceInitPlugin = true,

    -- Lifecycle hooks
    LrShutdownPlugin = 'Shutdown.lua',
    LrShutdownApp = 'Shutdown.lua',

    -- File menu items
    LrExportMenuItems = {
        {
            title = "MCP Bridge Status",
            file = "DebugAnalysis.lua",
        },
    },

    -- Library menu items
    LrLibraryMenuItems = {
        {
            title = "MCP Bridge Debug Analysis",
            file = "DebugAnalysis.lua",
            enabledWhen = "photosAvailable",
        },
    },

    -- Plugin metadata for Plug-in Manager
    LrPluginInfos = {
        {
            identifier = 'com.antigravity.mcp.info',
            text = 'MCP Bridge for LLM Control - Enables AI agents to interact with Lightroom via Model Context Protocol',
        },
    },

    VERSION = { major = 0, minor = 1, revision = 0 },
}
