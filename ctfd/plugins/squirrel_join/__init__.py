"""A four-step start: how the game works, your name, your team, then play."""

import os
import re
import secrets

from flask import redirect, render_template, request, session

from CTFd.cache import clear_standings, clear_team_session, clear_user_session
from CTFd.models import Brackets, Teams, Users, db
from CTFd.plugins import (
    override_template,
    register_plugin_assets_directory,
    register_plugin_script,
    register_plugin_stylesheet,
    register_user_page_menu_bar,
)
from CTFd.utils import get_config, set_config
from CTFd.utils.decorators import ratelimit
from CTFd.utils.security.auth import login_user
from CTFd.utils.user import authed, get_current_user, is_admin

LANES = ("Red", "Blue")
SCENARIO_URL = os.environ.get("SCENARIO_URL", "http://localhost:8080").rstrip("/")


def load(app):
    register_plugin_assets_directory(app, base_path="/plugins/squirrel_join/assets/")
    register_plugin_stylesheet("/plugins/squirrel_join/assets/inside.css?v=9")
    register_plugin_script("/plugins/squirrel_join/assets/hint.js?v=8")
    register_user_page_menu_bar("The building", SCENARIO_URL)
    plugin_dir = os.path.dirname(__file__)
    for name in ("base.html", "challenges.html", "challenge.html"):
        with open(os.path.join(plugin_dir, name), encoding="utf-8") as template:
            override_template(name, template.read())

    def ensure_lanes():
        if not get_config("setup"):
            return
        if get_config("team_creation") is not False:
            set_config("team_creation", "false")
        if get_config("team_disbanding") != "disabled":
            set_config("team_disbanding", "disabled")
        if get_config("name_changes") is not False:
            set_config("name_changes", "false")
        for name in LANES:
            bracket = Brackets.query.filter_by(name=name, type="teams").first()
            team = Teams.query.filter_by(name=name).first()
            if team is None:
                team = Teams(
                    name=name,
                    password=secrets.token_urlsafe(24),
                    hidden=False,
                    banned=False,
                )
                db.session.add(team)
            if bracket is not None and team.bracket_id != bracket.id:
                team.bracket_id = bracket.id
            if team.captain_id is not None:
                team.captain_id = None
        db.session.commit()

    def email_for(name):
        slug = re.sub(r"[^a-z0-9]", "", name.lower()) or "squirrel"
        slug = slug[:40]
        number = 1
        while True:
            local = slug if number == 1 else "%s%s" % (slug, number)
            candidate = "%s@squirrels.club" % local
            if Users.query.filter_by(email=candidate).first() is None:
                return candidate
            number += 1

    def place_on_team(user, team):
        user.team_id = team.id
        db.session.commit()
        clear_user_session(user_id=user.id)
        clear_team_session(team_id=team.id)
        clear_standings()

    def lane_counts():
        counts = {}
        for name in LANES:
            team = Teams.query.filter_by(name=name).first()
            counts[name] = len(team.members) if team is not None else 0
        return counts

    def render_join(error="", name="", team="", step="story"):
        user = get_current_user()
        return render_template(
            "plugins/squirrel_join/join.html",
            error=error,
            name=name,
            team=team,
            step=step,
            counts=lane_counts(),
            signed_in=bool(user),
            admin=is_admin(),
            player_name=user.name if user else "",
            nonce=session.get("nonce", ""),
            scenario_url=SCENARIO_URL,
        )

    @app.before_request
    def send_players_to_the_lanes():
        if request.method != "GET":
            return None
        path = request.path.rstrip("/") or "/"
        if path in ("/register", "/teams/new", "/teams/join"):
            return redirect("/join")
        if path in ("/", "/team"):
            user = get_current_user()
            if user is None or user.team_id is None:
                return redirect("/join")
        return None

    @app.route("/join", methods=["GET", "POST"])
    @ratelimit(method="POST", limit=10, interval=60)
    def join_lane():
        ensure_lanes()
        user = get_current_user()
        if user is not None and user.team_id:
            return redirect("/challenges")
        if get_config("registration_visibility") not in (None, "public") and not authed():
            return render_join(error="Joining is closed right now. Ask the organizer.")

        if request.method != "POST":
            return render_join()

        team_name = request.form.get("team", "").strip()
        if team_name not in LANES:
            return render_join(error="Tap Red or Blue.", step="team")
        team = Teams.query.filter_by(name=team_name).first()
        if team is None:
            return render_join(error="That team is not ready yet. Ask the organizer to refresh the scoreboard.", team=team_name, step="team")

        if user is None:
            name = request.form.get("name", "").strip()
            password = request.form.get("password", "").strip()
            if not name:
                return render_join(error="Type the name you want on the scoreboard.", team=team_name, step="name")
            if len(name) > 24:
                return render_join(error="Use a shorter name. 24 characters is the limit.", name=name, team=team_name, step="name")
            if "@" in name:
                return render_join(error="Use a name, not an email address.", name=name, team=team_name, step="name")
            if len(password) < 4:
                return render_join(error="Use a password of at least 4 characters.", name=name, team=team_name, step="name")
            if len(password) > 128:
                return render_join(error="That password is too long.", name=name, team=team_name, step="name")
            taken = Users.query.filter(db.func.lower(Users.name) == name.lower()).first()
            if taken is not None:
                return render_join(error="That name is taken. Try another.", name=name, team=team_name, step="name")
            user = Users(
                name=name,
                email=email_for(name),
                password=password,
                verified=True,
            )
            db.session.add(user)
            db.session.commit()
            login_user(user)

        place_on_team(user, team)
        return redirect("/challenges")

    with app.app_context():
        try:
            ensure_lanes()
        except Exception as error:  # noqa: BLE001 - the database may not be ready on first boot
            print("squirrel join: Red and Blue will be created on the next visit (%s)" % error)
