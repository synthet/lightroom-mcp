# Lightroom MCP Agents

This document describes how AI agents can interact with Adobe Lightroom Classic through the Model Context Protocol (MCP) server.

## Overview

The Lightroom MCP server provides a bridge between AI agents and Adobe Lightroom Classic, enabling automated photo management, metadata editing, and catalog operations. Agents can query photo information, modify ratings, labels, and captions, and retrieve catalog details.

## Architecture

The system consists of two main components:

1. **Lightroom Plugin** (`lightroom-plugin.lrplugin/`): A Lua plugin that runs inside Lightroom Classic and handles commands via a local socket connection (port 54321).

2. **MCP Server** (`mcp-server/`): A Python FastMCP server that exposes Lightroom functionality as MCP tools, allowing AI agents to interact with Lightroom through standardized tool calls.

## Available Tools

### `get_studio_info() -> str`

Retrieves information about the active Lightroom catalog.

**Returns:** JSON string containing:
- `catalogName`: Name of the active catalog
- `catalogPath`: File system path to the catalog
- `pluginVersion`: Version of the MCP Bridge plugin

**Use Cases:**
- Verify Lightroom connection
- Identify which catalog is active
- Check plugin availability

**Example Agent Usage:**
```
"Get information about the current Lightroom catalog"
→ Calls get_studio_info()
→ Returns: {"catalogName": "My Photos", "catalogPath": "/Users/...", "pluginVersion": "0.1.0"}
```

### `get_selection() -> str`

Gets details about currently selected photos in Lightroom.

**Returns:** JSON string containing an array of photo objects with:
- `localId`: Unique identifier for the photo
- `filename`: Formatted filename
- `path`: Full file system path
- `rating`: Star rating (0-5)
- `label`: Color label (red, yellow, green, blue, purple, or null)
- `title`: Photo title
- `caption`: Photo caption
- `pickFlag`: Pick flag ("pick", "reject", or "none")
- `keywords`: Array of keyword paths

**Use Cases:**
- Analyze selected photos
- Review metadata before making changes
- Batch operations on selected photos
- Photo organization workflows

**Example Agent Usage:**
```
"Show me details about the selected photos"
→ Calls get_selection()
→ Returns: {"photos": [{"filename": "IMG_001.jpg", "rating": 3, ...}, ...]}
```

### `get_photo_preview(width?: int, height?: int, photo_id?: str, save_path?: str) -> str`

Gets JPEG thumbnail previews for photos. Uses currently selected photos, or a specific photo by `localId` when `photo_id` is provided.

**Parameters:**
- `width`: Max width in pixels (default 800, max 4096).
- `height`: Max height in pixels (default 800, max 4096).
- `photo_id`: Optional. Photo `localId` from `get_selection()` or `search_photos()`. If omitted, uses selected photos.
- `save_path`: Optional. Directory path. If set, saves JPEG file(s) there and returns `{"saved": ["path1", ...]}` instead of base64 data.

**Returns:** JSON string. Without `save_path`: `{"photos": [{"localId", "filename", "jpegBase64"}, ...]}`. With `save_path`: `{"saved": ["/path/to/file1.jpg", ...]}`. Failed items include `"error"` instead of `jpegBase64`.

**Use Cases:**
- Let MCP or AI consume preview images (base64) for analysis or display.
- Export preview JPEGs to a folder for external use.

**Example Agent Usage:**
```
"Get previews of the selected photos"
→ Calls get_photo_preview()
→ Returns: {"photos": [{"localId": "...", "filename": "IMG_001.jpg", "jpegBase64": "..."}, ...]}

"Save previews of the selection to C:\\Previews"
→ Calls get_photo_preview(save_path="C:\\Previews")
→ Returns: {"saved": ["C:\\Previews\\IMG_001.jpg", ...]}
```

### `set_rating(rating: int) -> str`

Sets the star rating for currently selected photos.

**Parameters:**
- `rating`: Integer between 0 and 5

**Returns:** "Success" or error message

**Use Cases:**
- Automated photo culling
- Quality-based organization
- Workflow automation (e.g., "Rate all selected photos as 4 stars")

**Example Agent Usage:**
```
"Rate the selected photos 5 stars"
→ Calls set_rating(5)
→ Returns: "Success"
```

### `set_label(label: str) -> str`

Sets the color label for currently selected photos.

**Parameters:**
- `label`: One of 'Red', 'Yellow', 'Green', 'Blue', 'Purple', 'None'

**Returns:** "Success" or error message

**Use Cases:**
- Categorize photos by color labels
- Mark photos for specific workflows
- Visual organization and filtering

**Example Agent Usage:**
```
"Mark these photos with a green label"
→ Calls set_label("Green")
→ Returns: "Success"
```

### `set_caption(caption: str) -> str`

Sets the caption for currently selected photos.

**Parameters:**
- `caption`: Text caption to apply

**Returns:** "Success" or error message

**Use Cases:**
- Automated caption generation
- Batch caption updates
- Adding descriptions to photos

**Example Agent Usage:**
```
"Add the caption 'Sunset at the beach' to selected photos"
→ Calls set_caption("Sunset at the beach")
→ Returns: "Success"
```

### `set_title(title: str) -> str`

Sets the title for currently selected photos.

**Parameters:**
- `title`: Title text to apply

**Returns:** "Success" or error message

**Use Cases:**
- Automated title generation
- Batch title updates
- Adding descriptive titles to photos

**Example Agent Usage:**
```
"Set the title 'Mountain Landscape' for selected photos"
→ Calls set_title("Mountain Landscape")
→ Returns: "Success"
```

### `set_pick_flag(pick_flag: str) -> str`

Sets the pick flag (pick/reject) for currently selected photos.

**Parameters:**
- `pick_flag`: One of 'pick', 'reject', 'none'

**Returns:** "Success" or error message

**Use Cases:**
- Photo culling workflows
- Marking keepers and rejects
- Organizing photos by pick status

