#!/usr/bin/env python3
"""Create the Chippewa Squirrel Rescue event on a local CTFd, including both challenges."""

from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def load_env(path: Path) -> None:
    if not path.exists():
        raise SystemExit("Missing %s. Copy .env.example to .env first." % path)
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def caesar(text: str, shift: int) -> str:
    out = []
    for char in text:
        if "a" <= char <= "z":
            out.append(chr((ord(char) - 97 + shift) % 26 + 97))
        elif "A" <= char <= "Z":
            out.append(chr((ord(char) - 65 + shift) % 26 + 65))
        else:
            out.append(char)
    return "".join(out)


def clock_phrase(seconds: int) -> str:
    if seconds % 60 == 0:
        minutes = seconds // 60
        unit = "minute" if minutes == 1 else "minutes"
        return "%s %s" % (minutes, unit)
    return "%s seconds" % seconds


def extract_nonce(html: str) -> str:
    patterns = [
        r'name="nonce"[^>]*value="([^"]+)"',
        r'value="([^"]+)"[^>]*name="nonce"',
        r"csrfNonce':\s*\"([^\"]+)\"",
        r'<meta name="csrf-token" content="([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    raise RuntimeError("Could not find a CSRF nonce on the CTFd page.")


class Client:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = ""

    def open(self, method: str, path: str, data: bytes | None = None, headers: dict | None = None):
        request = urllib.request.Request(self.base + path, data=data, headers=headers or {}, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                body = response.read().decode()
                return response.status, body, response.geturl()
        except urllib.error.HTTPError as error:
            body = error.read().decode()
            return error.code, body, error.geturl()

    def form(self, path: str, fields: dict) -> tuple[int, str, str]:
        payload = urllib.parse.urlencode(fields).encode()
        return self.open(
            "POST",
            path,
            payload,
            {"Content-Type": "application/x-www-form-urlencoded"},
        )

    def refresh_csrf(self) -> None:
        status, body, _url = self.open("GET", "/")
        if status != 200:
            raise RuntimeError("Could not load CTFd to read the CSRF token (%s)." % status)
        self.csrf = extract_nonce(body)

    def api(self, method: str, path: str, payload: dict | None = None, retry: bool = True):
        headers = {"Accept": "application/json"}
        data = None
        if payload is not None:
            if not self.csrf:
                self.refresh_csrf()
            headers["Content-Type"] = "application/json"
            headers["CSRF-Token"] = self.csrf
            data = json.dumps(payload).encode()
        status, body, _url = self.open(method, path, data, headers)
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body[:500]}
        if status == 403 and retry and payload is not None:
            self.refresh_csrf()
            return self.api(method, path, payload, retry=False)
        if status >= 400 or (isinstance(parsed, dict) and parsed.get("success") is False):
            raise RuntimeError("%s %s failed (%s): %s" % (method, path, status, parsed))
        return parsed

    def wait_until_up(self) -> None:
        print("Waiting for CTFd at %s" % self.base)
        last = "no response"
        for _ in range(90):
            try:
                status, _body, _url = self.open("GET", "/setup")
                if status in (200, 302):
                    print("CTFd is answering.")
                    return
                last = "HTTP %s" % status
            except Exception as error:  # noqa: BLE001 - startup can fail in several network ways
                last = str(error)
            time.sleep(2)
        raise SystemExit("CTFd did not become ready: %s" % last)


def require_digits(name: str, value: str) -> str:
    if not value.isdigit() or not 4 <= len(value) <= 8:
        raise SystemExit("%s must be 4 to 8 digits." % name)
    return value


def challenge_text(scenario: str, tries: int, seconds: int) -> tuple[dict, dict]:
    door = require_digits("DOOR_CODE", os.environ["DOOR_CODE"])
    disarm = require_digits("DISARM_CODE", os.environ["DISARM_CODE"])
    spoken = " ".join(WORDS[int(digit)] for digit in door)
    cipher = caesar("the door pin is %s" % spoken, 3)
    token = base64.b64encode(("squirrel snack code %s" % disarm).encode()).decode()
    limit = clock_phrase(seconds)
    door_body = "\n".join(
        [
            "The Chippewa squirrels snuck into Acorn Hall for a midnight acorn party, and the front door locked behind them. Their captain left the rescue PIN on a clipboard as a Caesar cipher, shifted forward by 3, so the raccoons could not read it.",
            "",
            "```",
            cipher,
            "```",
            "",
            "Shift each letter back by 3. The PIN is the digits those number-words spell. Type that PIN on the simulator intercom.",
            "",
            "A wrong PIN only buzzes the door. The squirrels stay inside. When the door opens, the simulator shows a flag. Submit that flag here.",
        ]
    )
    closet_body = "\n".join(
        [
            "The squirrels are stuck in the snack closet, noses against the glass. The keypad is a game prop with a %s timer. You get %s full tries. The third wrong code, or the timer hitting zero, sets off the acorn alarm and the squirrels scatter."
            % (limit, tries),
            "",
            "The groundskeeper log is below. `0000` and `1234` are dummy acorn tests. Do not type them.",
            "",
            "```",
            "02:02:11 acorn.selftest code=0000 result=FAIL",
            "02:02:18 acorn.selftest code=1234 result=FAIL",
            "02:07:40 note=dummy acorn codes, do not type them",
            "02:07:41 snack.token=%s" % token,
            "```",
            "",
            "`snack.token` is base64. Decode it and type only the digits on the closet keypad.",
            "",
            "You can decode the token before you walk inside. The timer starts when you enter the closet. The right code pops the lock and the squirrels hop free.",
        ]
    )
    return (
        {
            "name": "Squirrel Door Note",
            "former_names": ["Clipboard at the Door"],
            "category": "Red Team",
            "value": 100,
            "description": door_body,
            "hint": "Write the alphabet in a row. Move each letter back 3 places. `wzr` becomes `two`. Then turn the number-words into digits.",
            "hint_cost": 25,
            "tag": "caesar",
        },
        {
            "name": "Snack Closet Log",
            "former_names": ["Closet Log"],
            "category": "Blue Team",
            "value": 200,
            "description": closet_body,
            "hint": "Copy snack.token into a base64 decoder. The digits at the end are the keypad code. Ignore 0000 and 1234.",
            "hint_cost": 40,
            "tag": "base64",
        },
    )


def find_challenge(rows: list, spec: dict) -> dict | None:
    by_name = {row.get("name"): row for row in rows}
    for name in [spec["name"], *spec.get("former_names", [])]:
        if name in by_name:
            return by_name[name]
    return None


def upsert_challenge(client: Client, spec: dict, scenario: str, flag: str) -> int:
    existing = client.api("GET", "/api/v1/challenges?view=admin")
    found = find_challenge(existing.get("data", []), spec)
    fields = {
        "name": spec["name"],
        "category": spec["category"],
        "description": spec["description"],
        "value": spec["value"],
        "state": "visible",
        "type": "standard",
        "connection_info": scenario,
        "max_attempts": 0,
        "attribution": "Club game. The squirrels are cartoons.",
    }
    if found:
        client.api("PATCH", "/api/v1/challenges/%s" % found["id"], fields)
        challenge_id = found["id"]
        print("Updated challenge: %s" % spec["name"])
    else:
        created = client.api("POST", "/api/v1/challenges", fields)
        challenge_id = created["data"]["id"]
        print("Created challenge: %s" % spec["name"])

    flags = client.api("GET", "/api/v1/flags")
    current = [row for row in flags.get("data", []) if row.get("challenge_id") == challenge_id]
    if current:
        if current[0].get("content") != flag:
            client.api("PATCH", "/api/v1/flags/%s" % current[0]["id"], {"content": flag, "data": "case_insensitive"})
    else:
        client.api(
            "POST",
            "/api/v1/flags",
            {
                "challenge_id": challenge_id,
                "content": flag,
                "type": "static",
                "data": "case_insensitive",
            },
        )

    hints = client.api("GET", "/api/v1/hints")
    owned = [row for row in hints.get("data", []) if row.get("challenge_id") == challenge_id]
    if owned:
        if owned[0].get("content") != spec["hint"] or owned[0].get("cost") != spec["hint_cost"]:
            client.api(
                "PATCH",
                "/api/v1/hints/%s" % owned[0]["id"],
                {"content": spec["hint"], "cost": spec["hint_cost"]},
            )
    else:
        client.api(
            "POST",
            "/api/v1/hints",
            {
                "challenge_id": challenge_id,
                "content": spec["hint"],
                "cost": spec["hint_cost"],
                "title": "Beginner hint",
            },
        )

    tags = client.api("GET", "/api/v1/tags")
    owned_tags = [row for row in tags.get("data", []) if row.get("challenge_id") == challenge_id]
    if not any(row.get("value") == spec["tag"] for row in owned_tags):
        client.api("POST", "/api/v1/tags", {"challenge_id": challenge_id, "value": spec["tag"]})
    return challenge_id


def ensure_brackets(client: Client) -> None:
    current = client.api("GET", "/api/v1/brackets")
    names = {row.get("name") for row in current.get("data", [])}
    for name, description in (
        ("Red", "Rescue lane. Same Chippewa squirrel mission as Blue."),
        ("Blue", "Rescue lane. Same Chippewa squirrel mission as Red."),
    ):
        if name in names:
            continue
        client.api(
            "POST",
            "/api/v1/brackets",
            {"name": name, "description": description, "type": "teams"},
        )
        print("Created bracket: %s" % name)


def ensure_homepage(client: Client, scenario: str, tries: int, seconds: int) -> None:
    pages = client.api("GET", "/api/v1/pages")
    index = next((row for row in pages.get("data", []) if row.get("route") == "index"), None)
    if not index:
        print("No index page found; the challenges are still loaded.")
        return
    content = "\n".join(
        [
            "# Chippewa Squirrel Rescue",
            "",
            "The Chippewa squirrels threw a midnight acorn party in Acorn Hall. The front door locked. Then the snack closet locked. Tiny paws, big problem.",
            "",
            "Red and Blue are rescue lanes on the scoreboard. Both lanes free the same squirrels, and the first lane through both flags wins the race.",
            "",
            "The closet keypad is a **game prop**, not a real lock. A wrong snack code, or a timer of %s, sets off the acorn alarm and the squirrels scatter. You get %s closet tries."
            % (clock_phrase(seconds), tries),
            "",
            "## How to play",
            "",
            "1. [Start here](/join). The page walks you through the game, your name, your team, and Start.",
            "2. Open [the rescue simulator](%s)." % scenario,
            "3. Solve **Squirrel Door Note**, type the PIN outside, and submit the flag the door gives you.",
            "4. Solve **Snack Closet Log** before you walk inside. Type that code on the keypad so the squirrels can hop out.",
            "",
            "This is a cartoon on a screen. Do not try any of it on a real building.",
        ]
    )
    client.api(
        "PATCH",
        "/api/v1/pages/%s" % index["id"],
        {
            "title": "Chippewa Squirrel Rescue",
            "route": "index",
            "content": content,
            "draft": False,
            "hidden": False,
            "format": "markdown",
            "auth_required": False,
        },
    )
    print("Updated the scoreboard homepage.")


def organizer_session(client: Client) -> bool:
    me = client.api("GET", "/api/v1/users/me")
    data = me.get("data") or {}
    return data.get("name") == os.environ["CTFD_ADMIN_USER"] and bool(data.get("id"))


def setup_or_login(client: Client) -> None:
    status, body, url = client.open("GET", "/setup")
    path = urllib.parse.urlparse(url).path
    if status == 200 and path.startswith("/setup"):
        print("First start: creating the organizer account and event.")
        client.form(
            "/setup",
            {
                "nonce": extract_nonce(body),
                "ctf_name": "Chippewa Squirrel Rescue",
                "ctf_description": "Race to free the Chippewa squirrels trapped in Acorn Hall.",
                "user_mode": "teams",
                "name": os.environ["CTFD_ADMIN_USER"],
                "email": os.environ["CTFD_ADMIN_EMAIL"],
                "password": os.environ["CTFD_ADMIN_PASSWORD"],
                "ctf_theme": "core-beta",
                "challenge_visibility": "public",
                "account_visibility": "public",
                "score_visibility": "public",
                "registration_visibility": "public",
                "theme_color": "#243044",
            },
        )
    status, body, url = client.open("GET", "/setup")
    if urllib.parse.urlparse(url).path.startswith("/setup") and "Admin Username" in body:
        raise SystemExit("CTFd setup did not finish. Open %s/setup and read the form errors." % client.base)

    client.refresh_csrf()
    if organizer_session(client):
        print("Organizer session is active.")
        return

    print("Logging in as the organizer.")
    _status, body, _url = client.open("GET", "/login")
    client.form(
        "/login",
        {
            "nonce": extract_nonce(body),
            "name": os.environ["CTFD_ADMIN_USER"],
            "password": os.environ["CTFD_ADMIN_PASSWORD"],
        },
    )
    client.refresh_csrf()
    if not organizer_session(client):
        raise SystemExit("Organizer login failed. Use the admin password from the first time you seeded.")


def main() -> None:
    load_env(ROOT / ".env")
    scenario = os.environ.get("SCENARIO_URL", "http://localhost:8080").rstrip("/")
    tries = int(os.environ.get("TRIES", "3"))
    seconds = int(os.environ.get("SECONDS", "300"))
    client = Client(os.environ.get("CTFD_URL", "http://localhost:8000"))
    client.wait_until_up()
    setup_or_login(client)
    ensure_brackets(client)
    door_spec, closet_spec = challenge_text(scenario, tries, seconds)
    upsert_challenge(client, door_spec, scenario, os.environ["DOOR_FLAG"])
    upsert_challenge(client, closet_spec, scenario, os.environ["DISARM_FLAG"])
    try:
        client.api(
            "PATCH",
            "/api/v1/configs",
            {
                "ctf_name": "Chippewa Squirrel Rescue",
                "ctf_description": "Race to free the Chippewa squirrels trapped in Acorn Hall.",
                "team_creation": "false",
            },
        )
        print("Updated the scoreboard title.")
    except RuntimeError as error:
        print("Scoreboard title was left unchanged: %s" % error)
    try:
        ensure_homepage(client, scenario, tries, seconds)
    except RuntimeError as error:
        print("Homepage was left unchanged: %s" % error)
    print("")
    print("Chippewa Squirrel Rescue is ready.")
    print("Scoreboard: %s" % client.base)
    print("Simulator:  %s" % scenario)
    print("Admin user: %s" % os.environ["CTFD_ADMIN_USER"])
    print("Admin password is CTFD_ADMIN_PASSWORD in .env")
    print("")
    print("Organizer answer key. Do not show this to players.")
    print("  Door PIN:     %s" % os.environ["DOOR_CODE"])
    print("  Closet code:  %s" % os.environ["DISARM_CODE"])
    print("  Door flag:    %s" % os.environ["DOOR_FLAG"])
    print("  Closet flag:  %s" % os.environ["DISARM_FLAG"])


if __name__ == "__main__":
    main()
