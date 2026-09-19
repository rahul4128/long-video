#!/usr/bin/env python3
import base64
import os
import sys
import requests
from nacl.public import PublicKey, SealedBox

def req(name):
    v = os.environ.get(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing {name}")
    return v

def main():
    client_id = req("CANVA_CLIENT_ID")
    client_secret = req("CANVA_CLIENT_SECRET")
    refresh_token = req("CANVA_REFRESH_TOKEN")
    github_token = req("REPO_SECRETS_TOKEN")
    repo = req("GITHUB_REPOSITORY")

    r = requests.post(
        "https://api.canva.com/rest/v1/oauth/token",
        auth=(client_id, client_secret),
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"Canva refresh failed ({r.status_code}): {r.text[:1000]}")
    data = r.json()
    access = data.get("access_token")
    new_refresh = data.get("refresh_token")
    if not access or not new_refresh:
        raise RuntimeError("Canva did not return both access_token and refresh_token.")

    h = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    r = requests.get(f"https://api.github.com/repos/{repo}/actions/secrets/public-key", headers=h, timeout=60)
    if not r.ok:
        raise RuntimeError(f"GitHub public-key lookup failed ({r.status_code}): {r.text[:1000]}")
    key = r.json()

    encrypted = SealedBox(PublicKey(key["key"].encode())).encrypt(new_refresh.encode())
    value = base64.b64encode(encrypted).decode()

    r = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/CANVA_REFRESH_TOKEN",
        headers=h,
        json={"encrypted_value": value, "key_id": key["key_id"]},
        timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"GitHub secret update failed ({r.status_code}): {r.text[:1000]}")

    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as f:
        f.write(f"CANVA_ACCESS_TOKEN={access}\n")

    print("Canva authentication succeeded.")
    print("Rotated Canva refresh token saved back to GitHub Actions Secrets.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
