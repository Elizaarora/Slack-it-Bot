import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def fetch_knowledge_base() -> list[dict]:
    """Fetch all KB articles from Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/knowledge_base",
            headers={
                "apikey":        SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
            params={"select": "id,title,category,tags,issue_pattern,resolution,article_url,auto_closeable"},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def format_kb_for_prompt(articles: list[dict]) -> str:
    """Format KB articles into a compact block for the Claude prompt."""
    if not articles:
        return ""
    lines = ["KNOWLEDGE BASE (known fixes — match tickets to these where applicable):"]
    for a in articles:
        lines.append(
            f'KB-ID:{a["id"][:8]} | {a["title"]} | auto_closeable:{a["auto_closeable"]} | '
            f'Pattern: {a["issue_pattern"]} | Fix: {a["resolution"][:120]}...'
        )
    return "\n".join(lines)
