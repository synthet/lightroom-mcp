--[[----------------------------------------------------------------------------
DebugAnalysis.lua - MCP Bridge Debug Analysis Menu Item
Displays plugin status, server state, and diagnostic information
------------------------------------------------------------------------------]]

local LrDialogs = import 'LrDialogs'
local LrLogger = import 'LrLogger'
local LrApplication = import 'LrApplication'
local LrSocket = import 'LrSocket'

local logger = LrLogger( 'MCPBridge' )
logger:enable( 'print' )
logger:enable( 'logfile' )

-- Collect debug information
local function collectDebugInfo()
    local info = {}
    
    -- Plugin info
    info.pluginPath = tostring(_PLUGIN.path)
    info.pluginVersion = tostring(_PLUGIN.version)
    info.pluginName = tostring(_PLUGIN.name)
    
    -- Server state
    info.serverRunning = _G.mcpServerRunning or false
    
    -- Catalog info
    local catalog = LrApplication.activeCatalog()
    if catalog then
        local success, path = pcall( function() return catalog:getPath() end )
        info.catalogPath = success and path or "Unable to get path"
        
        local success2, allPhotos = pcall( function() return catalog:getAllPhotos() end )
        info.photoCount = (success2 and allPhotos) and #allPhotos or 0
        
        local success3, targetPhotos = pcall( function() return catalog:getTargetPhotos() end )
        info.selectedPhotoCount = (success3 and targetPhotos) and #targetPhotos or 0
    else
        info.catalogPath = "No catalog"
        info.photoCount = 0
        info.selectedPhotoCount = 0
    end
    
    -- Check if port 54321 is accessible (basic check)
    info.portStatus = "Unknown"
    if info.serverRunning then
        info.portStatus = "Server flag is true"
    else
        info.portStatus = "Server flag is false"
    end
    
    -- Read plugin_debug.log if it exists
    local logPath = "D:\\Projects\\lightroom-mcp\\plugin_debug.log"
    local logFile = io.open( logPath, "r" )
    if logFile then
        local logLines = {}
        for line in logFile:lines() do
            table.insert( logLines, line )
        end
        logFile:close()
        -- Get last 10 lines
        local lastLines = {}
        for i = math.max(1, #logLines - 9), #logLines do
            table.insert( lastLines, logLines[i] )
        end
        info.lastLogLines = table.concat( lastLines, "\n" )
    else
        info.lastLogLines = "Log file not found"
    end
    
    return info
end

-- Format debug info for display
local function formatDebugInfo( info )
    local lines = {
        "=== MCP Bridge Debug Analysis ===",
        "",
        "Plugin Information:",
        "  Path: " .. info.pluginPath,
        "  Version: " .. info.pluginVersion,
        "  Name: " .. info.pluginName,
        "",
        "Server Status:",
        "  Running: " .. tostring( info.serverRunning ),
        "  Port Status: " .. info.portStatus,
        "",
        "Catalog Information:",
        "  Catalog Path: " .. (info.catalogPath or "Unknown"),
        "  Total Photos: " .. tostring( info.photoCount ),
        "  Selected Photos: " .. tostring( info.selectedPhotoCount or 0 ),
        "",
        "Recent Log Entries:",
        info.lastLogLines,
        "",
        "=== End Debug Analysis ===",
    }
    
    return table.concat( lines, "\n" )
end

-- Write debug info to file
local function writeDebugReport( info )
    local reportPath = "D:\\Projects\\lightroom-mcp\\debug_report.txt"
    local reportFile = io.open( reportPath, "w" )
    if reportFile then
        reportFile:write( formatDebugInfo( info ) )
        reportFile:close()
        return reportPath
    end
    return nil
end

-- Main function
local function runDebugAnalysis()
    logger:info( "Debug Analysis: Starting..." )
    
    local info = collectDebugInfo()
    local reportPath = writeDebugReport( info )
    
    -- Display dialog
    local message = formatDebugInfo( info )
    local reportMsg = ""
    if reportPath then
        reportMsg = "\n\nDebug report saved to:\n" .. reportPath
    end
    
    LrDialogs.message( 
        "MCP Bridge Debug Analysis", 
        message .. reportMsg,
        "info"
    )
    
    logger:info( "Debug Analysis: Completed" )
end

-- Execute
runDebugAnalysis()
