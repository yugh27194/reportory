"""파일 저장소(인계서 8.4절 추가 규칙, 14장).

모든 버킷은 비공개다. 웹은 저장소에 직접 접근하지 않고, 업로드·다운로드는 API 서버가 처리하며,
열람은 만료 시간이 있는 서명 URL로만 준다.

- SupabaseStorage: service role 키로 Supabase Storage REST API를 부른다.
- LocalStorage: 개발·테스트용. 로컬 폴더에 두고, HMAC 서명 토큰으로 /api/v1/files/{token}에서 내려준다.
"""

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import httpx

from app.config import Settings, get_settings

BUCKETS = ("evidence", "imports", "documents", "exports")


class StorageError(Exception):
    pass


class Storage(Protocol):
    async def put(self, bucket: str, path: str, data: bytes, content_type: str) -> None: ...
    async def get(self, bucket: str, path: str) -> bytes: ...
    async def delete(self, bucket: str, paths: list[str]) -> None: ...
    async def delete_prefix(self, bucket: str, prefix: str) -> int: ...
    async def signed_url(
        self, bucket: str, path: str, ttl: int, download_name: str | None = None
    ) -> str: ...


class SupabaseStorage:
    def __init__(self, url: str, key: str, transport: httpx.AsyncBaseTransport | None = None):
        self.base = f"{url.rstrip('/')}/storage/v1"
        self.headers = {"Authorization": f"Bearer {key}", "apikey": key}
        self.transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=self.headers, timeout=60.0, transport=self.transport)

    @staticmethod
    def _check(resp: httpx.Response, what: str) -> None:
        if resp.status_code >= 400:
            raise StorageError(f"Storage {what} 실패: HTTP {resp.status_code}")

    async def put(self, bucket, path, data, content_type):
        async with self._client() as http:
            resp = await http.post(
                f"{self.base}/object/{bucket}/{quote(path)}",
                content=data,
                headers={"Content-Type": content_type, "x-upsert": "true"},
            )
        self._check(resp, "업로드")

    async def get(self, bucket, path):
        async with self._client() as http:
            resp = await http.get(f"{self.base}/object/{bucket}/{quote(path)}")
        self._check(resp, "다운로드")
        return resp.content

    async def delete(self, bucket, paths):
        if not paths:
            return
        async with self._client() as http:
            resp = await http.request(
                "DELETE", f"{self.base}/object/{bucket}", json={"prefixes": paths}
            )
        self._check(resp, "삭제")

    async def delete_prefix(self, bucket, prefix):
        async with self._client() as http:
            resp = await http.post(
                f"{self.base}/object/list/{bucket}",
                json={"prefix": prefix.rstrip("/"), "limit": 1000, "offset": 0},
            )
        self._check(resp, "목록")
        names = [f"{prefix.rstrip('/')}/{o['name']}" for o in resp.json() if o.get("id")]
        await self.delete(bucket, names)
        return len(names)

    async def signed_url(self, bucket, path, ttl, download_name=None):
        async with self._client() as http:
            resp = await http.post(
                f"{self.base}/object/sign/{bucket}/{quote(path)}", json={"expiresIn": ttl}
            )
        self._check(resp, "서명 URL")
        url = self.base + resp.json()["signedURL"]
        if download_name:
            url += f"&download={quote(download_name)}"
        return url


class LocalStorage:
    def __init__(self, root: str, secret: str, public_url: str):
        self.root = Path(root).resolve()
        self.secret = secret.encode()
        self.public_url = public_url.rstrip("/")

    def _file(self, bucket: str, path: str) -> Path:
        if bucket not in BUCKETS:
            raise StorageError("알 수 없는 버킷이다.")
        target = (self.root / bucket / path).resolve()
        if not str(target).startswith(str(self.root / bucket)):
            raise StorageError("잘못된 경로다.")
        return target

    async def put(self, bucket, path, data, content_type):
        target = self._file(bucket, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    async def get(self, bucket, path):
        target = self._file(bucket, path)
        if not target.exists():
            raise StorageError("파일이 없다.")
        return target.read_bytes()

    async def delete(self, bucket, paths):
        for path in paths:
            self._file(bucket, path).unlink(missing_ok=True)

    async def delete_prefix(self, bucket, prefix):
        base = self._file(bucket, prefix.rstrip("/"))
        if not base.exists():
            return 0
        files = [f for f in base.rglob("*") if f.is_file()]
        for f in files:
            f.unlink()
        return len(files)

    def _sign(self, payload: bytes) -> str:
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    async def signed_url(self, bucket, path, ttl, download_name=None):
        payload = json.dumps(
            {"b": bucket, "p": path, "e": int(time.time()) + ttl, "n": download_name},
            separators=(",", ":"),
        ).encode()
        token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        return f"{self.public_url}/api/v1/files/{token}.{self._sign(payload)}"

    def verify(self, token: str) -> dict:
        try:
            body, sig = token.rsplit(".", 1)
            payload = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        except ValueError as exc:
            raise StorageError("잘못된 링크다.") from exc
        if not hmac.compare_digest(sig, self._sign(payload)):
            raise StorageError("잘못된 링크다.")
        data = json.loads(payload)
        if data["e"] < time.time():
            raise StorageError("링크가 만료됐다.")
        return data


def _local_secret(settings: Settings) -> str:
    return settings.supabase_jwt_secret or settings.cron_secret or "reportory-local-dev-secret"


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        s = get_settings()
        backend = s.storage_backend
        if backend == "auto":
            backend = "supabase" if s.supabase_url and s.supabase_service_role_key else "local"
        if backend == "supabase":
            _storage = SupabaseStorage(s.supabase_url, s.supabase_service_role_key)
        else:
            _storage = LocalStorage(s.storage_local_dir, _local_secret(s), s.api_public_url)
    return _storage


def set_storage(storage: Storage | None) -> None:
    global _storage
    _storage = storage
