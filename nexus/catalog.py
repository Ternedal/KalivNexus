import hashlib
import ipaddress
import re
from urllib.parse import urlparse

import httpx

SOURCE_URL = "https://raw.githubusercontent.com/cporter202/API-mega-list/master/README.md"
ALTERNATE_URL = "https://raw.githubusercontent.com/cporter202/API-mega-list/main/README.md"
MAX_BYTES = 4_000_000
LINK = re.compile(r"\[([^\]]{2,160})\]\((https?://[^\s)]+)(?:\s+[^)]*)?\)")
HEADER = re.compile(r"^#{1,4}\s+(.+?)\s*$")

def is_public_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            return False
        host = parsed.hostname.lower().rstrip(".")
        if host in ("localhost",) or host.endswith((".localhost", ".local", ".internal")):
            return False
        try:
            ip = ipaddress.ip_address(host)
            return ip.is_global
        except ValueError:
            return True
    except ValueError:
        return False

def parse_markdown(markdown: str, source: str = SOURCE_URL) -> list[dict]:
    category = "Uncategorized"
    found = {}
    for line in markdown.splitlines():
        h = HEADER.match(line)
        if h:
            category = re.sub(r"[`*_#]", "", h.group(1)).strip()[:120]
        for match in LINK.finditer(line):
            name, url = match.groups()
            url = url.rstrip(".,;")
            if not is_public_http_url(url):
                continue
            if "#" in url:
                url = url.split("#", 1)[0]
            if not url:
                continue
            key = hashlib.sha256(url.encode()).hexdigest()[:24]
            description = line.replace(match.group(0), "").strip(" -*:|\t")[:400]
            found[key] = dict(id=key, name=name.strip(), url=url, category=category,
                              description=description, source=source, status="discovered")
    return list(found.values())

async def fetch_source() -> tuple[str, str]:
    # Fixed allowlisted sources: never fetch arbitrary user-provided URLs.
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        for url in (SOURCE_URL, ALTERNATE_URL):
            async with client.stream("GET", url) as response:
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_BYTES:
                        raise ValueError("Source exceeds maximum size")
                return content.decode("utf-8"), url
    raise RuntimeError("README not found on master or main")
