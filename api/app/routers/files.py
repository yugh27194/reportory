"""로컬 저장소 서명 URL 다운로드(개발용). Supabase Storage를 쓰면 이 경로는 쓰이지 않는다."""

import mimetypes
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import Response

from app.errors import not_found
from app.storage import LocalStorage, StorageError, get_storage

router = APIRouter(tags=["files"])


@router.get("/files/{token}")
async def download(token: str):
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise not_found()
    try:
        meta = storage.verify(token)
        data = await storage.get(meta["b"], meta["p"])
    except StorageError as exc:
        raise not_found(str(exc)) from exc
    mime = mimetypes.guess_type(meta["p"])[0] or "application/octet-stream"
    headers = {"Cache-Control": "private, max-age=60"}
    if meta.get("n"):
        headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(meta['n'])}"
    return Response(data, media_type=mime, headers=headers)
