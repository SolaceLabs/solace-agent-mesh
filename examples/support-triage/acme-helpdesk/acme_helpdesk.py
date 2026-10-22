# Copyright Solace Corporation
# SPDX-License-Identifier: Apache-2.0

"""A deliberately tiny, fictional help desk for the Solace Agent Mesh
support-triage demo.

It plays the part of a ticketing system:

  1. When a ticket is created, it sends a signed webhook to Agent Mesh, which
     starts the ticket-intake workflow.
  2. The Classification tab sends a burst of generated tickets to the
     ticket-decision workflow at a steady rate.
  3. It exposes the API that Agent Mesh calls to write each result back.

State lives in memory and is lost on restart. Standard library only, so it
runs on any Python 3.10 or later with nothing to install.

    python3 acme-helpdesk/acme_helpdesk.py [-port 8900] [-no-browser]

The webhook secret comes from ACME_HELPDESK_WEBHOOK_SECRET, either in the
environment or in a .env file next to this script or in its parent directory.
"""

import argparse
import hashlib
import hmac
import json
import math
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SAM_WEBHOOK_URL = "http://127.0.0.1:8800/gw/acme-helpdesk/tickets"
DEFAULT_SAM_DECISION_WEBHOOK_URL = "http://127.0.0.1:8800/gw/acme-helpdesk-decisions/tickets"
SIGNATURE_HEADER = "X-Hub-Signature-256"
MIN_SECRET_LENGTH = 16
FIRST_TICKET_ID = 1001
PROJECT_KEY = "ACME"
BURST_KEY = "HT"
WEBHOOK_TIMEOUT_SECONDS = 10
MAX_BURST_COUNT = 500
MAX_BURST_RATE = 50
# Score levels of the ticket-decision workflow's sentiment question, lowest first.
SENTIMENT_LEVELS = ("angry", "frustrated", "neutral", "positive")

STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
}

# Field order of a ticket in API responses. Optional fields are omitted while
# empty, so a new ticket carries only the first six.
TICKET_FIELDS = (
    "ticket_id", "subject", "description", "requester", "created_at", "status",
    "category", "priority", "team", "summary", "internal_note", "respond_by", "triaged_at",
)
REQUIRED_TICKET_FIELDS = set(TICKET_FIELDS[:6])
TRIAGE_FIELDS = ("status", "category", "priority", "team", "summary", "internal_note", "respond_by")

SAMPLES = [
    {
        "subject": "Nobody can log in - Error 503",
        "description": "Since about 9:40 this morning none of our 300 users can log in to the dashboard. "
        "They all get 'Error 503 - service unavailable'. This is blocking our whole operations team.",
        "requester": "dana@globex.example",
    },
    {
        "subject": "Export invoices as CSV?",
        "description": "Hi, how do I export last month's invoices as a CSV? I can only find a PDF download.",
        "requester": "raj@example.com",
    },
    {
        "subject": "Charged twice this month",
        "description": "Our card was charged twice for the October subscription. Please refund the duplicate.",
        "requester": "kim@northwind.example",
    },
]

