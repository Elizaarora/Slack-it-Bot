import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

JIRA_URL     = os.getenv("JIRA_URL", "")
JIRA_EMAIL   = os.getenv("JIRA_EMAIL", "")
JIRA_TOKEN   = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT = os.getenv("JIRA_PROJECT_KEY", "IT")

PRIORITY_MAP = {
    "P1 - Critical": "Highest",
    "P2 - High":     "High",
    "P3 - Medium":   "Medium",
    "P4 - Low":      "Low",
}


def create_ticket(
    subject: str,
    description: str,
    department: str,
    submitter: str,
    triage: dict,
) -> dict | None:
    """Create a Jira ticket and return {"key": "IT-42", "url": "https://..."}"""
    if not all([JIRA_URL, JIRA_EMAIL, JIRA_TOKEN]):
        return None

    priority_name = PRIORITY_MAP.get(triage.get("priority", "P3 - Medium"), "Medium")
    labels = triage.get("tags", []) + [department.lower().replace(" ", "_")]

    body = {
        "fields": {
            "project": {"key": JIRA_PROJECT},
            "summary": subject,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": f"Submitted by: {submitter}"},
                        ],
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"AI Triage — Category: {triage.get('category')} | "
                                    f"Owner: {triage.get('owner')} | "
                                    f"SLA: {triage.get('sla_hours')}h"
                                ),
                            }
                        ],
                    },
                ],
            },
            "issuetype": {"name": "Task"},
            "priority": {"name": priority_name},
            "labels": [l.replace(" ", "_") for l in labels if l],
        }
    }

    try:
        resp = requests.post(
            f"{JIRA_URL}/rest/api/3/issue",
            json=body,
            auth=HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN),
            headers={"Accept": "application/json"},
            timeout=8,
        )
        if resp.status_code == 201:
            data = resp.json()
            key = data["key"]
            return {
                "key": key,
                "url": f"{JIRA_URL}/browse/{key}",
            }
    except Exception:
        pass
    return None
