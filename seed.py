"""Fill the database with demo devs: python seed.py [--count N] [--no-rank]

Every demo account uses the password "password123".
"""

import argparse
import random

from werkzeug.security import generate_password_hash

import db
from app import LANGUAGES, create_app

NAMES = [
    "ada", "linus", "grace", "dennis", "ken", "margaret", "guido", "bjarne",
    "barbara", "donald", "frances", "rob", "radia", "james", "anders", "yukihiro",
    "sophie", "brendan", "hedy",
]
PASSWORD = "password123"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=9, help=f"number of devs (max {len(NAMES)})")
    parser.add_argument("--no-rank", action="store_true", help="leave rankings empty")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    app = create_app()
    with app.app_context():
        conn = db.get_db()
        pw = generate_password_hash(PASSWORD)
        created = []
        with conn:
            for name in NAMES[: args.count]:
                langs = rng.sample(LANGUAGES, 3)
                cur = conn.execute(
                    "INSERT OR IGNORE INTO users (username, password_hash, lang1, lang2, lang3) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (name, pw, *langs),
                )
                if cur.rowcount:
                    created.append(name)
        if not args.no_rank:
            ids = [u["id"] for u in db.pool()]
            for name in created:
                me = conn.execute("SELECT id FROM users WHERE username = ?", (name,)).fetchone()["id"]
                others = [i for i in ids if i != me]
                rng.shuffle(others)
                db.save_ranking(me, others)
        print(f"created {len(created)} devs: {', '.join(created) or '-'} (password: {PASSWORD})")


if __name__ == "__main__":
    main()
