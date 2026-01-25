from mcp.server.fastmcp import FastMCP
from lrc_client import LrCClient
import base64
import io
import json
import logging
import os
import re
import hashlib
import fnmatch
from datetime import datetime

# Try to import Pillow for image metadata reading
try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS, IFD
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

# Try to import rawpy for RAW file preview extraction
try:
    import rawpy
    HAS_RAWPY = True
except ImportError:
    HAS_RAWPY = False

# RAW file extensions supported by rawpy
RAW_EXTENSIONS = {
    '.nef', '.cr2', '.cr3', '.arw', '.orf', '.rw2', '.dng', '.raf',
    '.pef', '.srw', '.x3f', '.3fr', '.mef', '.mrw', '.nrw', '.raw'
}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP Server
mcp = FastMCP("Lightroom MCP")

# Initialize LrC Client
lrc = LrCClient()

@mcp.tool()
def get_studio_info() -> str:
    """
    Get information about the active Lightroom Catalog.
    Returns JSON string with catalog name, path, and plugin version.
    """
    try:
        result = lrc.send_command("get_studio_info")
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_selection() -> str:
    """
    Get the list of currently selected photos in Lightroom.
    Returns JSON string with photo details (filename, rating, label, etc.).
    """
    try:
        result = lrc.send_command("get_selection")
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def set_rating(rating: int) -> str:
    """
    Set the star rating for the currently selected photos.

    Args:
        rating: Integer between 0 and 5.
    """
    if not (0 <= rating <= 5):
        return "Error: Rating must be between 0 and 5"

    try:
        result = lrc.send_command("set_rating", {"rating": rating})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def set_label(label: str) -> str:
    """
    Set the color label for the currently selected photos.

    Args:
        label: One of 'Red', 'Yellow', 'Green', 'Blue', 'Purple', 'None'.
    """
    valid_labels = ['Red', 'Yellow', 'Green', 'Blue', 'Purple', 'None']
    if label not in valid_labels:
        return f"Error: Label must be one of {valid_labels}"

    try:
        result = lrc.send_command("set_label", {"label": label})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def set_caption(caption: str) -> str:
    """
    Set the caption for the currently selected photos.
    """
    try:
        result = lrc.send_command("set_caption", {"caption": caption})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def set_title(title: str) -> str:
    """
    Set the title for the currently selected photos.

    Args:
        title: Title text to apply.
    """
    try:
        result = lrc.send_command("set_title", {"title": title})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def set_pick_flag(pick_flag: str) -> str:
    """
    Set the pick flag (pick/reject) for the currently selected photos.

    Args:
        pick_flag: One of 'pick', 'reject', 'none'.
    """
    valid_flags = ['pick', 'reject', 'none']
    if pick_flag.lower() not in valid_flags:
        return f"Error: pick_flag must be one of {valid_flags}"

    try:
        result = lrc.send_command("set_pick_flag", {"pickFlag": pick_flag})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def add_keywords(keywords: list[str]) -> str:
    """
    Add keywords to the currently selected photos.

    Args:
        keywords: Array of keyword strings. Supports hierarchical keywords using ' > ' separator (e.g., "Location > Europe > France").
    """
    if not isinstance(keywords, list):
        return "Error: keywords must be an array"

    try:
        result = lrc.send_command("add_keywords", {"keywords": keywords})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def remove_keywords(keywords: list[str]) -> str:
    """
    Remove keywords from the currently selected photos.

    Args:
        keywords: Array of keyword strings to remove. Supports hierarchical keywords using ' > ' separator.
    """
    if not isinstance(keywords, list):
        return "Error: keywords must be an array"

    try:
        result = lrc.send_command("remove_keywords", {"keywords": keywords})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_keywords() -> str:
    """
    Get all keywords from the currently selected photos.
    Returns JSON string with array of keyword paths.
    """
    try:
        result = lrc.send_command("get_keywords")
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def list_collections() -> str:
    """
    List all collections in the active catalog.
    Returns JSON string with array of collections (name, id, type).
    """
    try:
        result = lrc.send_command("list_collections")
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def add_to_collection(collection_name: str) -> str:
    """
    Add the currently selected photos to a collection. Creates the collection if it doesn't exist.

    Args:
        collection_name: Name of the collection to add photos to.
    """
    try:
        result = lrc.send_command("add_to_collection", {"collectionName": collection_name})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def search_photos(query: str) -> str:
    """
    Search for photos in the catalog by filename, title, or caption.

    Args:
        query: Search query string.
    Returns JSON string with array of matching photos.
    """
    try:
        result = lrc.send_command("search_photos", {"query": query})
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def set_metadata(field: str, value: str) -> str:
    """
    Set a metadata field for the currently selected photos.

    Args:
        field: Metadata field name (e.g., 'dateCreated', 'copyright', 'gps', 'gpsAltitude').
        value: Value to set. For dates, use ISO format strings. For GPS, use appropriate format.
    """
    try:
        result = lrc.send_command("set_metadata", {"field": field, "value": value})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_metadata(fields: list[str]) -> str:
    """
    Get metadata fields from the currently selected photos.

    Args:
        fields: Array of metadata field names to retrieve (e.g., ['dateCreated', 'copyright', 'gps']).
    Returns JSON string with array of photo metadata objects.
    """
    if not isinstance(fields, list):
        return "Error: fields must be an array"

    try:
        result = lrc.send_command("get_metadata", {"fields": fields})
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_develop_settings() -> str:
    """
    Get develop/Camera Raw settings for the currently selected photos.
    Returns JSON string with array of photo objects containing develop settings.
    Each photo includes localId, filename, and a settings dictionary with all develop parameters.
    """
    try:
        result = lrc.send_command("get_develop_settings")
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def set_develop_settings(settings: dict) -> str:
    """
    Set develop/Camera Raw settings for the currently selected photos.

    Args:
        settings: Dictionary of parameter names to values. Examples:
            - Basic/Light: {"Exposure": 1.0, "Contrast": 25, "Temperature": 5500, "Tint": 10, "Highlights": -20, "Shadows": 30, "Whites": 5, "Blacks": -10, "Clarity": 15, "Vibrance": 10, "Saturation": 5}
            - Tone Curve: {"ParametricDarks": -10, "ParametricLights": 15, "ParametricShadows": -5, "ParametricHighlights": 10}
            - HSL/Color: {"SaturationAdjustmentBlue": -20, "HueAdjustmentOrange": 10, "LuminanceAdjustmentRed": 15}
            - Split Toning: {"SplitToningShadowHue": 200, "SplitToningShadowSaturation": 25, "SplitToningHighlightHue": 50, "SplitToningHighlightSaturation": 15, "SplitToningBalance": 0}
            - Detail: {"Sharpness": 40, "SharpenRadius": 1.0, "SharpenDetail": 25, "SharpenEdgeMasking": 60, "LuminanceSmoothing": 0, "ColorNoiseReduction": 25}
            - Effects: {"Dehaze": 10, "PostCropVignetteAmount": -30, "GrainAmount": 25}
            - Lens Corrections: {"LensProfileDistortionScale": 100, "DefringePurpleAmount": 5}
            - Calibration: {"ShadowTint": 0, "RedHue": 0, "RedSaturation": 0}

    Returns "Success" or error message.
    """
    if not isinstance(settings, dict):
        return "Error: settings must be a dictionary"

    try:
        result = lrc.send_command("set_develop_settings", {"settings": settings})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"


