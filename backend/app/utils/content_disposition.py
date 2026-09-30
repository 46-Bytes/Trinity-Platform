"""Content-Disposition for downloads whose file name came from a user."""
from urllib.parse import quote


def _header(disposition: str, filename: str) -> str:
    fallback = "".join(
        c if 32 <= ord(c) < 127 and c not in '"\\' else "_" for c in (filename or "")
    ).strip() or "download"
    return f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename or 'download', safe='')}"


def attachment(filename: str) -> str:
    """
    RFC 6266 attachment header: an ASCII fallback, plus the exact name as UTF-8.

    A raw name can hold quotes, which break the header, or non-latin-1
    characters, which cannot be encoded into it at all.
    """
    return _header("attachment", filename)


def inline(filename: str) -> str:
    """The same header, asking the browser to show the file rather than save it."""
    return _header("inline", filename)
