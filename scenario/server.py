"""Animated Chippewa squirrel rescue for a club CTF.

The closet box is a game prop. Codes stay on the server so the page source
does not contain the answer.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
TOKEN_SECRET = os.environ.get("TOKEN_SECRET", "dev-only-change-me")
DOOR_CODE = os.environ.get("DOOR_CODE", "246813")
DISARM_CODE = os.environ.get("DISARM_CODE", "903177")
DOOR_FLAG = os.environ.get("DOOR_FLAG", "flag{door_is_open}")
DISARM_FLAG = os.environ.get("DISARM_FLAG", "flag{building_is_safe}")
SCOREBOARD_URL = os.environ.get("SCOREBOARD_URL", "http://localhost:8000").rstrip("/")
TRIES = int(os.environ.get("TRIES", "3"))
SECONDS = int(os.environ.get("SECONDS", "300"))
TTL = 60 * 60 * 3

LOCK = threading.Lock()
SESSIONS: dict[str, dict] = {}


def digits(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(ch for ch in value if ch.isdigit())


def same(guess: str, secret: str) -> bool:
    left = guess.encode()
    right = secret.encode()
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def purge() -> None:
    now = time.time()
    stale = [key for key, row in SESSIONS.items() if row["expires"] < now]
    for key in stale:
        del SESSIONS[key]


def new_session() -> str:
    token = secrets.token_urlsafe(24)
    with LOCK:
        purge()
        SESSIONS[token] = {
            "tries": TRIES,
            "exploded": False,
            "solved": False,
            "expires": time.time() + TTL,
        }
    return token


def session_for(token: object) -> dict | None:
    if not isinstance(token, str) or not token:
        return None
    with LOCK:
        purge()
        row = SESSIONS.get(token)
        if row is None:
            return None
        row["expires"] = time.time() + TTL
        return row


class Handler(BaseHTTPRequestHandler):
    server_version = "BuildingSweep/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self.respond(200, {"ok": True})
            return
        if path == "/api/config":
            self.respond(
                200,
                {
                    "scoreboard": SCOREBOARD_URL,
                    "door_digits": len(DOOR_CODE),
                    "disarm_digits": len(DISARM_CODE),
                    "tries": TRIES,
                    "seconds": SECONDS,
                },
            )
            return
        if path == "/":
            self.serve_file(STATIC / "index.html")
            return
        if path.startswith("/static/"):
            relative = path[len("/static/") :]
            target = (STATIC / relative).resolve()
            if STATIC.resolve() not in target.parents and target != STATIC.resolve():
                self.respond(404, {"message": "Not found"})
                return
            self.serve_file(target)
            return
        self.respond(404, {"message": "Not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > 4000:
            self.respond(413, {"message": "Request is too large."})
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            self.respond(400, {"message": "Send JSON."})
            return
        if not isinstance(payload, dict):
            self.respond(400, {"message": "Send a JSON object."})
            return
        if path == "/api/door":
            self.door(payload)
            return
        if path == "/api/disarm":
            self.disarm(payload)
            return
        if path == "/api/timeout":
            self.time_expired(payload)
            return
        self.respond(404, {"message": "Not found"})

    def door(self, payload: dict) -> None:
        guess = digits(payload.get("code"))
        if len(guess) != len(DOOR_CODE):
            self.respond(
                200,
                {
                    "ok": False,
                    "counted": False,
                    "message": "Enter the full PIN from the squirrel captain's clipboard.",
                },
            )
            return
        if not same(guess, DOOR_CODE):
            print("door rejected", flush=True)
            self.respond(
                200,
                {
                    "ok": False,
                    "counted": True,
                    "message": "That PIN buzzed. The squirrels are still locked in, and you are still outside.",
                },
            )
            return
        token = new_session()
        print("door opened", flush=True)
        self.respond(
            200,
            {
                "ok": True,
                "token": token,
                "flag": DOOR_FLAG,
                "message": "Door open. Copy the flag, then walk in when you are ready to free the squirrels.",
            },
        )

    def disarm(self, payload: dict) -> None:
        row = session_for(payload.get("token"))
        if row is None:
            self.respond(
                403,
                {"ok": False, "message": "Enter the door PIN again. This rescue run is gone."},
            )
            return
        if row["solved"]:
            self.respond(
                200,
                {
                    "ok": True,
                    "flag": DISARM_FLAG,
                    "message": "The squirrels are already out.",
                },
            )
            return
        if row["exploded"]:
            self.respond(
                200,
                {
                    "ok": False,
                    "exploded": True,
                    "attempts_left": 0,
                    "message": "This rescue already failed. Start again outside.",
                },
            )
            return
        guess = digits(payload.get("code"))
        if len(guess) != len(DISARM_CODE):
            self.respond(
                200,
                {
                    "ok": False,
                    "counted": False,
                    "attempts_left": row["tries"],
                    "message": "Enter the full code from the snack closet log.",
                },
            )
            return
        if same(guess, DISARM_CODE):
            row["solved"] = True
            print("prop safe", flush=True)
            self.respond(
                200,
                {
                    "ok": True,
                    "flag": DISARM_FLAG,
                    "message": "The closet popped open. The Chippewa squirrels are free.",
                },
            )
            return
        row["tries"] -= 1
        if row["tries"] <= 0:
            row["exploded"] = True
            print("prop triggered", flush=True)
            self.respond(
                200,
                {
                    "ok": False,
                    "exploded": True,
                    "attempts_left": 0,
                    "message": "Wrong code. The acorn alarm sent the squirrels scattering.",
                },
            )
            return
        print("prop rejected", flush=True)
        self.respond(
            200,
            {
                "ok": False,
                "exploded": False,
                "attempts_left": row["tries"],
                "message": "Wrong code. The squirrels are still stuck. Use the digits from the log.",
            },
        )

    def time_expired(self, payload: dict) -> None:
        row = session_for(payload.get("token"))
        if row is None:
            self.respond(
                403,
                {"ok": False, "message": "Enter the door PIN again. This rescue run is gone."},
            )
            return
        if row["solved"]:
            self.respond(200, {"ok": True, "flag": DISARM_FLAG, "message": "The squirrels are already out."})
            return
        row["exploded"] = True
        row["tries"] = 0
        print("timer expired", flush=True)
        self.respond(
            200,
            {
                "ok": False,
                "exploded": True,
                "attempts_left": 0,
                "message": "Time's up. The acorn alarm sent the squirrels scattering.",
            },
        )

    def serve_file(self, path: Path) -> None:
        if not path.is_file():
            self.respond(404, {"message": "Not found"})
            return
        kind = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
        }.get(path.suffix, "application/octet-stream")
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def respond(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    if not DOOR_CODE.isdigit() or not DISARM_CODE.isdigit():
        raise SystemExit("DOOR_CODE and DISARM_CODE must be digits.")
    if TOKEN_SECRET == "dev-only-change-me":
        print("warning: TOKEN_SECRET is the development default", flush=True)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(
        "Chippewa Squirrel Rescue on http://%s:%s (door digits %s, closet digits %s, tries %s, timer %ss)"
        % (HOST, PORT, len(DOOR_CODE), len(DISARM_CODE), TRIES, SECONDS),
        flush=True,
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
