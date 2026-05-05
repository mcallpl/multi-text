#!/usr/bin/env python3
"""Standalone bridge runner — polls PropertyTourPics and sends via iMessage.

Run this independently of the Flask app:
    cd ~/Projects/multitext && source venv/bin/activate && python run_bridge.py
"""

import sys
import time
import json
import requests
import hashlib

sys.path.insert(0, '/Users/chipmcallister/Projects/multitext')

from sender.engine import send_imessage, send_group_imessage, normalize_phone

POLL_INTERVAL = 15
PROPERTYTOURPICS_URL = "https://peoplestar.com/PropertyTourPics"

# Compute the MULTITEXT_API_KEY same way PropertyTourPics does
# Key is: 'ptp-mt-bridge-' + md5(DB_PASS + 'propertytourpics')
# We hardcode the DB_PASS from the vault for now
DB_PASS = "amazing123"
MULTITEXT_API_KEY = "ptp-mt-bridge-" + hashlib.md5((DB_PASS + "propertytourpics").encode()).hexdigest()


def poll_text_queue():
    try:
        # Fetch pending messages from PropertyTourPics
        resp = requests.get(
            f"{PROPERTYTOURPICS_URL}/api/poll-queue.php?action=fetch",
            headers={"Authorization": f"Bearer {MULTITEXT_API_KEY}"},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "success":
            print(f"[bridge] Error fetching from PropertyTourPics: {data.get('message')}", flush=True)
            return

        items = data.get("items", [])
        if not items:
            return

        print(f"[bridge] {len(items)} pending text(s) from PropertyTourPics", flush=True)

        for item in items:
            phone = normalize_phone(item["phone"])
            item_id = item["id"]

            if not phone:
                update_ptp_message(item_id, "failed", "Invalid phone number")
                print(f"[bridge] #{item_id} — invalid phone: {item['phone']}", flush=True)
                continue

            print(f"[bridge] #{item_id} — sending to {phone}...", flush=True)
            success, err = send_imessage(phone, item["message"])

            if success:
                update_ptp_message(item_id, "sent", "")
                print(f"[bridge] #{item_id} — sent!", flush=True)
            else:
                update_ptp_message(item_id, "failed", err)
                print(f"[bridge] #{item_id} — failed: {err}", flush=True)

            time.sleep(2)

    except Exception as e:
        print(f"[bridge] Error polling PropertyTourPics: {e}", flush=True)


def update_ptp_message(msg_id, status, error_msg):
    """Update message status in PropertyTourPics database via API."""
    try:
        requests.post(
            f"{PROPERTYTOURPICS_URL}/api/poll-queue.php?action=update",
            headers={
                "Authorization": f"Bearer {MULTITEXT_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "id": msg_id,
                "status": status,
                "error_message": error_msg
            },
            timeout=10
        )
    except Exception as e:
        print(f"[bridge] Error updating message {msg_id}: {e}", flush=True)


def poll_group_text_queue():
    # Group texts are still stored locally in MultiText's own DB for now
    # (not yet integrated with PropertyTourPics)
    try:
        from models.database import query, execute
        items = query(
            "SELECT id, phones, message FROM group_text_queue WHERE status = 'pending' ORDER BY id LIMIT 10"
        )
        if not items:
            return

        print(f"[bridge] {len(items)} pending group text(s)", flush=True)

        for item in items:
            raw_phones = item.get("phones") or []
            if isinstance(raw_phones, str):
                try:
                    raw_phones = json.loads(raw_phones)
                except Exception:
                    raw_phones = []
            phones = [normalize_phone(p) for p in raw_phones if normalize_phone(p)]
            item_id = item["id"]

            if len(phones) < 2:
                execute("UPDATE group_text_queue SET status='failed', error_message=%s WHERE id=%s",
                        ("Need 2+ valid phone numbers", item_id))
                continue

            execute("UPDATE group_text_queue SET status='sending' WHERE id=%s", (item_id,))
            success, err = send_group_imessage(phones, item["message"])

            if success:
                execute("UPDATE group_text_queue SET status='sent', sent_at=NOW() WHERE id=%s", (item_id,))
                print(f"[bridge] group #{item_id} — sent!", flush=True)
            else:
                execute("UPDATE group_text_queue SET status='failed', error_message=%s WHERE id=%s",
                        (err, item_id))
                print(f"[bridge] group #{item_id} — failed: {err}", flush=True)

            time.sleep(2)
    except Exception as e:
        print(f"[bridge] Error polling group texts: {e}", flush=True)


if __name__ == "__main__":
    print(f"[bridge] Starting — polling DigitalOcean MySQL every {POLL_INTERVAL}s", flush=True)
    while True:
        try:
            poll_text_queue()
            poll_group_text_queue()
        except Exception as e:
            print(f"[bridge] Error: {e}", flush=True)
        time.sleep(POLL_INTERVAL)
