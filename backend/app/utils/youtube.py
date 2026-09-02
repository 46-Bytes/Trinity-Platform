"""
YouTube URL parsing utilities.

Single source of truth for extracting the 11-character YouTube video ID from
any of the common URL shapes an admin might paste, and for reconstructing the
privacy-enhanced embed URL. Store the ID (not the raw URL) so parsing happens
once at save time and bad URLs are rejected at entry instead of surfacing as a
broken player.
"""
import re
from typing import Optional

# A valid YouTube video ID is exactly 11 chars: letters, digits, dash, underscore.
_VIDEO_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')

# Patterns covering the common YouTube URL shapes. `.search` ignores any
# trailing query params (&t=, &list=, &si=, ...) after the captured ID.
_URL_PATTERNS = [
    # youtube.com/watch?v=ID  (v may appear after other params, e.g. ?list=..&v=ID)
    re.compile(r'(?:youtube\.com|youtube-nocookie\.com)/watch\?(?:[^ ]*&)?v=([A-Za-z0-9_-]{11})'),
    # youtu.be/ID
    re.compile(r'youtu\.be/([A-Za-z0-9_-]{11})'),
    # youtube.com/embed/ID, /shorts/ID, /live/ID, /v/ID
    re.compile(r'(?:youtube\.com|youtube-nocookie\.com)/(?:embed|shorts|live|v)/([A-Za-z0-9_-]{11})'),
]


def extract_youtube_id(url_or_id: str) -> Optional[str]:
    """
    Extract the 11-character YouTube video ID from any common URL shape, or
    return the input unchanged if it is already a bare 11-char ID.

    Handles: youtube.com/watch?v=ID, youtu.be/ID, youtube.com/embed/ID,
    youtube.com/shorts/ID, youtube.com/live/ID, /v/ID, youtube-nocookie.com
    variants, and any trailing query params. Returns None if no valid ID is
    found.
    """
    if not url_or_id:
        return None

    candidate = url_or_id.strip()

    # Already a bare 11-char ID
    if _VIDEO_ID_RE.match(candidate):
        return candidate

    for pattern in _URL_PATTERNS:
        match = pattern.search(candidate)
        if match:
            return match.group(1)

    return None


def build_embed_url(video_id: str) -> str:
    """Reconstruct the privacy-enhanced YouTube embed URL for a video ID."""
    return f"https://www.youtube-nocookie.com/embed/{video_id}"
