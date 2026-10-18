"""Encrypted, one-run-only handoff of a short-lived Canva *access* token.

GitHub Actions repository secrets are snapshotted at workflow start. Canva's
refresh token is single-use, so a second job in the same run cannot refresh
the old snapshotted secret after the first job rotates it.

Encrypt the access token (never the refresh token) for a short-lived Actions
artifact, with a per-purpose SecretBox key derived from REPO_SECRETS_TOKEN.
The secret is required to decrypt; no plaintext token goes into artifacts.
"""
import base64
import hashlib
import os
from pathlib import Path

from nacl.exceptions import CryptoError
from nacl.secret import SecretBox


def _key(secret: str) -> bytes:
    if not secret or len(secret) < 20:
        raise ValueError("REPO_SECRETS_TOKEN is missing or too short for token handoff")
    return hashlib.blake2b(
        secret.encode("utf-8"), digest_size=SecretBox.KEY_SIZE,
        person=b"canva-run-oauth",
    ).digest()


def seal_access_token(access: str, path: str, *, secret: str) -> None:
    if not access or not access.strip():
        raise ValueError("No Canva access token to hand off")
    box = SecretBox(_key(secret))
    encrypted = box.encrypt(access.encode("utf-8"))  # fresh random nonce
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64encode(encrypted))
    target.chmod(0o600)


def unseal_access_token(path: str, *, secret: str) -> str:
    try:
        encrypted = base64.b64decode(Path(path).read_bytes(), validate=True)
        access = SecretBox(_key(secret)).decrypt(encrypted).decode("utf-8")
    except (OSError, ValueError, CryptoError, UnicodeDecodeError) as exc:
        raise RuntimeError("Canva access handoff is missing or could not be decrypted") from exc
    if not access:
        raise RuntimeError("Canva handoff contained an empty access token")
    return access


def restore_from_environment() -> None:
    path = os.environ.get("CANVA_TOKEN_TRANSFER_FILE", "out/canva-token.enc")
    secret = os.environ.get("REPO_SECRETS_TOKEN", "")
    access = unseal_access_token(path, secret=secret)
    print(f"::add-mask::{access}")
    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as handle:
        handle.write(f"CANVA_ACCESS_TOKEN={access}\n")
    print("Canva access token restored securely for finishing (no second OAuth refresh).")


if __name__ == "__main__":
    restore_from_environment()
