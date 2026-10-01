import os
import re
import secrets
from functools import wraps

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import db
from matching import build_preferences, compute_matching

LANGUAGES = sorted([
    "Assembly", "Bash", "C", "C#", "C++", "Clojure", "Dart", "Elixir", "Erlang",
    "F#", "Go", "Haskell", "Java", "JavaScript", "Julia", "Kotlin", "Lisp", "Lua",
    "MATLAB", "OCaml", "Perl", "PHP", "Python", "R", "Ruby", "Rust", "Scala",
    "SQL", "Swift", "TypeScript", "Zig",
], key=str.lower)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,20}$")
MIN_PASSWORD = 8


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or _instance_secret(app.instance_path),
        DATABASE=os.path.join(app.instance_path, "git-together.db"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)
    db.init_db(app)
    _register(app)
    return app


def _instance_secret(instance_path):
    path = os.path.join(instance_path, "secret_key")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        return f.read().strip()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def profile_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user["lang1"] is None:
            flash("init your profile first.", "warn")
            return redirect(url_for("profile"))
        return view(*args, **kwargs)
    return login_required(wrapped)


def langs_of(user):
    return [l for l in (user["lang1"], user["lang2"], user["lang3"]) if l]


def _register(app):
    @app.before_request
    def load_user_and_check_csrf():
        uid = session.get("user_id")
        g.user = None
        if uid is not None:
            g.user = db.get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
            if g.user is None:
                session.clear()
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        if request.method == "POST":
            if request.form.get("csrf") != session["csrf"]:
                abort(400, "bad csrf token")

    @app.context_processor
    def inject():
        return {"csrf_token": session.get("csrf", ""), "user": g.get("user")}

    @app.route("/")
    def index():
        if g.user is None:
            return redirect(url_for("login"))
        if g.user["lang1"] is None:
            return redirect(url_for("profile"))
        return redirect(url_for("rank"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        username = ""
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            error = None
            if not USERNAME_RE.match(username):
                error = "username must be 3-20 chars of [A-Za-z0-9_-]"
            elif len(password) < MIN_PASSWORD:
                error = f"password must be at least {MIN_PASSWORD} chars"
            elif password != request.form.get("confirm", ""):
                error = "passwords do not match"
            if error is None:
                conn = db.get_db()
                try:
                    with conn:
                        cur = conn.execute(
                            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                            (username, generate_password_hash(password)),
                        )
                except conn.IntegrityError:
                    error = f"user '{username}' already exists"
                else:
                    session.clear()
                    session["user_id"] = cur.lastrowid
                    flash(f"user {username} created. welcome aboard.", "ok")
                    return redirect(url_for("profile"))
            flash(error, "err")
        return render_template("register.html", username=username)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            user = db.get_db().execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            if user is None or not check_password_hash(user["password_hash"], request.form.get("password", "")):
                flash("permission denied (publickey,password).", "err")
            else:
                session.clear()
                session["user_id"] = user["id"]
                if user["lang1"] is None:
                    return redirect(url_for("profile"))
                flash("authenticated. re-sort your list - the pool may have changed.", "ok")
                return redirect(url_for("rank"))
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        current = langs_of(g.user)
        if request.method == "POST":
            picks = [request.form.get(f"lang{i}", "") for i in (1, 2, 3)]
            current = picks
            if any(p not in LANGUAGES for p in picks):
                flash("pick a language from the list for all three slots.", "err")
            elif len(set(picks)) != 3:
                flash("no duplicates - three different languages please.", "err")
            else:
                first_time = g.user["lang1"] is None
                conn = db.get_db()
                with conn:
                    conn.execute(
                        "UPDATE users SET lang1 = ?, lang2 = ?, lang3 = ? WHERE id = ?",
                        (*picks, g.user["id"]),
                    )
                flash("profile committed.", "ok")
                return redirect(url_for("rank") if first_time else url_for("profile"))
        return render_template("profile.html", languages=LANGUAGES, current=current)

    @app.route("/rank", methods=["GET", "POST"])
    @profile_required
    def rank():
        people = db.pool()
        by_id = {u["id"]: u for u in people}
        me = g.user["id"]

        if request.method == "POST":
            seen, order = set(), []
            for raw in request.form.getlist("order"):
                if raw.isdigit() and int(raw) in by_id and int(raw) != me and int(raw) not in seen:
                    seen.add(int(raw))
                    order.append(int(raw))
            db.save_ranking(me, order)
            return redirect(url_for("match"))

        ids = [u["id"] for u in people]
        saved = db.rankings_for([me]).get(me, [])
        languages = {u["id"]: langs_of(u) for u in people}
        prefs = build_preferences(ids, {me: saved}, languages).get(me, [])
        mine = set(langs_of(g.user))
        others = [
            {
                "id": uid,
                "username": by_id[uid]["username"],
                "langs": languages[uid],
                "shared": [l for l in languages[uid] if l in mine],
                "new": uid not in saved,
            }
            for uid in prefs
        ]
        return render_template("rank.html", others=others, has_saved=bool(saved))

    @app.route("/match")
    @profile_required
    def match():
        people = db.pool()
        by_id = {u["id"]: u for u in people}
        ids = list(by_id)
        rankings = db.rankings_for(ids)
        languages = {uid: langs_of(u) for uid, u in by_id.items()}
        result, method = compute_matching(ids, rankings, languages)

        me = g.user["id"]
        partner_id = result.get(me)
        partner = None
        if partner_id is not None:
            prefs = build_preferences(ids, rankings, languages)
            p = by_id[partner_id]
            partner = {
                "username": p["username"],
                "langs": languages[partner_id],
                "shared": [l for l in languages[partner_id] if l in languages[me]],
                "my_rank": prefs[me].index(partner_id) + 1,
            }
        stats = {
            "pool": len(ids),
            "ranked": sum(1 for u in people if u["ranked_at"]),
            "method": method,
        }
        return render_template("match.html", partner=partner, stats=stats)


if __name__ == "__main__":
    create_app().run(debug=True)
