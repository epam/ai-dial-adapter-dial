from urllib.parse import urlparse, urlunparse

_DEFAULT_PORTS = {"http": 80, "https": 443}


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


def _origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    return (
        scheme,
        (parsed.hostname or "").rstrip(".").lower(),
        parsed.port or _DEFAULT_PORTS.get(scheme),
    )


def has_same_origin(a: str, b: str) -> bool:
    """Whether two URLs share the same origin (scheme, host and port).

    Comparing origins is safer than a string-prefix check: a URL like
    ``http://<host>@evil.example`` or ``http://<host>.evil.example`` shares a
    prefix with ``http://<host>`` yet resolves to a different origin. Trusting
    such look-alikes would leak the api-key to an attacker-controlled host.
    """
    return _origin(a) == _origin(b)
