"""Core send engine — AppleScript iMessage/SMS, throttling, personalization, queueing."""

import subprocess
import random
import time
import uuid
from datetime import datetime, date, timedelta

import config


def normalize_phone(phone: str) -> str:
    """Strip a phone number to digits, ensure US +1 prefix."""
    if not phone:
        return ""
    digits = "".join(c for c in str(phone) if c.isdigit())
    if len(digits) == 10:
        digits = "1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return ""  # invalid


def send_group_imessage(phones: list[str], message: str) -> tuple[bool, str]:
    """Send a group iMessage to multiple recipients via macOS Messages app.

    Creates a new group chat with all recipients and sends the message.
    Returns (success, error_message).
    """
    if not phones or not message:
        return False, "phones and message required"

    escaped = message.replace("\\", "\\\\").replace('"', '\\"')

    # Build the list of buddy references
    buddy_lines = []
    for i, phone in enumerate(phones):
        buddy_lines.append(f'set buddy{i} to participant "{phone}" of targetService')

    buddies_setup = "\n        ".join(buddy_lines)
    buddy_refs = ", ".join(f"buddy{i}" for i in range(len(phones)))

    applescript = f'''
    tell application "Messages"
        set targetService to 1st account whose service type = iMessage
        {buddies_setup}
        set groupChat to make new text chat with properties {{participants: {{{buddy_refs}}}}}
        send "{escaped}" to groupChat
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "AppleScript timed out"
    except Exception as e:
        return False, str(e)


def send_imessage(phone: str, message: str) -> tuple[bool, str]:
    """Send a message via macOS Messages app using AppleScript.

    Returns (success, error_message).
    """
    escaped = message.replace("\\", "\\\\").replace('"', '\\"')
    applescript = f'''
    tell application "Messages"
        set targetService to 1st account whose service type = iMessage
        set targetBuddy to participant "{phone}" of targetService
        send "{escaped}" to targetBuddy
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "AppleScript timed out"
    except Exception as e:
        return False, str(e)


def personalize(template: str, contact: dict) -> str:
    """Replace {placeholders} with contact data."""
    msg = template
    for key, value in contact.items():
        msg = msg.replace("{" + str(key) + "}", str(value) if value else "")
    return msg.strip()


def is_within_send_hours() -> bool:
    """Check if current time is within allowed sending window."""
    hour = datetime.now().hour
    return config.SEND_HOUR_START <= hour < config.SEND_HOUR_END


def get_delay() -> float:
    """Return a randomized delay between messages."""
    return random.uniform(config.DELAY_MIN, config.DELAY_MAX)


# ── Queue system ─────────────────────────────────────────────────

def queue_send(contacts: list[dict], template_id: int, start_date: date = None) -> dict:
    """Queue contacts for sending, spread across multiple days.

    Returns summary: {batch_id, total, days, schedule}
    """
    from models.database import execute

    batch_id = str(uuid.uuid4())[:8]
    total = len(contacts)
    daily_cap = config.DAILY_CAP
    today = start_date or date.today()

    schedule = []  # list of {date, count}
    day_offset = 0

    for i, contact in enumerate(contacts):
        # Which day does this contact land on?
        day_index = i // daily_cap
        send_date = today + timedelta(days=day_index)

        execute(
            """INSERT INTO send_queue
               (contact_id, template_id, scheduled_date, batch_id)
               VALUES (%s, %s, %s, %s)""",
            (contact["id"], template_id, send_date.isoformat(), batch_id),
        )

        # Track schedule summary
        if day_index >= len(schedule):
            schedule.append({"date": send_date.isoformat(), "count": 0})
        schedule[day_index]["count"] += 1

    return {
        "batch_id": batch_id,
        "total": total,
        "days": len(schedule),
        "daily_cap": daily_cap,
        "schedule": schedule,
    }


def get_todays_queue():
    """Get pending queue items scheduled for today."""
    from models.database import query
    today = date.today().isoformat()
    return query(
        """SELECT sq.*, c.first_name, c.last_name, c.phone, c.email,
                  c.city, c.state, c.street_address, c.zip, c.source,
                  c.status as contact_status, c.own_or_rent
           FROM send_queue sq
           JOIN contacts c ON sq.contact_id = c.id
           WHERE sq.scheduled_date = %s AND sq.status = 'pending'
           ORDER BY sq.id""",
        (today,),
    )


