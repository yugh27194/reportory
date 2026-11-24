"""파일에서 글자 뽑기(인계서 10.9절, 10.10절). 뽑은 글자는 로그에 남기지 않는다."""

import io
import logging

log = logging.getLogger("reportory.text_extract")

SCANNED_THRESHOLD = 200  # 이보다 짧으면 스캔본으로 보고 파일 자체를 LLM에 넘긴다


def pdf_text(data: bytes, max_pages: int = 20) -> str:
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages[:max_pages]).strip()
    except Exception as exc:  # noqa: BLE001 - 깨진 PDF는 스캔본처럼 다룬다
        log.warning("pdf text extraction failed: %s", type(exc).__name__)
        return ""


def docx_text(data: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(data))
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts).strip()
