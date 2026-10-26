import os
import threading
from slack_bolt import App
from bot.claude_ops import triage_request
from bot.jira_ops import create_ticket
from bot.confluence_ops import search_and_format_for_prompt, create_incident_page
from bot.kb import fetch_knowledge_base, format_kb_for_prompt
from bot import blocks
from bot.middleware.rate_limit import check_and_increment, get_remaining, rate_limit_blocks

IT_CHANNEL = os.getenv("IT_REQUESTS_CHANNEL", "#it-requests")


def register(app: App):

    @app.command("/itrequest")
    def open_it_modal(ack, client, body):
        """Step 1: Immediately ack + open modal."""
        ack()
        client.views_open(
            trigger_id=body["trigger_id"],
            view=blocks.it_request_modal(
                channel_id=body.get("channel_id", ""),
                thread_ts=body.get("thread_ts", ""),
            ),
        )

    @app.view("it_request_modal")
    def handle_it_submission(ack, body, client, view):
        """Step 2: ack() immediately closes modal, heavy work runs in background."""
        ack()

        submitter_id   = body["user"]["id"]
        submitter_name = body["user"]["name"]
        meta = (view.get("private_metadata") or "").split("|", 1)
        invocation_channel = meta[0] or IT_CHANNEL
        invocation_thread  = meta[1] if len(meta) > 1 and meta[1] else None

        # Rate limit check (fast — Redis read, does not block Slack)
        allowed, _ = check_and_increment(submitter_id)
        if not allowed:
            client.chat_postEphemeral(
                channel=invocation_channel,
                user=submitter_id,
                thread_ts=invocation_thread,
                blocks=rate_limit_blocks(),
                text="Daily limit reached.",
            )
            return

        vals        = view["state"]["values"]
        subject     = vals["subject_block"]["subject"]["value"]
        description = vals["description_block"]["description"]["value"]
        urgency     = vals["urgency_block"]["urgency"]["selected_option"]["value"]
        department  = vals["department_block"]["department"]["selected_option"]["value"]

        def process():
            # Fetch Supabase KB articles
            kb_articles = fetch_knowledge_base()
            supabase_kb_block = format_kb_for_prompt(kb_articles)

            # Search Confluence and fetch page content
            conf_articles, confluence_kb_block = search_and_format_for_prompt(
                f"{subject} {department}"
            )

            # Combine both KB sources for the prompt
            combined_kb = "\n\n".join(filter(None, [supabase_kb_block, confluence_kb_block]))

            # Claude triage (with combined KB context)
            try:
                triage = triage_request(subject, description, urgency, department, combined_kb)
            except Exception:
                triage = {
                    "category": "Other",
                    "priority": "P3 - Medium",
                    "sla_hours": 24,
                    "owner": "IT Support (Tier 1)",
                    "suggested_action": "Review manually — AI triage unavailable.",
                    "auto_resolvable": False,
                    "tags": [],
                    "kb_id": None,
                    "resolution": None,
                    "auto_close": False,
                }

            # Jira ticket
            jira = create_ticket(subject, description, department, submitter_name, triage)
            jira_url = jira["url"] if jira else None

            # conf_articles already fetched above for the prompt

            # Confluence: incident page for P1/P2
            incident_page_url = None
            if triage.get("priority", "").startswith(("P1", "P2")):
                page = create_incident_page(
                    title=subject,
                    description=description,
                    assessment={
                        "summary": triage.get("suggested_action", ""),
                        "immediate_actions": [triage.get("suggested_action", "")],
                        "notify_teams": [triage.get("owner", "IT")],
                        "user_impact": f"{department} department — {urgency} urgency",
                        "estimated_scope": triage.get("category", "Unknown"),
                    },
                    submitter=submitter_name,
                )
                incident_page_url = page["url"] if page else None

            # Auto-close: DM user the KB resolution directly
            if triage.get("auto_close") and triage.get("resolution"):
                client.chat_postMessage(
                    channel=submitter_id,
                    text=(
                        f"✅ *Your IT request has been automatically resolved.*\n\n"
                        f"*Issue:* {subject}\n\n"
                        f"*Resolution:*\n{triage['resolution']}\n\n"
                        f"_Reply here or submit a new request if this didn't resolve your issue._"
                    ),
                )

            # Post to #it-requests (always, so IT team has visibility)
            client.chat_postMessage(
                channel=IT_CHANNEL,
                blocks=blocks.it_request_channel_message(
                    subject=subject,
                    description=description,
                    department=department,
                    submitter_id=submitter_id,
                    triage=triage,
                    jira_url=jira_url,
                    kb_articles=conf_articles,
                    incident_page_url=incident_page_url,
                ),
                text=f"New IT Request from <@{submitter_id}>: {subject}",
            )

            # Ephemeral confirmation to submitter (in the channel/thread they invoked from)
            client.chat_postEphemeral(
                channel=invocation_channel,
                user=submitter_id,
                thread_ts=invocation_thread,
                blocks=blocks.it_request_user_confirmation(
                    priority=triage["priority"],
                    sla_hours=triage["sla_hours"],
                    category=triage["category"],
                    remaining=get_remaining(submitter_id),
                    auto_closed=triage.get("auto_close", False),
                ),
                text=f"Your IT request has been logged. Priority: {triage['priority']}",
            )

        threading.Thread(target=process, daemon=True).start()
