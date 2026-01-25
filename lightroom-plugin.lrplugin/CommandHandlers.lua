--[[----------------------------------------------------------------------------
CommandHandlers.lua - JSON-RPC Command Handlers for MCP Bridge
Based on Lightroom SDK 15.0 API patterns
------------------------------------------------------------------------------]]

local LrApplication = import 'LrApplication'
local LrApplicationView = import 'LrApplicationView'
local LrSelection = import 'LrSelection'
local LrLogger = import 'LrLogger'
local LrTasks = import 'LrTasks'
local LrFunctionContext = import 'LrFunctionContext'

local logger = LrLogger( 'MCPBridge' )
logger:enable( 'print' )

local CommandHandlers = {}

-- Base64 encoding for binary data (Lua 5.1 compatible)
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

-- Helper function for error handling
-- Uses LrTasks.pcall to support yielding operations (e.g., withWriteAccessDo)
local function safeCall( func, params )
    local success, result = LrTasks.pcall( func, params )
    if not success then
        return { error = tostring( result ) }
    end
    return result
end

-- Helper function to safely get raw metadata (handles unknown keys)
local function safeGetRawMetadata( photo, key )
    local success, value = LrTasks.pcall( function()
        return photo:getRawMetadata( key )
    end )
    if success then
        return value
    end
    return nil
end

-- Helper function to safely get formatted metadata (handles unknown keys)
local function safeGetFormattedMetadata( photo, key )
    local success, value = LrTasks.pcall( function()
        return photo:getFormattedMetadata( key )
    end )
    if success then
        return value
    end
    return nil
end

--[[
    get_studio_info - Returns catalog and plugin information
    Returns: { catalogName, catalogPath, pluginVersion }
]]
function CommandHandlers.get_studio_info( params )
    return safeCall( function()
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local catalogPath = catalog:getPath() or ""
        -- Extract catalog name from path (filename without extension)
        local catalogName = catalogPath:match( "([^/\\]+)%.lrcat$" ) or catalogPath:match( "([^/\\]+)$" ) or "Unknown"

        return {
            catalogName = catalogName,
            catalogPath = catalogPath,
            pluginVersion = "0.1.0"
        }
    end )
end

--[[
    get_selection - Returns details about currently selected photos
    Returns: { photos = [{ localId, filename, path, rating, colorLabel, title, caption }] }
]]
function CommandHandlers.get_selection( params )
    return safeCall( function()
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        -- Try getting the single target photo first
        local targetPhoto = catalog:getTargetPhoto()
        if not targetPhoto then
            return { photos = {} }
        end

        local result = {}
        local photo = targetPhoto

        -- Get pick status
        local pickStatus = 0
        local pickSuccess = LrTasks.pcall( function()
            pickStatus = photo:getRawMetadata( 'pickStatus' ) or 0
        end )

        local pickFlag = "none"
        if pickStatus == 1 then
            pickFlag = "pick"
        elseif pickStatus == -1 then
            pickFlag = "reject"
        end

        -- Build result table field by field using LrTasks.pcall
        local photoData = {}

        -- localIdentifier
        LrTasks.pcall( function()
            photoData.localId = photo.localIdentifier or ""
        end )

        -- filename (using getFormattedMetadata)
        LrTasks.pcall( function()
            photoData.filename = photo:getFormattedMetadata( 'fileName' ) or ""
        end )

        -- path
        LrTasks.pcall( function()
            photoData.path = photo:getRawMetadata( 'path' ) or ""
        end )

        -- rating
        LrTasks.pcall( function()
            photoData.rating = photo:getRawMetadata( 'rating' ) or 0
        end )

        -- colorLabel (using colorNameForLabel key)
        LrTasks.pcall( function()
            photoData.colorLabel = photo:getRawMetadata( 'colorNameForLabel' )
        end )

        -- title
        LrTasks.pcall( function()
            photoData.title = photo:getFormattedMetadata( 'title' ) or ""
        end )

        -- caption
        LrTasks.pcall( function()
            photoData.caption = photo:getFormattedMetadata( 'caption' ) or ""
        end )

        photoData.pickFlag = pickFlag

        table.insert( result, photoData )

        return { photos = result }
    end )
end

