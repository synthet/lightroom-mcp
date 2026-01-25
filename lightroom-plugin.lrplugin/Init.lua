--[[----------------------------------------------------------------------------
Init.lua - MCP Bridge Plugin Initialization
Based on Lightroom SDK 15.0 patterns
------------------------------------------------------------------------------]]

local LrTasks = import 'LrTasks'
local LrFunctionContext = import 'LrFunctionContext'
local LrLogger = import 'LrLogger'
local LrDialogs = import 'LrDialogs'

local logger = LrLogger( 'MCPBridge' )
logger:enable( 'print' )
logger:enable( 'logfile' )

local function logToFile( msg )
    local path = "D:\\Projects\\lightroom-mcp\\plugin_debug.log"
    local f = io.open( path, "a" )
    if f then
        f:write( os.date() .. " [Init]: " .. tostring(msg) .. "\n" )
        f:close()
    end
end

-- Log startup
logToFile( "=== MCP Bridge Plugin Starting ===" )
logToFile( "Plugin path: " .. tostring(_PLUGIN.path) )
logger:info( "MCP Bridge: Plugin initialization starting" )

-- Load Server module
local status, Server = pcall( require, 'Server' )
if not status then
    logToFile( "ERROR: Failed to load Server module: " .. tostring(Server) )
    logger:error( "MCP Bridge: Failed to load Server: " .. tostring(Server) )
    LrDialogs.message( "MCP Bridge Error", "Failed to load Server module: " .. tostring(Server), "critical" )
    return
end

logToFile( "Server module loaded" )

-- Start server in async task (SDK pattern)
-- IMPORTANT: Do NOT wrap Server.start in pcall - it contains yield points
LrTasks.startAsyncTask( function()
    logToFile( "Starting async server task" )
    
    LrFunctionContext.callWithContext( 'MCPBridgeServer', function( context )
        logToFile( "Function context created, starting server" )
        
        -- Call directly without pcall (contains LrTasks.sleep which yields)
        Server.start( context )
        
        logToFile( "Server.start returned" )
    end )
    
    logToFile( "Async task completed" )
end )

logToFile( "Init.lua completed" )
