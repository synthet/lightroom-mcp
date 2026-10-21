import base64
import io
import json
import logging
import os
import re
import hashlib
import fnmatch
from datetime import datetime
from typing import Optional, Any
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession
from mcp.shared.exceptions import McpError
from mcp.types import INVALID_PARAMS, INTERNAL_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, PARSE_ERROR, ErrorData

class ErrorCode:
    PARSE_ERROR = PARSE_ERROR
    INVALID_REQUEST = INVALID_REQUEST
    METHOD_NOT_FOUND = METHOD_NOT_FOUND
    INVALID_PARAMS = INVALID_PARAMS
    INTERNAL_ERROR = INTERNAL_ERROR

from lrc_client import LrCClient

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

@dataclass
class AppContext:
    lrc: LrCClient

@asynccontextmanager
async def app_lifespan(server: FastMCP):
    """Manage Lightroom client lifecycle."""
    lrc = LrCClient()
    try:
        # Check connection on startup
        status = lrc._ensure_broker_running()
        logger.info(f"Lightroom broker status: {'OK' if status else 'Not running'}")
        yield AppContext(lrc=lrc)
    finally:
        lrc.close()

# Initialize MCP Server with metadata
mcp = FastMCP(
    "Lightroom MCP",
    instructions="Use this server to control Adobe Lightroom Classic: manage photos, metadata, develop settings, presets, and collections.",
    lifespan=app_lifespan
)