def _sanitize_filename(name: str) -> str:
    """Remove path components and invalid chars for use as a file name."""
    base = os.path.basename(name) if name else "preview"
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", base)
    base = base.strip() or "preview"
    root, ext = os.path.splitext(base)
    return (root or "preview") + ".jpg"



def _find_file(filename: str, search_root: str) -> str | None:
    """
    Recursively search for a file by name starting from search_root.
    Returns the absolute path if found, or None.
    """
    search_root = os.path.abspath(search_root)
    for root, dirnames, filenames in os.walk(search_root):
        # Case-insensitive match matching
        for name in filenames:
            if name.lower() == filename.lower():
                return os.path.join(root, name)

    return None

def _generate_preview_from_path(file_path: str, max_width: int = 800, max_height: int = 800) -> tuple[bytes, str]:
    """
    Generate a JPEG preview from an image file path.

    For RAW files, extracts the embedded JPEG thumbnail using rawpy.
    For other formats, uses PIL to read and resize.

    Args:
        file_path: Path to the image file
        max_width: Maximum width of the preview
        max_height: Maximum height of the preview

    Returns:
        Tuple of (jpeg_bytes, error_message). On success, error_message is None.
        On failure, jpeg_bytes is None.
    """
    if not os.path.isfile(file_path):
        return None, f"File not found: {file_path}"

    ext = os.path.splitext(file_path)[1].lower()
    img = None

    try:
        # Handle RAW files with rawpy
        if ext in RAW_EXTENSIONS:
            if not HAS_RAWPY:
                return None, "rawpy not installed - cannot process RAW files"

            try:
                raw = rawpy.imread(file_path)
                thumb = raw.extract_thumb()
                raw.close()

                if thumb.format == rawpy.ThumbFormat.JPEG:
                    # Embedded JPEG thumbnail - load into PIL for resizing
                    img = Image.open(io.BytesIO(thumb.data))
                elif thumb.format == rawpy.ThumbFormat.BITMAP:
                    # Bitmap data - convert to PIL Image
                    img = Image.fromarray(thumb.data)
                else:
                    return None, f"Unknown thumbnail format from RAW file"
            except Exception as e:
                return None, f"Failed to extract RAW thumbnail: {str(e)}"
        else:
            # Handle standard image formats with PIL
            if not HAS_PILLOW:
                return None, "Pillow not installed - cannot process image files"

            try:
                img = Image.open(file_path)
            except Exception as e:
                return None, f"Failed to open image: {str(e)}"

        if img is None:
            return None, "Failed to load image"

        # Convert to RGB if necessary (handles RGBA, P, etc.)
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')

        # Resize to fit within max dimensions while preserving aspect ratio
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        # Save to JPEG bytes
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        img.close()

        return buffer.getvalue(), None

    except Exception as e:
        if img:
            img.close()
        return None, f"Preview generation failed: {str(e)}"


