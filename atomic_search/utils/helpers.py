"""
Helper utilities for Atomic Search.

Provides common utility functions.
"""

import hashlib
import json
import random
import re
import string
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlparse


def generate_id(length: int = 16) -> str:
    """Generate a random ID."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def hash_string(text: str, algorithm: str = "sha256") -> str:
    """Hash a string."""
    if algorithm == "md5":
        return hashlib.md5(text.encode()).hexdigest()
    elif algorithm == "sha1":
        return hashlib.sha1(text.encode()).hexdigest()
    elif algorithm == "sha256":
        return hashlib.sha256(text.encode()).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(text.encode()).hexdigest()
    return hashlib.sha256(text.encode()).hexdigest()


def truncate(text: str, length: int, suffix: str = "...") -> str:
    """Truncate text to specified length."""
    if len(text) <= length:
        return text
    return text[:length - len(suffix)].rstrip() + suffix


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.lower().strip("-")


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        return domain.replace("www.", "")
    except Exception:
        return ""


def extract_root_domain(url: str) -> str:
    """Extract root domain from URL."""
    domain = extract_domain(url)
    parts = domain.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain


def is_valid_url(url: str) -> bool:
    """Check if string is a valid URL."""
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def normalize_url(url: str) -> str:
    """Normalize a URL."""
    try:
        parsed = urlparse(url)

        # Ensure scheme
        if not parsed.scheme:
            url = "https://" + url
            parsed = urlparse(url)

        # Remove www prefix
        netloc = parsed.netloc
        if netloc.startswith("www."):
            netloc = netloc[4:]

        # Remove trailing slash
        path = parsed.path.rstrip("/")

        return f"{parsed.scheme}://{netloc}{path}"
    except Exception:
        return url


def get_url_params(url: str) -> Dict[str, str]:
    """Get URL parameters as dict."""
    try:
        parsed = urlparse(url)
        return {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parsed.query).items()}
    except Exception:
        return {}


def set_url_params(url: str, params: Dict[str, Any]) -> str:
    """Set URL parameters."""
    try:
        parsed = urlparse(url)
        query = urlencode(params)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{query}"
    except Exception:
        return url


def strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text)


def escape_html(text: str) -> str:
    """Escape HTML characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def unescape_html(text: str) -> str:
    """Unescape HTML entities."""
    return (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )


def format_bytes(size: int) -> str:
    """Format bytes to human readable."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format duration to human readable."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"


def parse_duration(duration_str: str) -> float:
    """Parse duration string to seconds."""
    match = re.match(r"(\d+(?:\.\d+)?)\s*(ms|s|m|h|d)?", duration_str)
    if not match:
        return 0

    value = float(match.group(1))
    unit = match.group(2) or "s"

    multipliers = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400}
    return value * multipliers.get(unit, 1)


def time_ago(dt: datetime) -> str:
    """Get human-readable time difference."""
    now = datetime.utcnow()
    diff = now - dt

    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m ago"
    elif seconds < 86400:
        return f"{int(seconds / 3600)}h ago"
    elif seconds < 604800:
        return f"{int(seconds / 86400)}d ago"
    elif seconds < 2592000:
        return f"{int(seconds / 604800)}w ago"
    else:
        return dt.strftime("%Y-%m-%d")


def is_recent(dt: datetime, hours: int = 24) -> bool:
    """Check if datetime is within recent hours."""
    now = datetime.utcnow()
    return now - dt < timedelta(hours=hours)


def random_string(length: int, charset: str = None) -> str:
    """Generate random string."""
    if charset is None:
        charset = string.ascii_letters + string.digits
    return "".join(random.choices(charset, k=length))


def chunk_list(items: List, chunk_size: int) -> List[List]:
    """Split list into chunks."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def flatten_list(nested: List) -> List:
    """Flatten nested list."""
    result = []
    for item in nested:
        if isinstance(item, list):
            result.extend(flatten_list(item))
        else:
            result.append(item)
    return result


def merge_dicts(*dicts: Dict) -> Dict:
    """Merge multiple dictionaries."""
    result = {}
    for d in dicts:
        result.update(d)
    return result


def deep_get(d: Dict, path: str, default: Any = None) -> Any:
    """Get nested dictionary value using dot notation."""
    keys = path.split(".")
    value = d

    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default

        if value is None:
            return default

    return value


def deep_set(d: Dict, path: str, value: Any):
    """Set nested dictionary value using dot notation."""
    keys = path.split(".")
    current = d

    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    current[keys[-1]] = value


def retry(max_attempts: int = 3, delay: float = 1.0):
    """Decorator for retry logic."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    import time
                    time.sleep(delay * (attempt + 1))
        return wrapper
    return decorator


def memoize(func):
    """Decorator for memoization."""
    cache = {}

    def wrapper(*args, **kwargs):
        key = json.dumps((args, sorted(kwargs.items())), default=str)
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    wrapper.cache = cache
    wrapper.clear = lambda: cache.clear()
    return wrapper
