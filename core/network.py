import socket
from ipaddress import ip_address
from urllib.parse import urlsplit, urlunsplit

TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}

def canonicalize_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname:
        return url.split("#", 1)[0].strip()
    try:
        port = parsed.port
    except ValueError:
        port = None
    host = hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if port not in (None, 443):
        host = f"{host}:{port}"
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query_parts = [
        item for item in parsed.query.split("&")
        if item and item.split("=", 1)[0].lower() not in TRACKING_PARAMS
        and not item.split("=", 1)[0].lower().startswith("utm_")
    ]
    query = "&".join(query_parts)
    return urlunsplit(("https", host, path, query, ""))

def is_public_host(hostname: str) -> bool:
    if not hostname:
        return False
    try:
        addresses = {ip_address(hostname)}
    except ValueError:
        try:
            infos = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        except OSError:
            return False
        addresses = {ip_address(info[4][0]) for info in infos}
    return bool(addresses) and all(address.is_global for address in addresses)