**Example Agent Usage:**
```
"Mark these photos as picks"
→ Calls set_pick_flag("pick")
→ Returns: "Success"
```

### `add_keywords(keywords: list[str]) -> str`

Adds keywords to currently selected photos. Supports hierarchical keywords.

**Parameters:**
- `keywords`: Array of keyword strings. Supports hierarchical keywords using ' > ' separator (e.g., "Location > Europe > France")

**Returns:** "Success" or error message

**Use Cases:**
- Automated keyword tagging
- Batch keyword assignment
- Organizing photos by location, subject, or theme

**Example Agent Usage:**
```
"Add keywords 'Nature' and 'Landscape > Mountains' to selected photos"
→ Calls add_keywords(["Nature", "Landscape > Mountains"])
→ Returns: "Success"
```

### `remove_keywords(keywords: list[str]) -> str`

Removes keywords from currently selected photos.

**Parameters:**
- `keywords`: Array of keyword strings to remove. Supports hierarchical keywords using ' > ' separator

**Returns:** "Success" or error message

**Use Cases:**
- Cleaning up incorrect keywords
- Removing outdated tags
- Batch keyword removal

**Example Agent Usage:**
```
"Remove the keyword 'Old Tag' from selected photos"
→ Calls remove_keywords(["Old Tag"])
→ Returns: "Success"
```

### `get_keywords() -> str`

Gets all keywords from currently selected photos.

**Returns:** JSON string containing an array of keyword paths

**Use Cases:**
- Reviewing existing keywords before modification
- Analyzing keyword usage
- Verifying keyword assignments

**Example Agent Usage:**
```
"Show me all keywords on the selected photos"
→ Calls get_keywords()
→ Returns: {"keywords": ["Nature", "Landscape > Mountains", "Sunset"]}
```

### `list_collections() -> str`

Lists all collections in the active catalog.

**Returns:** JSON string containing an array of collection objects with:
- `name`: Collection name (includes path for nested collections)
- `id`: Collection identifier
- `type`: Always "collection"

**Use Cases:**
- Discovering available collections
- Organizing photos into collections
- Catalog management workflows

**Example Agent Usage:**
```
"List all collections in the catalog"
→ Calls list_collections()
→ Returns: {"collections": [{"name": "Vacation 2024", "id": "...", "type": "collection"}, ...]}
```

### `add_to_collection(collection_name: str) -> str`

Adds currently selected photos to a collection. Creates the collection if it doesn't exist.

**Parameters:**
- `collection_name`: Name of the collection to add photos to

**Returns:** "Success" or error message

**Use Cases:**
- Organizing photos into collections
- Creating new collections automatically
- Batch collection management

**Example Agent Usage:**
```
"Add selected photos to the 'Best Shots' collection"
→ Calls add_to_collection("Best Shots")
→ Returns: "Success"
```

### `search_photos(query: str) -> str`

Searches for photos in the catalog by filename, title, or caption.

**Parameters:**
- `query`: Search query string

**Returns:** JSON string containing an array of matching photo objects (same format as `get_selection()`)

**Use Cases:**
- Finding photos by content
- Locating specific images
- Catalog exploration

**Example Agent Usage:**
```
"Find all photos with 'sunset' in the filename or caption"
→ Calls search_photos("sunset")
→ Returns: {"photos": [{"filename": "sunset_001.jpg", ...}, ...]}
```

### `read_file_metadata(file_path: str) -> str`

Reads EXIF/IPTC/XMP metadata directly from an image file on disk. This reads metadata from the file itself, not from Lightroom catalog.

**Parameters:**
- `file_path`: Absolute path to the image file to read metadata from.

**Returns:** JSON string containing:
- `file`: filename, path, size, modified date
- `hash`: MD5 hash for file identification
- `format`: Image format (JPEG, PNG, etc.)
- `dimensions`: width, height
- `exif`: Structured EXIF data (camera, lens, exposure, dates, GPS, image settings)
- `rawExif`: Raw EXIF tags for completeness

**Use Cases:**
- Analyzing photos before importing to Lightroom
- Reading metadata from files outside the catalog
- Comparing file metadata with Lightroom metadata
- Extracting GPS coordinates from files

**Example Agent Usage:**
```
"Read metadata from this uploaded photo"
→ Calls read_file_metadata("C:\\Photos\\IMG_1234.jpg")
→ Returns: {"file": {"filename": "IMG_1234.jpg", ...}, "exif": {"camera": {"make": "Canon", "model": "EOS R5"}, "exposure": {...}, "gps": {...}}, "hash": "abc123..."}
```

### `find_photo_by_path(file_path: str) -> str`

Finds a photo in Lightroom catalog by its exact file path. Useful for locating a specific file you have on disk within Lightroom.

**Parameters:**
- `file_path`: Full path to the image file to find in Lightroom.

**Returns:** JSON string with `found` (boolean) and `photo` object (photo details if found, null if not).

**Use Cases:**
- Checking if a file is already in Lightroom
- Finding catalog entry for a known file
- Linking external files to Lightroom entries

**Example Agent Usage:**
```
"Is this file in my Lightroom catalog?"
→ Calls find_photo_by_path("D:\\Photos\\2024\\vacation\\IMG_5678.jpg")
→ Returns: {"found": true, "photo": {"localId": "123", "filename": "IMG_5678.jpg", "rating": 4, ...}}
```

### `find_photo_by_filename(filename: str, exact_match: bool = False) -> str`

Finds photos in Lightroom catalog by filename. Useful for locating photos when you have a file but don't know its exact location in Lightroom.

**Parameters:**
- `filename`: Filename to search for (e.g., "IMG_1234.jpg")
- `exact_match`: If True, requires exact filename match. If False (default), uses partial matching.

**Returns:** JSON string with `photos` array of matching photos and `count`.

**Use Cases:**
- Finding all copies/versions of a file
- Locating photos by name
- Searching for uploaded files in catalog

