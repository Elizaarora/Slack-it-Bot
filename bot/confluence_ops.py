import os
import re
import json
import requests
from datetime import datetime
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

# Confluence shares the same Atlassian instance as Jira — override only if different
CONF_URL     = os.getenv("CONFLUENCE_URL")   or os.getenv("JIRA_URL", "")
CONF_EMAIL   = os.getenv("CONFLUENCE_EMAIL") or os.getenv("JIRA_EMAIL", "")
CONF_TOKEN   = os.getenv("CONFLUENCE_API_TOKEN") or os.getenv("JIRA_API_TOKEN", "")
CONF_SPACE   = os.getenv("CONFLUENCE_SPACE_KEY", "IT")

_AUTH = None


def _auth() -> HTTPBasicAuth | None:
    global _AUTH
    if not all([CONF_URL, CONF_EMAIL, CONF_TOKEN]):
        return None
    if _AUTH is None:
        _AUTH = HTTPBasicAuth(CONF_EMAIL, CONF_TOKEN)
    return _AUTH


def _strip_html(html: str) -> str:
    """Strip HTML/XML tags and normalize whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def search_kb(query: str, limit: int = 3) -> list[dict]:
    """Search Confluence for KB articles matching query.
    Returns list of {"title": str, "url": str, "id": str}.
    """
    auth = _auth()
    if not auth:
        return []

    cql = f'type=page AND space="{CONF_SPACE}" AND text~"{query}" ORDER BY lastModified DESC'
    try:
        resp = requests.get(
            f"{CONF_URL}/wiki/rest/api/content/search",
            params={"cql": cql, "limit": limit, "expand": ""},
            auth=auth,
            headers={"Accept": "application/json"},
            timeout=5,
        )
        if resp.status_code != 200:
            return []
        results = resp.json().get("results", [])
        articles = []
        for r in results:
            web_ui = r.get("_links", {}).get("webui", "")
            articles.append({
                "id":    r.get("id", ""),
                "title": r.get("title", "Untitled"),
                "url":   f"{CONF_URL}/wiki{web_ui}" if web_ui else "",
            })
        return articles
    except Exception:
        return []


def fetch_article_content(page_id: str, max_chars: int = 500) -> str:
    """Fetch and return the plain-text content of a Confluence page."""
    auth = _auth()
    if not auth or not page_id:
        return ""
    try:
        resp = requests.get(
            f"{CONF_URL}/wiki/rest/api/content/{page_id}",
            params={"expand": "body.view"},
            auth=auth,
            headers={"Accept": "application/json"},
            timeout=5,
        )
        if resp.status_code != 200:
            return ""
        html = resp.json().get("body", {}).get("view", {}).get("value", "")
        text = _strip_html(html)
        return text[:max_chars] + "..." if len(text) > max_chars else text
    except Exception:
        return ""


def search_and_format_for_prompt(query: str) -> tuple[list[dict], str]:
    """Search Confluence, fetch content, and return:
      - articles: list of {"title", "url"} for Slack blocks
      - kb_block: formatted string to inject into the Claude prompt
    """
    articles = search_kb(query)
    if not articles:
        return [], ""

    enriched = []
    for a in articles:
        content = fetch_article_content(a["id"])
        enriched.append({**a, "content": content})

    lines = ["CONFLUENCE KNOWLEDGE BASE (use these articles to help resolve the ticket):"]
    for a in enriched:
        if a.get("content"):
            lines.append(f'- {a["title"]}: {a["content"]}')

    kb_block = "\n".join(lines) if len(lines) > 1 else ""
    slack_articles = [{"title": a["title"], "url": a["url"]} for a in enriched]
    return slack_articles, kb_block


def create_incident_page(
    title: str,
    description: str,
    assessment: dict,
    submitter: str,
) -> dict | None:
    """Create a Confluence incident page. Returns {"url": str} or None."""
    auth = _auth()
    if not auth:
        return None

    date_str    = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    page_title  = f"[INCIDENT] {title} — {datetime.utcnow().strftime('%Y-%m-%d')}"
    summary     = assessment.get("summary", "")
    actions     = assessment.get("immediate_actions", [])
    teams       = assessment.get("notify_teams", [])
    user_impact = assessment.get("user_impact", "Unknown")
    scope       = assessment.get("estimated_scope", "Unknown")

    actions_html = "".join(f"<li>{a}</li>" for a in actions)
    teams_html   = ", ".join(teams) if teams else "TBD"

    body_html = f"""
<h2>Incident Summary</h2>
<p><strong>Declared:</strong> {date_str}</p>
<p><strong>Declared by:</strong> {submitter}</p>
<p><strong>User Impact:</strong> {user_impact}</p>
<p><strong>Estimated Scope:</strong> {scope}</p>

<h2>Description</h2>
<p>{description}</p>

<h2>AI Assessment</h2>
<p>{summary}</p>

<h2>Immediate Actions</h2>
<ul>{actions_html}</ul>

<h2>Teams to Notify</h2>
<p>{teams_html}</p>

<h2>Timeline</h2>
<table>
  <tr><th>Time</th><th>Event</th><th>Owner</th></tr>
  <tr><td>{date_str}</td><td>Incident declared</td><td>{submitter}</td></tr>
</table>

<h2>Resolution</h2>
<p><em>To be filled in when resolved.</em></p>
"""

    payload = {
        "type": "page",
        "title": page_title,
        "space": {"key": CONF_SPACE},
        "body": {
            "storage": {
                "value": body_html,
                "representation": "storage",
            }
        },
    }

    try:
        resp = requests.post(
            f"{CONF_URL}/wiki/rest/api/content",
            json=payload,
            auth=auth,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            web_ui = data.get("_links", {}).get("webui", "")
            return {"url": f"{CONF_URL}/wiki{web_ui}" if web_ui else ""}
    except Exception:
        pass
    return None
