from datetime import datetime


# ── IT Request blocks ─────────────────────────────────────────────────────────

def it_request_modal(channel_id: str = "", thread_ts: str = "") -> dict:
    return {
        "type": "modal",
        "callback_id": "it_request_modal",
        "private_metadata": f"{channel_id}|{thread_ts}",
        "title": {"type": "plain_text", "text": "Submit IT Request"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "subject_block",
                "label": {"type": "plain_text", "text": "Subject"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "subject",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g. Okta MFA not working after new phone",
                    },
                    "max_length": 120,
                },
            },
            {
                "type": "input",
                "block_id": "description_block",
                "label": {"type": "plain_text", "text": "Description"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "description",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Describe the issue in detail. Include any error messages, when it started, and what you've already tried.",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "urgency_block",
                "label": {"type": "plain_text", "text": "Urgency"},
                "element": {
                    "type": "static_select",
                    "action_id": "urgency",
                    "placeholder": {"type": "plain_text", "text": "Select urgency"},
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "🟢 Low — no immediate impact"},
                            "value": "low",
                        },
                        {
                            "text": {"type": "plain_text", "text": "🟡 Medium — work partially affected"},
                            "value": "medium",
                        },
                        {
                            "text": {"type": "plain_text", "text": "🔴 High — completely blocked"},
                            "value": "high",
                        },
                        {
                            "text": {"type": "plain_text", "text": "🚨 Emergency — business critical"},
                            "value": "emergency",
                        },
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "department_block",
                "label": {"type": "plain_text", "text": "Department"},
                "element": {
                    "type": "static_select",
                    "action_id": "department",
                    "placeholder": {"type": "plain_text", "text": "Select your department"},
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": dept},
                            "value": dept.lower().replace(" ", "_"),
                        }
                        for dept in [
                            "Engineering", "Sales", "Marketing", "HR", "Finance",
                            "Product", "Customer Success", "Design", "Operations",
                            "Legal", "IT",
                        ]
                    ],
                },
            },
        ],
    }


PRIORITY_EMOJI = {
    "P1 - Critical": "🚨",
    "P2 - High":     "🔴",
    "P3 - Medium":   "🟡",
    "P4 - Low":      "🟢",
}

PRIORITY_COLOR = {
    "P1 - Critical": "#EF4444",
    "P2 - High":     "#F97316",
    "P3 - Medium":   "#F59E0B",
    "P4 - Low":      "#22C55E",
}


def it_request_channel_message(
    subject: str,
    description: str,
    department: str,
    submitter_id: str,
    triage: dict,
    jira_url: str | None = None,
    kb_articles: list | None = None,
    incident_page_url: str | None = None,
) -> list:
    priority = triage.get("priority", "P3 - Medium")
    emoji    = PRIORITY_EMOJI.get(priority, "🟡")
    sla      = triage.get("sla_hours", 24)
    category = triage.get("category", "Other")
    owner    = triage.get("owner", "IT Support")
    action   = triage.get("suggested_action", "")
    tags     = triage.get("tags", [])
    auto     = triage.get("auto_resolvable", False)

    tag_str  = "  ".join(f"`{t}`" for t in tags) if tags else ""
    auto_str = "  ✨ `auto-resolvable`" if auto else ""
    ts       = datetime.now().strftime("%I:%M %p")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} New IT Request — {priority}"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{subject}*\n"
                    f"{description[:300]}{'...' if len(description) > 300 else ''}"
                ),
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Category*\n{category}"},
                {"type": "mrkdwn", "text": f"*Department*\n{department.replace('_', ' ').title()}"},
                {"type": "mrkdwn", "text": f"*SLA Target*\n{sla} hours"},
                {"type": "mrkdwn", "text": f"*Assign To*\n{owner}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Suggested Action*\n{action}"},
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Submitted by <@{submitter_id}> at {ts}{auto_str}  {tag_str}",
                }
            ],
        },
    ]

    # KB resolution from triage agent
    resolution = triage.get("resolution")
    kb_id      = triage.get("kb_id")
    auto_close = triage.get("auto_close", False)
    if resolution and kb_id:
        close_badge = "  ✅ `auto-closed`" if auto_close else ""
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*🗂 Known Fix (KB-{kb_id}){close_badge}*\n{resolution}",
            },
        })

    # Confluence KB articles (related links)
    if kb_articles:
        links = "  ·  ".join(f"<{a['url']}|{a['title']}>" for a in kb_articles if a.get("url"))
        if links:
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"📚 *Related Confluence:*  {links}"}],
            })

    # Buttons: Jira + Confluence incident page
    buttons = []
    if jira_url:
        buttons.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "View Jira Ticket →"},
            "url": jira_url,
            "style": "primary",
        })
    if incident_page_url:
        buttons.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Incident Page →"},
            "url": incident_page_url,
        })
    if buttons:
        blocks.append({"type": "actions", "elements": buttons})

    return blocks


