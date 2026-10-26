import os
from datetime import datetime, timezone, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL   = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY   = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE          = "slack_bot_kv"

_HEADERS = None


def _headers() -> dict:
    global _HEADERS
    if _HEADERS is None:
        _HEADERS = {
            "apikey":        SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type":  "application/json",
            "Prefer":        "return=representation",
        }
    return _HEADERS


def _url() -> str:
    return f"{SUPABASE_URL}/rest/v1/{TABLE}"


class SupabaseKV:
    """Redis-like key-value wrapper over Supabase REST API.

    Same interface as the previous Upstash client — nothing else needs changing.
    """

    def get(self, key: str) -> str | None:
        resp = requests.get(
            _url(),
            headers=_headers(),
            params={"key": f"eq.{key}", "select": "value,expires_at"},
            timeout=5,
        )
        if resp.status_code != 200 or not resp.json():
            return None
        row = resp.json()[0]
        expires_at = row.get("expires_at")
        if expires_at:
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if exp < datetime.now(timezone.utc):
                self.delete(key)
                return None
        return row["value"]

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        expires_at = None
        if ex is not None:
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ex)).isoformat()
        requests.post(
            _url(),
            headers={**_headers(), "Prefer": "resolution=merge-duplicates"},
            json={"key": key, "value": str(value), "expires_at": expires_at},
            timeout=5,
        )

    def incr(self, key: str) -> int:
        resp = requests.get(
            _url(),
            headers=_headers(),
            params={"key": f"eq.{key}", "select": "value,expires_at"},
            timeout=5,
        )
        rows = resp.json() if resp.status_code == 200 else []
        if rows:
            row     = rows[0]
            new_val = (int(row["value"]) if row["value"] else 0) + 1
            requests.patch(
                _url(),
                headers=_headers(),
                params={"key": f"eq.{key}"},
                json={"value": str(new_val)},
                timeout=5,
            )
        else:
            new_val = 1
            requests.post(
                _url(),
                headers={**_headers(), "Prefer": "resolution=merge-duplicates"},
                json={"key": key, "value": "1", "expires_at": None},
                timeout=5,
            )
        return new_val

    def expire(self, key: str, seconds: int) -> None:
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
        requests.patch(
            _url(),
            headers=_headers(),
            params={"key": f"eq.{key}"},
            json={"expires_at": expires_at},
            timeout=5,
        )

    def delete(self, key: str) -> None:
        requests.delete(
            _url(),
            headers=_headers(),
            params={"key": f"eq.{key}"},
            timeout=5,
        )


_kv: SupabaseKV | None = None


def get_kv() -> SupabaseKV:
    global _kv
    if _kv is None:
        _kv = SupabaseKV()
    return _kv
