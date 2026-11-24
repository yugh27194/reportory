"""공고 페이지를 가져와 본문 텍스트를 뽑는다(인계서 11.4절).

- http(s)만 받고, 내부망·루프백·링크 로컬 주소로 가는 요청은 막는다(SSRF). 리다이렉트마다 다시 확인한다.
- robots.txt가 막은 경로는 가져오지 않는다.
- 같은 사이트에는 CRAWLER_SITE_INTERVAL_SECONDS(기본 2초) 이상 간격을 둔다.
- 원문 HTML은 저장하지 않는다. 본문 텍스트는 정규화(LLM)에만 쓰고 버린다.
"""

import asyncio
import ipaddress
import socket
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.config import get_settings

MAX_BYTES = 2_000_000
MAX_REDIRECTS = 3


class FetchError(Exception):
    """페이지를 가져오지 못했다. message는 사용자에게 보여도 된다. 다시 해도 같으므로 재시도하지 않는다."""

    permanent = True


@dataclass
class Page:
    url: str
    title: str
    text: str


Resolver = Callable[[str], Awaitable[list[str]]]


async def _resolve(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return [i[4][0] for i in infos]


# 테스트에서 바꿔 끼운다.
_resolver: Resolver = _resolve
_transport: httpx.AsyncBaseTransport | None = None
_last_hit: dict[str, float] = {}
_robots: dict[str, RobotFileParser | None] = {}


def set_test_hooks(*, resolver: Resolver | None = None, transport=None) -> None:
    global _resolver, _transport
    _resolver = resolver or _resolve
    _transport = transport
    _last_hit.clear()
    _robots.clear()


def _is_public(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


async def check_url(url: str) -> str:
    """요청해도 되는 공개 http(s) 주소인지 확인한다. 문제가 있으면 FetchError."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("http 또는 https 주소만 넣을 수 있다.")
    if parts.username or parts.password:
        raise FetchError("계정 정보가 들어간 주소는 쓸 수 없다.")
    if parts.port not in (None, 80, 443):
        raise FetchError("기본 포트(80, 443)가 아닌 주소는 쓸 수 없다.")
    try:
        ips = await _resolver(parts.hostname)
    except OSError as exc:
        raise FetchError("주소의 도메인을 찾을 수 없다.") from exc
    if not ips or not all(_is_public(ip) for ip in ips):
        raise FetchError("내부망 주소는 가져올 수 없다.")
    return parts.geturl()


def _client() -> httpx.AsyncClient:
    s = get_settings()
    return httpx.AsyncClient(
        transport=_transport,
        timeout=20,
        follow_redirects=False,
        headers={"User-Agent": s.crawler_user_agent, "Accept-Language": "ko,en;q=0.8"},
    )


async def _polite_wait(host: str) -> None:
    gap = get_settings().crawler_site_interval_seconds
    last = _last_hit.get(host)
    if last is not None:
        wait = gap - (time.monotonic() - last)
        if wait > 0:
            await asyncio.sleep(wait)
    _last_hit[host] = time.monotonic()


async def _allowed_by_robots(http: httpx.AsyncClient, url: str) -> bool:
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots:
        parser: RobotFileParser | None = RobotFileParser()
        try:
            await _polite_wait(parts.netloc)
            r = await http.get(f"{base}/robots.txt")
            if r.status_code in (401, 403):
                parser.disallow_all = True
            elif r.status_code >= 400:
                parser = None  # robots.txt가 없으면 모두 허용
            else:
                parser.parse(r.text.splitlines())
        except httpx.HTTPError:
            parser = None
        _robots[base] = parser
    parser = _robots[base]
    return parser is None or parser.can_fetch(get_settings().crawler_user_agent, url)


def extract_text(html: str, url: str) -> tuple[str, str]:
    """(제목, 본문). trafilatura로 본문을 뽑고, 실패하면 태그를 지운 글을 쓴다."""
    import re

    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
    text = ""
    try:
        import trafilatura

        text = (
            trafilatura.extract(
                html, url=url, include_comments=False, include_tables=True, favor_recall=True
            )
            or ""
        )
    except Exception:  # noqa: BLE001 - 본문 추출 실패는 아래 단순 추출로 대신한다
        text = ""
    if len(text) < 200:
        stripped = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
        stripped = re.sub(r"(?s)<[^>]+>", " ", stripped)
        stripped = re.sub(r"&nbsp;|&#160;", " ", stripped)
        stripped = re.sub(r"[ \t\r\f\v]+", " ", stripped)
        stripped = re.sub(r"\n\s*\n+", "\n", stripped).strip()
        if len(stripped) > len(text):
            text = stripped
    return title, text


async def fetch_page(url: str) -> Page:
    url = await check_url(url)
    async with _client() as http:
        if not await _allowed_by_robots(http, url):
            raise FetchError("이 사이트의 robots.txt가 수집을 허용하지 않는다.")
        for _ in range(MAX_REDIRECTS + 1):
            await _polite_wait(urlsplit(url).netloc)
            try:
                async with http.stream("GET", url) as r:
                    if r.is_redirect:
                        url = await check_url(urljoin(url, r.headers.get("location", "")))
                        continue
                    if r.status_code >= 400:
                        raise FetchError(f"페이지를 열 수 없다(HTTP {r.status_code}).")
                    ctype = r.headers.get("content-type", "")
                    if "html" not in ctype and "text/plain" not in ctype:
                        raise FetchError("웹 페이지(HTML)가 아니다.")
                    body = b""
                    async for chunk in r.aiter_bytes():
                        body += chunk
                        if len(body) > MAX_BYTES:
                            break
                    html = body.decode(r.encoding or "utf-8", errors="replace")
                    break
            except httpx.HTTPError as exc:
                raise FetchError("페이지를 가져오지 못했다.") from exc
        else:
            raise FetchError("리다이렉트가 너무 많다.")
    title, text = extract_text(html, url)
    if len(text.strip()) < 80:
        raise FetchError("페이지에서 본문을 찾지 못했다.")
    return Page(url=url, title=title, text=text[: get_settings().crawler_max_text_chars])