@mcp.tool(annotations={"readOnly": True})
async def get_studio_info(ctx: Context[ServerSession, AppContext]) -> Any:
    """
    Get information about the active Lightroom Catalog.
    Returns dictionary with catalog name, path, and plugin version.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("get_studio_info")
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"readOnly": True})
async def get_selection(ctx: Context[ServerSession, AppContext]) -> Any:
    """
    Get the list of currently selected photos in Lightroom.
    Returns list with photo details (filename, rating, label, etc.).
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("get_selection")
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def set_rating(rating: int, ctx: Context[ServerSession, AppContext]) -> str:
    """
    Set the star rating for the currently selected photos.

    Args:
        rating: Integer between 0 and 5.
    """
    if not (0 <= rating <= 5):
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message="Rating must be between 0 and 5"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("set_rating", {"rating": rating})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def set_label(label: str, ctx: Context[ServerSession, AppContext]) -> str:
    """
    Set the color label for the currently selected photos.

    Args:
        label: One of 'Red', 'Yellow', 'Green', 'Blue', 'Purple', 'None'.
    """
    valid_labels = ['Red', 'Yellow', 'Green', 'Blue', 'Purple', 'None']
    if label not in valid_labels:
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message=f"Label must be one of {valid_labels}"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("set_label", {"label": label})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def set_caption(caption: str, ctx: Context[ServerSession, AppContext]) -> str:
    """
    Set the caption for the currently selected photos.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("set_caption", {"caption": caption})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def set_title(title: str, ctx: Context[ServerSession, AppContext]) -> str:
    """
    Set the title for the currently selected photos.

    Args:
        title: Title text to apply.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("set_title", {"title": title})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def set_pick_flag(pick_flag: str, ctx: Context[ServerSession, AppContext]) -> str:
    """
    Set the pick flag (pick/reject) for the currently selected photos.

    Args:
        pick_flag: One of 'pick', 'reject', 'none'.
    """
    valid_flags = ['pick', 'reject', 'none']
    if pick_flag.lower() not in valid_flags:
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message=f"pick_flag must be one of {valid_flags}"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("set_pick_flag", {"pickFlag": pick_flag})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def add_keywords(keywords: list[str], ctx: Context[ServerSession, AppContext]) -> str:
    """
    Add keywords to the currently selected photos.

    Args:
        keywords: Array of keyword strings. Supports hierarchical keywords using ' > ' separator (e.g., "Location > Europe > France").
    """
    if not isinstance(keywords, list):
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message="keywords must be an array"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("add_keywords", {"keywords": keywords})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def remove_keywords(keywords: list[str], ctx: Context[ServerSession, AppContext]) -> str:
    """
    Remove keywords from the currently selected photos.

    Args:
        keywords: Array of keyword strings to remove. Supports hierarchical keywords using ' > ' separator.
    """
    if not isinstance(keywords, list):
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message="keywords must be an array"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("remove_keywords", {"keywords": keywords})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"readOnly": True})
async def get_keywords(ctx: Context[ServerSession, AppContext]) -> Any:
    """
    Get all keywords from the currently selected photos.
    Returns list of keyword paths.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("get_keywords")
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"readOnly": True})
async def list_collections(ctx: Context[ServerSession, AppContext]) -> Any:
    """
    List all collections in the active catalog.
    Returns list of collections (name, id, type).
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("list_collections")
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def add_to_collection(collection_name: str, ctx: Context[ServerSession, AppContext]) -> str:
    """
    Add the currently selected photos to a collection. Creates the collection if it doesn't exist.

    Args:
        collection_name: Name of the collection to add photos to.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("add_to_collection", {"collectionName": collection_name})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"readOnly": True})
async def search_photos(query: str, ctx: Context[ServerSession, AppContext]) -> Any:
    """
    Search for photos in the catalog by filename, title, or caption.

    Args:
        query: Search query string.
    Returns list of matching photos.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("search_photos", {"query": query})
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def set_metadata(field: str, value: str, ctx: Context[ServerSession, AppContext]) -> str:
    """
    Set a metadata field for the currently selected photos.

    Args:
        field: Metadata field name (e.g., 'dateCreated', 'copyright', 'gps', 'gpsAltitude').
        value: Value to set. For dates, use ISO format strings. For GPS, use appropriate format.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("set_metadata", {"field": field, "value": value})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"readOnly": True})
async def get_metadata(fields: list[str], ctx: Context[ServerSession, AppContext]) -> Any:
    """
    Get metadata fields from the currently selected photos.

    Args:
        fields: Array of metadata field names to retrieve (e.g., ['dateCreated', 'copyright', 'gps']).
    Returns list of photo metadata objects.
    """
    if not isinstance(fields, list):
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message="fields must be an array"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("get_metadata", {"fields": fields})
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))


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
def sanitize_filename(filename: str) -> str:
    """Sanitize filename to be safe for filesystem."""
    # Remove any characters that aren't alphanumeric, space, dot, underscore, or hyphen
    return re.sub(r'[^\w\s\.-]', '', filename).strip()

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


@mcp.tool(annotations={"readOnly": True})
async def get_exif_data(ctx: Context[ServerSession, AppContext]) -> Any:
    """
    Get EXIF metadata from the currently selected photos.
    Returns camera, lens, exposure, and capture settings.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("get_exif_data")
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"readOnly": True})
async def get_iptc_data(ctx: Context[ServerSession, AppContext]) -> Any:
    """
    Get IPTC metadata from the currently selected photos.
    Returns creator, copyright, and location information.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("get_iptc_data")
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def set_iptc_data(data: dict, ctx: Context[ServerSession, AppContext]) -> str:
    """
    Set IPTC metadata for the currently selected photos.
    """
    if not isinstance(data, dict):
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message="data must be a dictionary"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("set_iptc_data", {"data": data})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"readOnly": True})
async def get_xmp_data(ctx: Context[ServerSession, AppContext]) -> Any:
    """
    Get XMP/Adobe-specific metadata from the currently selected photos.
    Returns processing history, edit information, and Adobe-specific fields.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("get_xmp_data")
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"readOnly": True})
async def get_all_metadata(ctx: Context[ServerSession, AppContext]) -> Any:
    """
    Get comprehensive metadata from the currently selected photos.
    Combines EXIF, IPTC, XMP, and Lightroom-specific metadata in one call.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("get_all_metadata")
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def set_gps_data(latitude: float, longitude: float, altitude: Optional[float] = None, ctx: Context[ServerSession, AppContext] = None) -> str:
    """
    Set GPS coordinates for the currently selected photos.

    Args:
        latitude: GPS latitude in decimal degrees (-90 to 90)
        longitude: GPS longitude in decimal degrees (-180 to 180)
        altitude: Optional GPS altitude in meters
    """
    if not (-90 <= latitude <= 90):
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message="Latitude must be between -90 and 90"))
    if not (-180 <= longitude <= 180):
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message="Longitude must be between -180 and 180"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        params = {"latitude": latitude, "longitude": longitude}
        if altitude is not None:
            params["altitude"] = altitude

        result = lrc.send_command("set_gps_data", params)
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def clear_gps_data(ctx: Context[ServerSession, AppContext]) -> str:
    """
    Clear/remove GPS coordinates from the currently selected photos.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("clear_gps_data")
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

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



