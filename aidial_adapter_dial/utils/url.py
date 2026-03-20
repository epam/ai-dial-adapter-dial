from urllib.parse import urlparse, urlunparse


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme
    hostname = (parsed.hostname or "").rstrip(".")
    port = parsed.port

    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        netloc = hostname
    elif port is not None:
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname

    return urlunparse(parsed._replace(netloc=netloc))
