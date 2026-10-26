# Slack IT Ops Bot

Automates IT operations workflows via Slack slash commands — triage, access control, and incident
response — powered by Claude AI.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![Vercel](https://img.shields.io/badge/deployed-Vercel-black)
![slack-bolt](https://img.shields.io/badge/slack--bolt-1.18+-purple)

---

## What It Does

Three slash commands, each opening a modal, invoking Claude for structured AI analysis, and taking
downstream action — all without blocking the 3-second Slack response window.

| Command | AI Model | What Happens |
|---|---|---|
| `/itrequest` | Claude Haiku | Triages the request (category, P1–P4 priority, SLA, owner, suggested action) → posts to `#it-requests` → creates Jira ticket → auto-resolves if a KB match is found |
| `/accessrequest` | Claude Sonnet | Assesses risk (Low / Medium / High) → Low risk auto-approves with DM; Medium/High routes to `#it-approvals` with interactive Approve / Deny buttons → requester gets DM on decision |
| `/incident` | Claude Sonnet | Analyzes affected systems and severity → posts structured incident card to `#incidents` with immediate actions and teams to notify → creates Confluence incident page |

---

## Architecture

```
Slack slash command
  └── ack() immediately (< 1s)          # Slack's 3-second deadline cleared
      └── background thread
          ├── Supabase KB lookup         # known fixes
          ├── Confluence KB search       # optional
          ├── Claude AI analysis
          ├── Jira ticket creation       # optional
          ├── Confluence incident page   # optional, P1/P2 only
          └── Slack message / DM
```

Approval state for `/accessrequest` is persisted in Supabase KV so it survives Vercel cold starts
and redeploys. Rate limiting is enforced per user per day via the same KV store.

---

## Stack

| Component | Technology |
|---|---|
| Runtime | Python 3 (Flask + slack-bolt) |
| Deployment | Vercel (serverless, `@vercel/python`) |
| AI | Anthropic Claude API (Haiku 4.5 + Sonnet 4.5) |
| Persistence | Supabase (KV store + knowledge base table) |
| Ticketing | Jira Cloud REST API (optional) |
| Knowledge base | Supabase table + Confluence search (both optional) |
| Rate limiting | Supabase KV, configurable via `RATE_LIMIT_PER_DAY` |

---

## Quick Start

See **[docs/setup.md](docs/setup.md)** for full instructions:
1. Create and configure a Slack app
2. Copy `.env.example` → `.env` and fill in values
3. `pip install -r requirements.txt`
4. Run locally with Flask + ngrok, or deploy to Vercel

---

## Environment Variables

Copy `.env.example` to `.env`. Jira and Confluence are optional — the bot works without them.

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | Bot token (`xoxb-...`) from OAuth & Permissions |
| `SLACK_SIGNING_SECRET` | Yes | From Basic Information in Slack app settings |
| `ANTHROPIC_API_KEY` | Yes | From [console.anthropic.com](https://console.anthropic.com) |
| `SUPABASE_URL` | Yes | Supabase project REST URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key (for KV + KB reads) |
| `IT_REQUESTS_CHANNEL` | Yes | Channel for IT requests (e.g. `#it-requests`) |
| `IT_APPROVALS_CHANNEL` | Yes | Channel for pending access approvals (e.g. `#it-approvals`) |
| `INCIDENTS_CHANNEL` | Yes | Channel for incident declarations (e.g. `#incidents`) |
| `JIRA_URL` | No | e.g. `https://yoursite.atlassian.net` |
| `JIRA_EMAIL` | No | Jira account email |
| `JIRA_API_TOKEN` | No | Jira API token |
| `JIRA_PROJECT_KEY` | No | Jira project key (default: `IT`) |
| `CONFLUENCE_SPACE_KEY` | No | Confluence space for KB search and incident pages |
| `CONFLUENCE_URL` | No | Confluence URL — defaults to `JIRA_URL` if same Atlassian instance |
| `CONFLUENCE_EMAIL` | No | Defaults to `JIRA_EMAIL` if same instance |
| `CONFLUENCE_API_TOKEN` | No | Defaults to `JIRA_API_TOKEN` if same instance |
| `RATE_LIMIT_PER_DAY` | No | Max AI requests per user per day (default: `5`) |

---

## Project Structure

```
slack-it-bot/
├── api/
│   └── index.py                  # Flask app — Vercel entry point
├── bot/
│   ├── app.py                    # slack-bolt App + handler registration
│   ├── claude_ops.py             # triage_request(), assess_access_risk(), assess_incident()
│   ├── jira_ops.py               # create_ticket()
│   ├── confluence_ops.py         # search_and_format_for_prompt(), create_incident_page()
│   ├── kb.py                     # fetch_knowledge_base() from Supabase
│   ├── kv.py                     # SupabaseKV — Redis-compatible wrapper over Supabase REST
│   ├── blocks.py                 # All Block Kit message and modal builders
│   ├── handlers/
│   │   ├── it_request.py         # /itrequest command + modal submission
│   │   ├── access_request.py     # /accessrequest command + approval flow
│   │   └── incident.py           # /incident command + modal submission
│   └── middleware/
│       └── rate_limit.py         # Per-user daily rate limiting via Supabase KV
├── docs/
│   ├── setup.md                  # Slack app config + local setup guide
│   ├── commands.md               # Slash command reference
│   └── demo.md                   # Demo mode instructions
├── requirements.txt
├── vercel.json
└── .env.example
```

---

## Timeout Handling

Slack requires a response within **3 seconds**. This bot uses a two-step pattern:

1. Slash commands `ack()` immediately and open a modal (< 1s)
2. Modal submissions `ack()` to close the modal, then spawn a background thread for Claude +
   Jira + Confluece work

This keeps all AI and API calls off the critical path.

| Vercel Plan | Function Timeout | Notes |
|---|---|---|
| Hobby | 10s | Claude ~3–5s + Jira ~1s = ~6–7s. Works in practice |
| Pro | 300s | No constraint |

---

## Test Cases

| Input | Expected Claude Output |
|---|---|
| "Okta locked out, board presentation in 1 hour" | P1 Critical · Identity & Access Team · 4h SLA |
| "Mouse not scrolling properly" | P4 Low · IT Support Tier 1 · 72h SLA |
| "Read-only access to Notion for note-taking" | Low risk → auto-approved |
| "Admin access to AWS for production deploy" | High risk · SOX-sensitive → approval required |
| "API gateway returning 502s, all users affected" | Sev-1 Incident → immediate actions + Confluence page |

---

## Docs

- [Setup guide](docs/setup.md) — Slack app, Supabase, Jira, Confluence, Vercel deploy
- [Command reference](docs/commands.md) — modals, fields, and response format for each command
- [Demo mode](docs/demo.md) — run locally without Jira or Confluence

---

