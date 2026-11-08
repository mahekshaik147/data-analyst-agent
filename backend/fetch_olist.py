"""Download the private Olist database from a private GitHub release.

Reads the access token from OLIST_DATA_TOKEN. The token is never printed.
"""
import gzip
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

REPO = os.environ.get("OLIST_DATA_REPO", "mahekshaik147/data-analyst-agent-private-data")
TAG = os.environ.get("OLIST_RELEASE_TAG", "olist-v1")
ASSET = os.environ.get("OLIST_ASSET_NAME", "olist.db.gz")
EXPECTED_SHA256 = os.environ.get(
    "OLIST_SHA256",
    "f06b6bf2b5638b1e077a69a4a66fdabfd0b92103ebb90cfed4613bdfacd1f22f",
).lower()
TARGET = Path(os.environ.get("OLIST_TARGET", "backend/data/olist.db"))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(_NoRedirect)


def _request(url, token, accept):
    return urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": accept,
            "User-Agent": "olist-fetch",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )


def main() -> int:
    if TARGET.exists() and TARGET.stat().st_size > 0:
        print(f"olist: {TARGET} already exists, skipping download")
        return 0

    token = os.environ.get("OLIST_DATA_TOKEN", "").strip()
    if not token:
        print("olist: OLIST_DATA_TOKEN is not set; cannot download the database")
        return 1

    try:
        url = f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}"
        with OPENER.open(_request(url, token, "application/vnd.github+json")) as resp:
            release = json.load(resp)
        asset = next((a for a in release.get("assets", []) if a["name"] == ASSET), None)
        if asset is None:
            print(f"olist: asset {ASSET} not found in release {TAG}")
            return 1

        try:
            OPENER.open(_request(asset["url"], token, "application/octet-stream"))
            print("olist: expected a redirect to the file download")
            return 1
        except urllib.error.HTTPError as redirect:
            if redirect.code not in (301, 302, 303, 307, 308):
                raise
            location = redirect.headers["Location"]

        TARGET.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gz") as tmp:
            tmp_path = Path(tmp.name)
            download = urllib.request.Request(location, headers={"User-Agent": "olist-fetch"})
            with urllib.request.urlopen(download) as resp:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    tmp.write(chunk)
    except urllib.error.HTTPError as error:
        print(f"olist: download failed with HTTP {error.code} (401/403 = token problem, 404 = wrong repo or tag)")
        return 1
    except urllib.error.URLError as error:
        print(f"olist: network error: {error.reason}")
        return 1

    try:
        if EXPECTED_SHA256 and digest.hexdigest() != EXPECTED_SHA256:
            print("olist: checksum mismatch, refusing to use the download")
            return 1
        partial = TARGET.with_suffix(".partial")
        with gzip.open(tmp_path, "rb") as source, open(partial, "wb") as out:
            shutil.copyfileobj(source, out)
        with open(partial, "rb") as check:
            if check.read(16) != b"SQLite format 3\x00":
                partial.unlink()
                print("olist: unpacked file is not a SQLite database")
                return 1
        os.replace(partial, TARGET)
    finally:
        tmp_path.unlink(missing_ok=True)

    print(f"olist: database ready at {TARGET} ({TARGET.stat().st_size // 1048576} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
