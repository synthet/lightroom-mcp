# Lightroom SDK Integration

This document describes how the Lightroom MCP plugin integrates with the Adobe Lightroom Classic SDK (version 15.0).

## SDK Version

The plugin is built against **Lightroom SDK 15.0** (Lightroom Classic 15.1), with minimum SDK version 10.0 for backward compatibility.

## SDK Reference Location

**Official SDK Download**: [Adobe Lightroom Classic SDK](https://developer.adobe.com/console/4061681/servicesandapis)

The SDK is located in `lightroom_SDK/` and includes:
- **API Reference** (`lightroom_SDK/API Reference/`) - HTML documentation for all SDK modules
- **Sample Plugins** (`lightroom_SDK/Sample Plugins/`) - Reference implementations
- **Manual** (`lightroom_SDK/Manual/`) - PDF guides

## Key SDK Modules Used

### Core Modules

- **LrApplication** - Access to active catalog and application state
- **LrSocket** - TCP socket communication (port 8086)
- **LrTasks** - Asynchronous task management
- **LrFunctionContext** - Resource lifecycle management
- **LrLogger** - Logging and debugging

### Photo Metadata Modules

- **LrSelection** - Photo selection operations
- **LrCatalog** - Catalog operations and photo access
- **LrPhoto** - Photo metadata access and modification

### Develop Settings Modules

- **LrPhoto:getDevelopSettings()** - Retrieves all develop/Camera Raw settings from a photo
- **LrPhoto:applyDevelopSettings()** - Applies develop settings to a photo
- **LrDevelopController** - Controls develop module for the currently active photo (not used in MCP plugin, but available in SDK)

The plugin uses `photo:getDevelopSettings()` and `photo:applyDevelopSettings()` for batch operations on selected photos, which is more suitable for MCP workflows than `LrDevelopController` (which only works on the photo currently in Develop view).

### Develop Presets Modules

- **LrApplication.developPresetFolders()** - Gets all develop preset folders
- **LrDevelopPresetFolder** - Represents a folder containing develop presets
  - `folder:getName()` - Gets folder name
  - `folder:getDevelopPresets()` - Gets presets in folder
- **LrDevelopPreset** - Represents a develop preset
  - `preset:getName()` - Gets preset name
  - `preset:getUuid()` - Gets preset UUID
- **LrApplication.developPresetByUuid()** - Finds preset by UUID
- **LrPhoto:applyDevelopPreset()** - Applies a preset to a photo

### Develop Snapshots Modules

- **LrPhoto:createDevelopSnapshot()** - Creates a snapshot of current develop settings
- **LrPhoto:getDevelopSnapshots()** - Gets all snapshots for a photo
  - Returns array of snapshot objects with `snapshotID` and `name` properties

### Selection and Navigation Modules

- **LrSelection** - Photo selection operations
  - `LrSelection.selectAll()` - Selects all photos in filmstrip
  - `LrSelection.selectNone()` - Clears selection
  - `LrSelection.nextPhoto()` - Advances to next photo
  - `LrSelection.previousPhoto()` - Moves to previous photo
- **LrCatalog:setSelectedPhotos()** - Sets photo selection programmatically
  - Takes active photo and array of additional selected photos

### Module and View Control Modules

- **LrApplicationView** - Application view and module control
  - `LrApplicationView.switchToModule(moduleName)` - Switches to module ('library', 'develop', 'map', 'book', 'slideshow', 'print', 'web')
  - `LrApplicationView.getCurrentModuleName()` - Gets current module name
  - `LrApplicationView.showView(viewName)` - Switches view mode
    - Library views: 'loupe', 'grid', 'compare', 'survey', 'people'
    - Develop views: 'develop_loupe', 'develop_before_after_horiz', 'develop_before_after_vert', 'develop_before', 'develop_reference_horiz', 'develop_reference_vert'

### Search and Organization Modules

- **LrCatalog:findPhotos()** - Searches for photos using smart collection-style criteria
  - Takes search descriptor dictionary with criteria, operations, and values
  - Must be called from within an async task
- **LrCatalog:createSmartCollection()** - Creates a smart collection with search criteria
  - Takes name, search descriptor, parent collection set (optional), and whether to include subfolders
- **LrCatalog:getFolders()** - Gets all folders in the catalog hierarchy
  - Returns array of `LrFolder` objects
- **LrFolder** - Represents a folder in the catalog
  - `folder:getName()` - Gets folder name
  - `folder:getPath()` - Gets file system path
  - `folder:getChildren()` - Gets child folders and photos

### Photo Operations Modules

- **LrCatalog:createVirtualCopies()** - Creates virtual copies of selected photos
  - Takes optional copy name
  - Must be called from within an async task
- **LrPhoto:rotateLeft()** - Rotates photo 90 degrees counter-clockwise
- **LrPhoto:rotateRight()** - Rotates photo 90 degrees clockwise
- **LrPhoto:requestJpegThumbnail()** - Requests JPEG thumbnail preview
  - Takes width and height parameters
  - Returns callback function with success/failure
  - Asynchronous operation - requires waiting for callback

## Implementation Patterns

### Socket Server Pattern

The plugin follows the SDK's `remote_control_socket` example pattern:

```lua
serverSocket = LrSocket.bind {
    name = "MCP Bridge Server",
    functionContext = context,
    address = "localhost",
    port = 8086,
    mode = "receive",  -- Server receives messages
    onConnecting = function(socket, port) ... end,
    onConnected = function(socket, port) ... end,
    onMessage = function(socket, message) ... end,
    onClosed = function(socket) ... end,
    onError = function(socket, err) ... end,
    plugin = _PLUGIN
}
```

### Lifecycle Management

**Initialization** (`Init.lua`):
- Uses `LrTasks.startAsyncTask()` to start server in background
- Wraps server in `LrFunctionContext.callWithContext()` for proper resource management

**Shutdown** (`Shutdown.lua`):
- Implements `LrShutdownFunction` pattern from SDK
- Signals server to stop via global flag (`_G.mcpServerRunning`)
- Provides progress feedback during cleanup
- Ensures socket connections are properly closed

### Catalog Operations

All metadata modifications use the SDK's write access pattern:

```lua
catalog:withWriteAccessDo( "Operation Name", function( context )
    for _, photo in ipairs( targetPhotos ) do
        photo:setRawMetadata( 'field', value )
    end
end )
```

### Develop Settings Operations

Develop settings use `photo:getDevelopSettings()` and `photo:applyDevelopSettings()`:

```lua
-- Reading develop settings
local settings = photo:getDevelopSettings()
-- Returns a dictionary of all develop parameters

-- Applying develop settings
catalog:withWriteAccessDo( "MCP Set Develop Settings", function( context )
    for _, photo in ipairs( targetPhotos ) do
        photo:applyDevelopSettings( settingsDict )
    end
end )
```

**Supported Parameters**: All Camera Raw develop parameters are supported, including:
- **Basic/Light**: Temperature, Tint, Exposure, Contrast, Highlights, Shadows, Whites, Blacks, Clarity, Vibrance, Saturation
- **Tone Curve**: ParametricDarks, ParametricLights, ParametricShadows, ParametricHighlights, and split points
- **HSL/Color**: HueAdjustment*, SaturationAdjustment*, LuminanceAdjustment* for 8 color ranges
- **Split Toning**: SplitToningShadowHue/Saturation, SplitToningHighlightHue/Saturation, SplitToningBalance
- **Detail**: Sharpness, SharpenRadius/Detail/EdgeMasking, LuminanceSmoothing, ColorNoiseReduction
- **Effects**: Dehaze, PostCropVignette*, Grain*
- **Lens Corrections**: LensProfile*, Defringe*, Perspective*
- **Calibration**: ShadowTint, Red/Green/BlueHue, Red/Green/BlueSaturation

See the SDK's `LrDevelopController` API reference for the complete list of parameter names.

### Develop Presets Operations

Develop presets use `LrApplication.developPresetFolders()` and preset objects:

```lua
-- Listing presets
local presetFolders = LrApplication.developPresetFolders()
for _, folder in ipairs( presetFolders ) do
    local folderName = folder:getName()
    local presets = folder:getDevelopPresets()
    for _, preset in ipairs( presets ) do
        local presetName = preset:getName()
        local presetUuid = preset:getUuid()
    end
end

-- Finding preset by UUID
local preset = LrApplication.developPresetByUuid( uuid )

-- Applying preset
catalog:withWriteAccessDo( "MCP Apply Preset", function( context )
    for _, photo in ipairs( targetPhotos ) do
        photo:applyDevelopPreset( preset )
    end
end )
```

### Develop Snapshots Operations

Snapshots use `photo:createDevelopSnapshot()` and `photo:getDevelopSnapshots()`:

```lua
-- Creating snapshot
catalog:withWriteAccessDo( "MCP Create Snapshot", function( context )
    for _, photo in ipairs( targetPhotos ) do
        photo:createDevelopSnapshot( "Snapshot Name", false )
    end
end )

-- Listing snapshots
local snapshots = photo:getDevelopSnapshots()
for _, snapshot in ipairs( snapshots ) do
    local id = snapshot.snapshotID
    local name = snapshot.name
end
```

### Selection Operations

Selection uses `LrSelection` and `catalog:setSelectedPhotos()`:

```lua
-- Using LrSelection
LrSelection.selectAll()
LrSelection.selectNone()
LrSelection.nextPhoto()
LrSelection.previousPhoto()

-- Programmatic selection
local allPhotos = catalog:getAllPhotos()
local selectedPhotos = {}
local activePhoto = nil
-- Find photos by ID and build selection
catalog:setSelectedPhotos( activePhoto, selectedPhotos )
```

### Module and View Operations

Module and view control uses `LrApplicationView`:

```lua
-- Switching modules
LrApplicationView.switchToModule( "develop" )

-- Getting current module
local moduleName = LrApplicationView.getCurrentModuleName()

-- Changing views
LrApplicationView.showView( "grid" )
LrApplicationView.showView( "develop_before_after_horiz" )
```

### Search Operations

Search uses `catalog:findPhotos()` with search descriptors:

```lua
-- Simple search
local foundPhotos = catalog:findPhotos( {
    searchDesc = {
        criteria = "rating",
        operation = ">=",
        value = 3
    }
} )

-- Complex search with multiple criteria
local foundPhotos = catalog:findPhotos( {
    searchDesc = {
        criteria = {
            { criteria = "rating", operation = ">=", value = 3 },
            { criteria = "captureTime", operation = "inLast", value = 90, value_units = "days" }
        },
        combine = "intersect"
    }
} )
```

**Note**: `findPhotos()` must be called from within an async task. The server runs in an async task context, so this is handled automatically.

### Smart Collection Operations

Smart collections use `catalog:createSmartCollection()`:

```lua
catalog:withWriteAccessDo( "MCP Create Smart Collection", function( context )
    catalog:createSmartCollection(
        "Collection Name",
        searchDesc,  -- Same format as findPhotos
        nil,         -- Parent collection set (optional)
        false        -- Include subfolders
    )
end )
```

### Folder Operations

Folders use `catalog:getFolders()`:

```lua
local folders = catalog:getFolders()
for _, folder in ipairs( folders ) do
    local name = folder:getName()
    local path = folder:getPath()
    local children = folder:getChildren()  -- Recursive structure
end
```

### Virtual Copy Operations

Virtual copies use `catalog:createVirtualCopies()`:

```lua
-- Must be called from async task
LrTasks.startAsyncTask( function()
    catalog:createVirtualCopies( "Copy Name" )  -- Optional name
end )
```

### Photo Rotation Operations

Rotation uses `photo:rotateLeft()` and `photo:rotateRight()`:

```lua
catalog:withWriteAccessDo( "MCP Rotate Photo", function( context )
    for _, photo in ipairs( targetPhotos ) do
        photo:rotateLeft()   -- or rotateRight()
    end
end )
```

### Thumbnail Operations

Thumbnails use `photo:requestJpegThumbnail()` with callback:

```lua
local completed = false
local jpegData = nil
local holdRef = photo:requestJpegThumbnail( width, height, function( success, failure )
    if success then
        jpegData = success  -- Binary JPEG data
    else
        -- Handle failure
    end
    completed = true
end )

-- Wait for callback (with timeout)
local timeoutSeconds = 30
local elapsed = 0
while not completed and elapsed < timeoutSeconds do
    LrTasks.sleep( 0.1 )
    elapsed = elapsed + 0.1
end

holdRef = nil  -- Release reference
-- jpegData contains binary JPEG, encode to base64 for JSON transport
```

- Uses `pcall()` for safe function calls
- Validates parameters before operations
- Returns structured error responses in JSON-RPC format
- Logs errors to both LrLogger and debug file

## SDK Best Practices Applied

1. **Function Context Management**: All socket operations wrapped in `LrFunctionContext` for automatic cleanup
2. **Async Tasks**: Server runs in async task to avoid blocking Lightroom UI
3. **Resource Cleanup**: Proper shutdown sequence ensures sockets are closed
4. **Error Recovery**: Socket reconnection on timeout errors
5. **Write Access**: All catalog modifications use `withWriteAccessDo()` for thread safety
6. **Metadata Access**: Uses both `getRawMetadata()` and `getFormattedMetadata()` as appropriate
7. **Develop Settings**: Uses `photo:getDevelopSettings()` and `photo:applyDevelopSettings()` for batch operations on selected photos
8. **Async Operations**: Operations requiring async tasks (like `findPhotos()`, `createVirtualCopies()`) are handled within the server's async context
9. **Callback Handling**: Thumbnail requests use callback pattern with timeout handling
10. **Preset Management**: Uses `LrApplication.developPresetFolders()` and preset objects for preset operations
11. **Selection Management**: Uses `LrSelection` for UI-consistent selection operations and `catalog:setSelectedPhotos()` for programmatic selection
12. **View Control**: Uses `LrApplicationView` for module and view switching without requiring user interaction

## Reference Examples

The plugin implementation is based on:
- **remote_control_socket.lrdevplugin** - Socket server pattern
- **API Reference** - Module documentation for:
  - LrSocket, LrApplication, LrCatalog, LrPhoto
  - LrDevelopController (for develop parameter names)
  - LrApplicationView (for module/view control)
  - LrSelection (for selection operations)
  - LrDevelopPreset, LrDevelopPresetFolder (for preset management)
  - LrFolder (for folder operations)

## Testing with SDK

To test the plugin:
1. Load plugin in Lightroom Classic (Plug-in Manager)
2. Check plugin logs at `D:\Projects\lightroom-mcp\plugin_debug.log`
3. Use `mcp-server/test_connection.py` to verify connectivity
4. Monitor Lightroom console for LrLogger output (if enabled)

## SDK Documentation

**Download the SDK**: [Adobe Lightroom Classic SDK](https://developer.adobe.com/console/4061681/servicesandapis)

For detailed API documentation:
- Open `lightroom_SDK/API Reference/index.html` in a browser
- Navigate to specific modules (e.g., `LrSocket.html`, `LrApplication.html`, `LrPhoto.html`, `LrDevelopController.html`)
- Review sample plugins in `lightroom_SDK/Sample Plugins/`

**Key API References**:
- `LrPhoto.html` - `getDevelopSettings()`, `applyDevelopSettings()`, `createDevelopSnapshot()`, `getDevelopSnapshots()`, `applyDevelopPreset()`, `rotateLeft()`, `rotateRight()`, `requestJpegThumbnail()`
- `LrDevelopController.html` - Complete list of develop parameter names and their usage
- `LrApplication.html` - `developPresetFolders()`, `developPresetByUuid()`
- `LrDevelopPreset.html` - Preset object methods (`getName()`, `getUuid()`)
- `LrDevelopPresetFolder.html` - Preset folder methods (`getName()`, `getDevelopPresets()`)
- `LrSelection.html` - Selection operations (`selectAll()`, `selectNone()`, `nextPhoto()`, `previousPhoto()`)
- `LrApplicationView.html` - Module and view control (`switchToModule()`, `getCurrentModuleName()`, `showView()`)
- `LrCatalog.html` - `findPhotos()`, `createSmartCollection()`, `getFolders()`, `setSelectedPhotos()`, `createVirtualCopies()`
- `LrFolder.html` - Folder operations (`getName()`, `getPath()`, `getChildren()`)

## Version Compatibility

- **Minimum SDK**: 10.0 (Lightroom Classic 10.0+)
- **Target SDK**: 15.0 (Lightroom Classic 15.1)
- **Tested with**: Lightroom Classic 15.1

## Notes

- The SDK uses Lua 5.1-compatible syntax
- Some SDK modules may not be available in all Lightroom versions
- Plugin must be reloaded after code changes (restart Lightroom or use Plug-in Manager)
