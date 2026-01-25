--[[----------------------------------------------------------------------------
Shutdown.lua - MCP Bridge Plugin Shutdown
Based on Lightroom SDK 15.0 patterns and remote_control_socket example
------------------------------------------------------------------------------]]

local LrTasks = import 'LrTasks'
local LrDate = import 'LrDate'
local LrLogger = import 'LrLogger'
local LrDialogs = import 'LrDialogs'

local logger = LrLogger( 'MCPBridge' )
logger:enable( 'print' )
logger:enable( 'logfile' )

local function logToFile( msg )
    local path = "D:\\Projects\\lightroom-mcp\\plugin_debug.log"
    local f = io.open( path, "a" )
    if f then
        f:write( os.date() .. " [Shutdown]: " .. tostring(msg) .. "\n" )
        f:close()
    end
end

-- SDK shutdown function pattern (matching remote_control_socket)
return {
    LrShutdownFunction = function( doneFunction, progressFunction )
        logToFile( "Shutdown initiated..." )
        logger:info( "MCP Bridge: Shutdown initiated" )
        
        LrTasks.startAsyncTask( function()
            if _G.mcpServerRunning then
                local start = LrDate.currentTime()
                local timeout = 2.0 -- Maximum 2 seconds for shutdown
                
                progressFunction( 0 )
                
                -- Signal server to stop (matching SDK pattern)
                logToFile( "Signaling server to stop..." )
                _G.mcpServerRunning = false
                
                -- Wait for server to signal shutdown complete (with timeout)
                -- Uses _G.mcpShutdownComplete flag like SDK uses _G.shutdown
                while not _G.mcpShutdownComplete do
                    local elapsed = LrDate.currentTime() - start
                    if elapsed >= timeout then
                        logToFile( "Shutdown timeout reached, forcing exit" )
                        break
                    end
                    local percent = math.min( 1, math.max( 0, elapsed / timeout ) )
                    progressFunction( percent )
                    LrTasks.sleep( 0.1 )
                end
            end
            
            -- Signal completion
            progressFunction( 1 )
            logToFile( "Shutdown complete" )
            logger:info( "MCP Bridge: Shutdown complete" )
            LrDialogs.showBezel( "MCP Bridge Stopped", 2 )
            doneFunction()
        end )
    end,
}
