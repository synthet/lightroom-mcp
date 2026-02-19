--[[----------------------------------------------------------------------------
Server.lua - MCP Bridge Client
Connects to the broker server using HTTP (primary) or Socket (fallback).
------------------------------------------------------------------------------]]

local LrLogger = import 'LrLogger'
local LrHttp = import 'LrHttp'
local LrSocket = import 'LrSocket'
local LrTasks = import 'LrTasks'
local LrDialogs = import 'LrDialogs'
local JSON = require 'JSON'
local CommandHandlers = require 'CommandHandlers'

local logger = LrLogger( 'MCPBridge' )
logger:enable( 'print' )
logger:enable( 'logfile' )

-- Global flags for shutdown coordination
_G.mcpServerRunning = false
_G.mcpShutdownComplete = false

-- Broker configuration
local BROKER_HOST = "127.0.0.1"
local BROKER_HTTP_PORT = 8085
local BROKER_SOCKET_PORT = 8086
local BROKER_URL = "http://" .. BROKER_HOST .. ":" .. BROKER_HTTP_PORT
local POLL_INTERVAL = 0.1  -- seconds between polls
local HTTP_FAIL_THRESHOLD = 5  -- consecutive HTTP failures before fallback
local LOG_FILE = "D:\\Projects\\lightroom-mcp\\plugin_debug.log"

local function logToFile( msg )
    local f = io.open( LOG_FILE, "a" )
    if f then
        f:write( os.date() .. " [Server]: " .. tostring(msg) .. "\n" )
        f:close()
    end
end

local Server = {}

-- Process a JSON-RPC request and return the response
-- Note: Uses LrTasks.pcall to support yielding in handlers (e.g., withWriteAccessDo)
local function processRequest( request )
    local response = { jsonrpc = "2.0", id = request.id }

    local handler = CommandHandlers[ request.method ]

    if handler then
        -- Use LrTasks.pcall instead of pcall to allow handlers to yield
        local status, result = LrTasks.pcall( handler, request.params or {} )

        if status then
            response.result = result
            logToFile( "Handler success for: " .. tostring(request.method) )
        else
            logToFile( "Handler error for " .. tostring(request.method) .. ": " .. tostring(result) )
            response.error = { code = -32603, message = "Internal error: " .. tostring(result) }
        end
    else
        logToFile( "Method not found: " .. tostring(request.method) )
        response.error = { code = -32601, message = "Method not found: " .. tostring(request.method) }
    end

    return response
end

-- ============================================================================
-- HTTP Mode (Primary)
-- ============================================================================

local function runHttpMode( headers )
    logToFile( "Running in HTTP mode" )

    local consecutiveErrors = 0
    local shown = false

    while _G.mcpServerRunning do
        -- Use LrTasks.pcall instead of regular pcall to support yielding
        local success, errorMsg = LrTasks.pcall( function()
            local responseBody, responseHeaders = LrHttp.post(
                BROKER_URL .. "/poll",
                "{}",
                headers,
                "POST",
                5
            )

            if responseBody and responseBody ~= "" then
                if not shown then
                    LrDialogs.showBezel( "MCP Bridge Ready (HTTP)\n" .. BROKER_URL, 3 )
                    logToFile( "Connected to broker (HTTP)" )
                    shown = true
                end

                consecutiveErrors = 0

                -- Regular pcall is fine here since JSON.decode doesn't yield
                local requestStatus, request = pcall( JSON.decode, responseBody )

                if requestStatus and request then
                    logToFile( "Received request: " .. tostring(request.method) )

                    local brokerUuid = request._broker_uuid
                    local response = processRequest( request )
                    response._broker_uuid = brokerUuid

                    local responseJson = JSON.encode( response )
                    logToFile( "Sending response for: " .. tostring(request.method) )

                    local sendBody, sendHeaders = LrHttp.post(
                        BROKER_URL .. "/response",
                        responseJson,
                        headers,
                        "POST",
                        10
                    )

                    if sendBody then
                        logToFile( "Response sent successfully" )
                    else
                        logToFile( "Failed to send response" )
                    end
                else
                    logToFile( "Failed to parse request JSON" )
                end
            else
                if responseHeaders then
                    consecutiveErrors = 0
                    if not shown then
                        LrDialogs.showBezel( "MCP Bridge Ready (HTTP)\n" .. BROKER_URL, 3 )
                        logToFile( "Connected to broker (HTTP)" )
                        shown = true
                    end
                end
            end
        end )

        if not success then
            consecutiveErrors = consecutiveErrors + 1
            if consecutiveErrors <= 3 or consecutiveErrors % 10 == 0 then
                logToFile( "HTTP error (" .. consecutiveErrors .. "): " .. tostring(errorMsg) )
            end

            -- Check if we should fall back to socket mode
            if consecutiveErrors >= HTTP_FAIL_THRESHOLD then
                logToFile( "HTTP failed " .. consecutiveErrors .. " times, switching to socket fallback" )
                return "fallback_to_socket"
            end
        end

        LrTasks.sleep( POLL_INTERVAL )
    end

    return "shutdown"
end

-- ============================================================================
-- Socket Mode (Fallback)
-- ============================================================================

