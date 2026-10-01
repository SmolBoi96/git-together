import re

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"DATABASE": str(tmp_path / "test.db")})


class Dev:
    """A browser session for one user."""

    def __init__(self, app, name, langs=("Rust", "Go", "C"), password="hunter222"):
        self.client = app.test_client()
        self.name = name
        self.password = password
        r = self.post("/register", username=name, password=password, confirm=password)
        assert r.status_code == 302
        if langs:
            self.post("/profile", lang1=langs[0], lang2=langs[1], lang3=langs[2])

    def csrf(self):
        page = self.client.get("/login" if not self._logged_in() else "/profile").text
        return re.search(r'name="csrf" value="(\w+)"', page).group(1)

    def _logged_in(self):
        with self.client.session_transaction() as s:
            return "user_id" in s

    def post(self, url, follow=False, **data):
        data.setdefault("csrf", self.csrf())
        return self.client.post(url, data=data, follow_redirects=follow)

    def rank(self, *names):
        page = self.client.get("/rank").text
        ids = dict(re.findall(r'data-id="(\d+)">.*?<span class="who">(\w+)</span>', page, re.S))
        by_name = {v: k for k, v in ids.items()}
        return self.post("/rank", order=[by_name[n] for n in names])

    def partner(self):
        page = self.client.get("/match").text
        m = re.search(r'<span class="them">(\w+)</span>', page)
        return m.group(1) if m else None


def test_requires_login(app):
    c = app.test_client()
    for url in ("/profile", "/rank", "/match"):
        assert c.get(url).headers["Location"].endswith("/login")


def test_post_without_csrf_rejected(app):
    c = app.test_client()
    r = c.post("/register", data={"username": "eve", "password": "hunter222", "confirm": "hunter222"})
    assert r.status_code == 400


def test_register_validation_and_duplicates(app):
    Dev(app, "alice")
    c = Dev.__new__(Dev)
    c.client = app.test_client()
    assert "already exists" in c.post("/register", follow=True, username="ALICE",
                                      password="hunter222", confirm="hunter222").text
    assert "at least 8" in c.post("/register", follow=True, username="bob",
                                  password="short", confirm="short").text
    assert "3-20 chars" in c.post("/register", follow=True, username="b!",
                                  password="hunter222", confirm="hunter222").text


def test_register_error_keeps_username(app):
    c = Dev.__new__(Dev)
    c.client = app.test_client()
    r = c.post("/register", username="carol", password="hunter222", confirm="hunter333")
    assert "passwords do not match" in r.text
    assert 'name="username" value="carol"' in r.text


def test_profile_error_keeps_picks(app):
    bob = Dev(app, "bob", langs=None)
    r = bob.post("/profile", lang1="Rust", lang2="Go", lang3="Rust")
    assert "no duplicates" in r.text
    selected = re.findall(r'<option value="(\w*)"[^>]*selected', r.text)
    assert selected == ["Rust", "Go", "Rust"]


def test_login_logout_and_bad_password(app):
    alice = Dev(app, "alice")
    alice.post("/logout")
    assert alice.client.get("/rank").status_code == 302
    r = alice.post("/login", follow=True, username="alice", password="wrongpass")
    assert "permission denied" in r.text
    r = alice.post("/login", username="alice", password="hunter222")
    assert r.headers["Location"].endswith("/rank")


def test_profile_required_before_ranking(app):
    bob = Dev(app, "bob", langs=None)
    assert bob.client.get("/rank").headers["Location"].endswith("/profile")
    r = bob.post("/profile", follow=True, lang1="Rust", lang2="Rust", lang3="Go")
    assert "no duplicates" in r.text
    r = bob.post("/profile", follow=True, lang1="Rust", lang2="Brainfuck", lang3="Go")
    assert "pick a language" in r.text


def test_full_matching_flow(app):
    alice = Dev(app, "alice", ("Rust", "Go", "C"))
    bob = Dev(app, "bob", ("Python", "SQL", "R"))
    carol = Dev(app, "carol", ("Rust", "C", "Zig"))
    dave = Dev(app, "dave", ("Python", "R", "Julia"))

    # Before anyone ranks, defaults come from language overlap.
    assert alice.partner() == "carol"
    assert bob.partner() == "dave"

    # Explicit rankings override language overlap.
    alice.rank("bob", "dave", "carol")
    bob.rank("alice", "carol", "dave")
    carol.rank("dave", "alice", "bob")
    dave.rank("carol", "bob", "alice")
    assert alice.partner() == "bob"
    assert bob.partner() == "alice"
    assert carol.partner() == "dave"

    # A newcomer shows up on everyone's rank page marked as new.
    Dev(app, "erin", ("Go", "Rust", "C"))
    page = alice.client.get("/rank").text
    assert "erin" in page and 'class="badge">new' in page

    # Five devs: exactly one is benched.
    benched = [d for d in (alice, bob, carol, dave) if d.partner() is None]
    assert len(benched) <= 1


def test_rank_ignores_unknown_and_self_ids(app):
    alice = Dev(app, "alice")
    Dev(app, "bob")
    r = alice.post("/rank", order=["1", "999", "abc", "2", "2"])
    assert r.status_code == 302
    assert alice.partner() == "bob"
