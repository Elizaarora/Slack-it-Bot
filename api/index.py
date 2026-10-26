import sys
import os
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, request

flask_app = Flask(__name__)

_bolt_handler = None
_init_error: str | None = None


def _get_handler():
    """Lazy-initialize the Bolt app on the first Slack request.

    Avoids calling auth.test at module-import time, which would block every
    cold start (Vercel doesn't allow outbound network calls during module init
    in the same synchronous context as the build/deploy phase).
    """
    global _bolt_handler, _init_error
    if _bolt_handler is None and _init_error is None:
        try:
            from slack_bolt.adapter.flask import SlackRequestHandler
            from bot.app import create_bolt_app
            _bolt_handler = SlackRequestHandler(create_bolt_app())
        except Exception:
            _init_error = traceback.format_exc()
    if _init_error:
        raise RuntimeError(_init_error)
    return _bolt_handler


@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return _get_handler().handle(request)


@flask_app.route("/slack/actions", methods=["POST"])
def slack_actions():
    return _get_handler().handle(request)


@flask_app.route("/health", methods=["GET"])
def health():
    try:
        _get_handler()
        return {"status": "ok", "bot": "IT Ops Bot"}, 200
    except Exception as e:
        return {"status": "error", "detail": str(e)}, 500


# Vercel entry point
app = flask_app