def it_request_user_confirmation(priority: str, sla_hours: int, category: str,
                                  remaining: int | None = None,
                                  auto_closed: bool = False) -> list:
    emoji = PRIORITY_EMOJI.get(priority, "🟡")
    remaining_text = (
        f"\n\nYou have *{remaining}* AI request{'s' if remaining != 1 else ''} remaining today."
        if remaining is not None else ""
    )
    if auto_closed:
        body = (
            f"✅ *Your request was automatically resolved.*\n\n"
            f"A known fix has been sent to you via DM. Check your direct messages.\n\n"
            f"If the issue persists, reply in DM or submit a new request."
            f"{remaining_text}"
        )
    else:
        body = (
            f"✅ *Your IT request has been logged.*\n\n"
            f"{emoji} Priority: *{priority}* · SLA: *{sla_hours} hours*\n"
            f"Category: {category}\n\n"
            f"The IT team has been notified. You'll receive an update shortly."
            f"{remaining_text}"
        )
    return [{"type": "section", "text": {"type": "mrkdwn", "text": body}}]


# ── Access Request blocks ─────────────────────────────────────────────────────

def access_request_modal(channel_id: str = "", thread_ts: str = "") -> dict:
    return {
        "type": "modal",
        "callback_id": "access_request_modal",
        "private_metadata": f"{channel_id}|{thread_ts}",
        "title": {"type": "plain_text", "text": "Request Access"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "app_block",
                "label": {"type": "plain_text", "text": "App or System"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "app_name",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g. Salesforce, AWS, GitHub Enterprise",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "level_block",
                "label": {"type": "plain_text", "text": "Access Level Requested"},
                "element": {
                    "type": "static_select",
                    "action_id": "access_level",
                    "placeholder": {"type": "plain_text", "text": "Select access level"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Read-only"}, "value": "read-only"},
                        {"text": {"type": "plain_text", "text": "User (standard)"}, "value": "user"},
                        {"text": {"type": "plain_text", "text": "Admin"}, "value": "admin"},
                        {"text": {"type": "plain_text", "text": "Super-admin"}, "value": "super-admin"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "justification_block",
                "label": {"type": "plain_text", "text": "Business Justification"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "justification",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Why do you need this access? Be specific.",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "manager_block",
                "label": {"type": "plain_text", "text": "Your Manager's Name"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "manager_name",
                    "placeholder": {"type": "plain_text", "text": "e.g. Yuki Tanaka"},
                },
            },
        ],
    }


RISK_EMOJI = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}


def access_request_approval_message(
    requester_id: str,
    app_name: str,
    access_level: str,
    justification: str,
    manager_name: str,
    assessment: dict,
    request_id: str,
) -> list:
    risk         = assessment.get("risk_level", "Medium")
    rationale    = assessment.get("rationale", "")
    risk_factors = assessment.get("risk_factors", [])
    sox          = assessment.get("sox_sensitive", False)
    emoji        = RISK_EMOJI.get(risk, "🟡")
    sox_badge    = "  ⚠️ `SOX-sensitive`" if sox else ""

    factors_text = "\n".join(f"• {f}" for f in risk_factors) if risk_factors else "None identified"

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🔐 Access Request — {risk.upper()} RISK — Approval Required",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"<@{requester_id}> is requesting *{access_level}* access to *{app_name}*{sox_badge}\n\n"
                    f"*Justification:* {justification}\n"
                    f"*Manager:* {manager_name}"
                ),
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Risk Level*\n{emoji} {risk}"},
                {"type": "mrkdwn", "text": f"*SOX Sensitive*\n{'Yes ⚠️' if sox else 'No'}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Risk Assessment*\n{rationale}\n\n*Risk Factors:*\n{factors_text}",
            },
        },
        {"type": "divider"},
        {
            "type": "actions",
            "block_id": "approval_actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": f"approve_access_{request_id}",
                    "text": {"type": "plain_text", "text": "✓  Approve"},
                    "style": "primary",
                    "value": request_id,
                    "confirm": {
                        "title": {"type": "plain_text", "text": "Approve this request?"},
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Grant *{access_level}* access to *{app_name}* for <@{requester_id}>?",
                        },
                        "confirm": {"type": "plain_text", "text": "Approve"},
                        "deny":    {"type": "plain_text", "text": "Cancel"},
                    },
                },
                {
                    "type": "button",
                    "action_id": f"deny_access_{request_id}",
                    "text": {"type": "plain_text", "text": "✗  Deny"},
                    "style": "danger",
                    "value": request_id,
                },
            ],
        },
    ]


