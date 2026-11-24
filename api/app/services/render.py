"""문서 렌더링(인계서 11.5절): Jinja2 HTML 템플릿 → Playwright(Chromium) A4 PDF."""

import base64
import io
import logging
from datetime import date
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings

log = logging.getLogger("reportory.render")

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
# (파일, 글꼴 이름, 굵기, 기울임). Pretendard는 한글, Source Serif 4는 영문 Resume·CV의 라틴 문자용(둘 다 OFL).
FONT_FACES = [
    ("Pretendard-Regular.woff2", "Pretendard", 400, "normal"),
    ("Pretendard-SemiBold.woff2", "Pretendard", 600, "normal"),
    ("Pretendard-Bold.woff2", "Pretendard", 700, "normal"),
]
SERIF_FACES = [
    ("SourceSerif4-Regular.woff2", "Source Serif 4", 400, "normal"),
    ("SourceSerif4-Italic.woff2", "Source Serif 4", 400, "italic"),
    ("SourceSerif4-SemiBold.woff2", "Source Serif 4", 600, "normal"),
    ("SourceSerif4-Bold.woff2", "Source Serif 4", 700, "normal"),
]


class RenderError(Exception):
    pass


@lru_cache
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _faces_css(faces) -> str:
    rules = []
    for file, family, weight, style in faces:
        data = base64.b64encode((TEMPLATE_DIR / "fonts" / file).read_bytes()).decode()
        rules.append(
            f"@font-face {{ font-family: '{family}'; font-weight: {weight}; font-style: {style}; "
            f"src: url(data:font/woff2;base64,{data}) format('woff2'); }}"
        )
    return "\n".join(rules)


@lru_cache
def embedded_fonts_css() -> str:
    """PDF에는 글꼴을 데이터 URI로 넣어 어느 서버에서도 글자가 깨지지 않게 한다."""
    return _faces_css(FONT_FACES + SERIF_FACES)


@lru_cache
def preview_fonts_css() -> str:
    """미리보기에는 작은 영문 세리프만 넣는다(한글은 사용자 기기 글꼴로 대신 보인다)."""
    return _faces_css(SERIF_FACES)


def render_html(fmt: str, content: dict, *, title: str, for_pdf: bool) -> str:
    # 양식을 바꾸기 전에 만든 문서에는 profile·written_on이 없다. 빈 값으로 채워 그대로 보이게 한다.
    x = {"interests": [], "sections": [], **content["x-reportory"]}
    x["profile"] = x.get("profile") or {}
    x["written_on"] = x.get("written_on") or date.today().isoformat()
    return (
        _env()
        .get_template(f"{fmt}.html.j2")
        .render(
            c=content,
            x=x,
            title=title,
            summary=content.get("x-summary"),
            fonts_css=embedded_fonts_css() if for_pdf else preview_fonts_css(),
            editable=not for_pdf,
        )
    )


async def render_pdf(html: str) -> bytes:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover
        raise RenderError("Playwright가 설치되지 않았다.") from exc
    executable = get_settings().pdf_chromium_executable or None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(executable_path=executable)
            try:
                page = await browser.new_page()
                await page.set_content(html, wait_until="load")
                await page.evaluate("document.fonts.ready")
                return await page.pdf(format="A4", print_background=True, prefer_css_page_size=True)
            finally:
                await browser.close()
    except Exception as exc:  # noqa: BLE001 - 브라우저가 없거나 실패하면 PDF 없이 진행한다
        log.warning("pdf render failed: %s", type(exc).__name__)
        raise RenderError(
            "PDF를 만들지 못했다. API 서버에서 `uv run playwright install chromium`을 실행해 보세요."
        ) from exc


def page_count(pdf: bytes) -> int:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        return len(doc.pages)
