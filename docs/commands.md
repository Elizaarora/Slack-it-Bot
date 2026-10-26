# Slash Command Reference

---

## `/itrequest`

**Purpose:** Submit an IT support request. Claude triages it, creates a Jira ticket, and posts a
structured card to `#it-requests`.

### Modal Fields

| Field | Type | Description |
|---|---|---|
| Subject | Short text | One-line summary of the issue |
| Description | Long text | Full context — what's happening, what you've tried |
| Urgency | Dropdown | `Low` / `Medium` / `High` / `Critical` |
| Department | Dropdown | Submitter's department for routing and labeling |

### What Happens After Submit

1. Modal closes immediately
2. Background thread starts:
   - Fetches KB articles from Supabase and Confluence (if configured)
   - Claude triage call (Haiku) with KB context injected into the prompt
   - Jira ticket created (if `JIRA_API_TOKEN` is set) with Claude-assigned priority and labels
   - Confluence incident page created for P1/P2 tickets (if `CONFLUENCE_SPACE_KEY` is set)
   - If KB match found and `auto_closeable: true`: DM sent to submitter with the resolution
   - Structured card posted to `#it-requests`
   - Ephemeral confirmation sent to submitter in their original channel

### Claude Output Schema

```json
{
  "category":        "Access & Auth | Hardware | Software & Apps | Network & Connectivity | ...",
  "priority":        "P1 - Critical | P2 - High | P3 - Medium | P4 - Low",
  "sla_hours":       4 | 8 | 24 | 72,
  "owner":           "Identity & Access Team | IT Support (Tier 1) | ...",
  "suggested_action": "2-3 sentence action recommendation",
  "auto_resolvable": true | false,
  "tags":            ["password-reset", "mfa", ...],
  "kb_id":           "first 8 chars of matched KB article ID, or null",
  "resolution":      "exact resolution text from KB article, or null",
  "auto_close":      true | false
}
```

### Priority Logic (Claude-assigned)

| Priority | Criteria |
|---|---|
| P1 - Critical | Complete blockage, exec/customer-facing, security risk, >5 users affected, data loss risk |
| P2 - High | Significant impairment, time-sensitive deadline, single user blocked on critical tool |
| P3 - Medium | Partial impairment, workaround exists, normal access requests |
| P4 - Low | Non-urgent, improvements, low-impact issues |

---

## `/accessrequest`

**Purpose:** Request access to a system or application. Claude assesses risk; low-risk requests
auto-approve, medium/high route to `#it-approvals` for manager review.

### Modal Fields

| Field | Type | Description |
|---|---|---|
| Application | Short text | The system or app being requested (e.g. `Salesforce`, `AWS`) |
| Access Level | Dropdown | `Read-only` / `User` / `Admin` / `Super Admin` |
| Justification | Long text | Business reason for the request |
| Manager Name | Short text | Direct manager's name — used in risk assessment |

### What Happens After Submit

1. Modal closes immediately
2. Rate limit checked — request blocked if daily limit is reached
3. Background thread starts:
   - Claude risk assessment (Sonnet)
   - **Low risk + auto_approve**: auto-approved, DM sent to requester, logged to `#it-requests`
   - **Medium / High risk**: approval card posted to `#it-approvals` with Approve / Deny buttons;
     request state persisted in Supabase KV; requester receives "pending review" DM
   - On **Approve** button click: approval card updated, requester DM'd with confirmation
   - On **Deny** button click: deny reason modal opens; on submit, card updated, requester DM'd
     with the denial reason

### Claude Output Schema

```json
{
  "risk_level":    "Low | Medium | High",
  "risk_factors":  ["specific concerns..."],
  "recommendation": "Approve | Review | Deny",
  "rationale":     "2-sentence explanation",
  "sox_sensitive": true | false,
  "auto_approve":  true | false
}
```

### Risk Factor Logic

| Scenario | Risk Level |
|---|---|
| Admin / super-admin to a sensitive system | High |
| SOX-sensitive system (Salesforce, AWS, Okta, GitHub, NetSuite, Workday...) + elevated access | High |
| Vague or insufficient justification | Medium |
| Manager mismatch or unknown manager | Medium |
| Read-only to non-sensitive system, clear justification | Low |

### Approval State Persistence

Pending approvals are stored in Supabase KV with a 7-day TTL. This means approvals survive Vercel
cold starts and redeploys. Clicking Approve or Deny after the TTL expires is a no-op.

---

## `/incident`

**Purpose:** Declare a production incident. Claude analyzes the situation and generates a structured
response card; a Confluence incident runbook page is created automatically.

### Modal Fields

| Field | Type | Description |
|---|---|---|
| Title | Short text | One-line incident description |
| Severity | Dropdown | `SEV-1` / `SEV-2` / `SEV-3` |
| Systems Affected | Short text | Comma-separated list of affected systems/services |
| Description | Long text | What is happening, what you've observed, timeline so far |

### What Happens After Submit

1. Modal closes immediately
2. Background thread starts:
   - Claude incident assessment (Sonnet)
   - Confluence incident page created (if `CONFLUENCE_SPACE_KEY` is set) with timeline template,
     AI summary, immediate actions, and teams to notify
   - Structured incident card posted to `#incidents` with Confluence page link
   - Ephemeral confirmation sent to the declarer

### Claude Output Schema

```json
{
  "summary":           "1-2 sentence plain-English incident summary",
  "immediate_actions": ["ordered action 1", "action 2", ...],
  "notify_teams":      ["Engineering", "Customer Success", ...],
  "user_impact":       "who is affected and how",
  "estimated_scope":   "~500 affected users | All production traffic | ..."
}
```

---

## Rate Limiting

All three commands share a per-user daily limit controlled by the `RATE_LIMIT_PER_DAY` environment
variable (default: `5`). Limits reset at midnight UTC. When the limit is hit, the user receives an
ephemeral message in their channel — no silent failures.
