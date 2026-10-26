import json
import os
import anthropic
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

TRIAGE_SYSTEM = """You are an expert IT helpdesk triage specialist with 10+ years of experience. Given an IT support request, return a JSON object with exactly these fields:
{
  "category": str,         // "Access & Auth" | "Hardware" | "Software & Apps" | "Network & Connectivity" | "Onboarding/Offboarding" | "Security" | "Other"
  "priority": str,         // "P1 - Critical" | "P2 - High" | "P3 - Medium" | "P4 - Low"
  "sla_hours": int,        // 4 | 8 | 24 | 72
  "owner": str,            // "Identity & Access Team" | "IT Support (Tier 1)" | "IT Support (Tier 2)" | "Infrastructure Team" | "IT Manager" | "HR + IT Joint"
  "suggested_action": str, // 2-3 sentences: specific, actionable next step for the agent
  "auto_resolvable": bool, // true if self-service or automation could handle this without human intervention
  "tags": [str],           // 1-3 tags from: ["password-reset","mfa","access-request","offboarding","onboarding","hardware-failure","software-license","vpn","sso","mdm","compliance","vendor-app","network"]
  "kb_id": str | null,     // first 8 chars of the KB-ID if a KB article matches, else null
  "resolution": str | null, // exact resolution text from the matched KB article, else null
  "auto_close": bool       // true ONLY if kb_id is set AND auto_closeable:true AND issue is straightforward
}

Priority logic:
- P1: complete blockage, exec/customer-facing, security risk, multiple users affected (>5), data loss risk
- P2: significant impairment, time-sensitive deadline, single user blocked on critical tool
- P3: partial impairment, workaround exists, normal access requests
- P4: non-urgent, improvements, low-impact issues

KB matching rules (if KB context is provided):
- Only set kb_id if you are confident the article addresses this specific issue
- Copy the resolution text exactly from the KB article when matched
- Set auto_close:true only for truly routine issues (account unlocks, MFA resets, simple fixes)

Return ONLY valid JSON. No markdown, no preamble."""

RISK_SYSTEM = """You are an IAM security analyst. Given an access request, return a JSON object:
{
  "risk_level": str,       // "Low" | "Medium" | "High"
  "risk_factors": [str],   // specific concerns, empty list if Low risk
  "recommendation": str,   // "Approve" | "Review" | "Deny"
  "rationale": str,        // 2 sentences explaining the assessment
  "sox_sensitive": bool,   // true for: Salesforce, NetSuite, Workday, GitHub, AWS, Okta, financial systems
  "auto_approve": bool     // true ONLY if risk_level is Low AND access_level is read-only or user
}

Risk factors to consider:
- Admin/super-admin to sensitive systems = High
- SOX-sensitive system + elevated access = High
- Vague or insufficient justification = Medium
- Manager mismatch or unknown manager = Medium
- Read-only to non-sensitive system with clear justification = Low

Return ONLY valid JSON. No markdown, no preamble."""


def triage_request(subject: str, description: str,
                   urgency: str, department: str,
                   kb_block: str = "") -> dict:
    payload = {
        "subject": subject,
        "description": description,
        "urgency": urgency,
        "department": department,
    }
    user_content = json.dumps(payload)
    if kb_block:
        user_content = f"{kb_block}\n\n---\n\n{user_content}"

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=TRIAGE_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


INCIDENT_SYSTEM = """You are an incident commander. Given a production incident, return a JSON object:
{
  "summary": str,              // 1-2 sentence plain-English summary of what is happening
  "immediate_actions": [str],  // 3-5 specific, ordered actions for the responder to take right now
  "notify_teams": [str],       // teams that must be looped in, e.g. ["Engineering", "Customer Success"]
  "user_impact": str,          // who is affected and how, e.g. "All EU users cannot log in"
  "estimated_scope": str       // scale of impact, e.g. "~500 affected users" or "All production traffic"
}

Return ONLY valid JSON. No markdown, no preamble."""


def assess_incident(
    title: str,
    systems: str,
    description: str,
    severity: str,
) -> dict:
    payload = {
        "title": title,
        "systems_affected": systems,
        "description": description,
        "severity": severity,
    }
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=512,
        system=INCIDENT_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload)}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def assess_access_risk(app_name: str, access_level: str,
                       justification: str, manager: str) -> dict:
    payload = {
        "app_name": app_name,
        "access_level": access_level,
        "justification": justification,
        "manager_name": manager,
    }
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=512,
        system=RISK_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload)}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())
