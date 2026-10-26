# Setup Guide

This guide covers creating the Slack app, provisioning Supabase, configuring optional integrations
(Jira, Confluence), and deploying to Vercel.

---

## 1. Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From Scratch**
2. Name: `IT Ops Bot`, select your workspace

### OAuth & Permissions — Bot Token Scopes

| Scope | Why |
|---|---|
| `chat:write` | Post messages to channels and DMs |
| `commands` | Register slash commands |
| `users:read` | Resolve user display names |
| `views:open` | Open modals |

Install to workspace and copy the **Bot Token** (`xoxb-...`).

### Slash Commands

Create three commands, each pointing to the same Request URL:

| Command | Request URL |
|---|---|
| `/itrequest` | `https://your-app.vercel.app/slack/events` |
| `/accessrequest` | `https://your-app.vercel.app/slack/events` |
| `/incident` | `https://your-app.vercel.app/slack/events` |

### Interactivity & Shortcuts

Enable and set Request URL to: `https://your-app.vercel.app/slack/actions`

This handles modal submissions and button clicks (Approve / Deny).

### Event Subscriptions

Leave **off**. The bot uses HTTP mode (slash commands + interactivity), not Socket Mode or Events.

### Signing Secret

Copy from **Basic Information** → App Credentials → Signing Secret.

---

## 2. Supabase

Supabase is required for rate limiting, approval state persistence, and the optional knowledge base.

1. Create a free project at [supabase.com](https://supabase.com)
2. Copy the **Project URL** and **Service Role Key** from Settings → API

### Required: KV table

```sql
create table slack_bot_kv (
  key        text primary key,
  value      text,
  expires_at timestamptz
);
```

### Optional: Knowledge base table

If you want Claude to match tickets against known fixes and auto-resolve routine issues:

```sql
create table knowledge_base (
  id             text primary key,
  title          text not null,
  category       text,
  tags           text[],
  issue_pattern  text,
  resolution     text,
  article_url    text,
  auto_closeable boolean default false
);
```

Populate it with your team's common fixes. Claude will match incoming tickets against these entries
and, for routine issues marked `auto_closeable: true`, DM the user the resolution directly without
routing to IT.

---

## 3. Jira (optional)

The bot skips ticket creation gracefully if Jira vars are not set.

1. Create a free [Jira Cloud](https://www.atlassian.com/software/jira) account
2. Create a project — default key `IT`
3. Generate an API token: Account Settings → Security → API Tokens
4. Set `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY` in your env

---

## 4. Confluence (optional)

Confluence is used for two things:

- **KB search**: `/itrequest` searches your Confluence space for articles matching the ticket
  subject and injects the results into the Claude prompt as context
- **Incident pages**: `/itrequest` (P1/P2 only) and `/incident` create a structured incident
  runbook page automatically

If Confluence is on the **same Atlassian instance** as Jira, only `CONFLUENCE_SPACE_KEY` is
needed — the bot reuses `JIRA_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN`. Set the `CONFLUENCE_*`
overrides only if Confluence is on a separate instance.

---

## 5. Local Development

```bash
cp .env.example .env
# fill in at minimum: SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, ANTHROPIC_API_KEY,
# SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, and the three channel names

pip install -r requirements.txt

# Expose local server to Slack via ngrok:
ngrok http 3000
# Copy the ngrok URL and update your Slack app's Request URLs

python -m flask --app api/index.py run --port 3000
```

The `/health` endpoint (`GET /`) returns bot status and surfaces init errors — useful for
debugging Slack token or signing secret issues before the first real request.

---

## 6. Deploy to Vercel

```bash
npm i -g vercel       # install CLI if needed
vercel                # link project + preview deploy

# Add all required environment variables:
vercel env add SLACK_BOT_TOKEN
vercel env add SLACK_SIGNING_SECRET
vercel env add ANTHROPIC_API_KEY
vercel env add SUPABASE_URL
vercel env add SUPABASE_SERVICE_ROLE_KEY
vercel env add IT_REQUESTS_CHANNEL
vercel env add IT_APPROVALS_CHANNEL
vercel env add INCIDENTS_CHANNEL

# Optional integrations:
vercel env add JIRA_URL
vercel env add JIRA_EMAIL
vercel env add JIRA_API_TOKEN
vercel env add JIRA_PROJECT_KEY
vercel env add CONFLUENCE_SPACE_KEY

vercel --prod         # production deploy
```

After deploying, update your Slack app's Request URLs to the production Vercel URL.
