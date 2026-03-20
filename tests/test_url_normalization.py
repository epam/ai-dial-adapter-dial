import pytest

from aidial_adapter_dial.utils.url import normalize_url

test_cases = [
    # unchanged basic URLs
    ("http://example.com", "http://example.com"),
    ("https://example.com", "https://example.com"),
    ("http://example.com/path", "http://example.com/path"),
    ("https://example.com/path?x=1", "https://example.com/path?x=1"),
    ("https://example.com/path#frag", "https://example.com/path#frag"),
    # remove trailing dot
    ("http://example.com.", "http://example.com"),
    ("https://example.com.", "https://example.com"),
    ("http://example.com./path", "http://example.com/path"),
    ("https://example.com./path?x=1#frag", "https://example.com/path?x=1#frag"),
    # remove default ports
    ("http://example.com:80", "http://example.com"),
    ("https://example.com:443", "https://example.com"),
    ("http://example.com:80/path", "http://example.com/path"),
    ("https://example.com:443/path?x=1", "https://example.com/path?x=1"),
    # remove both default port and trailing dot
    ("http://example.com.:80", "http://example.com"),
    ("https://example.com.:443", "https://example.com"),
    ("http://example.com.:80/path", "http://example.com/path"),
    (
        "https://example.com.:443/path?x=1#frag",
        "https://example.com/path?x=1#frag",
    ),
    # preserve non-default ports
    ("http://example.com:8080", "http://example.com:8080"),
    ("https://example.com:8443", "https://example.com:8443"),
    ("http://example.com.:8080", "http://example.com:8080"),
    ("https://example.com.:8443/path", "https://example.com:8443/path"),
    # preserve case in path/query/fragment
    ("http://example.com./A/B?X=Y#Frag", "http://example.com/A/B?X=Y#Frag"),
    # lowercase host is returned by urlparse().hostname
    ("http://EXAMPLE.COM.", "http://example.com"),
    ("https://EXAMPLE.COM.:443/path", "https://example.com/path"),
    # DIAL upstream endpoints
    (
        "http://dial-core.dial.svc.cluster.local.:80/openai/deployments/gpt-4o-2024-05-13/chat/completions",
        "http://dial-core.dial.svc.cluster.local/openai/deployments/gpt-4o-2024-05-13/chat/completions",
    ),
    # empty path preserved as empty
    ("http://example.com.:80?x=1", "http://example.com?x=1"),
    ("https://example.com.:443#frag", "https://example.com#frag"),
]


@pytest.mark.parametrize("test_case", test_cases)
def test_normalize_url(test_case):
    url, expected = test_case
    assert normalize_url(url) == expected
