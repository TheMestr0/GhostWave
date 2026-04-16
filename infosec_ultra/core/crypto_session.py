import base64
import hashlib
import json
import secrets

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .errors import CryptoError, SettingsError

HKDF_INFO = b"infosec-ultra/v1"


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def _b64decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value.encode("ascii"))
    except Exception as exc:
        raise CryptoError("Invalid base64 value.") from exc


def generate_session_id() -> str:
    return secrets.token_hex(8)


def generate_nonce() -> str:
    return _b64encode(secrets.token_bytes(16))


def generate_x25519_keypair() -> tuple[str, str]:
    private_key = x25519.X25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _b64encode(private_bytes), _b64encode(public_bytes)


def _private_key_from_b64(value: str) -> x25519.X25519PrivateKey:
    raw = _b64decode(value)
    if len(raw) != 32:
        raise SettingsError("Private key must decode to 32 bytes.")
    return x25519.X25519PrivateKey.from_private_bytes(raw)


def _public_key_from_b64(value: str) -> x25519.X25519PublicKey:
    raw = _b64decode(value)
    if len(raw) != 32:
        raise SettingsError("Public key must decode to 32 bytes.")
    return x25519.X25519PublicKey.from_public_bytes(raw)


def derive_sender_session_key(
    receiver_public_key_b64: str,
    sender_private_key_b64: str,
    nonce_b64: str,
) -> bytes:
    try:
        receiver_public_key = _public_key_from_b64(receiver_public_key_b64)
        sender_private_key = _private_key_from_b64(sender_private_key_b64)
        nonce = _b64decode(nonce_b64)
        shared_secret = sender_private_key.exchange(receiver_public_key)
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=nonce,
            info=HKDF_INFO,
        ).derive(shared_secret)
    except SettingsError:
        raise
    except Exception as exc:
        raise CryptoError("Failed to derive sender session key.") from exc


def derive_receiver_session_key(
    receiver_private_key_b64: str,
    sender_public_key_b64: str,
    nonce_b64: str,
) -> bytes:
    try:
        receiver_private_key = _private_key_from_b64(receiver_private_key_b64)
        sender_public_key = _public_key_from_b64(sender_public_key_b64)
        nonce = _b64decode(nonce_b64)
        shared_secret = receiver_private_key.exchange(sender_public_key)
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=nonce,
            info=HKDF_INFO,
        ).derive(shared_secret)
    except SettingsError:
        raise
    except Exception as exc:
        raise CryptoError("Failed to derive receiver session key.") from exc


def encrypt_payload(payload: dict, session_key: bytes) -> str:
    try:
        serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        token = Fernet(_b64encode(session_key).encode("ascii")).encrypt(serialized)
        return token.decode("ascii")
    except Exception as exc:
        raise CryptoError("Failed to encrypt payload.") from exc


def decrypt_payload(token: str, session_key: bytes) -> dict:
    try:
        decrypted = Fernet(_b64encode(session_key).encode("ascii")).decrypt(token.encode("ascii"))
        payload = json.loads(decrypted.decode("utf-8"))
    except InvalidToken as exc:
        raise CryptoError("Decrypt failed.") from exc
    except Exception as exc:
        raise CryptoError("Invalid encrypted payload.") from exc

    if not isinstance(payload, dict):
        raise CryptoError("Payload must be a JSON object.")
    return payload


def key_fingerprint(public_key_b64: str) -> str:
    raw = _b64decode(public_key_b64)
    digest = hashlib.sha256(raw).hexdigest()
    return ":".join(digest[index:index + 4] for index in range(0, 16, 4))