**Example Agent Usage:**
```
"Find this photo in Lightroom"
→ Calls find_photo_by_filename("IMG_1234.jpg", exact_match=True)
→ Returns: {"photos": [{"localId": "123", "filename": "IMG_1234.jpg", "path": "D:\\Photos\\...", ...}], "count": 1}

"Find all photos with 'sunset' in the filename"
→ Calls find_photo_by_filename("sunset", exact_match=False)
→ Returns: {"photos": [...], "count": 5}
```

### `find_photo_by_hash(file_path: str) -> str`

Finds a photo in Lightroom by comparing file hash/checksum. Useful when a file may have been renamed or moved but content is identical.

**Parameters:**
- `file_path`: Path to the image file to match.

**Returns:** JSON string with `found` (boolean) and `photo` object if a hash match is found.

**Use Cases:**
- Finding renamed/moved files
- Verifying file identity across locations
- Matching uploaded files to catalog entries

**Example Agent Usage:**
```
"Find this photo in Lightroom even if it was renamed"
→ Calls find_photo_by_hash("C:\\Downloads\\photo_copy.jpg")
→ Returns: {"found": true, "photo": {"localId": "456", "filename": "original_name.jpg", "path": "D:\\Photos\\...", ...}, "sourceHash": "abc123...", "matchedHash": "abc123..."}
```

### `set_metadata(field: str, value: str) -> str`

Sets a metadata field for currently selected photos. Supports various metadata fields including dates, copyright, GPS, etc.

**Parameters:**
- `field`: Metadata field name (e.g., 'dateCreated', 'copyright', 'gps', 'gpsAltitude')
- `value`: Value to set. For dates, use ISO format strings. For GPS, use appropriate format.

**Returns:** "Success" or error message

**Use Cases:**
- Setting copyright information
- Updating creation dates
- Adding GPS coordinates
- Custom metadata management

**Example Agent Usage:**
```
"Set copyright to 'John Doe 2024' for selected photos"
→ Calls set_metadata("copyright", "John Doe 2024")
→ Returns: "Success"
```

**Note:** Only IPTC metadata fields can be written via `setRawMetadata()`. EXIF fields like `dateTimeOriginal` cannot be modified through this method.

### `get_metadata(fields: list[str]) -> str`

Gets specific metadata fields from currently selected photos.

**Parameters:**
- `fields`: Array of metadata field names to retrieve (e.g., ['dateCreated', 'copyright', 'gps'])

**Returns:** JSON string containing an array of photo metadata objects with:
- `localId`: Photo identifier
- `metadata`: Object with requested field values

**Use Cases:**
- Retrieving specific metadata fields
- Analyzing photo properties
- Verifying metadata values

**Example Agent Usage:**
```
"Get copyright and dateCreated for selected photos"
→ Calls get_metadata(["copyright", "dateCreated"])
→ Returns: {"metadata": [{"localId": "...", "metadata": {"copyright": "John Doe", "dateCreated": "2024-01-15"}}, ...]}
```

### `get_exif_data() -> str`

Gets EXIF metadata from currently selected photos. Returns camera, lens, exposure, and capture settings.

**Returns:** JSON string containing an array of photo objects with:
- `localId`: Photo identifier
- `filename`: Photo filename
- `camera`: `{make, model, serialNumber}`
- `lens`: `{name, focalLength, focalLength35mm}`
- `exposure`: `{aperture, shutterSpeed, iso, exposureBias, exposureProgram, meteringMode}`
- `flash`: `{fired, mode}`
- `dateTimeOriginal`, `dateTimeDigitized`
- `gps`: `{latitude, longitude, altitude, direction}`
- `dimensions`: `{width, height, orientation}`

**Use Cases:**
- Analyzing camera and lens information
- Reviewing exposure settings
- Extracting GPS data
- Understanding image capture details

**Example Agent Usage:**
```
"What camera and lens were used for these photos?"
→ Calls get_exif_data()
→ Returns: {"photos": [{"filename": "IMG_001.jpg", "camera": {"make": "Canon", "model": "EOS R5"}, "lens": {"name": "RF 24-70mm F2.8 L"}, ...}]}
```

### `get_iptc_data() -> str`

Gets IPTC metadata from currently selected photos. Returns creator, copyright, and location information.

**Returns:** JSON string containing an array of photo objects with:
- `localId`: Photo identifier
- `filename`: Photo filename
- `creator`: `{artist, credit, source}`
- `copyright`: `{notice, state, url}`
- `content`: `{headline, caption, title, instructions}`
- `location`: `{city, stateProvince, country, isoCountryCode, location}`
- `workflow`: `{jobIdentifier, provider, rightsUsageTerms}`

**Use Cases:**
- Reviewing copyright and creator information
- Checking location metadata
- Analyzing content descriptions
- Workflow tracking

**Example Agent Usage:**
```
"Show me the copyright and location info for selected photos"
→ Calls get_iptc_data()
→ Returns: {"photos": [{"filename": "IMG_001.jpg", "copyright": {"notice": "© 2024 John Doe"}, "location": {"city": "New York", "country": "USA"}, ...}]}
```

### `set_iptc_data(data: dict) -> str`

Sets IPTC metadata for currently selected photos.

**Parameters:**
- `data`: Dictionary with IPTC fields to set. Supported fields:
  - `creator`/`artist`: Artist/creator name
  - `copyright`: Copyright notice text
  - `copyrightState`: 'copyrighted', 'public domain', or 'unknown'
  - `copyrightInfoUrl`: URL for copyright information
  - `headline`: Brief synopsis/headline
  - `caption`: Description/caption text
  - `title`: Title of the work
  - `instructions`: Special instructions
  - `jobIdentifier`: Job/assignment ID
  - `city`: City name
  - `stateProvince`: State/Province name
  - `country`: Country name
  - `isoCountryCode`: ISO country code (e.g., 'US', 'UK')
  - `location`: Specific location/sublocation
  - `credit`: Credit line
  - `source`: Source
  - `rightsUsageTerms`: Rights usage terms