local function runSocketMode( context )
    logToFile( "Running in Socket fallback mode" )

    local senderSocket = nil
    local receiverSocket = nil
    local senderConnected = false
    local receiverConnected = false
    local messageQueue = {}
    local shown = false
    local socketErrors = 0

    -- Create sender socket (for sending responses)
    senderSocket = LrSocket.bind {
        name = "MCP Bridge Sender",
        functionContext = context,
        address = BROKER_HOST,
        port = BROKER_SOCKET_PORT,
        mode = "send",

        onConnecting = function( socket, port )
            logToFile( "Socket sender connecting to port " .. tostring(port) )
        end,

        onConnected = function( socket, port )
            logToFile( "Socket sender connected" )
            senderConnected = true
            if not shown and receiverConnected then
                LrDialogs.showBezel( "MCP Bridge Ready (Socket)\n" .. BROKER_HOST .. ":" .. BROKER_SOCKET_PORT, 3 )
                shown = true
            end
        end,

        onClosed = function( socket )
            logToFile( "Socket sender closed" )
            senderConnected = false
        end,

        onError = function( socket, err )
            if err ~= "timeout" then
                logToFile( "Socket sender error: " .. tostring(err) )
                socketErrors = socketErrors + 1
            end
        end,

        plugin = _PLUGIN
    }

    -- Create receiver socket (for receiving requests)
    receiverSocket = LrSocket.bind {
        name = "MCP Bridge Receiver",
        functionContext = context,
        address = BROKER_HOST,
        port = BROKER_SOCKET_PORT,
        mode = "receive",

        onConnecting = function( socket, port )
            logToFile( "Socket receiver connecting to port " .. tostring(port) )
        end,

        onConnected = function( socket, port )
            logToFile( "Socket receiver connected" )
            receiverConnected = true
            if not shown and senderConnected then
                LrDialogs.showBezel( "MCP Bridge Ready (Socket)\n" .. BROKER_HOST .. ":" .. BROKER_SOCKET_PORT, 3 )
                shown = true
            end
        end,

        onMessage = function( socket, message )
            if type( message ) == "string" and message ~= "" then
                logToFile( "Socket received: " .. string.sub(message, 1, 200) )
                table.insert( messageQueue, message )
            end
        end,

        onClosed = function( socket )
            logToFile( "Socket receiver closed" )
            receiverConnected = false
        end,

        onError = function( socket, err )
            if err ~= "timeout" then
                logToFile( "Socket receiver error: " .. tostring(err) )
                socketErrors = socketErrors + 1
            end
        end,

        plugin = _PLUGIN
    }

    if not senderSocket or not receiverSocket then
        logToFile( "Failed to create sockets" )
        return "fallback_to_http"
    end

    -- Main loop
    local httpRetryCounter = 0

    while _G.mcpServerRunning do
        -- Process any queued messages
        while #messageQueue > 0 do
            local msg = table.remove( messageQueue, 1 )

            local parseStatus, request = pcall( JSON.decode, msg )

            if parseStatus and request then
                logToFile( "Processing socket request: " .. tostring(request.method) )

                local brokerUuid = request._broker_uuid
                local response = processRequest( request )
                response._broker_uuid = brokerUuid

                local responseStr = JSON.encode( response )

                if senderSocket and senderConnected then
                    local sendStatus, sendErr = pcall( function()
                        senderSocket:send( responseStr .. "\n" )
                    end )

                    if sendStatus then
                        logToFile( "Socket response sent successfully" )
                    else
                        logToFile( "Socket send failed: " .. tostring(sendErr) )
                    end
                else
                    logToFile( "Socket not connected, cannot send response" )
                end
            else
                logToFile( "Failed to parse socket message" )
            end
        end

        -- Periodically try to switch back to HTTP (every ~30 seconds)
        httpRetryCounter = httpRetryCounter + 1
        if httpRetryCounter >= 300 then  -- 300 * 0.1s = 30s
            httpRetryCounter = 0
            logToFile( "Checking if HTTP is available again..." )
            return "retry_http"
        end

        -- Check for too many socket errors
        if socketErrors > 10 then
            logToFile( "Too many socket errors, trying HTTP again" )
            return "fallback_to_http"
        end

        LrTasks.sleep( POLL_INTERVAL )
    end

    -- Cleanup
    if senderConnected and senderSocket then
        pcall( function() senderSocket:close() end )
    end
    if receiverConnected and receiverSocket then
        pcall( function() receiverSocket:close() end )
    end

    return "shutdown"
end

-- ============================================================================
-- Main Entry Point
-- ============================================================================

function Server.start( context )
    logToFile( "Starting MCP Bridge client..." )
    logToFile( "HTTP endpoint: " .. BROKER_URL )
    logToFile( "Socket fallback: " .. BROKER_HOST .. ":" .. BROKER_SOCKET_PORT )

    _G.mcpServerRunning = true
    _G.mcpShutdownComplete = false

    local headers = {
        { field = "Content-Type", value = "application/json" },
    }

    local mode = "http"  -- Start with HTTP

    while _G.mcpServerRunning do
        if mode == "http" then
            local result = runHttpMode( headers )
            if result == "fallback_to_socket" then
                mode = "socket"
            elseif result == "shutdown" then
                break
            end
        elseif mode == "socket" then
            local result = runSocketMode( context )
            if result == "fallback_to_http" or result == "retry_http" then
                mode = "http"
            elseif result == "shutdown" then
                break
            end
        end

        -- Brief pause before mode switch
        if _G.mcpServerRunning then
            LrTasks.sleep( 1 )
        end
    end

    logToFile( "Server shutting down..." )
    _G.mcpShutdownComplete = true
    logToFile( "Server shutdown complete" )
end

return Server