# Templates for the Classification tab. Each reads as one priority and
# department, with a few deliberately vague ones so that some answers land
# below the decision model's confidence threshold.
PEOPLE = ("dana", "raj", "kim", "luis", "amara", "chen", "sofia", "omar", "priya", "jonas", "mei", "tariq")
COMPANIES = ("globex", "northwind", "initech", "umbrella", "hooli", "stark", "wayne", "tyrell", "cyberdyne", "acmecorp")
BURST_TEMPLATES = (
    # Critical: outages, data loss, security
    ("Nobody can log in - Error 503", "Since about {time} none of our {users} users can log in. Every request returns Error 503. Our whole operations team is blocked."),
    ("Dashboard is down for everyone", "The dashboard has not loaded for any of our {users} users since {time}. We have no workaround and production is stopped."),
    ("Customer records disappeared", "After this morning's sync, around {users} customer records are missing from our account. We need them back urgently; this is live data."),
    ("Suspicious logins on our admin account", "We see admin logins from a country we do not operate in since {time}. We think the account is compromised. Please lock it now."),
    ("API returning 500 on every call", "All API calls from our integration fail with HTTP 500 since {time}. Orders are not flowing to our warehouse at all."),
    # High: core feature broken, painful workaround
    ("Order form rejects apartment addresses", "The order form rejects any address with an apartment number. We re-key each order by hand, about ten minutes each, {users} orders a day."),
    ("Payments failing for some customers", "About a third of card payments fail at checkout since {time}. Customers can retry and sometimes it works."),
    ("Reports take 10 minutes to load", "Every report now takes around ten minutes to load for our {users} users. They used to load in seconds."),
    # Medium: non-core feature, workaround exists, billing errors
    ("Charged twice in {month}", "Our card was charged ${amount} twice for the {month} subscription. Please refund the duplicate."),
    ("Sorting by date does nothing", "Clicking the date column header in the usage report does not sort it. I export to a spreadsheet and sort there instead."),
    ("Wrong tax on invoice", "Invoice #{order} for {month} shows the wrong tax rate. We need a corrected invoice for our accounts."),
    ("Password reset email never arrives", "One of our users requested a password reset three times and never got the email. Other users are fine."),
    # Low: how-to, feature requests, cosmetic
    ("Export invoices as CSV?", "How do I export the {month} invoices as a CSV? I can only find a PDF download."),
    ("Feature request: dark mode", "It would be great to have a dark mode for the dashboard. Several of our team work late."),
    ("Logo slightly blurry", "Our logo looks a little blurry in the top bar on large screens. Not urgent."),
    ("How do I add a teammate?", "Where do I go to invite a new teammate to our workspace?"),
    ("Can we change our billing date?", "Is it possible to move our billing date to the first of the month?"),
    # Deliberately vague, to exercise low-confidence escalation
    ("Something is off", "Things have been weird since yesterday. Not sure what is going on. Can someone take a look?"),
    ("Urgent!!!", "URGENT!!! Please call me back about order #{order}."),
    ("Not working", "It does not work again."),
)

TICKET_PATH = re.compile(r"^/api/tickets/([^/]+)$")


class BadRequest(Exception):
    pass


def now():
    return datetime.now().strftime("%H:%M:%S")


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now_ms():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def or_default(value, fallback):
    return value.strip() or fallback


def sign(secret, body):
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def to_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def public(ticket):
    """Returns the ticket in API field order, without empty optional fields."""
    return {k: ticket[k] for k in TICKET_FIELDS if k in REQUIRED_TICKET_FIELDS or ticket.get(k)}


def json_object(body):
    """Parses a JSON object body; anything else is a bad request."""
    try:
        data = json.loads(body)
    except ValueError:
        raise BadRequest from None
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise BadRequest
    return data


def string_fields(body, names):
    """Parses a JSON object and returns the named string fields, "" when absent."""
    data = json_object(body)
    fields = {}
    for name in names:
        value = data.get(name)
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise BadRequest
        fields[name] = value
    return fields


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load_dotenv(*paths):
    """Sets variables from KEY=VALUE files. Variables already set win, and so
    does the first file that sets a variable."""
    for path in paths:
        try:
            lines = path.read_text().splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.removeprefix("export ").partition("=")
            key, value = key.strip(), value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            os.environ.setdefault(key, value)


def post_webhook(url, secret, body):
    """Sends a signed webhook. Returns the parsed JSON reply ({} if none)."""
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", SIGNATURE_HEADER: sign(secret, body)},
    )
    with urllib.request.urlopen(request, timeout=WEBHOOK_TIMEOUT_SECONDS) as response:
        status, reply = response.status, response.read()
    try:
        return status, json.loads(reply)
    except ValueError:
        return status, {}


def generate_burst_ticket():
    subject, description = random.choice(BURST_TEMPLATES)
    values = {
        "users": random.choice((12, 40, 85, 150, 300, 1200)),
        "time": random.choice(("8:15", "9:40", "10:05", "11:30", "13:20", "14:45", "16:10")),
        "month": random.choice(("September", "October", "November")),
        "amount": random.choice(("49.00", "129.00", "499.00", "1,250.00")),
        "order": random.randint(10000, 99999),
    }
    return {
        "subject": subject.format(**values),
        "description": description.format(**values),
        "requester": f"{random.choice(PEOPLE)}@{random.choice(COMPANIES)}.example",
    }


