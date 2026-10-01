# git-together

```
      _ _       _                 _   _
 __ _(_) |_ ___| |_ ___  __ _ ___| |_| |_  ___ _ _
/ _` | |  _|___|  _/ _ \/ _` / -_)  _| ' \/ -_) '_|
\__, |_|\__|    \__\___/\__, \___|\__|_||_\___|_|
|___/                   |___/
```

A tiny friend-matching app for a small group of coders (fewer than 20). Everyone
lists their top 3 programming languages, ranks everyone else, and gets paired
up with a stable matching.

The UI is a terminal: the profile page is `vim ~/.profile`, ranking is a
`git rebase -i` todo list (vim keys included), and your match is shown as a diff.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/flask --app app run          # http://127.0.0.1:5000
```

Optional demo data. The accounts share a random password, printed when the
script finishes (pass `--password` to choose one):

```bash
.venv/bin/python seed.py --count 9     # --no-rank to leave rankings empty
```

Run the tests:

```bash
.venv/bin/python -m pytest
```

## How it works

1. **Register / log in.** Passwords are hashed with Werkzeug (scrypt/pbkdf2);
   every form carries a CSRF token. After 5 failed logins for a username, or 20
   from one IP, `/login` returns 429 for 15 minutes.
2. **Profile.** Pick your top 3 languages (ordered, no duplicates).
3. **Rank.** Every login drops you on the rank page so you can re-sort the
   pool. Reorder by dragging, with the arrow buttons, or with vim keys
   (`j`/`k` move the cursor, `J`/`K` move the line, `:wq` saves). Devs who
   joined since your last ranking are tagged `new`.
4. **Match.** Saving takes you to your match, recomputed from everyone's
   latest rankings each time the page loads.

### The matching algorithm

Gale–Shapley needs two separate groups (proposers and acceptors). Friend
matching has a single pool, so `matching.py` uses its one-group version,
**Irving's stable roommates algorithm**. It finds a pairing where no two people
would both rather be with each other than with their current match.

* **Gaps in rankings.** Anyone you haven't ranked yet (new signups, or
  everyone if you've never ranked) is slotted in after your explicit ranking,
  ordered by weighted language overlap: a shared #1 language counts more than
  a shared #3.
* **Odd pool size.** A dummy "bye" partner is added, and everyone ranks it
  last. Whoever gets matched to it sits out this round, which favours the
  newest signups.
* **No stable matching.** Some ranking sets have no stable pairing at all, for
  example a ranks b first, b ranks c first, and c ranks a first. When that
  happens the app falls back to a greedy pairing that minimises each pair's
  combined rank, and shows a warning.

`tests/test_matching.py` checks the algorithm against brute force on 800
random preference sets.

## Layout

```
app.py          Flask app factory and routes
db.py           SQLite schema and queries (users, rankings)
matching.py     preference building, Irving's algorithm, greedy fallback
seed.py         demo data
templates/      Jinja templates
static/         style.css, rank.js (drag + vim keys)
tests/          pytest suite
```

Data lives in `instance/git-together.db`. A random secret key is generated
into `instance/secret_key` on first run; set `SECRET_KEY` to override it.