def get_queue_summary():
    """Get summary of all pending queue items grouped by date."""
    from models.database import query
    return query(
        """SELECT scheduled_date, batch_id, COUNT(*) as count,
                  SUM(status='pending') as pending,
                  SUM(status='sent') as sent,
                  SUM(status='failed') as failed,
                  SUM(status='skipped') as skipped
           FROM send_queue
           WHERE scheduled_date >= CURDATE()
           GROUP BY scheduled_date, batch_id
           ORDER BY scheduled_date"""
    )


def get_sent_today_count():
    """How many messages have already been sent today?"""
    from models.database import query
    today = date.today().isoformat()
    result = query(
        """SELECT COUNT(*) as c FROM send_history
           WHERE DATE(sent_at) = %s AND status = 'sent'""",
        (today,),
    )
    return result[0]["c"]


def process_todays_batch(dry_run=False, force=False, progress_callback=None):
    """Process today's queued messages, respecting the daily cap.

    Returns list of result dicts.
    """
    from models.database import execute, query

    already_sent = get_sent_today_count()
    remaining_cap = max(0, config.DAILY_CAP - already_sent)

    if remaining_cap == 0:
        return []

    queue_items = get_todays_queue()
    if not queue_items:
        return []

    # Get template body for each unique template_id
    template_cache = {}
    for item in queue_items:
        tid = item["template_id"]
        if tid not in template_cache:
            tpl = query("SELECT body FROM outreach_templates WHERE id=%s", (tid,))
            template_cache[tid] = tpl[0]["body"] if tpl else ""

    results = []
    to_process = queue_items[:remaining_cap]
    total = len(to_process)

    for i, item in enumerate(to_process):
        template_body = template_cache.get(item["template_id"], "")
        phone = normalize_phone(item.get("phone", ""))

        # Build a contact dict for personalization
        contact = {
            "id": item["contact_id"],
            "first_name": item.get("first_name", ""),
            "last_name": item.get("last_name", ""),
            "phone": item.get("phone", ""),
            "email": item.get("email", ""),
            "city": item.get("city", ""),
            "state": item.get("state", ""),
            "street_address": item.get("street_address", ""),
            "zip": item.get("zip", ""),
            "source": item.get("source", ""),
            "own_or_rent": item.get("own_or_rent", ""),
        }

        message = personalize(template_body, contact)
        contact_name = f"{contact['first_name']} {contact['last_name']}".strip()

        if not is_within_send_hours() and not dry_run and not force:
            status = "skipped"
            error = "Outside sending hours"
        elif not phone:
            status = "skipped"
            error = "Invalid or missing phone number"
        elif dry_run:
            status = "dry_run"
            error = ""
        else:
            success, error = send_imessage(phone, message)
            status = "sent" if success else "failed"

        # Update queue item
        queue_status = "sent" if status in ("sent", "dry_run") else status
        execute(
            "UPDATE send_queue SET status=%s, error_message=%s, sent_at=NOW() WHERE id=%s",
            (queue_status, error, item["id"]),
        )

        # Log to send_history
        execute(
            """INSERT INTO send_history
               (contact_id, contact_name, phone, template_id, message_text, status, error_message)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (contact["id"], contact_name, contact.get("phone", ""),
             item["template_id"], message, status, error),
        )

        result = {
            "index": i + 1,
            "contact": contact,
            "status": status,
            "error": error,
            "message": message,
        }
        results.append(result)

        if progress_callback:
            progress_callback(i + 1, total, contact, status, message)

        # Throttle between sends
        if i < total - 1 and not dry_run and status == "sent":
            time.sleep(get_delay())

    return results


def cancel_batch(batch_id: str) -> int:
    """Cancel all pending items in a batch. Returns count cancelled."""
    from models.database import execute, query
    count = query(
        "SELECT COUNT(*) as c FROM send_queue WHERE batch_id=%s AND status='pending'",
        (batch_id,),
    )[0]["c"]
    execute(
        "UPDATE send_queue SET status='cancelled' WHERE batch_id=%s AND status='pending'",
        (batch_id,),
    )
    return count
