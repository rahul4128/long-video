#!/usr/bin/env python3
import base64
import os
import sys
import time

import requests
from nacl.public import PublicKey, SealedBox


def req(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing {name}")
    return value


def github_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_github_public_key(repo, headers):
    response = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers,
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(
            f"GitHub public-key lookup failed ({response.status_code}): "
            f"{response.text[:1000]}"
        )

    payload = response.json()
    encoded_key = payload.get("key", "")
    key_id = payload.get("key_id", "")
    if not encoded_key or not key_id:
        raise RuntimeError("GitHub public-key response is missing key or key_id.")

    try:
        raw_key = base64.b64decode(encoded_key, validate=True)
    except Exception as exc:
        raise RuntimeError("GitHub public key is not valid base64.") from exc

    if len(raw_key) != 32:
        raise RuntimeError(
            f"GitHub public key decoded to {len(raw_key)} bytes; expected exactly 32."
        )

    return raw_key, key_id


def save_refresh_token(repo, github_token, new_refresh):
    headers = github_headers(github_token)
    last_error = None

    # The Canva refresh token is single-use. Once Canva returns a new token,
    # never call Canva again while retrying the GitHub secret update.
    for attempt in range(1, 4):
        try:
            raw_key, key_id = get_github_public_key(repo, headers)
            encrypted = SealedBox(PublicKey(raw_key)).encrypt(new_refresh.encode())
            encrypted_value = base64.b64encode(encrypted).decode()

            response = requests.put(
                f"https://api.github.com/repos/{repo}/actions/secrets/CANVA_REFRESH_TOKEN",
                headers=headers,
                json={
                    "encrypted_value": encrypted_value,
                    "key_id": key_id,
                },
                timeout=60,
            )

            if response.ok:
                return

            last_error = (
                f"GitHub secret update failed ({response.status_code}): "
                f"{response.text[:1000]}"
            )
        except Exception as exc:
            last_error = str(exc)

        if attempt < 3:
            time.sleep(2 * attempt)

    raise RuntimeError(last_error or "GitHub secret update failed.")


def main():
    client_id = req("CANVA_CLIENT_ID")
    client_secret = req("CANVA_CLIENT_SECRET")
    refresh_token = req("CANVA_REFRESH_TOKEN")
    github_token = req("REPO_SECRETS_TOKEN")
    repo = req("GITHUB_REPOSITORY")

    # Validate GitHub encryption BEFORE consuming Canva's single-use refresh token.
    github_headers_value = github_headers(github_token)
    get_github_public_key(repo, github_headers_value)

    response = requests.post(
        "https://api.canva.com/rest/v1/oauth/token",
        auth=(client_id, client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=60,
    )

    if not response.ok:
        # invalid_grant is not retryable. It means Canva rejected the stored
        # refresh token (invalid/revoked/expired or associated with different
        # client credentials). Retrying would not repair it.
        if response.status_code == 400:
            try:
                error = response.json()
            except ValueError:
                error = {}

            if error.get("error") == "invalid_grant":
                description = error.get("error_description", "Invalid refresh token")
                raise RuntimeError(
                    "Canva rejected CANVA_REFRESH_TOKEN with invalid_grant: "
                    f"{description}. "
                    "Generate a NEW token with scripts/canva_oauth.js using the "
                    "same CANVA_CLIENT_ID and CANVA_CLIENT_SECRET currently stored "
                    "in GitHub Actions, then replace CANVA_REFRESH_TOKEN. "
                    "Do not reuse an older refresh token."
                )

        raise RuntimeError(
            f"Canva refresh failed ({response.status_code}): "
            f"{response.text[:1000]}"
        )

    data = response.json()
    access = data.get("access_token")
    new_refresh = data.get("refresh_token")
    if not access or not new_refresh:
        raise RuntimeError("Canva did not return both access_token and refresh_token.")

    print(f"::add-mask::{access}")

    # Save the newly rotated token immediately. Retries happen only against
    # GitHub; Canva is never called twice for the same refresh token.
    save_refresh_token(repo, github_token, new_refresh)

    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as env_file:
        env_file.write(f"CANVA_ACCESS_TOKEN={access}\n")

    print("Canva authentication succeeded.")
    print("Rotated Canva refresh token saved back to GitHub Actions Secrets.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