class Desk:
    """The Triage tab: tickets that go to the ticket-intake workflow.
    lock protects tickets, events and next_id."""

    def __init__(self, sam_webhook_url, secret):
        self.sam_webhook_url = sam_webhook_url
        self.secret = secret
        self.lock = threading.Lock()
        self.tickets = {}
        self.events = []
        self.next_id = FIRST_TICKET_ID

    def log(self, direction, title, detail):
        with self.lock:
            self.events.append({"time": now(), "direction": direction, "title": title, "detail": detail})

    def send_webhook(self, ticket):
        """Does what a ticketing system's "ticket created" trigger does."""
        tid = ticket["ticket_id"]
        body = to_json({k: ticket[k] for k in ("ticket_id", "subject", "description", "requester", "created_at")})
        self.log("out", "Webhook sent for ticket " + tid,
                 "POST " + self.sam_webhook_url + ", body signed with HMAC-SHA256 in " + SIGNATURE_HEADER)
        try:
            status, reply = post_webhook(self.sam_webhook_url, self.secret, body)
        except urllib.error.HTTPError as err:
            self.log("error", "Agent Mesh rejected the webhook for ticket " + tid,
                     f"HTTP {err.code}. Check that ACME_HELPDESK_WEBHOOK_SECRET matches the Entrypoint's secret.")
            return
        except (urllib.error.URLError, OSError, ValueError) as err:
            reason = getattr(err, "reason", err)
            self.log("error", "Could not reach Agent Mesh for ticket " + tid,
                     f"{reason}. Is Agent Mesh running, and is -sam-webhook-url right?")
            return
        task_id = reply.get("taskId", "") if isinstance(reply, dict) else ""
        self.log("in", "Agent Mesh accepted ticket " + tid,
                 f"HTTP {status}, taskId {task_id}. The workflow now runs in the background.")

    def create_ticket(self, sample):
        with self.lock:
            ticket = {
                "ticket_id": f"{PROJECT_KEY}-{self.next_id}",
                "subject": or_default(sample["subject"], "(no subject)"),
                "description": sample["description"].strip(),
                "requester": or_default(sample["requester"], "customer@example.com"),
                "created_at": utc_now(),
                "status": "new",
            }
            self.next_id += 1
            self.tickets[ticket["ticket_id"]] = ticket
            created = dict(ticket)

        self.log("info", f"Ticket {created['ticket_id']} created",
                 f"{json.dumps(created['subject'], ensure_ascii=False)} from {created['requester']}")
        threading.Thread(target=self.send_webhook, args=(created,), daemon=True).start()
        return created

    def update_ticket(self, tid, update):
        with self.lock:
            ticket = self.tickets.get(tid)
            if ticket is None:
                return None
            ticket.update(update)
            ticket["status"] = or_default(update["status"], "triaged")
            ticket["triaged_at"] = utc_now()
            updated = dict(ticket)

        self.log("in", "Agent Mesh updated ticket " + tid,
                 f"PUT /api/tickets/{tid} via the acme-helpdesk-api connector: status {updated['status']}, "
                 f"priority {update['priority']}, team {update['team']}, respond by {update['respond_by']}")
        return updated

    def clear_tickets(self):
        """Deletes every ticket. IDs keep counting, so a late write-back for a
        cleared ticket gets a 404 instead of landing on a new one."""
        with self.lock:
            count = len(self.tickets)
            self.tickets.clear()
        self.log("info", "Tickets cleared", f"{count} ticket{'' if count == 1 else 's'} removed")

    def ticket_list(self):
        with self.lock:
            tickets = [public(t) for t in self.tickets.values()]
        return sorted(tickets, key=lambda t: t["ticket_id"], reverse=True)

    def event_list(self):
        with self.lock:
            return list(reversed(self.events))