def access_approved_message(
    requester_id: str,
    app_name: str,
    access_level: str,
    approver_id: str,
    ts: str,
) -> list:
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "✅ Access Request — APPROVED"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"<@{requester_id}>'s request for *{access_level}* access to *{app_name}* "
                    f"was approved by <@{approver_id}> at {ts}.\n\n"
                    f"IT team: please provision access and notify the requester."
                ),
            },
        },
    ]


def access_denied_message(
    requester_id: str,
    app_name: str,
    denier_id: str,
    reason: str,
    ts: str,
) -> list:
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "❌ Access Request — DENIED"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"<@{requester_id}>'s request for access to *{app_name}* "
                    f"was denied by <@{denier_id}> at {ts}.\n\n"
                    f"*Reason:* {reason}"
                ),
            },
        },
    ]


def deny_reason_modal(request_id: str, original_ts: str, channel: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "deny_reason_modal",
        "private_metadata": f"{request_id}|{original_ts}|{channel}",
        "title": {"type": "plain_text", "text": "Deny Request"},
        "submit": {"type": "plain_text", "text": "Deny"},
        "close":  {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "reason_block",
                "label": {"type": "plain_text", "text": "Reason for denial"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "reason",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Explain why this request is being denied.",
                    },
                },
            }
        ],
    }


# ── Incident blocks ───────────────────────────────────────────────────────────

SEVERITY_EMOJI = {"P1": "🚨", "P2": "🔴", "P3": "🟡"}


def incident_modal(channel_id: str = "", thread_ts: str = "") -> dict:
    return {
        "type": "modal",
        "callback_id": "incident_modal",
        "private_metadata": f"{channel_id}|{thread_ts}",
        "title": {"type": "plain_text", "text": "Declare Incident"},
        "submit": {"type": "plain_text", "text": "Declare"},
        "close":  {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "title_block",
                "label": {"type": "plain_text", "text": "Incident Title"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "title",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g. Login service returning 500 errors",
                    },
                    "max_length": 120,
                },
            },
            {
                "type": "input",
                "block_id": "severity_block",
                "label": {"type": "plain_text", "text": "Severity"},
                "element": {
                    "type": "static_select",
                    "action_id": "severity",
                    "placeholder": {"type": "plain_text", "text": "Select severity"},
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "🚨 P1 — Complete outage / customer-facing"},
                            "value": "P1",
                        },
                        {
                            "text": {"type": "plain_text", "text": "🔴 P2 — Major degradation"},
                            "value": "P2",
                        },
                        {
                            "text": {"type": "plain_text", "text": "🟡 P3 — Minor / partial degradation"},
                            "value": "P3",
                        },
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "systems_block",
                "label": {"type": "plain_text", "text": "Affected Systems"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "systems",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g. Auth service, API gateway, EU region",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "description_block",
                "label": {"type": "plain_text", "text": "What's happening?"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "description",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Describe what you're observing, any errors, first noticed at...",
                    },
                },
            },
        ],
    }


def incident_channel_message(
    title: str,
    systems: str,
    severity: str,
    declarer_id: str,
    assessment: dict,
    conf_url: str | None = None,
) -> list:
    emoji        = SEVERITY_EMOJI.get(severity, "🚨")
    summary      = assessment.get("summary", "")
    actions      = assessment.get("immediate_actions", [])
    teams        = assessment.get("notify_teams", [])
    user_impact  = assessment.get("user_impact", "Unknown")
    scope        = assessment.get("estimated_scope", "Unknown")
    ts           = datetime.now().strftime("%I:%M %p")

    actions_text = "\n".join(f"{i+1}. {a}" for i, a in enumerate(actions))
    teams_text   = "  ·  ".join(f"`{t}`" for t in teams) if teams else "TBD"

    blks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} INCIDENT DECLARED — {severity} — {title}"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Summary*\n{summary}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Severity*\n{emoji} {severity}"},
                {"type": "mrkdwn", "text": f"*Affected Systems*\n{systems}"},
                {"type": "mrkdwn", "text": f"*User Impact*\n{user_impact}"},
                {"type": "mrkdwn", "text": f"*Estimated Scope*\n{scope}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Immediate Actions*\n{actions_text}"},
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Declared by <@{declarer_id}> at {ts}  ·  Notify: {teams_text}",
                }
            ],
        },
    ]

    if conf_url:
        blks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Incident Page →"},
                    "url": conf_url,
                    "style": "primary",
                }
            ],
        })

    return blks


def incident_confirmation(severity: str, title: str, conf_url: str | None = None) -> list:
    emoji = SEVERITY_EMOJI.get(severity, "🚨")
    conf_text = f"\n\n<{conf_url}|View incident page on Confluence>" if conf_url else ""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{emoji} *Incident declared: {title}*\n\n"
                    f"Severity: *{severity}*\n"
                    f"The team has been notified in `#incidents`."
                    f"{conf_text}"
                ),
            },
        }
    ]