@mcp.tool(annotations={"readOnly": True})
async def get_metadata_by_filename(filename: str, ctx: Context[ServerSession, AppContext], search_root: str = ".") -> Any:
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
        return await read_file_metadata(filename, ctx)

    base_name = os.path.basename(filename)

    # 2. Try LrC Search first
    try:
        lrc_result = await search_photos(base_name, ctx)
        # If we got results and at least one matches our filename reasonably well
        if isinstance(lrc_result, list) and len(lrc_result) > 0:
            return lrc_result
    except Exception as e:
        logger.warning(f"LrC search failed: {e}")

    # 3. Fallback to local search
    logger.info(f"File '{base_name}' not found in LrC (or LrC unavailable), searching in {search_root}...")
    found_path = _find_file(base_name, search_root)

    if found_path:
        logger.info(f"Found file at {found_path}")
        return await read_file_metadata(found_path, ctx)

    raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"File '{filename}' not found in Lightroom catalog or in {os.path.abspath(search_root)}"))


@mcp.tool(annotations={"readOnly": True})
async def read_file_metadata(file_path: str, ctx: Context[ServerSession, AppContext]) -> Any:
    """
    Read EXIF/IPTC/XMP metadata directly from an image file on disk.
    This reads metadata from the file itself, not from Lightroom catalog.

    Args:
        file_path: Absolute path to the image file to read metadata from.

    Returns dictionary with:
        - file: filename, path, size, modified date
        - exif: camera, lens, exposure settings, GPS, dimensions, dates
        - iptc: creator, copyright, caption (if available)
        - hash: MD5 hash for file identification
    """
    if not HAS_PILLOW:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="Pillow library not installed. Run: pip install Pillow"))

    file_path = os.path.normpath(file_path)
    if not os.path.isfile(file_path):
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message=f"File not found: {file_path}"))

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
        return result

    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error reading file metadata: {str(e)}"))


@mcp.tool(annotations={"readOnly": True})
async def find_photo_by_path(file_path: str, ctx: Context[ServerSession, AppContext]) -> Any:
    """
    Find a photo in Lightroom catalog by its file path.
    Useful for locating a specific file you have on disk within Lightroom.

    Args:
        file_path: Full path to the image file to find in Lightroom.
    """
    file_path = os.path.normpath(file_path)
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("find_photo_by_path", {"path": file_path})
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))