class Throughput:
    """The Classification tab: a burst of generated tickets sent to the
    ticket-decision workflow at a fixed rate. lock protects everything."""

    def __init__(self, sam_webhook_url, secret):
        self.sam_webhook_url = sam_webhook_url
        self.secret = secret
        self.lock = threading.Lock()
        self.run = None
        self.tickets = {}
        # Keeps counting across resets, so a late write-back from an earlier
        # run can never land on a ticket in the current one.
        self.next_id = FIRST_TICKET_ID
        self.next_run_id = 1

    @staticmethod
    def _public(ticket):
        return {k: v for k, v in ticket.items() if not k.startswith("_") and v is not None}

    def state(self):
        with self.lock:
            tickets = [self._public(t) for t in self.tickets.values()]
            run = dict(self.run) if self.run else None
        return {"run": run, "tickets": sorted(tickets, key=lambda t: t["ticket_id"], reverse=True)}

    def sending(self):
        with self.lock:
            return bool(self.run and self.run["sending"])

    def reset(self):
        with self.lock:
            self.run = None
            self.tickets.clear()

    def start(self, count, rate):
        """Starts a run, sending one ticket every 1/rate seconds."""
        with self.lock:
            run = {"id": self.next_run_id, "count": count, "rate": rate, "started_at": utc_now_ms(), "sending": True}
            self.next_run_id += 1
            self.run = run
            self.tickets.clear()
        threading.Thread(target=self._pace, args=(run,), daemon=True).start()
        return dict(run)

    def _pace(self, run):
        start, interval = time.monotonic(), 1 / run["rate"]
        for i in range(run["count"]):
            delay = start + i * interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            with self.lock:
                if self.run is not run:
                    return  # reset, or a new run started
            threading.Thread(target=self._send, args=(run,), daemon=True).start()
        with self.lock:
            run["sending"] = False

    def _send(self, run):
        sample = generate_burst_ticket()
        with self.lock:
            if self.run is not run:
                return
            tid = f"{BURST_KEY}-{self.next_id}"
            self.next_id += 1
            ticket = {"ticket_id": tid, **sample, "sent_at": utc_now_ms(), "status": "sending", "_sent": time.time()}
            self.tickets[tid] = ticket
        # Only what the decision model's questions are about, plus the ID that
        # comes back to us in source_ticket.
        body = to_json({"ticket_id": tid, "subject": sample["subject"], "description": sample["description"]})
        error = None
        try:
            post_webhook(self.sam_webhook_url, self.secret, body)
        except urllib.error.HTTPError as err:
            error = (f"Agent Mesh answered HTTP {err.code}. Check ACME_HELPDESK_WEBHOOK_SECRET and that "
                     "the acme-helpdesk-decisions Entrypoint is deployed.")
        except (urllib.error.URLError, OSError, ValueError) as err:
            error = f"Could not reach Agent Mesh at {self.sam_webhook_url}: {getattr(err, 'reason', err)}"
        with self.lock:
            if ticket["status"] != "sending":
                return  # the decision already arrived
            ticket["status"] = "failed" if error else "sent"
            ticket["error"] = error

    def record(self, body):
        """Records a decision from Agent Mesh. Returns None for an unknown ticket."""
        try:
            ticket_id = json.loads(body.get("source_ticket") or "").get("ticket_id")
        except (ValueError, TypeError, AttributeError):
            return None

        def text(v):
            return v if isinstance(v, str) and v else None

        def number(v):
            return v if is_number(v) else None

        score = number(body.get("sentiment_score"))
        with self.lock:
            ticket = self.tickets.get(ticket_id) if isinstance(ticket_id, str) else None
            if ticket is None:
                return None
            ticket.update(
                status="classified",
                error=None,
                path="llm" if body.get("path") == "llm" else "decision",
                priority=text(body.get("priority")),
                department=text(body.get("department")),
                sentiment=None if score is None else SENTIMENT_LEVELS[max(0, min(3, round(score)))],
                churn_risk=body.get("churn_risk") in (True, "true"),
                needs_human=body.get("needs_human") in (True, "true"),
                confidence=number(body.get("confidence")),
                model_ms=number(body.get("model_ms")),
                escalation_reason=text(body.get("escalation_reason")),
                response=text(body.get("response")),
                received_at=utc_now_ms(),
                # Webhook sent to decision received back from Agent Mesh.
                latency_ms=round((time.time() - ticket["_sent"]) * 1000),
            )
            return self._public(ticket)


class Server(ThreadingHTTPServer):
    # On Windows, SO_REUSEADDR lets a second copy bind the same port silently.
    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True