**Returns:** "Success" or error message

**Use Cases:**
- Setting copyright information
- Adding creator/artist details
- Setting location metadata
- Batch updating IPTC fields

**Example Agent Usage:**
```
"Set copyright to '© 2024 John Doe' and location to New York"
→ Calls set_iptc_data({"copyright": "© 2024 John Doe", "city": "New York", "country": "USA"})
→ Returns: "Success"
```

### `get_xmp_data() -> str`

Gets XMP/Adobe-specific metadata from currently selected photos. Returns processing history, edit information, and Adobe-specific fields.

**Returns:** JSON string containing an array of photo objects with:
- `localId`: Photo identifier
- `filename`: Photo filename
- `fileInfo`: `{fileFormat, fileType, originalFilename, sidecarPath}`
- `dimensions`: `{croppedWidth, croppedHeight, aspectRatio}`
- `editing`: `{editCount, lastEditTime, developPresetName}`
- `catalogInfo`: `{dateAdded, uuid, isVirtualCopy, masterPhoto, stackPosition, stackInFolderIsCollapsed}`
- `colorLabel`: `{colorNameForLabel, label}`
- `smartPreview`: `{hasSmartPreview}`

**Use Cases:**
- Checking edit history
- Understanding file format and processing
- Working with virtual copies and stacks
- Analyzing smart preview status

**Example Agent Usage:**
```
"How many times have these photos been edited?"
→ Calls get_xmp_data()
→ Returns: {"photos": [{"filename": "IMG_001.jpg", "editing": {"editCount": 5, "developPresetName": "Vivid Colors"}, ...}]}
```

### `get_all_metadata() -> str`

Gets comprehensive metadata from currently selected photos. Combines EXIF, IPTC, XMP, and Lightroom-specific metadata in one call.

**Returns:** JSON string containing an array of photo objects with all available metadata:
- Basic info: `localId`, `filename`, `path`, `uuid`
- `exif`: Camera, lens, exposure settings, GPS, dimensions
- `iptc`: Creator, copyright, location, content
- `xmp`: Processing info, edit history, catalog info
- `lightroom`: Rating, label, pickStatus, keywords, collections

**Use Cases:**
- Getting complete metadata overview
- Comprehensive photo analysis
- Full metadata export
- Comparing metadata across photos

**Example Agent Usage:**
```
"Give me all metadata for the selected photos"
→ Calls get_all_metadata()
→ Returns: {"photos": [{"localId": "...", "filename": "IMG_001.jpg", "exif": {...}, "iptc": {...}, "xmp": {...}, "lightroom": {...}}]}
```

### `set_gps_data(latitude: float, longitude: float, altitude: float = None) -> str`

Sets GPS coordinates for currently selected photos.

**Parameters:**
- `latitude`: GPS latitude in decimal degrees (-90 to 90)
- `longitude`: GPS longitude in decimal degrees (-180 to 180)
- `altitude`: Optional GPS altitude in meters

**Returns:** "Success" or error message

**Use Cases:**
- Geotagging photos
- Correcting GPS coordinates
- Adding location data to photos without GPS

**Example Agent Usage:**
```
"Set GPS coordinates to Times Square, New York"
→ Calls set_gps_data(40.758, -73.9855)
→ Returns: "Success"
```

### `clear_gps_data() -> str`

Clears/removes GPS coordinates from currently selected photos.

**Returns:** "Success" or error message

**Use Cases:**
- Privacy protection
- Removing incorrect GPS data
- Preparing photos for public sharing without location

**Example Agent Usage:**
```
"Remove GPS data from selected photos for privacy"
→ Calls clear_gps_data()
→ Returns: "Success"
```

### `get_develop_settings() -> str`

Gets develop/Camera Raw settings for currently selected photos. Returns all develop parameters including exposure, color, tone curve, HSL, detail, effects, lens corrections, and calibration settings.

**Returns:** JSON string containing an array of photo objects with:
- `localId`: Photo identifier
- `filename`: Photo filename
- `settings`: Dictionary of all develop parameter names to values

**Use Cases:**
- Analyzing current develop settings
- Reading settings before modification
- Copying settings between photos
- Understanding photo processing state

**Example Agent Usage:**
```
"Get the develop settings for selected photos"
→ Calls get_develop_settings()
→ Returns: {"photos": [{"localId": "...", "filename": "IMG_001.jpg", "settings": {"Exposure": 0.5, "Temperature": 5500, "Contrast": 25, ...}}, ...]}
```

### `set_develop_settings(settings: dict) -> str`

Sets develop/Camera Raw settings for currently selected photos. Supports all develop parameters including basic adjustments, tone curve, HSL/color, split toning, detail, effects, lens corrections, and calibration.

**Parameters:**
- `settings`: Dictionary of parameter names to values. Examples:
  - **Basic/Light**: `{"Exposure": 1.0, "Contrast": 25, "Temperature": 5500, "Tint": 10, "Highlights": -20, "Shadows": 30, "Whites": 5, "Blacks": -10, "Clarity": 15, "Vibrance": 10, "Saturation": 5}`
  - **Tone Curve**: `{"ParametricDarks": -10, "ParametricLights": 15, "ParametricShadows": -5, "ParametricHighlights": 10}`
  - **HSL/Color**: `{"SaturationAdjustmentBlue": -20, "HueAdjustmentOrange": 10, "LuminanceAdjustmentRed": 15}`
  - **Split Toning**: `{"SplitToningShadowHue": 200, "SplitToningShadowSaturation": 25, "SplitToningHighlightHue": 50, "SplitToningHighlightSaturation": 15, "SplitToningBalance": 0}`
  - **Detail**: `{"Sharpness": 40, "SharpenRadius": 1.0, "SharpenDetail": 25, "SharpenEdgeMasking": 60, "LuminanceSmoothing": 0, "ColorNoiseReduction": 25}`
  - **Effects**: `{"Dehaze": 10, "PostCropVignetteAmount": -30, "GrainAmount": 25}`
  - **Lens Corrections**: `{"LensProfileDistortionScale": 100, "DefringePurpleAmount": 5}`
  - **Calibration**: `{"ShadowTint": 0, "RedHue": 0, "RedSaturation": 0}`