@mcp.tool(annotations={"readOnly": True})
async def find_photo_by_filename(filename: str, ctx: Context[ServerSession, AppContext], exact_match: bool = False) -> Any:
    """
    Find photos in Lightroom catalog by filename.
    Useful for locating photos when you have a file but don't know its location in Lightroom.

    Args:
        filename: Filename to search for (e.g., "IMG_1234.jpg")
        exact_match: If True, requires exact filename match. If False (default), uses partial matching.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("find_photo_by_filename", {"filename": filename, "exactMatch": exact_match})
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))


@mcp.tool(annotations={"readOnly": True})
async def find_photo_by_hash(file_path: str, ctx: Context[ServerSession, AppContext]) -> Any:
    """
    Find a photo in Lightroom by comparing file hash/checksum.
    Useful when a file may have been renamed or moved but content is identical.

    This reads the file, calculates its hash, then searches Lightroom for photos
    with matching filenames and compares their hashes.

    Args:
        file_path: Path to the image file to match.
    """
    file_path = os.path.normpath(file_path)
    if not os.path.isfile(file_path):
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message=f"File not found: {file_path}"))

    # Calculate hash of the input file
    try:
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        source_hash = hasher.hexdigest()
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error reading file: {str(e)}"))

    # Get filename for initial search
    filename = os.path.basename(file_path)
    lrc = ctx.request_context.lifespan_context.lrc

    try:
        result = lrc.send_command("find_photo_by_hash", {"filename": filename, "hash": source_hash})
        if result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        if not result or "result" not in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))

        payload = result["result"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                return payload

        candidates = payload.get("candidates", [])
        if not candidates:
            return {"found": False, "photo": None, "message": payload.get("message", "No matching photos")}

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
                        return {
                            "found": True,
                            "photo": candidate,
                            "sourceHash": source_hash,
                            "matchedHash": candidate_hash
                        }
                except Exception:
                    continue

        return {
            "found": False,
            "photo": None,
            "candidatesChecked": len(candidates),
            "message": "No exact hash match found among candidates"
        }

    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))


@mcp.tool(annotations={"readOnly": True})
async def get_photo_preview(
    ctx: Context[ServerSession, AppContext],
    width: int = 800,
    height: int = 800,
    photo_id: Optional[str | int] = None,
    save_path: Optional[str] = None,
) -> Any:
    """
    Get JPEG preview thumbnails for photos. Uses selected photos, or a specific photo by ID.

    Generates previews locally from the source files - extracts embedded JPEG from RAW files
    using rawpy, or resizes standard image formats using PIL.

    Args:
        width: Max width in pixels (default 800, max 4096).
        height: Max height in pixels (default 800, max 4096).
        photo_id: Optional photo localId. If omitted, uses currently selected photos.
        save_path: Optional directory path. If set, saves JPEG file(s) there and returns paths instead of base64.
    """
    # Validate dimensions
    width = max(1, min(width, 4096))
    height = max(1, min(height, 4096))

    lrc = ctx.request_context.lifespan_context.lrc

    # If photo_id specified, select that photo first
    if photo_id is not None:
        try:
            pid = int(str(photo_id).strip())
            select_result = lrc.send_command("select_photos", {"photoIds": [pid]})
            if select_result and "error" in select_result:
                raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error selecting photo: {select_result['error'].get('message', select_result['error'])}"))
        except ValueError:
            raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message=f"Invalid photo_id: {photo_id}"))
        except Exception as e:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error selecting photo: {str(e)}"))

    # Get photo paths from Lightroom for selected photos
    try:
        result = lrc.send_command("get_metadata", {"fields": ["path"]})
        if not result or "result" not in result:
            if result and "error" in result:
                raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error'].get('message', result['error'])}"))
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))

        payload = result["result"]
        # Handle case where result might be a string (Old API behavior?)
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Invalid response from Lightroom: {payload}"))

        metadata_list = payload.get("metadata") or []
        if not metadata_list:
            return {"photos": [], "message": "No photos selected"}

    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error getting metadata: {str(e)}"))

    # Generate previews locally
    results = []
    saved_paths = []
    seen_filenames = set()

    for item in metadata_list:
        local_id = item.get("localId", "")
        photo_meta = item.get("metadata", {})
        file_path = photo_meta.get("path", "")
        filename = os.path.basename(file_path) if file_path else f"photo_{local_id}.jpg"

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

                base_name = sanitize_filename(filename)
                name = base_name
                idx = 0
                while name in seen_filenames or os.path.exists(os.path.join(save_dir, name)):
                    idx += 1
                    root, ext = os.path.splitext(base_name)
                    name = f"{root}_{idx}{ext}"

                seen_filenames.add(name)
                out_path = os.path.join(save_dir, name)

                with open(out_path, "wb") as f:
                    f.write(jpeg_bytes)
                saved_paths.append(out_path)

                results.append({
                    "localId": local_id,
                    "filename": filename,
                    "savePath": out_path
                })
            except Exception as e:
                results.append({
                    "localId": local_id,
                    "filename": filename,
                    "error": f"Failed to save preview: {str(e)}"
                })
        else:
            # Return as base64
            results.append({
                "localId": local_id,
                "filename": filename,
                "jpegBase64": base64.b64encode(jpeg_bytes).decode('ascii')
            })

    # Return summary consistent with specifications
    response = {"photos": results}
    if save_path and saved_paths:
        response["savedPaths"] = saved_paths

    return response


# ============================================================================
# Develop Presets Tools
# ============================================================================


@mcp.tool(annotations={"readOnly": True})
async def get_develop_settings(ctx: Context[ServerSession, AppContext]) -> Any:
    """
    Get develop/Camera Raw settings for the currently selected photos.
    Returns list of photo objects containing develop settings.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("get_develop_settings")
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def set_develop_settings(settings: dict, ctx: Context[ServerSession, AppContext]) -> str:
    """
    Set develop/Camera Raw settings for the currently selected photos.

    Args:
        settings: Dictionary of parameter names to values (e.g., {"Exposure": 1.0, "Contrast": 25}).
    """
    if not isinstance(settings, dict):
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message="settings must be a dictionary"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("set_develop_settings", {"settings": settings})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"readOnly": True})
async def list_develop_presets(ctx: Context[ServerSession, AppContext]) -> Any:
    """
    List all develop preset folders and their presets.
    Returns list of preset objects (name, uuid, folder).
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("list_develop_presets")
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def apply_develop_preset(preset_name: Optional[str] = None, preset_uuid: Optional[str] = None, ctx: Context[ServerSession, AppContext] = None) -> str:
    """
    Apply a develop preset to the currently selected photos.

    Args:
        preset_name: Name of the preset to apply (optional if preset_uuid is provided).
        preset_uuid: UUID of the preset to apply (optional if preset_name is provided).
    """
    if not preset_name and not preset_uuid:
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message="Either preset_name or preset_uuid must be provided"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        params = {}
        if preset_name: params["presetName"] = preset_name
        if preset_uuid: params["presetUuid"] = preset_uuid

        result = lrc.send_command("apply_develop_preset", params)
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def create_snapshot(name: str, ctx: Context[ServerSession, AppContext]) -> str:
    """
    Create a develop snapshot for the currently selected photos.

    Args:
        name: Name for the snapshot.
    """
    if not name or not isinstance(name, str):
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message="name must be a non-empty string"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("create_snapshot", {"name": name})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"readOnly": True})
async def list_snapshots(ctx: Context[ServerSession, AppContext]) -> Any:
    """
    Get all develop snapshots for the currently selected photos.
    Returns list of snapshot objects (id, name).
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("list_snapshots")
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

