from cryptography.fernet import Fernet
from itsdangerous import URLSafeSerializer, BadSignature
from typing import Optional
from .config import settings


def get_fernet() -> Fernet:
    key = settings.encryption_key
    if not key:
        # For dev convenience, generate a temporary key at runtime; recommend setting ENV in prod
        key = Fernet.generate_key().decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(token: str) -> str:
    return get_fernet().encrypt(token.encode()).decode()


def decrypt_token(token_encrypted: str) -> str:
    return get_fernet().decrypt(token_encrypted.encode()).decode()


_serializer = URLSafeSerializer(settings.session_secret, salt="session")


def create_session_cookie(user_id: int) -> str:
    return _serializer.dumps({"user_id": user_id})


def read_session_cookie(cookie_value: str) -> Optional[int]:
    try:
        data = _serializer.loads(cookie_value)
        return int(data.get("user_id"))
    except (BadSignature, Exception):
        return None


