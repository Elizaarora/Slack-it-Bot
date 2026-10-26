import os
from datetime import datetime, timezone
from bot.kv import get_kv

LIMIT = int(os.getenv("RATE_LIMIT_PER_DAY", "5"))


def _key(user_id: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"usage:{user_id}:{today}"


def check_and_increment(user_id: str) -> tuple[bool, int]:
    """Returns (allowed, new_count). Increments counter if allowed."""
    kv = get_kv()
    key = _key(user_id)

    raw = kv.get(key)
    current = int(raw) if raw else 0

    if current >= LIMIT:
        return False, current

    kv.incr(key)
    kv.expire(key, 86400)
    return True, current + 1


def get_remaining(user_id: str) -> int:
    kv = get_kv()
    raw = kv.get(_key(user_id))
    current = int(raw) if raw else 0
    return max(0, LIMIT - current)


def rate_limit_blocks() -> list:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"⚠️ *Daily limit reached.*\n\n"
                    f"You've used all {LIMIT} AI-powered requests for today. "
                    "Your limit resets at midnight UTC.\n\n"
                    "This is a demo environment — limits keep API costs in check. "
                    "Thanks for understanding!"
                ),
            },
        }
    ]
