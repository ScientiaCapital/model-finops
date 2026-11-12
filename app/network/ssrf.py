"""Guard for outbound requests to URLs that a user supplies (budget alert webhooks).

A URL is accepted only if it uses https and its host resolves, on every answer, to a globally
routable address. Loopback, private, link-local (cloud metadata), CGNAT, unspecified and
multicast addresses are refused, and so are IPv4-mapped IPv6 forms of those. Resolution
failures refuse the URL: the guard fails closed.

At send time the request goes to the address that was just checked (with the original host
kept for the Host header and TLS), so a DNS answer that changes between the check and the
connection cannot redirect it. Redirects are never followed.
"""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import httpx

SEND_TIMEOUT_SECONDS = 5.0

_NAT64 = ipaddress.ip_network("64:ff9b::/96")


class UnsafeURLError(ValueError):
    """The URL may not be used for an outbound request. The message is safe to show a caller."""


@dataclass(frozen=True)
class ResolvedTarget:
    host: str
    port: int
    path_query: str
    addresses: tuple[str, ...]


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        elif ip in _NAT64:
            ip = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return ip.is_global and not ip.is_multicast


def _parse_ip(text: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    return ipaddress.ip_address(text.split("%", 1)[0])


def resolve_public_https(url: str) -> ResolvedTarget:
    """Check a URL and return the checked addresses. Raises UnsafeURLError if it is not allowed.

    Blocking: it calls socket.getaddrinfo. Use it from async code through asyncio.to_thread.
    """
    refused = "URL must be https and resolve only to public addresses"
    try:
        parts = urlsplit(url.strip())
        host = parts.hostname
        port = parts.port or 443
    except ValueError:
        raise UnsafeURLError(refused) from None
    if parts.scheme != "https" or not host or parts.username or parts.password:
        raise UnsafeURLError(refused)

    try:
        literal = _parse_ip(host)
        addresses = [str(literal)]
        checked = [literal]
    except ValueError:
        try:
            answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            checked = [_parse_ip(a[4][0]) for a in answers]
        except (OSError, ValueError):
            raise UnsafeURLError(refused) from None
        addresses = [str(ip) for ip in checked]

    if not checked or not all(_is_public(ip) for ip in checked):
        raise UnsafeURLError(refused)

    path_query = urlunsplit(("", "", parts.path or "/", parts.query, ""))
    return ResolvedTarget(host=host, port=port, path_query=path_query, addresses=tuple(addresses))


async def validate_public_https_url(url: str) -> None:
    """Async wrapper used when a URL is saved."""
    await asyncio.to_thread(resolve_public_https, url)


async def safe_post(
    client: httpx.AsyncClient, url: str, payload: dict[str, object]
) -> httpx.Response:
    """POST JSON to a user-supplied URL after checking it, never following a redirect."""
    target = await asyncio.to_thread(resolve_public_https, url)
    ip = target.addresses[0]
    netloc = f"[{ip}]" if ":" in ip else ip
    pinned = f"https://{netloc}:{target.port}{target.path_query}"
    host_text = f"[{target.host}]" if ":" in target.host else target.host
    host_header = host_text if target.port == 443 else f"{host_text}:{target.port}"
    response = await client.post(
        pinned,
        json=payload,
        headers={"Host": host_header},
        extensions={"sni_hostname": target.host},
        timeout=SEND_TIMEOUT_SECONDS,
        follow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        raise UnsafeURLError("redirects are not followed")
    return response
