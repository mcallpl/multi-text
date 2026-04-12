"""Bridge between PropertyTourPics (GoDaddy) and MultiText (local Mac).

Polls the text_queue table on GoDaddy for pending messages and sends
them via iMessage. Syncs contacts from propertypulse to GoDaddy's
contacts_cache table so the PropertyTourPics contact search works.
"""

import json
import time
import threading
import urllib.request
import urllib.error

from sender.engine import send_imessage, normalize_phone
from models.database import query

PTP_BASE = "https://peoplestar.com/PropertyTourPics/api"
API_KEY = "ptp-mt-bridge-d4c3621a54464a20211be5bfec8d9ad9"

POLL_INTERVAL = 15       # seconds between queue checks
SYNC_INTERVAL = 300      # seconds between contact syncs (5 min)


def _headers():
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def _request(url, data=None):
    """Make an HTTPS request to GoDaddy."""
    req = urllib.request.Request(url, headers=_headers())
    if data is not None:
        req.data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [bridge] Request failed: {url} — {e}")
        return None


def poll_text_queue():
    """Fetch pending messages from GoDaddy and send via iMessage."""
    result = _request(f"{PTP_BASE}/poll-queue.php?action=fetch")
    if not result or result.get("status") != "success":
        return

    items = result.get("items", [])
    if not items:
        return

    print(f"  [bridge] {len(items)} pending text(s) to send")

    for item in items:
        phone = normalize_phone(item["phone"])
        message = item["message"]
        item_id = item["id"]

        if not phone:
            _request(f"{PTP_BASE}/poll-queue.php?action=update",
                     {"id": item_id, "status": "failed", "error_message": "Invalid phone number"})
            print(f"  [bridge] #{item_id} — invalid phone: {item['phone']}")
            continue

        print(f"  [bridge] #{item_id} — sending to {phone}...")
        success, err = send_imessage(phone, message)

        if success:
            _request(f"{PTP_BASE}/poll-queue.php?action=update",
                     {"id": item_id, "status": "sent", "error_message": ""})
            print(f"  [bridge] #{item_id} — sent!")
        else:
            _request(f"{PTP_BASE}/poll-queue.php?action=update",
                     {"id": item_id, "status": "failed", "error_message": err})
            print(f"  [bridge] #{item_id} — failed: {err}")

        time.sleep(2)  # Small delay between sends


def sync_contacts():
    """Sync contacts from propertypulse DB to GoDaddy contacts_cache."""
    try:
        rows = query(
            """SELECT id, first_name, last_name, phone, city, status
               FROM contacts
               WHERE phone IS NOT NULL AND phone != ''
               ORDER BY id""",
        )
    except Exception as e:
        print(f"  [bridge] Contact sync — DB query failed: {e}")
        return

    if not rows:
        print("  [bridge] Contact sync — no contacts found")
        return

    # Send in batches of 200
    batch_size = 200
    total_synced = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        result = _request(f"{PTP_BASE}/sync-contacts.php", {"contacts": batch})
        if result and result.get("status") == "success":
            total_synced += result.get("synced", 0)

    print(f"  [bridge] Synced {total_synced} contacts to GoDaddy")


def _poll_loop():
    """Background loop: poll queue every POLL_INTERVAL seconds."""
    while True:
        try:
            poll_text_queue()
        except Exception as e:
            print(f"  [bridge] Poll error: {e}")
        time.sleep(POLL_INTERVAL)


def _sync_loop():
    """Background loop: sync contacts every SYNC_INTERVAL seconds."""
    # Initial sync on startup
    time.sleep(5)
    sync_contacts()

    while True:
        time.sleep(SYNC_INTERVAL)
        try:
            sync_contacts()
        except Exception as e:
            print(f"  [bridge] Sync error: {e}")


def start_bridge():
    """Start background threads for polling and syncing."""
    poll_thread = threading.Thread(target=_poll_loop, daemon=True)
    poll_thread.start()
    print("  [bridge] Queue poller started (every 15s)")

    sync_thread = threading.Thread(target=_sync_loop, daemon=True)
    sync_thread.start()
    print("  [bridge] Contact syncer started (every 5m)")