# ============================================================================
# Selection and Navigation Tools
# ============================================================================

@mcp.tool(annotations={"destructive": True})
async def select_photos(photo_ids: list[int], ctx: Context[ServerSession, AppContext]) -> str:
    """
    Set the photo selection by providing a list of photo local identifiers.

    Args:
        photo_ids: Array of photo local identifiers (numbers).
    """
    if not isinstance(photo_ids, list):
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message="photo_ids must be an array"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("select_photos", {"photoIds": photo_ids})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def select_all(ctx: Context[ServerSession, AppContext]) -> str:
    """
    Select all photos in the filmstrip.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("select_all")
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def select_none(ctx: Context[ServerSession, AppContext]) -> str:
    """
    Clear the photo selection (deselect all).
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("select_none")
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def next_photo(ctx: Context[ServerSession, AppContext]) -> str:
    """
    Advance the selection to the next photo in the filmstrip.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("next_photo")
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def previous_photo(ctx: Context[ServerSession, AppContext]) -> str:
    """
    Move the selection to the previous photo in the filmstrip.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("previous_photo")
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def switch_module(module: str, ctx: Context[ServerSession, AppContext]) -> str:
    """
    Switch to a different Lightroom module.

    Args:
        module: Module name - one of: 'library', 'develop', 'map', 'book', 'slideshow', 'print', 'web'.
    """
    valid_modules = ['library', 'develop', 'map', 'book', 'slideshow', 'print', 'web']
    if module.lower() not in valid_modules:
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message=f"module must be one of {valid_modules}"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("switch_module", {"module": module})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"readOnly": True})
async def get_current_module(ctx: Context[ServerSession, AppContext]) -> str:
    """
    Get the name of the currently active module.
    Returns module name.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("get_current_module")
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def show_view(view: str, ctx: Context[ServerSession, AppContext]) -> str:
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
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message=f"view must be one of {valid_views}"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("show_view", {"view": view})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

# ============================================================================
# Advanced Search and Organization Tools
# ============================================================================

@mcp.tool(annotations={"readOnly": True})
async def find_photos(search_desc: dict, ctx: Context[ServerSession, AppContext]) -> Any:
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
    Returns list of matching photos.
    """
    if not isinstance(search_desc, dict):
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message="search_desc must be a dictionary"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("find_photos", {"searchDesc": search_desc})
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def create_smart_collection(name: str, search_desc: dict, ctx: Context[ServerSession, AppContext]) -> str:
    """
    Create a smart collection with search criteria.

    Args:
        name: Name for the smart collection.
        search_desc: Search descriptor dictionary (same format as find_photos).
    """
    if not name or not isinstance(name, str):
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message="name must be a non-empty string"))
    if not isinstance(search_desc, dict):
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message="search_desc must be a dictionary"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("create_smart_collection", {"name": name, "searchDesc": search_desc})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"readOnly": True})
async def list_folders(ctx: Context[ServerSession, AppContext]) -> Any:
    """
    List all folders in the catalog hierarchy.
    Returns list of folder objects (name, path, id).
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("list_folders")
        if result and "result" in result:
            return result["result"]
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

# ============================================================================
# Photo Operations Tools
# ============================================================================

@mcp.tool(annotations={"destructive": True})
async def create_virtual_copy(copy_name: Optional[str] = None, ctx: Context[ServerSession, AppContext] = None) -> str:
    """
    Create virtual copies of the currently selected photos.

    Args:
        copy_name: Optional name to apply to each virtual copy.
    """
    lrc = ctx.request_context.lifespan_context.lrc
    try:
        params = {}
        if copy_name:
            params["copyName"] = copy_name

        result = lrc.send_command("create_virtual_copy", params)
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.tool(annotations={"destructive": True})
async def rotate_photo(direction: str, ctx: Context[ServerSession, AppContext]) -> str:
    """
    Rotate the currently selected photos.

    Args:
        direction: Rotation direction - either 'left' or 'right'.
    """
    if direction.lower() not in ['left', 'right']:
        raise McpError(ErrorData(code=ErrorCode.INVALID_PARAMS, message="direction must be 'left' or 'right'"))

    lrc = ctx.request_context.lifespan_context.lrc
    try:
        result = lrc.send_command("rotate_photo", {"direction": direction})
        if result and "result" in result:
            return "Success"
        elif result and "error" in result:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Lightroom error: {result['error']['message']}"))
        else:
            raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message="No response from Lightroom"))
    except McpError:
        raise
    except Exception as e:
        raise McpError(ErrorData(code=ErrorCode.INTERNAL_ERROR, message=f"Error: {str(e)}"))

@mcp.resource("lightroom://status")
def get_lightroom_status() -> dict:
    """Connection status of the Lightroom broker and plugin."""
    from lrc_client import check_plugin_status
    return check_plugin_status()

if __name__ == "__main__":
    mcp.run()
