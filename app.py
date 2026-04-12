"""MultiText — Flask app for personalized iMessage/SMS outreach."""

import csv
import io
import json
import queue
import threading
from datetime import date

from flask import (Flask, Response, jsonify, redirect, render_template,
                   request, stream_with_context, url_for)

import config
from models.database import execute, query, shutdown
from sender.engine import (cancel_batch, get_queue_summary, get_sent_today_count,
                           get_todays_queue, is_within_send_hours, normalize_phone,
                           personalize, process_todays_batch, queue_send,
                           send_imessage)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY


# ── Dashboard ────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    stats = {}
    stats["total_contacts"] = query(
        "SELECT COUNT(*) as c FROM contacts WHERE status='active'"
    )[0]["c"]
    stats["total_templates"] = query(
        "SELECT COUNT(*) as c FROM outreach_templates"
    )[0]["c"]
    stats["sent_today"] = get_sent_today_count()
    stats["daily_cap"] = config.DAILY_CAP
    stats["sent_week"] = query(
        "SELECT COUNT(*) as c FROM send_history WHERE sent_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) AND status='sent'"
    )[0]["c"]
    stats["sent_month"] = query(
        "SELECT COUNT(*) as c FROM send_history WHERE sent_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) AND status='sent'"
    )[0]["c"]
    last_run = query(
        "SELECT sent_at FROM send_history WHERE status='sent' ORDER BY sent_at DESC LIMIT 1"
    )
    stats["last_run"] = last_run[0]["sent_at"].strftime("%b %d, %Y %I:%M %p") if last_run else "Never"
    stats["within_hours"] = is_within_send_hours()

    # Queue info
    todays_pending = len(get_todays_queue())
    stats["todays_pending"] = todays_pending
    queue_summary = get_queue_summary()
    stats["queue_days"] = len(queue_summary)
    stats["queue_total"] = sum(int(q["pending"] or 0) for q in queue_summary)

    return render_template("dashboard.html", stats=stats, queue=queue_summary,
                           send_hours=(config.SEND_HOUR_START, config.SEND_HOUR_END))


# ── Templates CRUD ───────────────────────────────────────────────

@app.route("/templates")
def templates_page():
    templates = query("SELECT * FROM outreach_templates ORDER BY updated_at DESC")
    placeholders = query("SHOW COLUMNS FROM contacts")
    placeholder_names = [p["Field"] for p in placeholders]
    return render_template("templates.html", templates=templates,
                           placeholders=placeholder_names)


@app.route("/templates/create", methods=["POST"])
def template_create():
    name = request.form.get("name", "").strip()
    body = request.form.get("body", "").strip()
    if name and body:
        execute("INSERT INTO outreach_templates (name, body) VALUES (%s, %s)",
                (name, body))
    return redirect(url_for("templates_page"))


@app.route("/templates/<int:tid>/update", methods=["POST"])
def template_update(tid):
    name = request.form.get("name", "").strip()
    body = request.form.get("body", "").strip()
    if name and body:
        execute("UPDATE outreach_templates SET name=%s, body=%s WHERE id=%s",
                (name, body, tid))
    return redirect(url_for("templates_page"))


@app.route("/templates/<int:tid>/delete", methods=["POST"])
def template_delete(tid):
    execute("DELETE FROM outreach_templates WHERE id=%s", (tid,))
    return redirect(url_for("templates_page"))


@app.route("/api/templates/<int:tid>/preview")
def template_preview(tid):
    tpl = query("SELECT * FROM outreach_templates WHERE id=%s", (tid,))[0]
    contact = query("SELECT * FROM contacts WHERE status='active' AND phone IS NOT NULL LIMIT 1")
    if contact:
        preview = personalize(tpl["body"], contact[0])
        return jsonify({"preview": preview, "contact": f"{contact[0]['first_name']} {contact[0]['last_name']}"})
    return jsonify({"preview": tpl["body"], "contact": "No contacts found"})


# ── Send (Queue-based) ──────────────────────────────────────────

