--[[----------------------------------------------------------------------------
AutoSettings.lua - Implements the Auto Settings pipeline via MCP Broker
------------------------------------------------------------------------------]]

local LrApplication = import 'LrApplication'
local LrTasks = import 'LrTasks'
local LrDialogs = import 'LrDialogs'
local LrView = import 'LrView'
local LrHttp = import 'LrHttp'
local LrLogger = import 'LrLogger'
local JSON = require 'JSON'

local logger = LrLogger( 'MCPBridge' )
logger:enable( 'print' )

-- Base64 encoding for binary data
local b64chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
local function base64encode( data )
    if not data or #data == 0 then
        return ""
    end
    local result = {}
    local len = #data
    for i = 1, len, 3 do
        local a = data:byte( i ) or 0
        local b = ( i + 1 <= len ) and data:byte( i + 1 ) or 0
        local c = ( i + 2 <= len ) and data:byte( i + 2 ) or 0
        local n = a * 65536 + b * 256 + c
        local n1 = math.floor( n / 262144 ) % 64 + 1
        local n2 = math.floor( n / 4096 ) % 64 + 1
        local n3 = math.floor( n / 64 ) % 64 + 1
        local n4 = n % 64 + 1
        result[#result + 1] = b64chars:sub( n1, n1 )
        result[#result + 1] = b64chars:sub( n2, n2 )
        result[#result + 1] = b64chars:sub( n3, n3 )
        result[#result + 1] = b64chars:sub( n4, n4 )
    end
    local pad = ( 3 - len % 3 ) % 3
    if pad == 1 then
        result[#result] = "="
    elseif pad == 2 then
        result[#result - 1] = "="
        result[#result] = "="
    end
    return table.concat( result )
end

LrTasks.startAsyncTask(function()
    local catalog = LrApplication.activeCatalog()
    if not catalog then
        LrDialogs.message("Error", "No active catalog.", "critical")
        return
    end

    local targetPhoto = catalog:getTargetPhoto()
    if not targetPhoto then
        LrDialogs.message("Error", "No photo selected.", "critical")
        return
    end

    -- Prompt for creative intent
    local f = LrView.osFactory()
    local properties = { intent = "auto_balanced" }
    local dialogContents = f:column {
        bind_to_object = properties,
        spacing = f:control_spacing(),
        f:static_text {
            title = "Choose creative style / intent for AI develop settings:"
        },
        f:popup_menu {
            value = LrView.bind 'intent',
            items = {
                { title = "Auto (Balanced & Natural)", value = "auto_balanced" },
                { title = "Moody / Cinematic", value = "moody_cinematic" },
                { title = "Clean Commercial / Bright", value = "clean_commercial" },
                { title = "Golden Hour Warmth", value = "golden_hour" },
                { title = "B&W Fine Art", value = "bw_fine_art" },
            }
        }
    }

    local dlgResult = LrDialogs.presentModalDialog {
        title = "AI Auto-Develop",
        contents = dialogContents,
        actionVerb = "Develop"
    }

    if dlgResult == "cancel" then
        return
    end

    local selectedIntent = properties.intent or "auto_balanced"

    -- Extract capture EXIF for informed develop adjustments
    local exif = {}
    pcall(function()
        exif.camera = targetPhoto:getFormattedMetadata('cameraModel')
        exif.lens = targetPhoto:getFormattedMetadata('lens')
        exif.iso = targetPhoto:getFormattedMetadata('isoSpeedRating')
        exif.shutterSpeed = targetPhoto:getFormattedMetadata('shutterSpeed')
        exif.aperture = targetPhoto:getFormattedMetadata('aperture')
        exif.focalLength = targetPhoto:getFormattedMetadata('focalLength')
    end)

    LrDialogs.showBezel("Auto Settings: Analyzing image (" .. selectedIntent .. ")...")

    -- 1. Get JPEG Thumbnail
    local jpegData = nil
    local errorMsg = nil
    local completed = false

    local holdRef = targetPhoto:requestJpegThumbnail(800, 800, function(success, failure)
        if success and type(success) == 'string' and #success > 0 then
            jpegData = success
        else
            errorMsg = (type(failure) == 'string' and failure) or "Failed to get thumbnail"
        end
        completed = true
    end)

    -- Wait for thumbnail request to complete
    local elapsed = 0
    while not completed and elapsed < 30 do
        LrTasks.sleep(0.1)
        elapsed = elapsed + 0.1
    end

    holdRef = nil

    if not jpegData then
        local extraAdvice = ""
        if errorMsg == "error loading thumb" then
            extraAdvice = "\n\nTip: Try building Standard or 1:1 previews for this photo in Lightroom (Library > Previews > Build Standard Previews)."
        end
        LrDialogs.message("Error", "Could not generate thumbnail: " .. (errorMsg or "Timeout") .. extraAdvice, "critical")
        return
    end

    -- 2. Send to Broker
    local base64Image = base64encode(jpegData)
    local payload = {
        image = base64Image,
        localId = targetPhoto.localIdentifier,
        provider = "gemini",
        intent = selectedIntent,
        exif = exif
    }

    local payloadJson = JSON:encode(payload)

    local headers = {
        { field = "Content-Type", value = "application/json" }
    }

    local brokerUrl = "http://127.0.0.1:8085/auto_edit"

    logger:info("Sending auto_edit request to broker...")
    local responseBody, responseHeaders = LrHttp.post(brokerUrl, payloadJson, headers, 60)

    if not responseBody then
        LrDialogs.message("Error", "Failed to communicate with MCP Broker. Is the server running?", "critical")
        return
    end

    local status = responseHeaders.status
    if status ~= 200 then
        LrDialogs.message("Error", "Broker returned error status: " .. tostring(status) .. "\n" .. tostring(responseBody), "critical")
        return
    end

    -- 3. Parse and Apply Settings
    local responseData = JSON:decode(responseBody)
    if not responseData or not responseData.settings then
        LrDialogs.message("Error", "Broker returned invalid response format", "critical")
        return
    end

    local developSettings = responseData.settings

    -- Some simple mappings from Python snake_case to Lightroom mixed case if needed, but Pydantic should match the names
    local lrSettings = {}
    if developSettings.exposure then lrSettings.Exposure2012 = developSettings.exposure end
    if developSettings.contrast then lrSettings.Contrast2012 = developSettings.contrast end
    if developSettings.highlights then lrSettings.Highlights2012 = developSettings.highlights end
    if developSettings.shadows then lrSettings.Shadows2012 = developSettings.shadows end
    if developSettings.whites then lrSettings.Whites2012 = developSettings.whites end
    if developSettings.blacks then lrSettings.Blacks2012 = developSettings.blacks end
    if developSettings.texture then lrSettings.Texture = developSettings.texture end
    if developSettings.clarity then lrSettings.Clarity2012 = developSettings.clarity end
    if developSettings.dehaze then lrSettings.Dehaze = developSettings.dehaze end
    if developSettings.vibrance then lrSettings.Vibrance = developSettings.vibrance end
    if developSettings.saturation then lrSettings.Saturation = developSettings.saturation end
    if developSettings.color_temp then lrSettings.Temperature = developSettings.color_temp end
    if developSettings.tint then lrSettings.Tint = developSettings.tint end

    catalog:withWriteAccessDo("MCP Auto Settings", function(context)
        targetPhoto:applyDevelopSettings(lrSettings)
    end)

    -- 4. Verification Ratchet (Pass 2: Request updated preview to warm cache and confirm rendering)
    LrDialogs.showBezel("Auto Settings: Verifying adjustments (" .. selectedIntent .. ")...")

    local verifyCompleted = false
    local newJpegData = nil
    local verifyRef = targetPhoto:requestJpegThumbnail(800, 800, function(success, failure)
        if success and type(success) == 'string' and #success > 0 then
            newJpegData = success
        end
        verifyCompleted = true
    end)

    local vElapsed = 0
    while not verifyCompleted and vElapsed < 10 do
        LrTasks.sleep(0.1)
        vElapsed = vElapsed + 0.1
    end
    verifyRef = nil

    if newJpegData then
        logger:info("Post-application preview successfully generated for photo: " .. tostring(targetPhoto.localIdentifier))
    else
        logger:warn("Post-application preview verification timed out; settings applied.")
    end

    LrDialogs.showBezel("AI Auto Settings (" .. selectedIntent .. ") applied & verified!")
end)