@mcp.tool()
def get_exif_data() -> str:
    """
    Get EXIF metadata from the currently selected photos.
    Returns camera, lens, exposure, and capture settings.

    Returns JSON with array of photo objects containing:
        - localId, filename
        - camera: make, model, serialNumber
        - lens: name, focalLength, focalLength35mm
        - exposure: aperture, shutterSpeed, iso, exposureBias, exposureProgram, meteringMode
        - flash: fired, mode
        - dateTimeOriginal, dateTimeDigitized
        - gps: latitude, longitude, altitude, direction
        - dimensions: width, height, orientation
    """
    try:
        result = lrc.send_command("get_exif_data")
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_iptc_data() -> str:
    """
    Get IPTC metadata from the currently selected photos.
    Returns creator, copyright, and location information.

    Returns JSON with array of photo objects containing:
        - localId, filename
        - creator: artist, credit, source, byline, bylineTitle
        - copyright: notice, status, url
        - content: headline, caption, title, instructions, scene, subjectCode
        - location: city, stateProvince, country, countryCode, location, sublocation
        - workflow: jobIdentifier, provider, rightsUsageTerms
        - contact: address, city, region, postalCode, country, phone, email, website
    """
    try:
        result = lrc.send_command("get_iptc_data")
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def set_iptc_data(data: dict) -> str:
    """
    Set IPTC metadata for the currently selected photos.

    Args:
        data: Dictionary with IPTC fields to set. Supported fields:
            - creator: Artist name/creator
            - copyright: Copyright notice text
            - copyrightState: 'copyrighted', 'public domain', or 'unknown'
            - copyrightInfoUrl: URL for copyright info
            - headline: Brief synopsis/headline
            - caption: Description/caption text
            - title: Title of the work
            - instructions: Special instructions
            - jobIdentifier: Job/assignment ID
            - city: City name
            - stateProvince: State/Province name
            - country: Country name
            - isoCountryCode: ISO country code (e.g., 'US', 'UK')
            - location: Specific location/sublocation

    Example: {"creator": "John Doe", "copyright": "© 2024 John Doe", "city": "New York"}

    Returns "Success" or error message.
    """
    if not isinstance(data, dict):
        return "Error: data must be a dictionary"

    try:
        result = lrc.send_command("set_iptc_data", {"data": data})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_xmp_data() -> str:
    """
    Get XMP/Adobe-specific metadata from the currently selected photos.
    Returns processing history, edit information, and Adobe-specific fields.

    Returns JSON with array of photo objects containing:
        - localId, filename
        - fileInfo: fileFormat, fileType, originalFilename, sidecarPath
        - dimensions: croppedWidth, croppedHeight, aspectRatio
        - editing: editCount, lastEditTime, developPresetName
        - processing: processVersion, cameraProfile, whiteBalance
        - catalogInfo: dateAdded, virtualCopy, masterPhoto, stackPosition, stackInFolderIsCollapsed
        - colorLabel: colorNameForLabel, label
        - smartPreview: hasSmartPreview, smartPreviewStatus
    """
    try:
        result = lrc.send_command("get_xmp_data")
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_all_metadata() -> str:
    """
    Get comprehensive metadata from the currently selected photos.
    Combines EXIF, IPTC, XMP, and Lightroom-specific metadata in one call.

    Returns JSON with array of photo objects containing all available metadata:
        - Basic info: localId, filename, path, uuid
        - EXIF: camera, lens, exposure settings, GPS, dimensions
        - IPTC: creator, copyright, location, content
        - XMP: processing info, edit history, catalog info
        - Lightroom: rating, label, pickStatus, keywords, collections
    """
    try:
        result = lrc.send_command("get_all_metadata")
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def set_gps_data(latitude: float, longitude: float, altitude: float = None) -> str:
    """
    Set GPS coordinates for the currently selected photos.

    Args:
        latitude: GPS latitude in decimal degrees (-90 to 90)
        longitude: GPS longitude in decimal degrees (-180 to 180)
        altitude: Optional GPS altitude in meters

    Returns "Success" or error message.
    """
    if not (-90 <= latitude <= 90):
        return "Error: Latitude must be between -90 and 90"
    if not (-180 <= longitude <= 180):
        return "Error: Longitude must be between -180 and 180"

    params = {"latitude": latitude, "longitude": longitude}
    if altitude is not None:
        params["altitude"] = altitude

    try:
        result = lrc.send_command("set_gps_data", params)
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def clear_gps_data() -> str:
    """
    Clear/remove GPS coordinates from the currently selected photos.

    Returns "Success" or error message.
    """
    try:
        result = lrc.send_command("clear_gps_data")
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

