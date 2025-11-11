thonfrom typing import List
from urllib.parse import urlparse, urlunparse

def normalize_url(url: str) -> str:
    """
    Ensure the URL has a scheme and is properly normalized.
    """
    url = url.strip()
    if not url:
        return url
    parsed = urlparse(url, scheme="https")
    if not parsed.netloc and parsed.path:
        # Handle URLs given without protocol like "www.immobiliare.it/..."
        parsed = urlparse("https://" + url)
    normalized = urlunparse(parsed)
    return normalized

def read_urls_from_file(path: str) -> List[str]:
    """
    Read URLs from a file, ignoring comments and empty lines.
    """
    urls: List[str] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw or raw.startswith("#"):
                    continue
                urls.append(raw)
    except FileNotFoundError:
        # The caller can decide how to handle an empty list.
        pass
    return urls