**Returns:** "Success" or error message

**Use Cases:**
- Automated photo editing
- Batch adjustments
- Color grading workflows
- Applying presets programmatically
- Fine-tuning exposure and color

**Example Agent Usage:**
```
"Increase exposure by 1 stop and add contrast"
→ Calls set_develop_settings({"Exposure": 1.0, "Contrast": 25})
→ Returns: "Success"

"Warm up the colors and reduce blue saturation"
→ Calls set_develop_settings({"Temperature": 6000, "SaturationAdjustmentBlue": -20})
→ Returns: "Success"
```

**Note:** Only the parameters specified in the `settings` dictionary will be modified. Other develop settings remain unchanged. To reset a parameter to default, you may need to read current settings first, modify them, and apply the full set.

### `list_develop_presets() -> str`

Lists all develop preset folders and their presets.

**Returns:** JSON string containing an array of preset objects with:
- `name`: Preset name
- `uuid`: Preset UUID (for programmatic access)
- `folder`: Folder name containing the preset

**Use Cases:**
- Discovering available presets
- Finding preset UUIDs for programmatic application
- Organizing develop workflows
- Preset management

**Example Agent Usage:**
```
"List all available develop presets"
→ Calls list_develop_presets()
→ Returns: {"presets": [{"name": "Vivid Colors", "uuid": "abc-123", "folder": "User Presets"}, ...]}
```

### `apply_develop_preset(preset_name: str = None, preset_uuid: str = None) -> str`

Applies a develop preset to currently selected photos.

**Parameters:**
- `preset_name`: Name of the preset to apply (optional if preset_uuid is provided)
- `preset_uuid`: UUID of the preset to apply (optional if preset_name is provided)

**Returns:** "Success" or error message

**Use Cases:**
- Applying presets programmatically
- Batch preset application
- Automated photo processing workflows
- Style consistency across photos

**Example Agent Usage:**
```
"Apply the 'Vivid Colors' preset to selected photos"
→ Calls apply_develop_preset(preset_name="Vivid Colors")
→ Returns: "Success"

"Apply preset by UUID"
→ Calls apply_develop_preset(preset_uuid="abc-123-def-456")
→ Returns: "Success"
```

### `create_snapshot(name: str) -> str`

Creates a develop snapshot for currently selected photos. Snapshots allow you to save the current develop settings state and return to it later.

**Parameters:**
- `name`: Name for the snapshot

**Returns:** "Success" or error message

**Use Cases:**
- Saving develop state before major changes
- Creating multiple versions of edits
- Experimenting with different looks
- Version control for photo edits

**Example Agent Usage:**
```
"Create a snapshot called 'Before Color Grading'"
→ Calls create_snapshot("Before Color Grading")
→ Returns: "Success"
```

### `list_snapshots() -> str`

Gets all develop snapshots for currently selected photos.

**Returns:** JSON string containing an array of snapshot objects with:
- `id`: Snapshot identifier
- `name`: Snapshot name
- `photoId`: Photo local identifier

**Use Cases:**
- Reviewing available snapshots
- Managing edit versions
- Understanding edit history

**Example Agent Usage:**
```
"Show me all snapshots for the selected photo"
→ Calls list_snapshots()
→ Returns: {"snapshots": [{"id": "snap1", "name": "Before Color Grading", "photoId": "123"}, ...]}
```

### `select_photos(photo_ids: list[int]) -> str`

Sets the photo selection by providing a list of photo local identifiers.

**Parameters:**
- `photo_ids`: Array of photo local identifiers (numbers)

**Returns:** "Success" or error message

**Use Cases:**
- Programmatically selecting specific photos
- Selecting photos from search results
- Batch operations on specific photos
- Navigation workflows

**Example Agent Usage:**
```
"Select photos with IDs 123, 456, and 789"
→ Calls select_photos([123, 456, 789])
→ Returns: "Success"
```

### `select_all() -> str`

Selects all photos in the filmstrip.

**Returns:** "Success" or error message

**Use Cases:**
- Batch operations on all visible photos
- Selecting entire folders or collections
- Mass operations

**Example Agent Usage:**
```
"Select all photos in the filmstrip"
→ Calls select_all()
→ Returns: "Success"
```

### `select_none() -> str`

Clears the photo selection (deselects all).

**Returns:** "Success" or error message

**Use Cases:**
- Clearing selection before new operations
- Resetting selection state
- Preparing for new batch operations

**Example Agent Usage:**
```
"Clear the selection"
→ Calls select_none()
→ Returns: "Success"
```

### `next_photo() -> str`

Advances the selection to the next photo in the filmstrip.

**Returns:** "Success" or error message

**Use Cases:**
- Navigating through photos programmatically
- Sequential photo review
- Automated culling workflows

**Example Agent Usage:**
```
"Move to the next photo"
→ Calls next_photo()
→ Returns: "Success"
```

### `previous_photo() -> str`

Moves the selection to the previous photo in the filmstrip.

**Returns:** "Success" or error message

**Use Cases:**
- Navigating backwards through photos
- Sequential photo review
- Review workflows

**Example Agent Usage:**
```
"Go back to the previous photo"
→ Calls previous_photo()
→ Returns: "Success"
```

### `switch_module(module: str) -> str`

Switches to a different Lightroom module.

**Parameters:**
- `module`: Module name - one of: 'library', 'develop', 'map', 'book', 'slideshow', 'print', 'web'

**Returns:** "Success" or error message

**Use Cases:**
- Navigating between Lightroom modules
- Workflow automation
- Module-specific operations

**Example Agent Usage:**
```
"Switch to the Develop module"
→ Calls switch_module("develop")
→ Returns: "Success"
```

### `get_current_module() -> str`