@app.route("/send")
def send_page():
    templates = query("SELECT id, name, body FROM outreach_templates ORDER BY name")
    statuses = query("SELECT DISTINCT status FROM contacts ORDER BY status")
    cities = query("SELECT DISTINCT city FROM contacts WHERE city IS NOT NULL ORDER BY city")
    sources = query("SELECT DISTINCT source FROM contacts WHERE source IS NOT NULL ORDER BY source")
    placeholders = query("SHOW COLUMNS FROM contacts")
    placeholder_names = [p["Field"] for p in placeholders]
    return render_template("send.html", templates=templates,
                           statuses=[s["status"] for s in statuses],
                           cities=[c["city"] for c in cities],
                           sources=[s["source"] for s in sources],
                           placeholders=placeholder_names,
                           daily_cap=config.DAILY_CAP)


@app.route("/api/send/preview", methods=["POST"])
def send_preview():
    data = request.json
    where_clauses = ["phone IS NOT NULL", "phone != ''"]
    params = []

    if data.get("status"):
        where_clauses.append("status = %s")
        params.append(data["status"])
    if data.get("city"):
        where_clauses.append("city = %s")
        params.append(data["city"])
    if data.get("source"):
        where_clauses.append("source = %s")
        params.append(data["source"])

    # Cooldown: skip contacts who received this template recently
    if data.get("template_id"):
        where_clauses.append(f"""id NOT IN (
            SELECT contact_id FROM send_history
            WHERE template_id = %s
            AND status = 'sent'
            AND sent_at >= DATE_SUB(NOW(), INTERVAL {int(config.COOLDOWN_DAYS)} DAY)
        )""")
        params.append(data["template_id"])

        # Also exclude contacts already in the queue for this template
        where_clauses.append("""id NOT IN (
            SELECT contact_id FROM send_queue
            WHERE template_id = %s AND status = 'pending'
        )""")
        params.append(data["template_id"])

    where = " AND ".join(where_clauses)
    sql = f"SELECT id, first_name, last_name, phone, city, status FROM contacts WHERE {where} ORDER BY last_name LIMIT 500"
    contacts = query(sql, tuple(params))

    # Show how many days this will take
    days_needed = max(1, -(-len(contacts) // config.DAILY_CAP))  # ceiling division

    return jsonify({
        "contacts": contacts,
        "count": len(contacts),
        "days_needed": days_needed,
        "daily_cap": config.DAILY_CAP,
    })


@app.route("/api/send/queue", methods=["POST"])
def send_queue_create():
    """Queue contacts for multi-day sending."""
    data = request.json
    template_id = data.get("template_id")
    custom_body = data.get("message_body", "").strip()
    save_as_template = data.get("save_as_template", "").strip()

    # If a custom message was written, create an ad-hoc template for it
    if custom_body:
        tpl_name = save_as_template if save_as_template else f"Quick send {date.today().strftime('%b %d')}"
        template_id = execute(
            "INSERT INTO outreach_templates (name, body) VALUES (%s, %s)",
            (tpl_name, custom_body),
        )
    elif template_id:
        # If the user edited the template body inline, update it
        edited_body = data.get("edited_body", "").strip()
        if edited_body:
            tpl = query("SELECT body FROM outreach_templates WHERE id=%s", (template_id,))
            if tpl and tpl[0]["body"] != edited_body:
                execute("UPDATE outreach_templates SET body=%s WHERE id=%s",
                        (edited_body, template_id))
    else:
        return jsonify({"error": "No template or message provided"}), 400

    tpl = query("SELECT * FROM outreach_templates WHERE id=%s", (template_id,))
    if not tpl:
        return jsonify({"error": "Template not found"}), 404

    # If specific contact IDs were provided (from the contact picker), use those
    contact_ids = data.get("contact_ids")
    if contact_ids and isinstance(contact_ids, list) and len(contact_ids) > 0:
        placeholders = ",".join(["%s"] * len(contact_ids))
        contacts = query(
            f"""SELECT * FROM contacts
                WHERE id IN ({placeholders})
                  AND phone IS NOT NULL AND phone != ''
                  AND id NOT IN (
                      SELECT contact_id FROM send_queue
                      WHERE template_id = %s AND status = 'pending'
                  )
                ORDER BY last_name""",
            tuple(contact_ids) + (template_id,),
        )
    else:
        # Build contact list with same filters as preview
        where_clauses = ["phone IS NOT NULL", "phone != ''"]
        params = []

        if data.get("status"):
            where_clauses.append("status = %s")
            params.append(data["status"])
        if data.get("city"):
            where_clauses.append("city = %s")
            params.append(data["city"])
        if data.get("source"):
            where_clauses.append("source = %s")
            params.append(data["source"])

        where_clauses.append(f"""id NOT IN (
            SELECT contact_id FROM send_history
            WHERE template_id = %s AND status = 'sent'
            AND sent_at >= DATE_SUB(NOW(), INTERVAL {int(config.COOLDOWN_DAYS)} DAY)
        )""")
        params.append(template_id)

        where_clauses.append("""id NOT IN (
            SELECT contact_id FROM send_queue
            WHERE template_id = %s AND status = 'pending'
        )""")
        params.append(template_id)

        where = " AND ".join(where_clauses)
        contacts = query(f"SELECT * FROM contacts WHERE {where} ORDER BY last_name", tuple(params))

    if not contacts:
        return jsonify({"error": "No contacts match these filters"}), 400

    # Allow scheduling for a specific date (e.g. "tomorrow")
    start_date = None
    if data.get("schedule_date"):
        start_date = date.fromisoformat(data["schedule_date"])

    result = queue_send(contacts, template_id, start_date=start_date)
    return jsonify(result)


@app.route("/api/send/hours")
def send_hours():
    """Check if we're within the send window."""
    return jsonify({
        "within_hours": is_within_send_hours(),
        "start": config.SEND_HOUR_START,
        "end": config.SEND_HOUR_END,
    })


@app.route("/api/send/run-today", methods=["POST"])
def send_run_today():
    """Process today's queued messages. Streams progress via SSE."""
    data = request.json or {}
    dry_run = data.get("dry_run", False)
    force = data.get("force", False)

    event_queue = queue.Queue()

    def generate():
        pending = get_todays_queue()
        already_sent = get_sent_today_count()
        remaining = max(0, config.DAILY_CAP - already_sent)
        total = min(len(pending), remaining)

        yield f"data: {json.dumps({'type': 'start', 'total': total, 'already_sent': already_sent, 'daily_cap': config.DAILY_CAP})}\n\n"

        if total == 0:
            reason = "Daily cap reached" if already_sent >= config.DAILY_CAP else "No messages queued for today"
            yield f"data: {json.dumps({'type': 'done', 'sent': 0, 'failed': 0, 'skipped': 0, 'dry_run': 0, 'message': reason})}\n\n"
            return

        def on_progress(index, total, contact, status, message):
            event_queue.put({
                "type": "progress",
                "index": index,
                "total": total,
                "name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                "phone": contact.get("phone", ""),
                "status": status,
                "message": message[:80] + "..." if len(message) > 80 else message,
            })

        def run_batch():
            try:
                results = process_todays_batch(dry_run=dry_run, force=force, progress_callback=on_progress)
                sent = sum(1 for r in results if r["status"] == "sent")
                failed = sum(1 for r in results if r["status"] == "failed")
                skipped = sum(1 for r in results if r["status"] == "skipped")
                dry = sum(1 for r in results if r["status"] == "dry_run")
                event_queue.put({"type": "done", "sent": sent, "failed": failed, "skipped": skipped, "dry_run": dry})
            except Exception as e:
                event_queue.put({"type": "done", "sent": 0, "failed": 0, "skipped": 0, "dry_run": 0, "message": str(e)})

        thread = threading.Thread(target=run_batch, daemon=True)
        thread.start()

        while True:
            event = event_queue.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event["type"] == "done":
                break

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/api/send/cancel/<batch_id>", methods=["POST"])
def send_cancel(batch_id):
    count = cancel_batch(batch_id)
    return jsonify({"cancelled": count, "batch_id": batch_id})


# ── Queue status ─────────────────────────────────────────────────

@app.route("/queue")
def queue_page():
    queue = get_queue_summary()
    sent_today = get_sent_today_count()
    todays_pending = len(get_todays_queue())
    return render_template("queue.html", queue=queue, sent_today=sent_today,
                           todays_pending=todays_pending,
                           daily_cap=config.DAILY_CAP)


# ── History ──────────────────────────────────────────────────────

@app.route("/history")
def history_page():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "")
    per_page = 50

    where_clauses = []
    params = []

    if search:
        where_clauses.append("(contact_name LIKE %s OR phone LIKE %s OR message_text LIKE %s)")
        params.extend([f"%{search}%"] * 3)
    if status_filter:
        where_clauses.append("status = %s")
        params.append(status_filter)

    where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    total = query(f"SELECT COUNT(*) as c FROM send_history {where}", tuple(params))[0]["c"]
    offset = (page - 1) * per_page

    records = query(
        f"""SELECT sh.*, ot.name as template_name
            FROM send_history sh
            LEFT JOIN outreach_templates ot ON sh.template_id = ot.id
            {where}
            ORDER BY sh.sent_at DESC
            LIMIT %s OFFSET %s""",
        tuple(params) + (per_page, offset),
    )

    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template("history.html", records=records, page=page,
                           total_pages=total_pages, total=total,
                           search=search, status_filter=status_filter)


@app.route("/history/export")
def history_export():
    records = query(
        """SELECT sh.contact_name, sh.phone, ot.name as template_name,
                  sh.message_text, sh.status, sh.error_message, sh.sent_at
           FROM send_history sh
           LEFT JOIN outreach_templates ot ON sh.template_id = ot.id
           ORDER BY sh.sent_at DESC"""
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Phone", "Template", "Message", "Status", "Error", "Sent At"])
    for r in records:
        writer.writerow([r["contact_name"], r["phone"], r["template_name"],
                         r["message_text"], r["status"], r["error_message"],
                         r["sent_at"]])
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=multitext_history.csv"
    return response


# ── API helpers ──────────────────────────────────────────────────

@app.route("/api/contacts/search", methods=["GET", "OPTIONS"])
def contacts_search():
    """Search contacts by name for the contact picker."""
    if request.method == "OPTIONS":
        resp = Response("", status=204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    q = request.args.get("q", "").strip()
    if len(q) < 2:
        resp = jsonify([])
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    rows = query(
        """SELECT id, first_name, last_name, phone, city, status
           FROM contacts
           WHERE phone IS NOT NULL AND phone != ''
             AND (first_name LIKE %s OR last_name LIKE %s
                  OR CONCAT(first_name, ' ', last_name) LIKE %s)
           ORDER BY last_name, first_name
           LIMIT 25""",
        (f"%{q}%", f"%{q}%", f"%{q}%"),
    )
    resp = jsonify(rows)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/api/contacts/sample")
def contacts_sample():
    contact = query("SELECT * FROM contacts WHERE status='active' AND phone IS NOT NULL ORDER BY RAND() LIMIT 1")
    if contact:
        return jsonify(contact[0])
    return jsonify({})


# ── Send Single Message Now (for external apps) ─────────────────

@app.route("/api/send/now", methods=["POST", "OPTIONS"])
def send_now():
    """Send a single iMessage immediately. Used by PropertyTourPics and other apps."""
    # CORS preflight
    if request.method == "OPTIONS":
        resp = Response("", status=204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    data = request.get_json(force=True)
    phone = data.get("phone", "")
    message = data.get("message", "")

    if not phone or not message:
        resp = jsonify({"status": "error", "message": "phone and message required"})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 400

    normalized = normalize_phone(phone)
    if not normalized:
        resp = jsonify({"status": "error", "message": "Invalid phone number"})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 400

    success, err = send_imessage(normalized, message)

    if success:
        resp = jsonify({"status": "success", "message": "Message sent via iMessage"})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    else:
        resp = jsonify({"status": "error", "message": f"Send failed: {err}"})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 500


# ── Startup ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import atexit
    atexit.register(shutdown)

    # Start PropertyTourPics bridge (queue poller + contact syncer)
    from sender.godaddy_bridge import start_bridge
    start_bridge()

    print("\n  MultiText is running at http://localhost:8080")
    print("  Phone access: http://100.111.21.108:8080\n")
    app.run(host="0.0.0.0", port=8080, debug=True, threaded=True)
