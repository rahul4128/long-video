"""Offline tests for encrypted Canva access-token transfer between jobs."""
import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from nacl.exceptions import CryptoError

from scripts.canva_token_handoff import (
    seal_access_token, unseal_access_token, restore_from_environment,
)


class CanvaTokenHandoffTests(TestCase):
    def test_encrypted_token_roundtrip_without_plaintext_leak(self):
        secret = "GitHub-PAT-for-tests-only-" + "x"*40
        access = "canva-access-token-for-tests"
        with tempfile.TemporaryDirectory() as root:
            target = str(Path(root)/"access.enc")
            seal_access_token(access, target, secret=secret)
            ciphertext = Path(target).read_bytes()
            self.assertNotIn(access.encode(), ciphertext)
            self.assertEqual(unseal_access_token(target, secret=secret), access)
            self.assertEqual(os.stat(target).st_mode & 0o777, 0o600)

    def test_wrong_secret_cannot_decrypt(self):
        with tempfile.TemporaryDirectory() as root:
            target = str(Path(root)/"access.enc")
            seal_access_token("access-private", target, secret="a"*50)
            with self.assertRaises(RuntimeError):
                unseal_access_token(target, secret="b"*50)

    def test_cannot_write_without_secret(self):
        with tempfile.TemporaryDirectory() as root:
            target = str(Path(root)/"access.enc")
            with self.assertRaises(ValueError):
                seal_access_token("access", target, secret="")
            self.assertFalse(Path(target).exists())

    def test_missing_artifact_is_handled(self):
        with self.assertRaises(RuntimeError):
            unseal_access_token("/tmp/nonexistent-canva-access-handoff.enc", secret="a"*50)

    def test_handoff_restores_only_process_scoped_access_token(self):
        secret = "a"*50
        access = "safe-canva-short-lived-access-token"
        with tempfile.TemporaryDirectory() as root:
            target = str(Path(root)/"access.enc")
            github_env = str(Path(root)/"github_env")
            Path(github_env).touch()
            seal_access_token(access, target, secret=secret)
            with patch.dict(os.environ, {
                "CANVA_TOKEN_TRANSFER_FILE": target,
                "REPO_SECRETS_TOKEN": secret,
                "GITHUB_ENV": github_env,
            }):
                restore_from_environment()
            self.assertIn("CANVA_ACCESS_TOKEN=" + access, Path(github_env).read_text())
            self.assertNotIn("CANVA_REFRESH_TOKEN", Path(github_env).read_text())