Gets the name of the currently active module.

**Returns:** JSON string with module name

**Use Cases:**
- Checking current module context
- Conditional operations based on module
- Workflow state management

**Example Agent Usage:**
```
"What module am I in?"
→ Calls get_current_module()
→ Returns: {"module": "library"}
```

### `show_view(view: str) -> str`

Switches the application's view mode.

**Parameters:**
- `view`: View name - one of:
  - Library views: 'loupe', 'grid', 'compare', 'survey', 'people'
  - Develop views: 'develop_loupe', 'develop_before_after_horiz', 'develop_before_after_vert', 'develop_before', 'develop_reference_horiz', 'develop_reference_vert'

**Returns:** "Success" or error message

**Use Cases:**
- Changing view modes programmatically
- Setting up comparison views
- Workflow automation

**Example Agent Usage:**
```
"Switch to grid view"
→ Calls show_view("grid")
→ Returns: "Success"

"Show before/after comparison"
→ Calls show_view("develop_before_after_horiz")
→ Returns: "Success"
```

### `find_photos(search_desc: dict) -> str`

Searches for photos using smart collection-style search criteria.

**Parameters:**
- `search_desc`: Search descriptor dictionary. Example:
  ```python
  {
      "criteria": "rating",
      "operation": ">=",
      "value": 3
  }
  ```
  Or with multiple criteria:
  ```python
  {
      "criteria": [
          {"criteria": "rating", "operation": ">=", "value": 3},
          {"criteria": "captureTime", "operation": "inLast", "value": 90, "value_units": "days"}
      ],
      "combine": "union"
  }
  ```

**Returns:** JSON string containing an array of matching photo objects (same format as `get_selection()`)

**Use Cases:**
- Advanced photo search
- Finding photos by multiple criteria
- Smart collection-style queries
- Complex filtering operations

**Example Agent Usage:**
```
"Find all photos rated 4 or 5 stars"
→ Calls find_photos({"criteria": "rating", "operation": ">=", "value": 4})
→ Returns: {"photos": [{"filename": "IMG_001.jpg", "rating": 5, ...}, ...]}

"Find photos from the last 30 days rated 3+ stars"
→ Calls find_photos({
    "criteria": [
        {"criteria": "rating", "operation": ">=", "value": 3},
        {"criteria": "captureTime", "operation": "inLast", "value": 30, "value_units": "days"}
    ],
    "combine": "intersect"
})
```

### `create_smart_collection(name: str, search_desc: dict) -> str`

Creates a smart collection with search criteria. Smart collections automatically update as photos match or stop matching the criteria.

**Parameters:**
- `name`: Name for the smart collection
- `search_desc`: Search descriptor dictionary (same format as `find_photos()`)

**Returns:** "Success" or error message

**Use Cases:**
- Creating dynamic collections
- Organizing photos by criteria
- Automated collection management
- Workflow organization

**Example Agent Usage:**
```
"Create a smart collection for all 5-star photos from 2024"
→ Calls create_smart_collection("Best of 2024", {
    "criteria": [
        {"criteria": "rating", "operation": "==", "value": 5},
        {"criteria": "captureTime", "operation": "inYear", "value": 2024}
    ],
    "combine": "intersect"
})
→ Returns: "Success"
```

### `list_folders() -> str`

Lists all folders in the catalog hierarchy.

**Returns:** JSON string containing an array of folder objects with:
- `name`: Folder name (includes path for nested folders)
- `path`: Full file system path
- `id`: Folder identifier

**Use Cases:**
- Discovering catalog structure
- Understanding folder organization
- Catalog management
- Path-based operations

**Example Agent Usage:**
```
"List all folders in the catalog"
→ Calls list_folders()
→ Returns: {"folders": [{"name": "2024", "path": "D:\\Photos\\2024", "id": "123"}, ...]}
```

### `create_virtual_copy(copy_name: str = None) -> str`

Creates virtual copies of currently selected photos. Virtual copies allow multiple develop versions of the same photo without duplicating the file.

**Parameters:**
- `copy_name`: Optional name to apply to each virtual copy

**Returns:** "Success" or error message

**Use Cases:**
- Creating multiple edit versions
- Experimenting with different looks
- Non-destructive editing workflows
- Version management

**Example Agent Usage:**
```
"Create virtual copies of selected photos"
→ Calls create_virtual_copy()
→ Returns: "Success"

"Create virtual copies with a specific name"
→ Calls create_virtual_copy("B&W Version")
→ Returns: "Success"
```

### `rotate_photo(direction: str) -> str`

Rotates currently selected photos.

**Parameters:**
- `direction`: Rotation direction - either 'left' or 'right'

**Returns:** "Success" or error message

**Use Cases:**
- Correcting photo orientation
- Batch rotation operations
- Orientation fixes

**Example Agent Usage:**
```
"Rotate selected photos 90 degrees to the left"
→ Calls rotate_photo("left")
→ Returns: "Success"
```

## Agent Workflows

### Workflow 1: Photo Culling Assistant

An agent can help photographers cull through large batches of photos:

1. User selects photos in Lightroom
2. Agent calls `get_selection()` to retrieve photo details
3. Agent analyzes filenames, existing ratings, or other metadata
4. Agent calls `set_rating()` to mark keepers/rejects
5. Agent calls `set_label()` to categorize photos

**Example:**
```
User: "Rate all selected photos 3 stars, then mark the best ones 5 stars"
Agent:
  1. get_selection() → Analyze photos
  2. set_rating(3) → Rate all as 3
  3. [Agent logic to identify "best" photos]
  4. set_rating(5) → Rate best ones as 5
```

### Workflow 2: Metadata Enhancement

An agent can enhance photo metadata:

1. Agent calls `get_selection()` to get current metadata
2. Agent generates or updates captions based on filenames, dates, or other context
3. Agent calls `set_caption()` to apply new captions
4. Agent calls `set_label()` to organize by content