def _extract_exif_value(value):
    """Helper to convert EXIF values to JSON-serializable format."""
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8', errors='replace')
        except:
            return base64.b64encode(value).decode('ascii')
    elif isinstance(value, tuple):
        if len(value) == 2 and isinstance(value[0], int) and isinstance(value[1], int) and value[1] != 0:
            # Rational number
            return value[0] / value[1]
        return [_extract_exif_value(v) for v in value]
    elif hasattr(value, 'numerator') and hasattr(value, 'denominator'):
        # IFDRational
        if value.denominator != 0:
            return float(value)
        return None
    return value


def _convert_gps_to_decimal(gps_coords, gps_ref):
    """Convert GPS coordinates from degrees/minutes/seconds to decimal."""
    try:
        degrees = float(gps_coords[0])
        minutes = float(gps_coords[1])
        seconds = float(gps_coords[2])
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        if gps_ref in ['S', 'W']:
            decimal = -decimal
        return round(decimal, 6)
    except:
        return None



@mcp.tool()
def get_metadata_by_filename(filename: str, search_root: str = ".") -> str:
    """
    Get metadata for a photo by its filename.

    Tries the following strategy:
    1. If filename is an absolute path, use it directly.
    2. Query Lightroom via search_photos. If found, return LrC metadata.
    3. If not found in LrC, search recursively in search_root.
    4. If found on disk, return file-based metadata.

    Args:
        filename: Name of the file (e.g. "image.jpg") or absolute path.
        search_root: Root directory to search for file if not found in LrC (default: current directory).
    """
    # 1. Check if it's an absolute path that exists
    if os.path.isabs(filename) and os.path.isfile(filename):
        return read_file_metadata(filename)

    base_name = os.path.basename(filename)

    # 2. Try LrC Search first
    lrc_result_str = search_photos(base_name)
    try:
        # Check if we got a valid JSON list response
        # search_photos returns a JSON string, so we need to parse it to check if it's empty
        if not lrc_result_str.startswith("Error"):
            try:
                data = json.loads(lrc_result_str)
                # If we got results and at least one matches our filename reasonably well
                if isinstance(data, list) and len(data) > 0:
                    # Return the LrC metadata for the first match
                    # We might want to be stricter here, but for now this is good
                    return lrc_result_str
            except json.JSONDecodeError:
                pass
    except Exception as e:
        logger.warning(f"LrC search failed: {e}")

    # 3. Fallback to local search
    logger.info(f"File '{base_name}' not found in LrC (or LrC unavailable), searching in {search_root}...")
    found_path = _find_file(base_name, search_root)

    if found_path:
        logger.info(f"Found file at {found_path}")
        return read_file_metadata(found_path)

    return f"Error: File '{filename}' not found in Lightroom catalog or in {os.path.abspath(search_root)}"


