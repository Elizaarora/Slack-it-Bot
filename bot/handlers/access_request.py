import os
import json
import re
import uuid
import threading
from datetime import datetime
from slack_bolt import App
from bot.claude_ops import assess_access_risk
from bot import blocks
from bot.kv import get_kv
from bot.middleware.rate_limit import check_and_increment, rate_limit_blocks

APPROVALS_CHANNEL = os.getenv("IT_APPROVALS_CHANNEL", "#it-approvals")
IT_CHANNEL        = os.getenv("IT_REQUESTS_CHANNEL",  "#it-requests")

_TTL = 7 * 24 * 3600  # 7 days


def _save_pending(request_id: str, data: dict) -> None:
    get_kv().set(f"pending:{request_id}", json.dumps(data), ex=_TTL)


def _pop_pending(request_id: str) -> dict | None:
    kv  = get_kv()
    key = f"pending:{request_id}"
    raw = kv.get(key)
    if raw is None:
        return None
    kv.delete(key)
    return json.loads(raw)


def _peek_pending(request_id: str) -> dict | None:
    raw = get_kv().get(f"pending:{request_id}")
    return json.loads(raw) if raw else None


def register(app: App):

    @app.command("/accessrequest")
    def open_access_modal(ack, client, body):
        """Step 1: ack + open modal."""
        ack()
        client.views_open(
            trigger_id=body["trigger_id"],
            view=blocks.access_request_modal(
                channel_id=body.get("channel_id", ""),
                thread_ts=body.get("thread_ts", ""),
            ),
        )

    @app.view("access_request_modal")
    def handle_access_submission(ack, body, client, view):
        """Step 2: ack immediately, heavy work runs in background."""
        ack()

        requester_id = body["user"]["id"]
        meta = (view.get("private_metadata") or "").split("|", 1)
        invocation_channel = meta[0] or IT_CHANNEL
        invocation_thread  = meta[1] if len(meta) > 1 and meta[1] else None

        # Rate limit check (fast — does not block Slack)
        allowed, _ = check_and_increment(requester_id)
        if not allowed:
            client.chat_postEphemeral(
                channel=invocation_channel,
                user=requester_id,
                thread_ts=invocation_thread,
                blocks=rate_limit_blocks(),
                text="Daily limit reached.",
            )
            return

        vals          = view["state"]["values"]
        app_name      = vals["app_block"]["app_name"]["value"]
        access_level  = vals["level_block"]["access_level"]["selected_option"]["value"]
        justification = vals["justification_block"]["justification"]["value"]
        manager_name  = vals["manager_block"]["manager_name"]["value"]

        def process():
            # Claude risk assessment
            try:
                assessment = assess_access_risk(
                    app_name, access_level, justification, manager_name
                )
            except Exception:
                assessment = {
                    "risk_level": "Medium",
                    "risk_factors": ["AI assessment unavailable — manual review required"],
                    "recommendation": "Review",
                    "rationale": "Unable to complete automated risk assessment. Please review manually.",
                    "sox_sensitive": False,
                    "auto_approve": False,
                }

            request_id = str(uuid.uuid4())[:8]

            if assessment.get("auto_approve"):
                # Low-risk: auto-approve, notify IT + requester
                client.chat_postMessage(
                    channel=IT_CHANNEL,
                    text=(
                        f"✅ Auto-approved: <@{requester_id}> → *{access_level}* access "
                        f"to *{app_name}* (Low risk, justification verified)"
                    ),
                )
                client.chat_postMessage(
                    channel=requester_id,
                    text=(
                        f"✅ Your request for *{access_level}* access to *{app_name}* "
                        f"has been *auto-approved* (low risk). IT will provision shortly."
                    ),
                )
                return

            # Medium/High risk: post to #it-approvals with buttons
            result = client.chat_postMessage(
                channel=APPROVALS_CHANNEL,
                blocks=blocks.access_request_approval_message(
                    requester_id=requester_id,
                    app_name=app_name,
                    access_level=access_level,
                    justification=justification,
                    manager_name=manager_name,
                    assessment=assessment,
                    request_id=request_id,
                ),
                text=f"Access request from <@{requester_id}>: {access_level} on {app_name}",
            )

            # Persist pending request in Supabase (survives redeploys)
            _save_pending(request_id, {
                "requester_id": requester_id,
                "app_name":     app_name,
                "access_level": access_level,
                "channel":      APPROVALS_CHANNEL,
                "message_ts":   result["ts"],
            })

            # Notify requester
            client.chat_postMessage(
                channel=requester_id,
                text=(
                    f"🔄 Your request for *{access_level}* access to *{app_name}* "
                    f"has been sent to `#it-approvals` for review. "
                    f"You'll be notified when a decision is made."
                ),
            )

        threading.Thread(target=process, daemon=True).start()

    # ── Approve button ────────────────────────────────────────────────────────

    @app.action(re.compile(r"^approve_access_"))
    def handle_approve(ack, body, client, action):
        ack()
        request_id  = action["value"]
        approver_id = body["user"]["id"]
        ts_str      = datetime.now().strftime("%I:%M %p")

        pending = _pop_pending(request_id)
        if not pending:
            return

        client.chat_update(
            channel=pending["channel"],
            ts=pending["message_ts"],
            blocks=blocks.access_approved_message(
                requester_id=pending["requester_id"],
                app_name=pending["app_name"],
                access_level=pending["access_level"],
                approver_id=approver_id,
                ts=ts_str,
            ),
            text=f"Access approved by <@{approver_id}>",
        )

        client.chat_postMessage(
            channel=pending['requester_id'],
            text=(
                f"✅ Your request for *{pending['access_level']}* access to "
                f"*{pending['app_name']}* was *approved* by <@{approver_id}> "
                f"at {ts_str}. IT will provision your access shortly."
            ),
        )

    # ── Deny button → opens reason modal ─────────────────────────────────────

    @app.action(re.compile(r"^deny_access_"))
    def handle_deny_button(ack, client, body, action):
        ack()
        request_id = action["value"]
        pending    = _peek_pending(request_id)
        if not pending:
            return

        client.views_open(
            trigger_id=body["trigger_id"],
            view=blocks.deny_reason_modal(
                request_id=request_id,
                original_ts=pending["message_ts"],
                channel=pending["channel"],
            ),
        )

    # ── Deny reason modal submit ──────────────────────────────────────────────

    @app.view("deny_reason_modal")
    def handle_deny_submit(ack, body, client, view):
        ack()
        denier_id = body["user"]["id"]
        ts_str    = datetime.now().strftime("%I:%M %p")
        reason    = view["state"]["values"]["reason_block"]["reason"]["value"]

        # Parse metadata: request_id|message_ts|channel
        meta        = view.get("private_metadata", "||").split("|")
        request_id  = meta[0] if len(meta) > 0 else ""
        original_ts = meta[1] if len(meta) > 1 else ""
        channel     = meta[2] if len(meta) > 2 else APPROVALS_CHANNEL

        pending = _pop_pending(request_id)
        if not pending:
            return

        client.chat_update(
            channel=channel,
            ts=original_ts,
            blocks=blocks.access_denied_message(
                requester_id=pending["requester_id"],
                app_name=pending["app_name"],
                denier_id=denier_id,
                reason=reason,
                ts=ts_str,
            ),
            text=f"Access denied by <@{denier_id}>",
        )

        client.chat_postMessage(
            channel=pending['requester_id'],
            text=(
                f"❌ Your request for *{pending['access_level']}* access to "
                f"*{pending['app_name']}* was *denied* by <@{denier_id}>.\n"
                f"*Reason:* {reason}"
            ),
        )
