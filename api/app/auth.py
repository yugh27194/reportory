"""Supabase access token 검증 의존성(인계서 9.1절).

SUPABASE_JWT_SECRET이 있으면 HS256으로, 없으면 SUPABASE_JWKS_URL의 공개 키로 검증한다.
"""

from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends, Header, Request

from app.config import Settings, get_settings
from app.errors import ApiError, unauthorized


@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True)


def decode_token(token: str, settings: Settings) -> dict:
    try:
        if settings.supabase_jwt_secret:
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience=settings.jwt_audience,
            )
        if settings.supabase_jwks_url:
            key = _jwks_client(settings.supabase_jwks_url).get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                key.key,
                algorithms=["RS256", "ES256"],
                audience=settings.jwt_audience,
            )
    except jwt.PyJWTError as exc:
        raise unauthorized("로그인 정보가 올바르지 않거나 만료됐다.") from exc
    raise unauthorized("서버에 토큰 검증 설정이 없다.")


async def current_user_id(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> UUID:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise unauthorized()
    claims = decode_token(authorization.split(" ", 1)[1].strip(), settings)
    try:
        user_id = UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise unauthorized("토큰에 사용자 정보가 없다.") from exc
    request.state.user_id = user_id
    return user_id


async def require_cron_secret(
    x_cron_secret: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.cron_secret or x_cron_secret != settings.cron_secret:
        raise ApiError(403, "forbidden", "내부 호출 권한이 없다.")
