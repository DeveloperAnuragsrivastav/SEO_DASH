"""The picture a web page shows for itself, for the report's page lists.

Most sites name one in their <head> for link previews (og:image, then the
Twitter card); failing that, the first real image in the page will do. Every
candidate is fetched before it is used, so the report never prints a broken
image — a page with nothing usable simply gets none.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from typing import Optional
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,image/*;q=0.9,*/*;q=0.8",
}
_TIMEOUT = httpx.Timeout(6.0, connect=4.0)
_MAX_HTML = 1_500_000

# Preview images the site names for itself, most to least specific.
_META = [
    re.compile(r'<meta[^>]+(?:property|name)=["\']og:image(?::secure_url|:url)?["\'][^>]*>', re.I),
    re.compile(r'<meta[^>]+(?:property|name)=["\']twitter:image(?::src)?["\'][^>]*>', re.I),
    re.compile(r'<link[^>]+rel=["\']image_src["\'][^>]*>', re.I),
]
_ATTR = re.compile(r'(?:content|href)=["\']([^"\']+)["\']', re.I)
_IMG = re.compile(r'<img[^>]+?(?:data-src|data-lazy-src|src)=["\']([^"\']+)["\'][^>]*>', re.I)
# Not a picture of the page: icons, logos, tracking pixels, spacers.
_SKIP = re.compile(r'(logo|icon|sprite|pixel|spacer|blank|avatar|gravatar|emoji|\.svg(\?|$)|^data:)', re.I)


def _candidates(html: str, base: str) -> list[str]:
    head = html[: html.lower().find("</head>") + 7] if "</head>" in html.lower() else html[:200_000]
    found: list[str] = []
    for pattern in _META:
        for tag in pattern.findall(head):
            m = _ATTR.search(tag)
            if m:
                found.append(urljoin(base, unescape(m.group(1).strip())))
    for src in _IMG.findall(html):
        src = unescape(src.strip())
        if src and not _SKIP.search(src):
            found.append(urljoin(base, src))
        if len(found) >= 8:
            break
    seen: set[str] = set()
    return [u for u in found if u.startswith("http") and not (u in seen or seen.add(u))]


def _loads(client: httpx.Client, url: str) -> bool:
    """True when the URL answers with an actual raster image."""
    try:
        with client.stream("GET", url) as res:
            kind = res.headers.get("content-type", "").lower()
            return res.status_code == 200 and kind.startswith("image/") and "svg" not in kind
    except Exception:
        return False


def page_image(url: str) -> Optional[str]:
    """The URL of the image a page shows for itself, or None."""
    try:
        with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
            res = client.get(url)
            if res.status_code != 200 or "html" not in res.headers.get("content-type", "").lower():
                return None
            for candidate in _candidates(res.text[:_MAX_HTML], str(res.url))[:4]:
                if _loads(client, candidate):
                    return candidate
    except Exception as e:
        logger.info("No image for %s: %s", url, e)
    return None


def page_images(urls: list[str]) -> dict[str, Optional[str]]:
    """page_image for several pages at once."""
    urls = [u for u in dict.fromkeys(urls) if u]
    if not urls:
        return {}
    with ThreadPoolExecutor(max_workers=min(6, len(urls))) as pool:
        return dict(zip(urls, pool.map(page_image, urls)))