@mcp.tool()
def read_file_metadata(file_path: str) -> str:
    """
    Read EXIF/IPTC/XMP metadata directly from an image file on disk.
    This reads metadata from the file itself, not from Lightroom catalog.

    Args:
        file_path: Absolute path to the image file to read metadata from.

    Returns JSON with:
        - file: filename, path, size, modified date
        - exif: camera, lens, exposure settings, GPS, dimensions, dates
        - iptc: creator, copyright, caption (if available)
        - hash: MD5 hash for file identification
    """
    if not HAS_PILLOW:
        return "Error: Pillow library not installed. Run: pip install Pillow"

    file_path = os.path.normpath(file_path)
    if not os.path.isfile(file_path):
        return f"Error: File not found: {file_path}"

    try:
        # Basic file info
        stat = os.stat(file_path)
        file_info = {
            "filename": os.path.basename(file_path),
            "path": file_path,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
        }

        # Calculate file hash for matching
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        file_hash = hasher.hexdigest()

        # Read image with Pillow
        img = Image.open(file_path)

        result = {
            "file": file_info,
            "hash": file_hash,
            "format": img.format,
            "mode": img.mode,
            "dimensions": {
                "width": img.width,
                "height": img.height
            }
        }

        # Extract EXIF data
        exif_data = {}
        gps_data = {}

        exif = img.getexif()
        if exif:
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                exif_data[tag] = _extract_exif_value(value)

            # Get IFD data (more detailed EXIF)
            for ifd_id in IFD:
                try:
                    ifd_data = exif.get_ifd(ifd_id)
                    if ifd_data:
                        for tag_id, value in ifd_data.items():
                            if ifd_id == IFD.GPSInfo:
                                tag = GPSTAGS.get(tag_id, tag_id)
                                gps_data[tag] = _extract_exif_value(value)
                            else:
                                tag = TAGS.get(tag_id, tag_id)
                                exif_data[tag] = _extract_exif_value(value)
                except:
                    pass

        # Structure EXIF into categories
        structured_exif = {
            "camera": {
                "make": exif_data.get("Make"),
                "model": exif_data.get("Model"),
                "software": exif_data.get("Software")
            },
            "lens": {
                "model": exif_data.get("LensModel"),
                "focalLength": exif_data.get("FocalLength"),
                "focalLength35mm": exif_data.get("FocalLengthIn35mmFilm")
            },
            "exposure": {
                "exposureTime": exif_data.get("ExposureTime"),
                "fNumber": exif_data.get("FNumber"),
                "iso": exif_data.get("ISOSpeedRatings"),
                "exposureBias": exif_data.get("ExposureBiasValue"),
                "exposureProgram": exif_data.get("ExposureProgram"),
                "meteringMode": exif_data.get("MeteringMode"),
                "flash": exif_data.get("Flash")
            },
            "dates": {
                "dateTimeOriginal": exif_data.get("DateTimeOriginal"),
                "dateTimeDigitized": exif_data.get("DateTimeDigitized"),
                "dateTime": exif_data.get("DateTime")
            },
            "image": {
                "orientation": exif_data.get("Orientation"),
                "xResolution": exif_data.get("XResolution"),
                "yResolution": exif_data.get("YResolution"),
                "colorSpace": exif_data.get("ColorSpace")
            }
        }

        # Process GPS data
        if gps_data:
            lat = None
            lon = None
            if "GPSLatitude" in gps_data and "GPSLatitudeRef" in gps_data:
                lat = _convert_gps_to_decimal(gps_data["GPSLatitude"], gps_data["GPSLatitudeRef"])
            if "GPSLongitude" in gps_data and "GPSLongitudeRef" in gps_data:
                lon = _convert_gps_to_decimal(gps_data["GPSLongitude"], gps_data["GPSLongitudeRef"])

            structured_exif["gps"] = {
                "latitude": lat,
                "longitude": lon,
                "altitude": gps_data.get("GPSAltitude"),
                "altitudeRef": gps_data.get("GPSAltitudeRef"),
                "timestamp": gps_data.get("GPSTimeStamp"),
                "datestamp": gps_data.get("GPSDateStamp")
            }

        result["exif"] = structured_exif

        # Add raw EXIF for completeness (only non-empty values)
        result["rawExif"] = {k: v for k, v in exif_data.items() if v is not None}

        img.close()
        return json.dumps(result)

    except Exception as e:
        return f"Error reading file metadata: {str(e)}"


