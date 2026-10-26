# Demo Mode

You can run a fully functional demo locally using only Slack, Anthropic, and Supabase.
Jira and Confluence are optional — the bot degrades gracefully when those vars are absent.

---

## Minimum Required Configuration

```bash
# .env — minimum for a working demo
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_SIGNING_SECRET=your-secret
ANTHROPIC_API_KEY=sk-ant-your-key

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

IT_REQUESTS_CHANNEL=#it-requests
IT_APPROVALS_CHANNEL=#it-approvals
INCIDENTS_CHANNEL=#incidents

RATE_LIMIT_PER_DAY=20   # raise limit for demo testing
```

With this configuration:
- `/itrequest` — triages and posts to channel; no Jira ticket (skipped silently)
- `/accessrequest` — full approval flow with Approve/Deny buttons
- `/incident` — full incident card; no Confluence page (skipped silently)

---

## What Each Command Shows

### `/itrequest` demo scenarios

Try these inputs to see different priority levels and categories:

| Subject | What to Expect |
|---|---|
| "Okta locked out, board presentation in 1 hour" | P1 Critical · Identity & Access Team · 4h SLA |
| "Laptop running slowly, fan loud" | P3-P4 · IT Support Tier 1 · hardware tags |
| "New hire starting Monday, need laptop + Slack access" | P3 · Onboarding/Offboarding · HR + IT Joint |
| "Can't connect to VPN from home" | P2-P3 · Network & Connectivity |
| "Mouse not scrolling" | P4 Low · IT Support Tier 1 · 72h SLA |

Watch `#it-requests` — the card appears with category, priority badge, SLA, owner, and suggested
action. If Jira is configured, a ticket link appears on the card.

### `/accessrequest` demo scenarios

| App | Access Level | Justification | Expected Risk |
|---|---|---|---|
| Notion | Read-only | "Note-taking for project docs" | Low → auto-approved |
| GitHub | User | "Contributing to internal tooling repo" | Low-Medium |
| Salesforce | Admin | "Need to run financial reports" | High · SOX-sensitive |
| AWS | Super Admin | "Production deployment" | High · SOX-sensitive |
| Google Drive | Read-only | "Access shared team folder" | Low → auto-approved |

For high-risk requests: watch `#it-approvals` for the approval card with Approve/Deny buttons.
Click Approve or Deny and observe the card update and the requester DM in real time.

### `/incident` demo scenarios

| Title | Systems | Severity | What to Expect |
|---|---|---|---|
| "Login page returning 500 errors" | `auth-service, postgres` | SEV-1 | Immediate actions list, all-hands teams |
| "Slow API responses in EU region" | `api-gateway` | SEV-2 | Scope estimate, engineering + infra teams |
| "Single user can't access email" | `Google Workspace` | SEV-3 | Targeted scope, IT-only |

Watch `#incidents` for the structured card. If Confluence is configured, a runbook page is created
with a timeline template ready to be filled in during the incident.

---

## Verifying the Full Flow

1. Submit a **high-risk** `/accessrequest` (e.g., Salesforce Admin)
2. Check `#it-approvals` — approval card should appear within ~5 seconds
3. Click **Deny** — a reason modal opens
4. Submit a reason — the card updates to "Denied" and the original requester gets a DM
5. Submit the same request again — same flow, fresh `request_id`

The Approve path:
1. Submit another high-risk request
2. Click **Approve** in `#it-approvals`
3. Card updates to "Approved"; requester DM confirms access will be provisioned

---

## Checking the Health Endpoint

```bash
curl https://your-app.vercel.app/health
# {"status": "ok", "bot": "IT Ops Bot"}
```

A non-200 response includes the initialization error — useful for diagnosing missing env vars
before the first Slack interaction.

---

## Rate Limit Reset

Limits are stored in Supabase KV with a 24-hour TTL keyed by `usage:{user_id}:{date}`. To reset
during testing, either:
- Delete rows from `slack_bot_kv` where `key` starts with `usage:`
- Wait until midnight UTC
- Set `RATE_LIMIT_PER_DAY` to a higher number (e.g. `50`) for demo purposes
