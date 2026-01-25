--[[----------------------------------------------------------------------------
Start.lua - MCP Bridge Plugin Manual Start
Manually starts the MCP server (if not already running)
Based on remote_control_socket SDK pattern
------------------------------------------------------------------------------]]

local LrDialogs = import 'LrDialogs'
local LrTasks = import 'LrTasks'
local LrFunctionContext = import 'LrFunctionContext'

-- Log function
local function logToFile( msg )
    local path = "D:\\Projects\\lightroom-mcp\\plugin_debug.log"
    local f = io.open( path, "a" )
    if f then
        f:write( os.date() .. " [Start]: " .. tostring(msg) .. "\n" )
        f:close()
    end
end

-- Check if already running
if _G.mcpServerRunning then
    logToFile( "Server already running, ignoring start request" )
    LrDialogs.showBezel( "MCP Bridge Already Running", 2 )
    return
end

logToFile( "Manual start requested by user" )

-- Load Server module
local status, Server = pcall( require, 'Server' )
if not status then
    logToFile( "Failed to require Server: " .. tostring(Server) )
    LrDialogs.message( "MCP Bridge Error", "Failed to load Server module: " .. tostring(Server), "critical" )
    return
end

-- Start server in async task
-- IMPORTANT: Do NOT use pcall around Server.start - it contains LrTasks.sleep()
LrTasks.startAsyncTask( function()
    logToFile( "Starting async server task..." )
    
    LrFunctionContext.callWithContext( 'MCPServer', function( context )
        logToFile( "Function context created, starting server..." )
        LrDialogs.showBezel( "MCP Bridge Starting...", 2 )
        
        -- Call Server.start directly (no pcall - it contains yield points)
        Server.start( context )
        
        logToFile( "Server.start completed" )
    end )
    
    logToFile( "Async task completed" )
end )
