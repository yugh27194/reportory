"""저장소와 업로드 검사(인계서 11.7절, 14장)."""

import io
import json
import zipfile

import httpx
import pytest

from app.errors import ApiError
from app.storage import LocalStorage, StorageError, SupabaseStorage, get_storage
from app.uploads import check_upload, check_zip_safety, sniff

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
PDF = b"%PDF-1.4\n%%EOF"


def make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_sniff_by_content_not_extension():
    assert sniff(PDF) == "application/pdf"
    assert sniff(PNG) == "image/png"
    assert sniff(b"\xff\xd8\xff\xe0" + b"0" * 8) == "image/jpeg"
    assert sniff(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert sniff(make_zip({"Positions.csv": b"a"})) == "application/zip"
    assert sniff(make_zip({"word/document.xml": b"<w/>"})).endswith("document")
    assert sniff(b"<html>") is None


def test_check_upload_limits():
    assert check_upload(PNG, {"image/png"}) == "image/png"
    with pytest.raises(ApiError) as e:
        check_upload(b"<script>", {"image/png"})
    assert e.value.status == 415
    with pytest.raises(ApiError) as e:
        check_upload(PNG + b"0" * (1024 * 1024), {"image/png"}, max_mb=1)
    assert e.value.status == 413


def test_zip_bomb_guard():
    check_zip_safety(make_zip({f"f{i}.csv": b"x" for i in range(10)}))
    with pytest.raises(ApiError):
        check_zip_safety(make_zip({f"f{i}.csv": b"x" for i in range(201)}))


async def test_local_signed_url_roundtrip(anon):
    storage = get_storage()
    assert isinstance(storage, LocalStorage)
    await storage.put("evidence", "u1/a.png", PNG, "image/png")
    url = await storage.signed_url("evidence", "u1/a.png", 60, download_name="성적표.png")
    path = url.removeprefix("http://test/api/v1")
    r = await anon.get(path)
    assert r.status_code == 200 and r.content == PNG
    assert "filename*=UTF-8''" in r.headers["content-disposition"]
    assert (await anon.get(path[:-3] + "abc")).status_code == 404
    expired = await storage.signed_url("evidence", "u1/a.png", -1)
    assert (await anon.get(expired.removeprefix("http://test/api/v1"))).status_code == 404
    with pytest.raises(StorageError):
        await storage.put("evidence", "../../etc/x", b"x", "text/plain")


async def test_supabase_storage_calls():
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path, req.headers.get("x-upsert")))
        if "/object/sign/" in req.url.path:
            return httpx.Response(200, json={"signedURL": "/object/sign/evidence/u/a.png?token=t"})
        if "/object/list/" in req.url.path:
            assert json.loads(req.content)["prefix"] == "u"
            return httpx.Response(200, json=[{"name": "a.png", "id": "1"}])
        return httpx.Response(200, json={})

    s = SupabaseStorage("https://x.supabase.co", "key", transport=httpx.MockTransport(handler))
    await s.put("evidence", "u/a.png", PNG, "image/png")
    url = await s.signed_url("evidence", "u/a.png", 300, download_name="a.png")
    assert url == (
        "https://x.supabase.co/storage/v1/object/sign/evidence/u/a.png?token=t&download=a.png"
    )
    assert await s.delete_prefix("evidence", "u/") == 1
    assert calls[0] == ("POST", "/storage/v1/object/evidence/u/a.png", "true")
    assert calls[-1][0] == "DELETE"
