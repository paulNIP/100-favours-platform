"""Telegram message templates (parse_mode=HTML) with {placeholder} variables.

Values are HTML-escaped on render, so callers pass plain text and can't break the
markup (or inject tags) with characters like < > & in their data.
"""

import html
from string import Formatter

TEMPLATES: dict[str, str] = {
    "welcome": """\
👋 <b>Welcome, {first_name}!</b>

Thanks for joining <b>{channel_name}</b>. Here's how to get started:

1️⃣ Read the pinned message for the rules
2️⃣ Use /help to see available commands
3️⃣ Turn on notifications so you don't miss updates 🔔

Questions? Just reply here.""",
    "announcement": """\
📢 <b>ANNOUNCEMENT</b>

<b>{headline}</b>

{short_description}

🗓 <b>Date:</b> {date}
⏰ <b>Time:</b> {time} ({timezone})
📍 <b>Where:</b> {location_or_link}

👉 <a href="{link}">Learn more</a>""",
    "trading_signal": """\
🚨 <b>{symbol} ALERT</b> — {timeframe}

📈 <b>Direction:</b> {direction}
💰 <b>Entry:</b> <code>{entry_price}</code>
🎯 <b>TP1:</b> <code>{tp1}</code>
🎯 <b>TP2:</b> <code>{tp2}</code>
🛑 <b>Stop loss:</b> <code>{sl}</code>
⚖️ <b>Risk:reward:</b> {rr}

📊 <i>Reason:</i> {setup_notes}

⚠️ <i>Not financial advice. Manage your risk.</i>""",
    "trade_update": """\
✅ <b>{symbol} — TP1 HIT</b>

Entry: <code>{entry}</code> → Exit: <code>{exit}</code>
Result: <b>+{pct}%</b>

🔒 Move stop to breakeven on the rest of the position.""",
    "daily_report": """\
📊 <b>Daily Report — {date}</b>

• Total: <b>{total}</b>
• Wins: {wins} ✅ | Losses: {losses} ❌
• Win rate: <b>{win_rate}%</b>
• Net: <b>{net_pnl}</b>

<blockquote>{comment_of_the_day}</blockquote>""",
    "order_confirmation": """\
🧾 <b>Order Confirmed</b>

Order #: <code>{order_id}</code>
Item: {item_name} × {qty}
Total: <b>{currency}{amount}</b>

📦 Estimated delivery: {delivery_date}
Track it: <a href="{tracking_url}">here</a>

Thank you for your purchase, {first_name}! 🙏""",
    "reminder": """\
⏰ <b>Reminder</b>

Hi {first_name}, just a reminder that <b>{event}</b> starts in <b>{time_until}</b>.

🔗 Join: {link}""",
    "service_down": """\
🔴 <b>SERVICE DOWN</b>

<b>Service:</b> {service_name}
<b>Status:</b> {status_code}
<b>Detected:</b> {timestamp}

<pre>{error_message}</pre>

🟢 A follow-up message will be sent when the service recovers.""",
    "help": """\
🤖 <b>Available commands</b>

/start — Start the bot
/status — Check current status
/subscribe — Get alerts
/unsubscribe — Stop alerts
/help — Show this message""",
    "quiz": """\
🧠 <b>Quiz time!</b>

{question}

Answer: <tg-spoiler>{answer}</tg-spoiler>""",
}


class TemplateError(Exception):
    pass


def fields(name: str) -> list[str]:
    """Placeholder names in the order they first appear."""
    names = (f for _, f, _, _ in Formatter().parse(TEMPLATES[name]) if f)
    return list(dict.fromkeys(names))


def render(name: str, variables: dict[str, object]) -> str:
    expected = set(fields(name))
    if missing := expected - variables.keys():
        raise TemplateError(f"missing variables: {', '.join(sorted(missing))}")
    # Unknown keys are almost always typos that would silently drop data.
    if unknown := variables.keys() - expected:
        raise TemplateError(f"unknown variables: {', '.join(sorted(unknown))}")
    return TEMPLATES[name].format_map({k: html.escape(str(v)) for k, v in variables.items()})
