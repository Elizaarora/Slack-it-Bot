import os
import threading
from slack_bolt import App
from bot.claude_ops import assess_incident
from bot.confluence_ops import create_incident_page
from bot import blocks

INCIDENTS_CHANNEL = os.getenv("INCIDENTS_CHANNEL", "#incidents")


def register(app: App):

    @app.command("/incident")
    def open_incident_modal(ack, client, body):
        """Step 1: ack + open modal."""
        ack()
        client.views_open(
            trigger_id=body["trigger_id"],
            view=blocks.incident_modal(
                channel_id=body.get("channel_id", ""),
                thread_ts=body.get("thread_ts", ""),
            ),
        )

    @app.view("incident_modal")
    def handle_incident_submission(ack, body, client, view):
        """Step 2: ack immediately, heavy work runs in background."""
        ack()

        declarer_id   = body["user"]["id"]
        declarer_name = body["user"]["name"]
        meta = (view.get("private_metadata") or "").split("|", 1)
        invocation_channel = meta[0] or INCIDENTS_CHANNEL
        invocation_thread  = meta[1] if len(meta) > 1 and meta[1] else None

        vals        = view["state"]["values"]
        title       = vals["title_block"]["title"]["value"]
        severity    = vals["severity_block"]["severity"]["selected_option"]["value"]
        systems     = vals["systems_block"]["systems"]["value"]
        description = vals["description_block"]["description"]["value"]

        def process():
            try:
                assessment = assess_incident(title, systems, description, severity)
            except Exception:
                assessment = {
                    "summary": "AI assessment unavailable — review manually.",
                    "immediate_actions": [
                        "Identify the root cause",
                        "Check logs and monitoring dashboards",
                        "Notify relevant team leads",
                    ],
                    "notify_teams": ["Engineering", "IT"],
                    "user_impact": "Unknown — assess manually",
                    "estimated_scope": "Unknown",
                }

            conf_page = create_incident_page(
                title=title,
                description=description,
                assessment=assessment,
                submitter=declarer_name,
            )
            conf_url = conf_page["url"] if conf_page else None

            client.chat_postMessage(
                channel=INCIDENTS_CHANNEL,
                blocks=blocks.incident_channel_message(
                    title=title,
                    systems=systems,
                    severity=severity,
                    declarer_id=declarer_id,
                    assessment=assessment,
                    conf_url=conf_url,
                ),
                text=f"{severity} Incident declared by <@{declarer_id}>: {title}",
            )

            client.chat_postEphemeral(
                channel=invocation_channel,
                user=declarer_id,
                thread_ts=invocation_thread,
                blocks=blocks.incident_confirmation(
                    severity=severity,
                    title=title,
                    conf_url=conf_url,
                ),
                text=f"Incident declared: {title}",
            )

        threading.Thread(target=process, daemon=True).start()