--[[
    set_rating - Sets star rating (0-5) for selected photos
    Params: { rating: number }
]]
function CommandHandlers.set_rating( params )
    return safeCall( function()
        if not params or type( params.rating ) ~= "number" then
            return { error = "Invalid rating parameter" }
        end

        local rating = math.floor( params.rating )
        if rating < 0 or rating > 5 then
            return { error = "Rating must be between 0 and 5" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        catalog:withWriteAccessDo( "MCP Set Rating", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    photo:setRawMetadata( 'rating', rating )
                end
            end
        end )

        return { success = true }
    end )
end

--[[
    set_label - Sets color label for selected photos
    Params: { label: string } - One of: "Red", "Yellow", "Green", "Blue", "Purple", "None"
]]
function CommandHandlers.set_label( params )
    return safeCall( function()
        if not params or type( params.label ) ~= "string" then
            return { error = "Invalid label parameter" }
        end

        -- Valid label values (Lightroom expects string values)
        local validLabels = {
            Red = true,
            Yellow = true,
            Green = true,
            Blue = true,
            Purple = true,
            None = true
        }

        if not validLabels[ params.label ] then
            return { error = "Label must be one of: Red, Yellow, Green, Blue, Purple, None" }
        end

        -- For "None", use empty string to clear the label
        local labelValue = params.label == "None" and "" or params.label

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        catalog:withWriteAccessDo( "MCP Set Label", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    photo:setRawMetadata( 'label', labelValue )
                end
            end
        end )

        return { success = true }
    end )
end

--[[
    set_caption - Sets caption text for selected photos
    Params: { caption: string }
]]
function CommandHandlers.set_caption( params )
    return safeCall( function()
        if not params or type( params.caption ) ~= "string" then
            return { error = "Invalid caption parameter" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        catalog:withWriteAccessDo( "MCP Set Caption", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    photo:setRawMetadata( 'caption', params.caption )
                end
            end
        end )

        return { success = true }
    end )
end

--[[
    set_title - Sets title text for selected photos
    Params: { title: string }
]]
function CommandHandlers.set_title( params )
    return safeCall( function()
        if not params or type( params.title ) ~= "string" then
            return { error = "Invalid title parameter" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        catalog:withWriteAccessDo( "MCP Set Title", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    photo:setRawMetadata( 'title', params.title )
                end
            end
        end )

        return { success = true }
    end )
end

--[[
    set_pick_flag - Sets pick flag (pick/reject) for selected photos
    Params: { pickFlag: string } - One of: "pick", "reject", "none"
]]
function CommandHandlers.set_pick_flag( params )
    return safeCall( function()
        if not params or type( params.pickFlag ) ~= "string" then
            return { error = "Invalid pickFlag parameter" }
        end

        local flagMap = {
            pick = 1,
            reject = -1,
            none = 0
        }

        local flagValue = flagMap[ params.pickFlag:lower() ]
        if flagValue == nil then
            return { error = "pickFlag must be one of: pick, reject, none" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        catalog:withWriteAccessDo( "MCP Set Pick Flag", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    photo:setRawMetadata( 'pickStatus', flagValue )
                end
            end
        end )

        return { success = true }
    end )
end

--[[
    add_keywords - Adds keywords to selected photos
    Params: { keywords: array of strings }
]]
function CommandHandlers.add_keywords( params )
    return safeCall( function()
        if not params or type( params.keywords ) ~= "table" then
            return { error = "Invalid keywords parameter - must be an array" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        -- Helper function to find or create keyword
        local function findOrCreateKeyword( keywordPath )
            local keywords = catalog:getKeywords()
            local parts = {}
            for part in string.gmatch( keywordPath, "[^>]+" ) do
                table.insert( parts, part:match( "^%s*(.-)%s*$" ) ) -- trim whitespace
            end

            local currentKeywords = keywords
            local keyword = nil

            for i, part in ipairs( parts ) do
                local found = false
                for _, kw in ipairs( currentKeywords ) do
                    if kw:getName() == part then
                        keyword = kw
                        currentKeywords = kw:getChildren()
                        found = true
                        break
                    end
                end

                if not found then
                    -- Create new keyword
                    keyword = catalog:createKeyword( part, keyword )
                    if keyword then
                        currentKeywords = keyword:getChildren()
                    else
                        return nil
                    end
                end
            end

            return keyword
        end

        catalog:withWriteAccessDo( "MCP Add Keywords", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    for _, keywordPath in ipairs( params.keywords ) do
                        local keyword = findOrCreateKeyword( keywordPath )
                        if keyword then
                            photo:addKeyword( keyword )
                        end
                    end
                end
            end
        end )

        return { success = true }
    end )
end

--[[
    remove_keywords - Removes keywords from selected photos
    Params: { keywords: array of strings }
]]
function CommandHandlers.remove_keywords( params )
    return safeCall( function()
        if not params or type( params.keywords ) ~= "table" then
            return { error = "Invalid keywords parameter - must be an array" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        -- Helper function to find keyword by path
        local function findKeyword( keywordPath )
            local keywords = catalog:getKeywords()
            local parts = {}
            for part in string.gmatch( keywordPath, "[^>]+" ) do
                table.insert( parts, part:match( "^%s*(.-)%s*$" ) ) -- trim whitespace
            end

            local currentKeywords = keywords
            local keyword = nil

            for i, part in ipairs( parts ) do
                local found = false
                for _, kw in ipairs( currentKeywords ) do
                    if kw:getName() == part then
                        keyword = kw
                        currentKeywords = kw:getChildren()
                        found = true
                        break
                    end
                end
                if not found then
                    return nil
                end
            end

            return keyword
        end

        catalog:withWriteAccessDo( "MCP Remove Keywords", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    for _, keywordPath in ipairs( params.keywords ) do
                        local keyword = findKeyword( keywordPath )
                        if keyword then
                            photo:removeKeyword( keyword )
                        end
                    end
                end
            end
        end )

        return { success = true }
    end )
end

--[[
    get_keywords - Gets all keywords from selected photos
    Returns: { keywords: array of keyword paths }
]]
function CommandHandlers.get_keywords( params )
    return safeCall( function()
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { keywords = {} }
        end

        -- Helper to get keyword path
        local function getKeywordPath( keyword )
            local path = keyword:getName()
            local parent = keyword:getParent()
            while parent do
                path = parent:getName() .. " > " .. path
                parent = parent:getParent()
            end
            return path
        end

        local allKeywords = {}
        for _, photo in ipairs( targetPhotos ) do
            if photo then
                local photoKeywords = photo:getKeywords()
                for _, keyword in ipairs( photoKeywords ) do
                    local path = getKeywordPath( keyword )
                    -- Avoid duplicates
                    local found = false
                    for _, existing in ipairs( allKeywords ) do
                        if existing == path then
                            found = true
                            break
                        end
                    end
                    if not found then
                        table.insert( allKeywords, path )
                    end
                end
            end
        end

        return { keywords = allKeywords }
    end )
end

--[[
    list_collections - Lists all collections in the catalog
    Returns: { collections: array of { name, id, type } }
]]
function CommandHandlers.list_collections( params )
    return safeCall( function()
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local collections = {}

        -- Helper to recursively get collections
        local function getCollections( collectionSet, prefix )
            prefix = prefix or ""
            local childCollections = collectionSet:getChildCollections()
            local childSets = collectionSet:getChildCollectionSets()

            for _, coll in ipairs( childCollections ) do
                table.insert( collections, {
                    name = prefix .. coll:getName(),
                    id = coll.localIdentifier or "",
                    type = "collection"
                } )
            end

            for _, set in ipairs( childSets ) do
                getCollections( set, prefix .. set:getName() .. " > " )
            end
        end

        -- Get root collections
        local rootCollections = catalog:getChildCollections()
        local rootSets = catalog:getChildCollectionSets()

        for _, coll in ipairs( rootCollections ) do
            table.insert( collections, {
                name = coll:getName(),
                id = coll.localIdentifier or "",
                type = "collection"
            } )
        end

        for _, set in ipairs( rootSets ) do
            getCollections( set, set:getName() .. " > " )
        end

        return { collections = collections }
    end )
end

--[[
    add_to_collection - Adds selected photos to a collection
    Params: { collectionName: string }
]]
function CommandHandlers.add_to_collection( params )
    return safeCall( function()
        if not params or type( params.collectionName ) ~= "string" then
            return { error = "Invalid collectionName parameter" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        -- Helper to find collection by name
        local function findCollection( name )
            local function searchCollections( collectionSet )
                local childCollections = collectionSet:getChildCollections()
                for _, coll in ipairs( childCollections ) do
                    if coll:getName() == name then
                        return coll
                    end
                end

                local childSets = collectionSet:getChildCollectionSets()
                for _, set in ipairs( childSets ) do
                    local found = searchCollections( set )
                    if found then
                        return found
                    end
                end
                return nil
            end

            -- Check root collections
            local rootCollections = catalog:getChildCollections()
            for _, coll in ipairs( rootCollections ) do
                if coll:getName() == name then
                    return coll
                end
            end

            -- Check collection sets
            local rootSets = catalog:getChildCollectionSets()
            for _, set in ipairs( rootSets ) do
                local found = searchCollections( set )
                if found then
                    return found
                end
            end

            return nil
        end

        local collection = findCollection( params.collectionName )
        if not collection then
            -- Create collection if it doesn't exist
            collection = catalog:createCollection( params.collectionName, nil, false )
            if not collection then
                return { error = "Failed to create or find collection" }
            end
        end

        catalog:withWriteAccessDo( "MCP Add to Collection", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    collection:addPhotos( { photo } )
                end
            end
        end )

        return { success = true }
    end )
end

--[[
    search_photos - Searches for photos in the catalog
    Params: { query: string } - Search query (searches in filename, title, caption)
    Returns: { photos: array of photo details }
]]
function CommandHandlers.search_photos( params )
    return safeCall( function()
        if not params or type( params.query ) ~= "string" then
            return { error = "Invalid query parameter" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local query = params.query:lower()
        local allPhotos = catalog:getAllPhotos()
        local results = {}

        for _, photo in ipairs( allPhotos ) do
            if photo then
                local filename = ( safeGetFormattedMetadata( photo, 'fileName' ) or "" ):lower()
                local title = ( safeGetFormattedMetadata( photo, 'title' ) or "" ):lower()
                local caption = ( safeGetFormattedMetadata( photo, 'caption' ) or "" ):lower()

                if string.find( filename, query, 1, true ) or
                   string.find( title, query, 1, true ) or
                   string.find( caption, query, 1, true ) then
                    table.insert( results, {
                        localId = photo.localIdentifier or "",
                        filename = safeGetFormattedMetadata( photo, 'fileName' ) or "",
                        path = safeGetRawMetadata( photo, 'path' ) or "",
                        rating = safeGetRawMetadata( photo, 'rating' ) or 0,
                        label = safeGetRawMetadata( photo, 'colorNameForLabel' ),
                        title = safeGetFormattedMetadata( photo, 'title' ) or "",
                        caption = safeGetFormattedMetadata( photo, 'caption' ) or ""
                    } )
                end
            end
        end

        return { photos = results }
    end )
end

--[[
    set_metadata - Sets additional metadata fields for selected photos
    Params: { field: string, value: any }
    Supported fields: dateCreated, copyright, gps, gpsAltitude, etc.
]]
function CommandHandlers.set_metadata( params )
    return safeCall( function()
        if not params or type( params.field ) ~= "string" then
            return { error = "Invalid field parameter" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        local field = params.field
        local value = params.value

        catalog:withWriteAccessDo( "MCP Set Metadata", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    photo:setRawMetadata( field, value )
                end
            end
        end )

        return { success = true }
    end )
end

--[[
    get_metadata - Gets metadata fields from selected photos
    Params: { fields: array of field names }
    Returns: { metadata: array of { field: value } objects }
]]
function CommandHandlers.get_metadata( params )
    return safeCall( function()
        if not params or type( params.fields ) ~= "table" then
            return { error = "Invalid fields parameter - must be an array" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { metadata = {} }
        end

        local results = {}
        for _, photo in ipairs( targetPhotos ) do
            if photo then
                local photoMetadata = {}
                for _, field in ipairs( params.fields ) do
                    photoMetadata[ field ] = safeGetRawMetadata( photo, field )
                end
                table.insert( results, {
                    localId = photo.localIdentifier or "",
                    metadata = photoMetadata
                } )
            end
        end

        return { metadata = results }
    end )
end

--[[
    get_develop_settings - Gets develop/Camera Raw settings for selected photos
    Returns: { photos: array of { localId, filename, settings: dict } }
]]
function CommandHandlers.get_develop_settings( params )
    return safeCall( function()
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { photos = {} }
        end

        local results = {}
        for _, photo in ipairs( targetPhotos ) do
            if photo then
                local success, settings = LrTasks.pcall( function()
                    return photo:getDevelopSettings()
                end )
                table.insert( results, {
                    localId = photo.localIdentifier or "",
                    filename = safeGetFormattedMetadata( photo, 'fileName' ) or "",
                    settings = ( success and settings ) or {}
                } )
            end
        end

        return { photos = results }
    end )
end

--[[
    set_develop_settings - Sets develop/Camera Raw settings for selected photos
    Params: { settings: dict } - Dictionary of parameter names to values
    Example: { settings = { Exposure = 1.0, Contrast = 25, Temperature = 5500 } }
]]
function CommandHandlers.set_develop_settings( params )
    return safeCall( function()
        if not params or type( params.settings ) ~= "table" then
            return { error = "Invalid settings parameter - must be a dictionary" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        catalog:withWriteAccessDo( "MCP Set Develop Settings", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    photo:applyDevelopSettings( params.settings )
                end
            end
        end )

        return { success = true }
    end )
end

--[[
    get_exif_data - Gets EXIF metadata from selected photos
    Returns: { photos: array of { localId, filename, exif data } }
]]
function CommandHandlers.get_exif_data( params )
    return safeCall( function()
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { photos = {} }
        end

        local results = {}
        for _, photo in ipairs( targetPhotos ) do
            if photo then
                local exif = {
                    localId = photo.localIdentifier or "",
                    filename = safeGetFormattedMetadata( photo, 'fileName' ) or "",
                    camera = {
                        make = safeGetFormattedMetadata( photo, 'cameraMake' ),
                        model = safeGetFormattedMetadata( photo, 'cameraModel' ),
                        serialNumber = safeGetRawMetadata( photo, 'cameraSerialNumber' )
                    },
                    lens = {
                        name = safeGetFormattedMetadata( photo, 'lens' ),
                        focalLength = safeGetFormattedMetadata( photo, 'focalLength' ),
                        focalLength35mm = safeGetFormattedMetadata( photo, 'focalLength35mm' )
                    },
                    exposure = {
                        aperture = safeGetFormattedMetadata( photo, 'aperture' ),
                        shutterSpeed = safeGetFormattedMetadata( photo, 'shutterSpeed' ),
                        iso = safeGetFormattedMetadata( photo, 'isoSpeedRating' ),
                        exposureBias = safeGetFormattedMetadata( photo, 'exposureBias' ),
                        exposureProgram = safeGetRawMetadata( photo, 'exposureProgram' ),
                        meteringMode = safeGetRawMetadata( photo, 'meteringMode' )
                    },
                    flash = {
                        fired = safeGetRawMetadata( photo, 'flashFired' ),
                        mode = safeGetRawMetadata( photo, 'flashMode' )
                    },
                    dateTimeOriginal = safeGetRawMetadata( photo, 'dateTimeOriginal' ),
                    dateTimeDigitized = safeGetRawMetadata( photo, 'dateTimeDigitized' ),
                    gps = {
                        latitude = safeGetRawMetadata( photo, 'gpsLatitude' ),
                        longitude = safeGetRawMetadata( photo, 'gpsLongitude' ),
                        altitude = safeGetRawMetadata( photo, 'gpsAltitude' ),
                        direction = safeGetRawMetadata( photo, 'gpsImgDirection' )
                    },
                    dimensions = {
                        width = safeGetRawMetadata( photo, 'width' ),
                        height = safeGetRawMetadata( photo, 'height' ),
                        orientation = safeGetRawMetadata( photo, 'orientation' )
                    }
                }
                table.insert( results, exif )
            end
        end

        return { photos = results }
    end )
end

--[[
    get_iptc_data - Gets IPTC metadata from selected photos
    Returns: { photos: array of { localId, filename, iptc data } }
]]
function CommandHandlers.get_iptc_data( params )
    return safeCall( function()
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { photos = {} }
        end

        local results = {}
        for _, photo in ipairs( targetPhotos ) do
            if photo then
                local iptc = {
                    localId = photo.localIdentifier or "",
                    filename = safeGetFormattedMetadata( photo, 'fileName' ) or "",
                    creator = {
                        artist = safeGetFormattedMetadata( photo, 'artist' ),
                        credit = safeGetFormattedMetadata( photo, 'credit' ),
                        source = safeGetFormattedMetadata( photo, 'source' )
                    },
                    copyright = {
                        notice = safeGetFormattedMetadata( photo, 'copyright' ),
                        state = safeGetRawMetadata( photo, 'copyrightState' ),
                        url = safeGetRawMetadata( photo, 'copyrightInfoUrl' )
                    },
                    content = {
                        headline = safeGetFormattedMetadata( photo, 'headline' ),
                        caption = safeGetFormattedMetadata( photo, 'caption' ),
                        title = safeGetFormattedMetadata( photo, 'title' ),
                        instructions = safeGetRawMetadata( photo, 'instructions' )
                    },
                    location = {
                        city = safeGetFormattedMetadata( photo, 'city' ),
                        stateProvince = safeGetFormattedMetadata( photo, 'stateProvince' ),
                        country = safeGetFormattedMetadata( photo, 'country' ),
                        isoCountryCode = safeGetFormattedMetadata( photo, 'isoCountryCode' ),
                        location = safeGetFormattedMetadata( photo, 'location' )
                    },
                    workflow = {
                        jobIdentifier = safeGetFormattedMetadata( photo, 'jobIdentifier' ),
                        provider = safeGetRawMetadata( photo, 'provider' ),
                        rightsUsageTerms = safeGetRawMetadata( photo, 'rightsUsageTerms' )
                    }
                }
                table.insert( results, iptc )
            end
        end

        return { photos = results }
    end )
end

--[[
    set_iptc_data - Sets IPTC metadata for selected photos
    Params: { data: { field: value, ... } }
]]
function CommandHandlers.set_iptc_data( params )
    return safeCall( function()
        if not params or type( params.data ) ~= "table" then
            return { error = "Invalid data parameter - must be a dictionary" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        -- Map of IPTC field names to Lightroom metadata field names
        local fieldMap = {
            creator = 'creator',
            artist = 'creator',
            copyright = 'copyright',
            copyrightState = 'copyrightState',
            copyrightInfoUrl = 'copyrightInfoUrl',
            headline = 'headline',
            caption = 'caption',
            title = 'title',
            instructions = 'instructions',
            jobIdentifier = 'jobIdentifier',
            city = 'city',
            stateProvince = 'stateProvince',
            country = 'country',
            isoCountryCode = 'isoCountryCode',
            location = 'location',
            credit = 'credit',
            source = 'source',
            rightsUsageTerms = 'rightsUsageTerms'
        }

        catalog:withWriteAccessDo( "MCP Set IPTC Data", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    for fieldName, value in pairs( params.data ) do
                        local lrField = fieldMap[ fieldName ]
                        if lrField then
                            photo:setRawMetadata( lrField, value )
                        end
                    end
                end
            end
        end )

        return { success = true }
    end )
end

--[[
    get_xmp_data - Gets XMP/Adobe-specific metadata from selected photos
    Returns: { photos: array of { localId, filename, xmp data } }
]]
function CommandHandlers.get_xmp_data( params )
    return safeCall( function()
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { photos = {} }
        end

        local results = {}
        for _, photo in ipairs( targetPhotos ) do
            if photo then
                -- Get masterPhoto safely
                local masterPhotoId = nil
                local masterPhoto = safeGetRawMetadata( photo, 'masterPhoto' )
                if masterPhoto then
                    masterPhotoId = masterPhoto.localIdentifier
                end

                -- Get smartPreviewInfo safely
                local hasSmartPreview = safeGetRawMetadata( photo, 'smartPreviewInfo' ) and true or false

                local xmp = {
                    localId = photo.localIdentifier or "",
                    filename = safeGetFormattedMetadata( photo, 'fileName' ) or "",
                    fileInfo = {
                        fileFormat = safeGetRawMetadata( photo, 'fileFormat' ),
                        fileType = safeGetFormattedMetadata( photo, 'fileType' ),
                        originalFilename = safeGetRawMetadata( photo, 'originalFilename' ),
                        sidecarPath = safeGetRawMetadata( photo, 'sidecarPath' )
                    },
                    dimensions = {
                        croppedWidth = safeGetRawMetadata( photo, 'croppedWidth' ),
                        croppedHeight = safeGetRawMetadata( photo, 'croppedHeight' ),
                        aspectRatio = safeGetFormattedMetadata( photo, 'croppedDimensions' )
                    },
                    editing = {
                        editCount = safeGetRawMetadata( photo, 'editCount' ),
                        lastEditTime = safeGetRawMetadata( photo, 'lastEditTime' ),
                        developPresetName = safeGetFormattedMetadata( photo, 'developPresetName' )
                    },
                    catalogInfo = {
                        dateAdded = safeGetRawMetadata( photo, 'dateTimeOriginal' ),
                        uuid = safeGetRawMetadata( photo, 'uuid' ),
                        isVirtualCopy = safeGetRawMetadata( photo, 'isVirtualCopy' ),
                        masterPhoto = masterPhotoId,
                        stackPosition = safeGetRawMetadata( photo, 'stackPositionInFolder' ),
                        stackInFolderIsCollapsed = safeGetRawMetadata( photo, 'stackInFolderIsCollapsed' )
                    },
                    colorLabel = {
                        colorNameForLabel = safeGetRawMetadata( photo, 'colorNameForLabel' ),
                        label = safeGetRawMetadata( photo, 'colorNameForLabel' )
                    },
                    smartPreview = {
                        hasSmartPreview = hasSmartPreview
                    }
                }
                table.insert( results, xmp )
            end
        end

        return { photos = results }
    end )
end

--[[
    get_all_metadata - Gets comprehensive metadata from selected photos
    Returns: { photos: array with all metadata combined }
]]
function CommandHandlers.get_all_metadata( params )
    return safeCall( function()
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { photos = {} }
        end

        -- Helper to get keyword paths
        local function getKeywordPaths( photo )
            local success, keywords = LrTasks.pcall( function()
                return photo:getKeywords()
            end )
            if not success or not keywords then
                return {}
            end
            local paths = {}
            local function getPath( keyword )
                local path = keyword:getName()
                local parent = keyword:getParent()
                while parent do
                    path = parent:getName() .. " > " .. path
                    parent = parent:getParent()
                end
                return path
            end
            for _, keyword in ipairs( keywords ) do
                table.insert( paths, getPath( keyword ) )
            end
            return paths
        end

        local results = {}
        for _, photo in ipairs( targetPhotos ) do
            if photo then
                local pickStatus = safeGetRawMetadata( photo, 'pickStatus' ) or 0
                local pickFlag = "none"
                if pickStatus == 1 then
                    pickFlag = "pick"
                elseif pickStatus == -1 then
                    pickFlag = "reject"
                end

                local metadata = {
                    -- Basic info
                    localId = photo.localIdentifier or "",
                    filename = safeGetFormattedMetadata( photo, 'fileName' ) or "",
                    path = safeGetRawMetadata( photo, 'path' ) or "",
                    uuid = safeGetRawMetadata( photo, 'uuid' ),

                    -- EXIF
                    exif = {
                        camera = {
                            make = safeGetFormattedMetadata( photo, 'cameraMake' ),
                            model = safeGetFormattedMetadata( photo, 'cameraModel' ),
                            serialNumber = safeGetRawMetadata( photo, 'cameraSerialNumber' )
                        },
                        lens = {
                            name = safeGetFormattedMetadata( photo, 'lens' ),
                            focalLength = safeGetFormattedMetadata( photo, 'focalLength' ),
                            focalLength35mm = safeGetFormattedMetadata( photo, 'focalLength35mm' )
                        },
                        exposure = {
                            aperture = safeGetFormattedMetadata( photo, 'aperture' ),
                            shutterSpeed = safeGetFormattedMetadata( photo, 'shutterSpeed' ),
                            iso = safeGetFormattedMetadata( photo, 'isoSpeedRating' ),
                            exposureBias = safeGetFormattedMetadata( photo, 'exposureBias' ),
                            exposureProgram = safeGetRawMetadata( photo, 'exposureProgram' ),
                            meteringMode = safeGetRawMetadata( photo, 'meteringMode' )
                        },
                        flash = {
                            fired = safeGetRawMetadata( photo, 'flashFired' ),
                            mode = safeGetRawMetadata( photo, 'flashMode' )
                        },
                        dateTimeOriginal = safeGetRawMetadata( photo, 'dateTimeOriginal' ),
                        gps = {
                            latitude = safeGetRawMetadata( photo, 'gpsLatitude' ),
                            longitude = safeGetRawMetadata( photo, 'gpsLongitude' ),
                            altitude = safeGetRawMetadata( photo, 'gpsAltitude' )
                        },
                        dimensions = {
                            width = safeGetRawMetadata( photo, 'width' ),
                            height = safeGetRawMetadata( photo, 'height' ),
                            orientation = safeGetRawMetadata( photo, 'orientation' )
                        }
                    },

                    -- IPTC
                    iptc = {
                        creator = safeGetFormattedMetadata( photo, 'artist' ),
                        copyright = safeGetFormattedMetadata( photo, 'copyright' ),
                        copyrightState = safeGetRawMetadata( photo, 'copyrightState' ),
                        headline = safeGetFormattedMetadata( photo, 'headline' ),
                        caption = safeGetFormattedMetadata( photo, 'caption' ),
                        title = safeGetFormattedMetadata( photo, 'title' ),
                        city = safeGetFormattedMetadata( photo, 'city' ),
                        stateProvince = safeGetFormattedMetadata( photo, 'stateProvince' ),
                        country = safeGetFormattedMetadata( photo, 'country' ),
                        location = safeGetFormattedMetadata( photo, 'location' ),
                        jobIdentifier = safeGetFormattedMetadata( photo, 'jobIdentifier' )
                    },

                    -- XMP/Adobe
                    xmp = {
                        fileFormat = safeGetRawMetadata( photo, 'fileFormat' ),
                        editCount = safeGetRawMetadata( photo, 'editCount' ),
                        developPresetName = safeGetFormattedMetadata( photo, 'developPresetName' ),
                        isVirtualCopy = safeGetRawMetadata( photo, 'isVirtualCopy' ),
                        colorNameForLabel = safeGetRawMetadata( photo, 'colorNameForLabel' ),
                        croppedDimensions = safeGetFormattedMetadata( photo, 'croppedDimensions' )
                    },

                    -- Lightroom-specific
                    lightroom = {
                        rating = safeGetRawMetadata( photo, 'rating' ) or 0,
                        label = safeGetRawMetadata( photo, 'colorNameForLabel' ),
                        pickFlag = pickFlag,
                        keywords = getKeywordPaths( photo ),
                        isInStackInFolder = safeGetRawMetadata( photo, 'isInStackInFolder' ),
                        stackPositionInFolder = safeGetRawMetadata( photo, 'stackPositionInFolder' )
                    }
                }
                table.insert( results, metadata )
            end
        end

        return { photos = results }
    end )
end

--[[
    set_gps_data - Sets GPS coordinates for selected photos
    Params: { latitude: number, longitude: number, altitude?: number }
]]
function CommandHandlers.set_gps_data( params )
    return safeCall( function()
        if not params or type( params.latitude ) ~= "number" or type( params.longitude ) ~= "number" then
            return { error = "Invalid GPS parameters - latitude and longitude required" }
        end

        local latitude = params.latitude
        local longitude = params.longitude

        if latitude < -90 or latitude > 90 then
            return { error = "Latitude must be between -90 and 90" }
        end
        if longitude < -180 or longitude > 180 then
            return { error = "Longitude must be between -180 and 180" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        catalog:withWriteAccessDo( "MCP Set GPS Data", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    photo:setRawMetadata( 'gps', { latitude = latitude, longitude = longitude } )
                    if params.altitude and type( params.altitude ) == "number" then
                        photo:setRawMetadata( 'gpsAltitude', params.altitude )
                    end
                end
            end
        end )

        return { success = true }
    end )
end

--[[
    clear_gps_data - Clears GPS coordinates from selected photos
]]
function CommandHandlers.clear_gps_data( params )
    return safeCall( function()
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        catalog:withWriteAccessDo( "MCP Clear GPS Data", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    photo:setRawMetadata( 'gps', nil )
                    photo:setRawMetadata( 'gpsAltitude', nil )
                end
            end
        end )

        return { success = true }
    end )
end

--[[
    find_photo_by_path - Finds a photo in catalog by its file path
    Params: { path: string }
    Returns: { photo: photo details } or { photo: null }
]]
function CommandHandlers.find_photo_by_path( params )
    return safeCall( function()
        if not params or type( params.path ) ~= "string" then
            return { error = "Invalid path parameter" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local searchPath = params.path
        -- Normalize path separators for comparison
        searchPath = searchPath:gsub( "\\", "/" ):lower()

        local allPhotos = catalog:getAllPhotos()
        for _, photo in ipairs( allPhotos ) do
            if photo then
                local photoPath = ( safeGetRawMetadata( photo, 'path' ) or "" ):gsub( "\\", "/" ):lower()
                if photoPath == searchPath then
                    local pickStatus = safeGetRawMetadata( photo, 'pickStatus' ) or 0
                    local pickFlag = "none"
                    if pickStatus == 1 then
                        pickFlag = "pick"
                    elseif pickStatus == -1 then
                        pickFlag = "reject"
                    end

                    return {
                        found = true,
                        photo = {
                            localId = photo.localIdentifier or "",
                            filename = safeGetFormattedMetadata( photo, 'fileName' ) or "",
                            path = safeGetRawMetadata( photo, 'path' ) or "",
                            rating = safeGetRawMetadata( photo, 'rating' ) or 0,
                            label = safeGetRawMetadata( photo, 'colorNameForLabel' ),
                            title = safeGetFormattedMetadata( photo, 'title' ) or "",
                            caption = safeGetFormattedMetadata( photo, 'caption' ) or "",
                            pickFlag = pickFlag
                        }
                    }
                end
            end
        end

        return { found = false, photo = nil }
    end )
end

--[[
    find_photo_by_filename - Finds photos in catalog by filename
    Params: { filename: string, exactMatch?: boolean }
    Returns: { photos: array of photo details }
]]
function CommandHandlers.find_photo_by_filename( params )
    return safeCall( function()
        if not params or type( params.filename ) ~= "string" then
            return { error = "Invalid filename parameter" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local searchFilename = params.filename:lower()
        local exactMatch = params.exactMatch == true

        local allPhotos = catalog:getAllPhotos()
        local results = {}

        for _, photo in ipairs( allPhotos ) do
            if photo then
                local photoFilename = ( safeGetFormattedMetadata( photo, 'fileName' ) or "" ):lower()

                local matches = false
                if exactMatch then
                    matches = ( photoFilename == searchFilename )
                else
                    matches = ( string.find( photoFilename, searchFilename, 1, true ) ~= nil )
                end

                if matches then
                    local pickStatus = safeGetRawMetadata( photo, 'pickStatus' ) or 0
                    local pickFlag = "none"
                    if pickStatus == 1 then
                        pickFlag = "pick"
                    elseif pickStatus == -1 then
                        pickFlag = "reject"
                    end

                    table.insert( results, {
                        localId = photo.localIdentifier or "",
                        filename = safeGetFormattedMetadata( photo, 'fileName' ) or "",
                        path = safeGetRawMetadata( photo, 'path' ) or "",
                        rating = safeGetRawMetadata( photo, 'rating' ) or 0,
                        label = safeGetRawMetadata( photo, 'colorNameForLabel' ),
                        title = safeGetFormattedMetadata( photo, 'title' ) or "",
                        caption = safeGetFormattedMetadata( photo, 'caption' ) or "",
                        pickFlag = pickFlag
                    } )
                end
            end
        end

        return { photos = results, count = #results }
    end )
end

--[[
    find_photo_by_hash - Finds photos by comparing file hash
    Params: { filename: string, hash: string }
    Returns: { photo: photo details } or { photo: null }
    Note: This searches for photos with matching filename, then compares hashes
          by reading the actual file. Limited by Lightroom SDK file access.
]]
function CommandHandlers.find_photo_by_hash( params )
    return safeCall( function()
        if not params or type( params.filename ) ~= "string" or type( params.hash ) ~= "string" then
            return { error = "Invalid parameters - filename and hash required" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local searchFilename = params.filename:lower()
        local searchHash = params.hash:lower()

        -- First find photos with matching filename
        local allPhotos = catalog:getAllPhotos()
        local candidates = {}

        for _, photo in ipairs( allPhotos ) do
            if photo then
                local photoFilename = ( safeGetFormattedMetadata( photo, 'fileName' ) or "" ):lower()
                if photoFilename == searchFilename then
                    table.insert( candidates, photo )
                end
            end
        end

        if #candidates == 0 then
            return { found = false, photo = nil, message = "No photos with matching filename" }
        end

        -- For hash comparison, we need to read the file
        -- This is limited - Lightroom SDK doesn't have built-in hashing
        -- We'll return the candidates and let the MCP server compare hashes
        local results = {}
        for _, photo in ipairs( candidates ) do
            local pickStatus = safeGetRawMetadata( photo, 'pickStatus' ) or 0
            local pickFlag = "none"
            if pickStatus == 1 then
                pickFlag = "pick"
            elseif pickStatus == -1 then
                pickFlag = "reject"
            end

            table.insert( results, {
                localId = photo.localIdentifier or "",
                filename = safeGetFormattedMetadata( photo, 'fileName' ) or "",
                path = safeGetRawMetadata( photo, 'path' ) or "",
                rating = safeGetRawMetadata( photo, 'rating' ) or 0,
                label = safeGetRawMetadata( photo, 'colorNameForLabel' ),
                title = safeGetFormattedMetadata( photo, 'title' ) or "",
                caption = safeGetFormattedMetadata( photo, 'caption' ) or "",
                pickFlag = pickFlag
            } )
        end

        return { candidates = results, count = #results, searchHash = searchHash }
    end )
end

--[[
    get_photo_preview - Returns JPEG thumbnail previews for selected photos or by ID
    Params: { width?: number, height?: number, photoId?: string }
    Returns: { photos: [{ localId, filename, jpegBase64 }] }
    Uses LrPhoto:requestJpegThumbnail (async); waits with timeout.
]]
function CommandHandlers.get_photo_preview( params )
    return safeCall( function()
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local width = 800
        local height = 800
        if params and type( params.width ) == "number" and params.width > 0 then
            width = math.floor( math.min( params.width, 4096 ) )
        end
        if params and type( params.height ) == "number" and params.height > 0 then
            height = math.floor( math.min( params.height, 4096 ) )
        end

        local targetPhotos = {}
        if params and type( params.photoId ) == "string" and params.photoId ~= "" then
            local allPhotos = catalog:getAllPhotos()
            for _, p in ipairs( allPhotos ) do
                if p and ( p.localIdentifier or "" ) == params.photoId then
                    targetPhotos = { p }
                    break
                end
            end
            if #targetPhotos == 0 then
                return { error = "Photo not found: " .. params.photoId }
            end
        else
            targetPhotos = catalog:getTargetPhotos()
            if not targetPhotos or #targetPhotos == 0 then
                return { error = "No photos selected" }
            end
        end

        local results = {}
        local timeoutSeconds = 30
        local pollInterval = 0.1

        for _, photo in ipairs( targetPhotos ) do
            if photo then
                local completed = false
                local jpegData = nil
                local errMsg = nil
                local holdRef = photo:requestJpegThumbnail( width, height, function( success, failure )
                    if success and type( success ) == "string" and #success > 0 then
                        jpegData = success
                    else
                        errMsg = ( type( failure ) == "string" and failure ) or "Thumbnail request failed"
                    end
                    completed = true
                end )

                local elapsed = 0
                while not completed and elapsed < timeoutSeconds do
                    LrTasks.sleep( pollInterval )
                    elapsed = elapsed + pollInterval
                end

                holdRef = nil

                if not completed then
                    table.insert( results, {
                        localId = photo.localIdentifier or "",
                        filename = safeGetFormattedMetadata( photo, 'fileName' ) or "",
                        error = "Timeout waiting for thumbnail"
                    } )
                elseif errMsg then
                    table.insert( results, {
                        localId = photo.localIdentifier or "",
                        filename = safeGetFormattedMetadata( photo, 'fileName' ) or "",
                        error = errMsg
                    } )
                else
                    table.insert( results, {
                        localId = photo.localIdentifier or "",
                        filename = safeGetFormattedMetadata( photo, 'fileName' ) or "",
                        jpegBase64 = base64encode( jpegData )
                    } )
                end
            end
        end

        return { photos = results }
    end )
end

--[[
    list_develop_presets - Lists all develop preset folders and their presets
    Returns: { presets: array of { name, uuid, folder } }
]]
function CommandHandlers.list_develop_presets( params )
    return safeCall( function()
        local LrApplication = import 'LrApplication'
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local presetFolders = LrApplication.developPresetFolders()
        local result = {}

        for _, folder in ipairs( presetFolders ) do
            local folderName = folder:getName() or ""
            local presets = folder:getDevelopPresets()
            for _, preset in ipairs( presets ) do
                table.insert( result, {
                    name = preset:getName() or "",
                    uuid = preset:getUuid() or "",
                    folder = folderName
                } )
            end
        end

        return { presets = result }
    end )
end

--[[
    apply_develop_preset - Applies a develop preset to selected photos
    Params: { presetName?: string, presetUuid?: string }
]]
function CommandHandlers.apply_develop_preset( params )
    return safeCall( function()
        if not params or ( not params.presetName and not params.presetUuid ) then
            return { error = "Either presetName or presetUuid must be provided" }
        end

        local LrApplication = import 'LrApplication'
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        local preset = nil
        if params.presetUuid then
            preset = LrApplication.developPresetByUuid( params.presetUuid )
        elseif params.presetName then
            -- Search for preset by name
            local presetFolders = LrApplication.developPresetFolders()
            for _, folder in ipairs( presetFolders ) do
                local presets = folder:getDevelopPresets()
                for _, p in ipairs( presets ) do
                    if p:getName() == params.presetName then
                        preset = p
                        break
                    end
                end
                if preset then
                    break
                end
            end
        end

        if not preset then
            return { error = "Preset not found" }
        end

        catalog:withWriteAccessDo( "MCP Apply Develop Preset", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    photo:applyDevelopPreset( preset )
                end
            end
        end )

        return { success = true }
    end )
end

--[[
    create_snapshot - Creates a develop snapshot for selected photos
    Params: { name: string }
]]
function CommandHandlers.create_snapshot( params )
    return safeCall( function()
        if not params or type( params.name ) ~= "string" or params.name == "" then
            return { error = "Invalid name parameter" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        catalog:withWriteAccessDo( "MCP Create Snapshot", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    photo:createDevelopSnapshot( params.name, false )
                end
            end
        end )

        return { success = true }
    end )
end

--[[
    list_snapshots - Gets all develop snapshots for selected photos
    Returns: { snapshots: array of { id, name } }
]]
function CommandHandlers.list_snapshots( params )
    return safeCall( function()
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { snapshots = {} }
        end

        local allSnapshots = {}
        for _, photo in ipairs( targetPhotos ) do
            if photo then
                local success, snapshots = LrTasks.pcall( function()
                    return photo:getDevelopSnapshots()
                end )
                if success and snapshots then
                    for _, snapshot in ipairs( snapshots ) do
                        table.insert( allSnapshots, {
                            id = snapshot.snapshotID or "",
                            name = snapshot.name or "",
                            photoId = photo.localIdentifier or ""
                        } )
                    end
                end
            end
        end

        return { snapshots = allSnapshots }
    end )
end

--[[
    select_photos - Sets photo selection by local identifiers
    Params: { photoIds: array of numbers }
]]
function CommandHandlers.select_photos( params )
    return safeCall( function()
        if not params or type( params.photoIds ) ~= "table" then
            return { error = "Invalid photoIds parameter - must be an array" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local allPhotos = catalog:getAllPhotos()
        local selectedPhotos = {}
        local activePhoto = nil

        for _, photoId in ipairs( params.photoIds ) do
            for _, photo in ipairs( allPhotos ) do
                if photo and photo.localIdentifier == photoId then
                    if not activePhoto then
                        activePhoto = photo
                    else
                        table.insert( selectedPhotos, photo )
                    end
                    break
                end
            end
        end

        if activePhoto then
            catalog:setSelectedPhotos( activePhoto, selectedPhotos )
            return { success = true }
        else
            return { error = "No matching photos found" }
        end
    end )
end

--[[
    select_all - Selects all photos in the filmstrip
]]
function CommandHandlers.select_all( params )
    return safeCall( function()
        LrSelection.selectAll()
        return { success = true }
    end )
end

--[[
    select_none - Clears the photo selection
]]
function CommandHandlers.select_none( params )
    return safeCall( function()
        LrSelection.selectNone()
        return { success = true }
    end )
end

--[[
    next_photo - Advances selection to next photo
]]
function CommandHandlers.next_photo( params )
    return safeCall( function()
        LrSelection.nextPhoto()
        return { success = true }
    end )
end

--[[
    previous_photo - Moves selection to previous photo
]]
function CommandHandlers.previous_photo( params )
    return safeCall( function()
        LrSelection.previousPhoto()
        return { success = true }
    end )
end

--[[
    switch_module - Switches to a different Lightroom module
    Params: { module: string }
]]
function CommandHandlers.switch_module( params )
    return safeCall( function()
        if not params or type( params.module ) ~= "string" then
            return { error = "Invalid module parameter" }
        end

        local LrApplicationView = import 'LrApplicationView'
        LrApplicationView.switchToModule( params.module )
        return { success = true }
    end )
end

--[[
    get_current_module - Gets the currently active module name
    Returns: { module: string }
]]
function CommandHandlers.get_current_module( params )
    return safeCall( function()
        local LrApplicationView = import 'LrApplicationView'
        local moduleName = LrApplicationView.getCurrentModuleName()
        return { module = moduleName or "" }
    end )
end

--[[
    show_view - Switches the application view mode
    Params: { view: string }
]]
function CommandHandlers.show_view( params )
    return safeCall( function()
        if not params or type( params.view ) ~= "string" then
            return { error = "Invalid view parameter" }
        end

        local LrApplicationView = import 'LrApplicationView'
        LrApplicationView.showView( params.view )
        return { success = true }
    end )
end

--[[
    find_photos - Searches for photos using smart collection-style criteria
    Params: { searchDesc: table }
    Returns: { photos: array of photo details }
    Note: findPhotos must be called from within an async task (server is already async)
]]
function CommandHandlers.find_photos( params )
    return safeCall( function()
        if not params or type( params.searchDesc ) ~= "table" then
            return { error = "Invalid searchDesc parameter - must be a dictionary" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        -- findPhotos requires async task context (server is already in async task)
        local foundPhotos = catalog:findPhotos( { searchDesc = params.searchDesc } )
        local results = {}

        for _, photo in ipairs( foundPhotos ) do
            if photo then
                local pickStatus = safeGetRawMetadata( photo, 'pickStatus' ) or 0
                local pickFlag = "none"
                if pickStatus == 1 then
                    pickFlag = "pick"
                elseif pickStatus == -1 then
                    pickFlag = "reject"
                end

                table.insert( results, {
                    localId = photo.localIdentifier or "",
                    filename = safeGetFormattedMetadata( photo, 'fileName' ) or "",
                    path = safeGetRawMetadata( photo, 'path' ) or "",
                    rating = safeGetRawMetadata( photo, 'rating' ) or 0,
                    label = safeGetRawMetadata( photo, 'colorNameForLabel' ),
                    title = safeGetFormattedMetadata( photo, 'title' ) or "",
                    caption = safeGetFormattedMetadata( photo, 'caption' ) or "",
                    pickFlag = pickFlag
                } )
            end
        end

        return { photos = results }
    end )
end

--[[
    create_smart_collection - Creates a smart collection with search criteria
    Params: { name: string, searchDesc: table }
]]
function CommandHandlers.create_smart_collection( params )
    return safeCall( function()
        if not params or type( params.name ) ~= "string" or params.name == "" then
            return { error = "Invalid name parameter" }
        end
        if not params.searchDesc or type( params.searchDesc ) ~= "table" then
            return { error = "Invalid searchDesc parameter - must be a dictionary" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        catalog:withWriteAccessDo( "MCP Create Smart Collection", function( context )
            catalog:createSmartCollection( params.name, params.searchDesc, nil, false )
        end )

        return { success = true }
    end )
end

--[[
    list_folders - Lists all folders in the catalog hierarchy
    Returns: { folders: array of { name, path, id } }
]]
function CommandHandlers.list_folders( params )
    return safeCall( function()
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local folders = catalog:getFolders()
        local result = {}

        local function processFolder( folder, prefix )
            prefix = prefix or ""
            local success, folderName = LrTasks.pcall( function()
                return folder:getName() or ""
            end )
            if not success then folderName = "" end

            local success2, folderPath = LrTasks.pcall( function()
                return folder:getPath() or ""
            end )
            if not success2 then folderPath = "" end

            table.insert( result, {
                name = prefix .. folderName,
                path = folderPath,
                id = folder.localIdentifier or ""
            } )

            local success3, children = LrTasks.pcall( function()
                return folder:getChildren()
            end )
            if success3 and children then
                for _, child in ipairs( children ) do
                    processFolder( child, prefix .. folderName .. " > " )
                end
            end
        end

        for _, folder in ipairs( folders ) do
            processFolder( folder, "" )
        end

        return { folders = result }
    end )
end

--[[
    create_virtual_copy - Creates virtual copies of selected photos
    Params: { copyName?: string }
]]
function CommandHandlers.create_virtual_copy( params )
    return safeCall( function()
        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        local copyName = params and params.copyName or nil

        LrTasks.startAsyncTask( function()
            catalog:createVirtualCopies( copyName )
        end )

        return { success = true }
    end )
end

--[[
    rotate_photo - Rotates selected photos
    Params: { direction: string } - "left" or "right"
]]
function CommandHandlers.rotate_photo( params )
    return safeCall( function()
        if not params or type( params.direction ) ~= "string" then
            return { error = "Invalid direction parameter" }
        end

        local direction = params.direction:lower()
        if direction ~= "left" and direction ~= "right" then
            return { error = "Direction must be 'left' or 'right'" }
        end

        local catalog = LrApplication.activeCatalog()
        if not catalog then
            return { error = "No active catalog" }
        end

        local targetPhotos = catalog:getTargetPhotos()
        if not targetPhotos or #targetPhotos == 0 then
            return { error = "No photos selected" }
        end

        catalog:withWriteAccessDo( "MCP Rotate Photo", function( context )
            for _, photo in ipairs( targetPhotos ) do
                if photo then
                    if direction == "left" then
                        photo:rotateLeft()
                    else
                        photo:rotateRight()
                    end
                end
            end
        end )

        return { success = true }
    end )
end

return CommandHandlers
