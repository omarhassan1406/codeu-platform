import re

_INVALID_WINDOWS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_WINDOWS_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_filename(value: str, max_length: int = 100) -> str:
    cleaned = value.replace("/", "-")
    cleaned = _INVALID_WINDOWS_CHARS.sub("_", cleaned)
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip(" ._")
    if not cleaned:
        cleaned = "untitled"
    if cleaned.split(".")[0].upper() in _RESERVED_WINDOWS_NAMES:
        cleaned = f"_{cleaned}"
    cleaned = cleaned[:max_length].rstrip(" ._")
    return cleaned or "untitled"
