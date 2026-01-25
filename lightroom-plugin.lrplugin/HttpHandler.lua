--[[----------------------------------------------------------------------------
HttpHandler.lua - MCP Bridge HTTP Handler
Handles JSON-RPC requests over HTTP
Based on Lightroom SDK remote_control sample
------------------------------------------------------------------------------]]

local LrApplication = import "LrApplication"
local LrLogger = import 'LrLogger'
local LrTasks = import 'LrTasks'
local JSON = require 'JSON'
local CommandHandlers = require 'CommandHandlers'

local logger = LrLogger( 'MCPBridge' )
logger:enable( 'print' )
logger:enable( 'logfile' )

local function logToFile( msg )
    local path = "D:\\Projects\\lightroom-mcp\\plugin_debug.log"
    local f = io.open( path, "a" )
    if f then
        f:write( os.date() .. " [HTTP]: " .. tostring(msg) .. "\n" )
        f:close()
    end
end

--------------------------------------------------------------------------------
-- Send JSON response
local function sendJSON( response, data, statusCode )
    statusCode = statusCode or 200
    local jsonStr = JSON.encode( data )
    logToFile( "Sending response: " .. jsonStr )

    response.data = jsonStr
    response.headers = {
        { name = 'Content-Type', value = 'application/json' },
        { name = 'Content-Length', value = tostring( #jsonStr ) },
        { name = 'Access-Control-Allow-Origin', value = '*' },
    }
    response:transmit()
end

--------------------------------------------------------------------------------
-- Handle JSON-RPC request
local function handleJsonRpc( requestBody )
    logToFile( "Received request: " .. tostring(requestBody) )

    local jsonRpcResponse = { jsonrpc = "2.0", id = nil }

    -- Parse JSON-RPC request
    local status, request = pcall( JSON.decode, requestBody )

    if not status or not request then
        logToFile( "JSON Decode Error: " .. tostring(request) )
        jsonRpcResponse.error = { code = -32700, message = "Parse error" }
        return jsonRpcResponse
    end

    jsonRpcResponse.id = request.id

    local handler = CommandHandlers[ request.method ]

    if handler then
        -- Use LrTasks.pcall to support yielding operations in handlers
        local success, result = LrTasks.pcall( handler, request.params or {} )
        if success then
            jsonRpcResponse.result = result
            logToFile( "Handler success: " .. tostring(JSON.encode(result)) )
        else
            logToFile( "Handler error: " .. tostring(result) )
            jsonRpcResponse.error = { code = -32603, message = "Internal error", data = tostring(result) }
        end
    else
        logToFile( "Method not found: " .. tostring(request.method) )
        jsonRpcResponse.error = { code = -32601, message = "Method not found: " .. tostring(request.method) }
    end

    return jsonRpcResponse
end

--------------------------------------------------------------------------------
-- HTTP GET handler - for health checks and info
local function handleGET( request, response, plugin )
    logToFile( "GET request: " .. tostring(request.uri) )

    -- Health check endpoint
    if request.uri == "/" or request.uri == "/health" then
        sendJSON( response, {
            status = "ok",
            plugin = "MCP Bridge",
            version = "0.1.0"
        })
        return
    end

    -- Unknown endpoint
    sendJSON( response, {
        error = "Unknown endpoint. Use POST for JSON-RPC requests."
    }, 404 )
end

--------------------------------------------------------------------------------
-- HTTP POST handler - for JSON-RPC requests
local function handlePOST( request, response, plugin )
    logToFile( "POST request: " .. tostring(request.uri) )
    logToFile( "Content: " .. tostring(request.content) )

    local requestBody = request.content or ""

    -- Handle JSON-RPC request
    local jsonRpcResponse = handleJsonRpc( requestBody )
    sendJSON( response, jsonRpcResponse )
end

--------------------------------------------------------------------------------
-- HTTP OPTIONS handler - for CORS preflight
local function handleOPTIONS( request, response, plugin )
    logToFile( "OPTIONS request (CORS preflight)" )

    response.data = ""
    response.headers = {
        { name = 'Content-Type', value = 'text/plain' },
        { name = 'Content-Length', value = '0' },
        { name = 'Access-Control-Allow-Origin', value = '*' },
        { name = 'Access-Control-Allow-Methods', value = 'GET, POST, OPTIONS' },
        { name = 'Access-Control-Allow-Headers', value = 'Content-Type' },
    }
    response:transmit()
end

--------------------------------------------------------------------------------
-- Mark server as running
_G.mcpServerRunning = true
logToFile( "HTTP Handler loaded - MCP Bridge ready" )
logger:info( "MCP Bridge: HTTP Handler loaded" )

return {
    GET = handleGET,
    POST = handlePOST,
    OPTIONS = handleOPTIONS,
}
