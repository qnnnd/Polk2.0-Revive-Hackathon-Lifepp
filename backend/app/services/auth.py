import base64
import hashlib
import hmac
from typing import Optional

from fastapi import HTTPException, status

from app.core.config import settings
from app.services.storage import Storage


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_token(user_id: int, username: str) -> str:
    payload = f"{user_id}:{username}".encode("utf-8")
    sig = hmac.new(settings.secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    blob = payload + b"." + sig.encode("utf-8")
    return base64.urlsafe_b64encode(blob).decode("utf-8")


def decode_token(token: str) -> tuple[int, str]:
    try:
        decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        payload, sig = decoded.rsplit(".", 1)
        expected = hmac.new(settings.secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        user_id_str, username = payload.split(":", 1)
        return int(user_id_str), username
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def get_current_user_id(auth_header: Optional[str], storage: Storage) -> int:
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = auth_header.split(" ", 1)[1]
    user_id, username = decode_token(token)
    with storage.connect() as conn:
        row = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row or row["username"] != username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user_id
