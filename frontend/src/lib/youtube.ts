/**
 * YouTube URL parsing utilities (mirrors backend app/utils/youtube.py).
 *
 * Used in the admin form for a live preview from a pasted URL. The backend
 * remains the source of truth — it re-extracts and validates on save.
 */

// A valid YouTube video ID is exactly 11 chars: letters, digits, dash, underscore.
const VIDEO_ID_RE = /^[A-Za-z0-9_-]{11}$/;

const URL_PATTERNS: RegExp[] = [
  // youtube.com/watch?v=ID  (v may appear after other params)
  /(?:youtube\.com|youtube-nocookie\.com)\/watch\?(?:[^ ]*&)?v=([A-Za-z0-9_-]{11})/,
  // youtu.be/ID
  /youtu\.be\/([A-Za-z0-9_-]{11})/,
  // youtube.com/embed/ID, /shorts/ID, /live/ID, /v/ID
  /(?:youtube\.com|youtube-nocookie\.com)\/(?:embed|shorts|live|v)\/([A-Za-z0-9_-]{11})/,
];

/** Extract the 11-char YouTube video ID from any common URL shape, or null. */
export function extractYouTubeId(input: string): string | null {
  if (!input) return null;
  const candidate = input.trim();
  if (VIDEO_ID_RE.test(candidate)) return candidate;
  for (const pattern of URL_PATTERNS) {
    const match = candidate.match(pattern);
    if (match) return match[1];
  }
  return null;
}

/** Reconstruct the privacy-enhanced YouTube embed URL for a video ID. */
export function buildEmbedUrl(videoId: string): string {
  return `https://www.youtube-nocookie.com/embed/${videoId}`;
}
