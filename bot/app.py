import os
from slack_bolt import App
from dotenv import load_dotenv

load_dotenv()


def create_bolt_app() -> App:
    app = App(
        token=os.environ["SLACK_BOT_TOKEN"],
        signing_secret=os.environ["SLACK_SIGNING_SECRET"],
        process_before_response=True,  # CRITICAL: allows ack() before heavy work
        token_verification_enabled=False,  # skip auth.test on cold start (Vercel)
    )

    from bot.handlers.it_request import register as register_it
    from bot.handlers.access_request import register as register_access
    from bot.handlers.incident import register as register_incident

    register_it(app)
    register_access(app)
    register_incident(app)

    return app