def make_handler(desk, throughput):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # The browser polls every second or so; keep the terminal quiet.

        def send(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status, value):
            self.send(status, to_json(value) + b"\n", "application/json")

        def bad_json(self):
            self.send_json(400, {"message": "body must be JSON"})

        def read_body(self):
            return self.rfile.read(int(self.headers.get("Content-Length") or 0))

        def route(self):
            return urllib.parse.urlsplit(self.path).path

        def not_found(self):
            self.send(404, b"404 page not found\n", "text/plain; charset=utf-8")

        def do_GET(self):
            path = self.route()
            if path in STATIC:
                name, content_type = STATIC[path]
                self.send(200, (HERE / name).read_bytes(), content_type)
            elif path == "/api/samples":
                self.send_json(200, SAMPLES)
            elif path == "/api/tickets":
                self.send_json(200, desk.ticket_list())
            elif path == "/api/events":
                self.send_json(200, desk.event_list())
            elif path == "/api/throughput":
                self.send_json(200, throughput.state())
            else:
                self.not_found()

        def do_POST(self):
            path = self.route()
            try:
                if path == "/api/tickets":
                    sample = string_fields(self.read_body(), ("subject", "description", "requester"))
                    self.send_json(201, public(desk.create_ticket(sample)))
                elif path == "/api/throughput/runs":
                    self.start_run(json_object(self.read_body()))
                elif path == "/api/decisions":
                    ticket = throughput.record(json_object(self.read_body()))
                    if ticket:
                        self.send_json(200, ticket)
                    else:
                        self.send_json(404, {"message": "no Classification ticket matches source_ticket"})
                else:
                    self.not_found()
            except BadRequest:
                self.bad_json()

        def start_run(self, data):
            count, rate = data.get("count"), data.get("rate")
            if not (isinstance(count, int) and not isinstance(count, bool) and 1 <= count <= MAX_BURST_COUNT
                    and is_number(rate) and 0 < rate <= MAX_BURST_RATE):
                return self.send_json(400, {
                    "message": f"count must be 1-{MAX_BURST_COUNT} and rate must be above 0 and at most {MAX_BURST_RATE}"})
            if throughput.sending():
                return self.send_json(409, {"message": "a run is already sending"})
            self.send_json(202, throughput.start(count, rate))

        def do_PUT(self):
            match = TICKET_PATH.match(self.route())
            if not match:
                return self.not_found()
            tid = urllib.parse.unquote(match.group(1))
            try:
                update = string_fields(self.read_body(), TRIAGE_FIELDS)
            except BadRequest:
                return self.bad_json()
            ticket = desk.update_ticket(tid, update)
            if ticket is None:
                desk.log("error", "Update for unknown ticket " + tid, "PUT rejected with 404")
                return self.send_json(404, {"message": f"ticket {tid} not found"})
            self.send_json(200, public(ticket))

        def do_DELETE(self):
            path = self.route()
            if path == "/api/tickets":
                desk.clear_tickets()
                self.send_json(200, desk.ticket_list())
            elif path == "/api/throughput":
                throughput.reset()
                self.send_json(200, throughput.state())
            else:
                self.not_found()

    return Handler


def main():
    load_dotenv(HERE / ".env", HERE.parent / ".env")

    parser = argparse.ArgumentParser(description="The fictional Acme Help Desk for the support-triage example.")
    parser.add_argument("-port", "--port", type=int, default=8900, help="port to serve the Acme Help Desk on")
    parser.add_argument(
        "-sam-webhook-url", "--sam-webhook-url",
        default=os.environ.get("ACME_HELPDESK_SAM_WEBHOOK_URL", "").strip() or DEFAULT_SAM_WEBHOOK_URL,
        help="the Agent Mesh Webhook Entrypoint URL that new tickets are sent to",
    )
    parser.add_argument(
        "-sam-decision-webhook-url", "--sam-decision-webhook-url",
        default=os.environ.get("ACME_HELPDESK_SAM_DECISION_WEBHOOK_URL", "").strip() or DEFAULT_SAM_DECISION_WEBHOOK_URL,
        help="the Agent Mesh Webhook Entrypoint URL that Classification tickets are sent to",
    )
    parser.add_argument("-no-browser", "--no-browser", action="store_true", help="do not open a browser on start")
    args = parser.parse_args()

    secret = os.environ.get("ACME_HELPDESK_WEBHOOK_SECRET", "")
    if len(secret) < MIN_SECRET_LENGTH:
        sys.exit(f"Set ACME_HELPDESK_WEBHOOK_SECRET ({MIN_SECRET_LENGTH}+ characters) to the same value you "
                 "applied to Agent Mesh, in the environment or in examples/support-triage/.env.")

    desk = Desk(args.sam_webhook_url, secret)
    throughput = Throughput(args.sam_decision_webhook_url, secret)
    try:
        server = Server(("127.0.0.1", args.port), make_handler(desk, throughput))
    except OSError as err:
        sys.exit(f"Could not listen on 127.0.0.1:{args.port}: {err.strerror or err}")
    url = f"http://127.0.0.1:{args.port}"
    print(f"Acme Help Desk running at {url}\n"
          f"New tickets are sent to {desk.sam_webhook_url}\n"
          f"Classification tickets are sent to {throughput.sam_webhook_url}", flush=True)
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