**Example:**
```
User: "Add descriptive captions to these photos based on their filenames"
Agent:
  1. get_selection() → Get filenames
  2. [Generate captions from filenames]
  3. set_caption("Generated caption") → Apply to each photo
```

### Workflow 4: Keyword Management

An agent can help organize photos with keywords:

1. Agent calls `get_selection()` to see current keywords
2. Agent analyzes photo content or metadata
3. Agent calls `add_keywords()` to tag photos appropriately
4. Agent can use `remove_keywords()` to clean up incorrect tags

**Example:**
```
User: "Tag all selected photos with 'Nature' and 'Landscape' keywords"
Agent:
  1. get_selection() → Verify photos
  2. add_keywords(["Nature", "Landscape"]) → Apply keywords
  3. get_keywords() → Verify tags were applied
```

### Workflow 5: Collection Organization

An agent can organize photos into collections:

1. Agent calls `list_collections()` to see available collections
2. Agent calls `get_selection()` to understand what photos to organize
3. Agent calls `add_to_collection()` to organize photos

**Example:**
```
User: "Add these photos to the 'Vacation 2024' collection"
Agent:
  1. list_collections() → Check if collection exists
  2. add_to_collection("Vacation 2024") → Add photos (creates if needed)
```

### Workflow 6: Photo Search and Discovery

An agent can help find photos in the catalog:

1. Agent calls `search_photos()` with user's query
2. Agent presents results to user
3. Agent can perform operations on search results

**Example:**
```
User: "Find all photos with 'beach' in the title or caption"
Agent:
  1. search_photos("beach") → Find matching photos
  2. Reports: "Found 15 photos matching 'beach'"
```

### Workflow 7: Comprehensive Metadata Management

An agent can manage multiple metadata fields:

1. Agent calls `get_metadata()` to retrieve current values
2. Agent updates specific fields using `set_metadata()`
3. Agent can set title, caption, copyright, dates, etc.

**Example:**
```
User: "Set copyright to 'John Doe 2024' and update the title for selected photos"
Agent:
  1. get_metadata(["copyright", "title"]) → Get current values
  2. set_metadata("copyright", "John Doe 2024") → Set copyright
  3. set_title("Updated Title") → Set title
```

### Workflow 8: Develop Settings Management

An agent can read and modify develop/Camera Raw settings:

1. Agent calls `get_develop_settings()` to read current settings
2. Agent analyzes or modifies settings based on user request
3. Agent calls `set_develop_settings()` to apply changes
4. Agent can copy settings from one photo to others

**Example:**
```
User: "Increase exposure by 1 stop and add some contrast"
Agent:
  1. get_develop_settings() → Read current settings
  2. Calculate new values: Exposure + 1.0, Contrast + 25
  3. set_develop_settings({"Exposure": 1.0, "Contrast": 25}) → Apply changes

User: "Copy the develop settings from the first photo to all other selected photos"
Agent:
  1. get_develop_settings() → Get settings for all photos
  2. Extract settings from first photo
  3. set_develop_settings(firstPhotoSettings) → Apply to all (works on all selected)
```

### Workflow 9: Automated Color Grading

An agent can perform color grading operations:

1. Agent calls `get_develop_settings()` to understand current color state
2. Agent adjusts HSL, temperature, tint, or other color parameters
3. Agent applies changes using `set_develop_settings()`

**Example:**
```
User: "Make the blues more saturated and warm up the overall temperature"
Agent:
  1. get_develop_settings() → Check current settings
  2. set_develop_settings({"SaturationAdjustmentBlue": 20, "Temperature": 6000}) → Apply color adjustments
```

### Workflow 10: EXIF/Camera Analysis

An agent can analyze camera and capture settings across photos:

1. Agent calls `get_exif_data()` to retrieve camera and exposure information
2. Agent analyzes lens choices, exposure settings, ISO patterns
3. Agent can provide insights about shooting patterns

**Example:**
```
User: "What camera settings did I use for these photos?"
Agent:
  1. get_exif_data() → Get camera/lens/exposure data
  2. Reports: "These photos were shot with Canon EOS R5 and RF 24-70mm F2.8L at ISO 400-1600, f/2.8-8, shutter 1/125-1/500s"
```

### Workflow 11: Copyright and IPTC Management

An agent can manage copyright and creator metadata:

1. Agent calls `get_iptc_data()` to check existing copyright info
2. Agent updates fields using `set_iptc_data()`
3. Agent can batch-apply creator, copyright, and location info

**Example:**
```
User: "Add my copyright and location to all selected photos"
Agent:
  1. get_iptc_data() → Check current IPTC data
  2. set_iptc_data({
       "copyright": "© 2024 John Doe",
       "creator": "John Doe",
       "city": "San Francisco",
       "stateProvince": "California",
       "country": "USA"
     }) → Apply IPTC metadata
```

### Workflow 12: GPS Geotagging

An agent can add or modify GPS coordinates:

1. Agent identifies location from user input or other metadata
2. Agent calls `set_gps_data()` with coordinates
3. Or agent calls `clear_gps_data()` for privacy

**Example:**
```
User: "Geotag these photos with the location 'Eiffel Tower, Paris'"
Agent:
  1. Looks up coordinates for Eiffel Tower (48.8584, 2.2945)
  2. set_gps_data(48.8584, 2.2945) → Apply GPS coordinates

User: "Remove GPS from these photos before I share them"
Agent:
  1. clear_gps_data() → Remove all GPS data
```

### Workflow 13: Comprehensive Metadata Audit

An agent can perform a complete metadata review:

1. Agent calls `get_all_metadata()` to get everything in one call
2. Agent analyzes EXIF, IPTC, XMP, and Lightroom metadata
3. Agent identifies missing or inconsistent metadata

**Example:**
```
User: "Audit the metadata for these photos and tell me what's missing"
Agent:
  1. get_all_metadata() → Get complete metadata
  2. Analyzes: EXIF present, IPTC missing copyright, no GPS data
  3. Reports: "These photos are missing copyright info and GPS coordinates. Would you like me to add them?"
```