@mcp.tool()
def find_photo_by_path(file_path: str) -> str:
    """
    Find a photo in Lightroom catalog by its file path.
    Useful for locating a specific file you have on disk within Lightroom.

    Args:
        file_path: Full path to the image file to find in Lightroom.

    Returns JSON with matching photo details or empty if not found.
    """
    file_path = os.path.normpath(file_path)

    try:
        result = lrc.send_command("find_photo_by_path", {"path": file_path})
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
def find_photo_by_filename(filename: str, exact_match: bool = False) -> str:
    """
    Find photos in Lightroom catalog by filename.
    Useful for locating photos when you have a file but don't know its location in Lightroom.

    Args:
        filename: Filename to search for (e.g., "IMG_1234.jpg")
        exact_match: If True, requires exact filename match. If False (default), uses partial matching.

    Returns JSON with array of matching photos.
    """
    try:
        result = lrc.send_command("find_photo_by_filename", {"filename": filename, "exactMatch": exact_match})
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
def find_photo_by_hash(file_path: str) -> str:
    """
    Find a photo in Lightroom by comparing file hash/checksum.
    Useful when a file may have been renamed or moved but content is identical.

    This reads the file, calculates its hash, then searches Lightroom for photos
    with matching filenames and compares their hashes.

    Args:
        file_path: Path to the image file to match.

    Returns JSON with matching photo details or empty if not found.
    """
    file_path = os.path.normpath(file_path)
    if not os.path.isfile(file_path):
        return f"Error: File not found: {file_path}"

    # Calculate hash of the input file
    try:
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        source_hash = hasher.hexdigest()
    except Exception as e:
        return f"Error reading file: {str(e)}"

    # Get filename for initial search
    filename = os.path.basename(file_path)

    try:
        result = lrc.send_command("find_photo_by_hash", {"filename": filename, "hash": source_hash})
        if result and "error" in result:
            return f"Error: {result['error']['message']}"
        if not result or "result" not in result:
            return "Error: No response from Lightroom"

        payload = result["result"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                return payload

        candidates = payload.get("candidates", [])
        if not candidates:
            return json.dumps({"found": False, "photo": None, "message": payload.get("message", "No matching photos")})

        # Compare hashes by reading candidate files
        for candidate in candidates:
            candidate_path = candidate.get("path", "")
            if candidate_path and os.path.isfile(candidate_path):
                try:
                    hasher = hashlib.md5()
                    with open(candidate_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(65536), b''):
                            hasher.update(chunk)
                    candidate_hash = hasher.hexdigest()

                    if candidate_hash == source_hash:
                        return json.dumps({
                            "found": True,
                            "photo": candidate,
                            "sourceHash": source_hash,
                            "matchedHash": candidate_hash
                        })
                except Exception:
                    continue

        return json.dumps({
            "found": False,
            "photo": None,
            "candidatesChecked": len(candidates),
            "message": "No exact hash match found among candidates"
        })

    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
def get_photo_preview(
    width: int = 800,
    height: int = 800,
    photo_id: str = None,
    save_path: str = None,
) -> str:
    """
    Get JPEG preview thumbnails for photos. Uses selected photos, or a specific photo by ID.

    Generates previews locally from the source files - extracts embedded JPEG from RAW files
    using rawpy, or resizes standard image formats using PIL.

    Args:
        width: Max width in pixels (default 800, max 4096).
        height: Max height in pixels (default 800, max 4096).
        photo_id: Optional photo localId. If omitted, uses currently selected photos.
        save_path: Optional directory path. If set, saves JPEG file(s) there and returns paths instead of base64.

    Returns: JSON with either base64-encoded previews or saved file path(s).
    """
    if not (0 < width <= 4096):
        return "Error: width must be between 1 and 4096"
    if not (0 < height <= 4096):
        return "Error: height must be between 1 and 4096"

    # If photo_id specified, select that photo first
    if photo_id is not None and isinstance(photo_id, str) and photo_id.strip():
        try:
            pid = int(photo_id.strip())
            select_result = lrc.send_command("select_photos", {"photoIds": [pid]})
            if select_result and "error" in select_result:
                return f"Error selecting photo: {select_result['error'].get('message', select_result['error'])}"
        except ValueError:
            return f"Error: Invalid photo_id - must be a number"
        except Exception as e:
            return f"Error selecting photo: {str(e)}"

    # Get photo paths from Lightroom
    try:
        result = lrc.send_command("get_metadata", {"fields": ["path"]})
    except Exception as e:
        return f"Error: {str(e)}"

    if result and "error" in result:
        return f"Error: {result['error'].get('message', result['error'])}"
    if not result or "result" not in result:
        return "Error: No response from Lightroom"

    payload = result["result"]
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return f"Error: Invalid response: {payload}"

    metadata_list = payload.get("metadata") or []
    if not metadata_list:
        return json.dumps({"photos": []})

    # Generate previews locally
    results = []
    saved_paths = []
    seen_filenames = set()

    for i, item in enumerate(metadata_list):
        local_id = item.get("localId", "")
        photo_meta = item.get("metadata", {})
        file_path = photo_meta.get("path", "")
        filename = os.path.basename(file_path) if file_path else f"photo_{local_id}"

        if not file_path:
            results.append({
                "localId": local_id,
                "filename": filename,
                "error": "No file path available"
            })
            continue

        # Generate preview
        jpeg_bytes, error = _generate_preview_from_path(file_path, width, height)

        if error:
            results.append({
                "localId": local_id,
                "filename": filename,
                "error": error
            })
            continue

        if save_path:
            # Save to file
            save_dir = os.path.normpath(save_path)
            try:
                os.makedirs(save_dir, exist_ok=True)
            except OSError as e:
                results.append({
                    "localId": local_id,
                    "filename": filename,
                    "error": f"Cannot create directory: {e}"
                })
                continue

            base_name = _sanitize_filename(filename)
            name = base_name
            idx = 0
            while name in seen_filenames:
                idx += 1
                root, _ = os.path.splitext(base_name)
                name = f"{root}_{idx}.jpg"
            seen_filenames.add(name)

            out_path = os.path.join(save_dir, name)
            try:
                with open(out_path, "wb") as f:
                    f.write(jpeg_bytes)
                saved_paths.append(out_path)
            except OSError as e:
                results.append({
                    "localId": local_id,
                    "filename": filename,
                    "error": f"Cannot write file: {e}"
                })
        else:
            # Return as base64
            results.append({
                "localId": local_id,
                "filename": filename,
                "jpegBase64": base64.b64encode(jpeg_bytes).decode('ascii')
            })

    if save_path:
        return json.dumps({"saved": saved_paths})

    return json.dumps({"photos": results})


# ============================================================================
# Develop Presets Tools
# ============================================================================

@mcp.tool()
def list_develop_presets() -> str:
    """
    List all develop preset folders and their presets.
    Returns JSON string with array of preset objects (name, uuid, folder).
    """
    try:
        result = lrc.send_command("list_develop_presets")
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def apply_develop_preset(preset_name: str = None, preset_uuid: str = None) -> str:
    """
    Apply a develop preset to the currently selected photos.

    Args:
        preset_name: Name of the preset to apply (optional if preset_uuid is provided).
        preset_uuid: UUID of the preset to apply (optional if preset_name is provided).
    """
    if not preset_name and not preset_uuid:
        return "Error: Either preset_name or preset_uuid must be provided"

    try:
        params = {}
        if preset_name:
            params["presetName"] = preset_name
        if preset_uuid:
            params["presetUuid"] = preset_uuid

        result = lrc.send_command("apply_develop_preset", params)
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def create_snapshot(name: str) -> str:
    """
    Create a develop snapshot for the currently selected photos.

    Args:
        name: Name for the snapshot.
    """
    if not name or not isinstance(name, str):
        return "Error: name must be a non-empty string"

    try:
        result = lrc.send_command("create_snapshot", {"name": name})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def list_snapshots() -> str:
    """
    Get all develop snapshots for the currently selected photos.
    Returns JSON string with array of snapshot objects (id, name).
    """
    try:
        result = lrc.send_command("list_snapshots")
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

# ============================================================================
# Selection and Navigation Tools
# ============================================================================

@mcp.tool()
def select_photos(photo_ids: list[int]) -> str:
    """
    Set the photo selection by providing a list of photo local identifiers.

    Args:
        photo_ids: Array of photo local identifiers (numbers).
    """
    if not isinstance(photo_ids, list):
        return "Error: photo_ids must be an array"

    try:
        result = lrc.send_command("select_photos", {"photoIds": photo_ids})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def select_all() -> str:
    """
    Select all photos in the filmstrip.
    """
    try:
        result = lrc.send_command("select_all")
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def select_none() -> str:
    """
    Clear the photo selection (deselect all).
    """
    try:
        result = lrc.send_command("select_none")
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def next_photo() -> str:
    """
    Advance the selection to the next photo in the filmstrip.
    """
    try:
        result = lrc.send_command("next_photo")
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def previous_photo() -> str:
    """
    Move the selection to the previous photo in the filmstrip.
    """
    try:
        result = lrc.send_command("previous_photo")
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

# ============================================================================
# Module and View Control Tools
# ============================================================================

@mcp.tool()
def switch_module(module: str) -> str:
    """
    Switch to a different Lightroom module.

    Args:
        module: Module name - one of: 'library', 'develop', 'map', 'book', 'slideshow', 'print', 'web'.
    """
    valid_modules = ['library', 'develop', 'map', 'book', 'slideshow', 'print', 'web']
    if module not in valid_modules:
        return f"Error: module must be one of {valid_modules}"

    try:
        result = lrc.send_command("switch_module", {"module": module})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_current_module() -> str:
    """
    Get the name of the currently active module.
    Returns JSON string with module name.
    """
    try:
        result = lrc.send_command("get_current_module")
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def show_view(view: str) -> str:
    """
    Switch the application's view mode.

    Args:
        view: View name - one of: 'loupe', 'grid', 'compare', 'survey', 'people',
              'develop_loupe', 'develop_before_after_horiz', 'develop_before_after_vert',
              'develop_before', 'develop_reference_horiz', 'develop_reference_vert'.
    """
    valid_views = ['loupe', 'grid', 'compare', 'survey', 'people',
                   'develop_loupe', 'develop_before_after_horiz', 'develop_before_after_vert',
                   'develop_before', 'develop_reference_horiz', 'develop_reference_vert']
    if view not in valid_views:
        return f"Error: view must be one of {valid_views}"

    try:
        result = lrc.send_command("show_view", {"view": view})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

# ============================================================================
# Advanced Search and Organization Tools
# ============================================================================

@mcp.tool()
def find_photos(search_desc: dict) -> str:
    """
    Search for photos using smart collection-style search criteria.

    Args:
        search_desc: Search descriptor dictionary. Example:
            {
                "criteria": "rating",
                "operation": ">=",
                "value": 3
            }
            Or with combine:
            {
                {"criteria": "rating", "operation": ">=", "value": 3},
                {"criteria": "captureTime", "operation": "inLast", "value": 90, "value_units": "days"},
                "combine": "union"
            }
    Returns JSON string with array of matching photos.
    """
    if not isinstance(search_desc, dict):
        return "Error: search_desc must be a dictionary"

    try:
        result = lrc.send_command("find_photos", {"searchDesc": search_desc})
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def create_smart_collection(name: str, search_desc: dict) -> str:
    """
    Create a smart collection with search criteria.

    Args:
        name: Name for the smart collection.
        search_desc: Search descriptor dictionary (same format as find_photos).
    """
    if not name or not isinstance(name, str):
        return "Error: name must be a non-empty string"
    if not isinstance(search_desc, dict):
        return "Error: search_desc must be a dictionary"

    try:
        result = lrc.send_command("create_smart_collection", {"name": name, "searchDesc": search_desc})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def list_folders() -> str:
    """
    List all folders in the catalog hierarchy.
    Returns JSON string with array of folder objects (name, path, id).
    """
    try:
        result = lrc.send_command("list_folders")
        if result and "result" in result:
            return str(result["result"])
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

# ============================================================================
# Photo Operations Tools
# ============================================================================

@mcp.tool()
def create_virtual_copy(copy_name: str = None) -> str:
    """
    Create virtual copies of the currently selected photos.

    Args:
        copy_name: Optional name to apply to each virtual copy.
    """
    try:
        params = {}
        if copy_name:
            params["copyName"] = copy_name

        result = lrc.send_command("create_virtual_copy", params)
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def rotate_photo(direction: str) -> str:
    """
    Rotate the currently selected photos.

    Args:
        direction: Rotation direction - either 'left' or 'right'.
    """
    if direction not in ['left', 'right']:
        return "Error: direction must be 'left' or 'right'"

    try:
        result = lrc.send_command("rotate_photo", {"direction": direction})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            return f"Error: {result['error']['message']}"
        else:
            return "Error: No response from Lightroom"
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    mcp.run()
