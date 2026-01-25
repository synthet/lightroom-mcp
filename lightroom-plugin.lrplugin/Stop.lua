--[[----------------------------------------------------------------------------
Stop.lua - MCP Bridge Plugin Stop
Stops the MCP server when user selects "Stop MCP Bridge" from menu
Based on remote_control_socket SDK pattern
------------------------------------------------------------------------------]]

local LrDialogs = import 'LrDialogs'

-- Signal the server to stop
_G.mcpServerRunning = false

-- Show notification
LrDialogs.showBezel( "MCP Bridge Stopping...", 2 )

-- Log the stop request
local function logToFile( msg )
    local path = "D:\\Projects\\lightroom-mcp\\plugin_debug.log"
    local f = io.open( path, "a" )
    if f then
        f:write( os.date() .. " [Stop]: " .. tostring(msg) .. "\n" )
        f:close()
    end
end

logToFile( "Stop requested by user" )