### Workflow 14: Find Uploaded File in Lightroom

An agent can locate an uploaded/external file in the Lightroom catalog:

1. User provides a file path (e.g., uploaded image)
2. Agent calls `find_photo_by_path()` for exact path match
3. If not found, agent calls `find_photo_by_filename()` to find by name
4. If still not found, agent calls `find_photo_by_hash()` to find by content

**Example:**
```
User: "Find this photo in my Lightroom catalog: C:\Downloads\vacation_photo.jpg"
Agent:
  1. find_photo_by_path("C:\\Downloads\\vacation_photo.jpg") → Not found (different location)
  2. find_photo_by_filename("vacation_photo.jpg") → Found 2 candidates
  3. Reports: "Found 2 photos with that filename. One at D:\Photos\2024\vacation_photo.jpg (4 stars) and another at D:\Archive\vacation_photo.jpg (unrated)"

User: "This photo was renamed, find it by content"
Agent:
  1. find_photo_by_hash("C:\\Downloads\\mystery_photo.jpg") → Found exact match
  2. Reports: "Found the exact same photo in your catalog as 'IMG_5678.jpg' at D:\Photos\2024\Summer\"
```

### Workflow 15: Read External File Metadata

An agent can read metadata from files outside the Lightroom catalog:

1. User provides a file path to analyze
2. Agent calls `read_file_metadata()` to extract EXIF, GPS, etc.
3. Agent can compare with Lightroom data or suggest actions

**Example:**
```
User: "What camera was used for this photo? C:\Downloads\image.jpg"
Agent:
  1. read_file_metadata("C:\\Downloads\\image.jpg")
  2. Reports: "This photo was taken with a Canon EOS R5, 24-70mm lens at f/2.8, 1/250s, ISO 400. Shot on January 15, 2024 in New York (GPS: 40.7128, -74.0060)"

User: "Compare this file's metadata with what's in Lightroom"
Agent:
  1. read_file_metadata("C:\\Photos\\test.jpg") → Get file metadata
  2. find_photo_by_path("C:\\Photos\\test.jpg") → Find in Lightroom
  3. get_exif_data() → Get Lightroom's metadata (after selecting)
  4. Reports differences between file and catalog metadata
```

## Best Practices for Agents

1. **Always verify connection first**: Call `get_studio_info()` to ensure Lightroom is running and the plugin is active.

2. **Check selection before modifying**: Call `get_selection()` to see what photos will be affected before making changes.

3. **Handle errors gracefully**: All tools return error messages that agents should parse and report to users.

4. **Batch operations**: The tools operate on all selected photos, so agents should inform users about the scope of operations.

5. **Respect user intent**: Agents should confirm destructive operations or operations affecting many photos.

6. **Provide feedback**: After operations, agents can call `get_selection()` again to verify changes were applied.

## Error Handling

All tools may return error messages in the following format:
- `"Error: {error message}"` - Specific error from Lightroom or the plugin
- `"Error: No response from Lightroom"` - Connection or communication issue
- `"Error: Rating must be between 0 and 5"` - Validation error

Agents should:
- Parse error messages and provide user-friendly feedback
- Retry operations if connection errors occur
- Validate parameters before calling tools (e.g., rating range, label values)

## Technical Notes

- **Connection**: The MCP server connects to Lightroom via localhost:54321
- **Protocol**: JSON-RPC 2.0 over TCP socket
- **Threading**: Operations are synchronous; agents should wait for responses
- **Selection-based**: All metadata operations work on currently selected photos in Lightroom
- **Write Access**: Metadata changes require write access to the catalog (handled automatically by the plugin)

## Enhanced Features

The following features have been implemented and are available:

✅ **Photo search and filtering** - `search_photos()`, `find_photos()`  
✅ **Collection management** - `list_collections()`, `add_to_collection()`, `create_smart_collection()`  
✅ **Keyword operations** - `add_keywords()`, `remove_keywords()`, `get_keywords()`  
✅ **Title management** - `set_title()`  
✅ **Pick flag operations** - `set_pick_flag()`  
✅ **Advanced metadata** - `set_metadata()`, `get_metadata()`  
✅ **Develop settings access** - `get_develop_settings()`, `set_develop_settings()` - Full Camera Raw API support  
✅ **Develop presets** - `list_develop_presets()`, `apply_develop_preset()`  
✅ **Develop snapshots** - `create_snapshot()`, `list_snapshots()`  
✅ **Photo selection** - `select_photos()`, `select_all()`, `select_none()`, `next_photo()`, `previous_photo()`  
✅ **Module navigation** - `switch_module()`, `get_current_module()`  
✅ **View control** - `show_view()` - Library and Develop view modes  
✅ **EXIF metadata** - `get_exif_data()` - Camera, lens, exposure, GPS, dimensions  
✅ **IPTC metadata** - `get_iptc_data()`, `set_iptc_data()` - Creator, copyright, location  
✅ **XMP metadata** - `get_xmp_data()` - File info, editing history, catalog info  
✅ **Comprehensive metadata** - `get_all_metadata()` - All metadata in one call  
✅ **GPS operations** - `set_gps_data()`, `clear_gps_data()` - Geotagging and privacy  
✅ **File metadata reading** - `read_file_metadata()` - Read EXIF/IPTC from any image file  
✅ **Photo lookup** - `find_photo_by_path()`, `find_photo_by_filename()`, `find_photo_by_hash()` - Find catalog entries  
✅ **Folder management** - `list_folders()` - Catalog folder hierarchy  
✅ **Virtual copies** - `create_virtual_copy()` - Multiple edit versions  
✅ **Photo rotation** - `rotate_photo()` - Orientation correction  
✅ **Thumbnails** - `get_photo_preview()` - Image previews

## Future Enhancements

Potential additions for agent workflows:
- Export operations
- Batch operations across multiple photos
- Photo filtering by metadata criteria
- Additional develop preset operations
