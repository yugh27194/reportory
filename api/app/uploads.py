"""업로드 파일 검사(인계서 11.7절, 14장). 파일 종류는 확장자가 아니라 내용(매직 바이트)으로 본다."""

import io
import zipfile

from app.config import get_settings
from app.errors import ApiError

MIME_EXT = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/zip": "zip",
}

ZIP_MAX_TOTAL = 50 * 1024 * 1024
ZIP_MAX_FILES = 200


def sniff(data: bytes) -> str | None:
    """매직 바이트로 MIME 형식을 알아낸다. 모르면 None."""
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = z.namelist()
        except zipfile.BadZipFile:
            return None
        if "word/document.xml" in names:
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return "application/zip"
    return None


def check_upload(data: bytes, allowed: set[str], max_mb: int | None = None) -> str:
    limit = (max_mb or get_settings().max_upload_mb) * 1024 * 1024
    if not data:
        raise ApiError(422, "validation_error", "빈 파일이다.")
    if len(data) > limit:
        raise ApiError(413, "file_too_large", f"파일은 {limit // (1024 * 1024)}MB 이하여야 한다.")
    mime = sniff(data)
    if mime not in allowed:
        raise ApiError(415, "unsupported_file", "지원하지 않는 파일 형식이다.")
    return mime


def check_zip_safety(data: bytes) -> None:
    """압축 해제 전에 전체 크기(50MB)와 파일 수(200개)를 확인한다."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        infos = z.infolist()
        if len(infos) > ZIP_MAX_FILES:
            raise ApiError(422, "validation_error", "ZIP 안의 파일이 너무 많다.")
        if sum(i.file_size for i in infos) > ZIP_MAX_TOTAL:
            raise ApiError(422, "validation_error", "ZIP을 풀었을 때 크기가 너무 크다.")
