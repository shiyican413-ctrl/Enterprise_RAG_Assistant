import base64
import hashlib
import hmac
import json
import time

from backend.ai_service.core.config import JWT_EXPIRE_MINUTES, JWT_SECRET
from backend.ai_service.security.models import User


def create_access_token(user: User) -> tuple[str, int]:
    expires_in = JWT_EXPIRE_MINUTES * 60
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_in,
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_encode_json(header)}.{_encode_json(payload)}"
    signature = hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_encode(signature)}", expires_in


def decode_access_token(token: str) -> dict:
    try:
        header, payload, signature = token.split(".")
        signing_input = f"{header}.{payload}"
        expected = hmac.new(
            JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _decode(signature)):
            raise ValueError("invalid token signature")
        claims = json.loads(_decode(payload))
        if int(claims.get("exp", 0)) <= int(time.time()):
            raise ValueError("token expired")
        if not claims.get("sub"):
            raise ValueError("token subject missing")
        return claims
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid or expired access token") from exc


def _encode_json(value: dict) -> str:
    return _encode(json.dumps(value, separators=(",", ":")).encode())


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
