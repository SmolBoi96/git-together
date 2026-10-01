"""Friend matching for a single pool of people.

Gale-Shapley needs two sides (proposers and acceptors). Friend matching has
only one pool, so we use its one-sided generalisation: Irving's stable
roommates algorithm (1985). It finds a pairing where no two people would both
rather be with each other than with their assigned match - if such a pairing
exists. When it does not, we fall back to a greedy pairing that minimises the
combined rank of each pair.
"""

from collections import deque

BYE = "__bye__"  # dummy partner used when the pool has an odd size


def language_score(langs_a, langs_b):
    """Weighted overlap of two top-3 lists: a shared #1 counts more than a shared #3."""
    weights_b = {lang: 3 - i for i, lang in enumerate(langs_b)}
    return sum((3 - i) * weights_b[lang] for i, lang in enumerate(langs_a) if lang in weights_b)


def build_preferences(people, rankings, languages):
    """Turn possibly stale or partial rankings into complete preference lists.

    people:    ordered list of ids in the pool (signup order).
    rankings:  {id: [ids in preference order]} - may be missing, may mention
               people who left, may omit people who joined later.
    languages: {id: [lang1, lang2, lang3]}

    Anyone a person has not ranked yet is appended after their explicit
    ranking, ordered by language overlap (then signup order).
    """
    pool = set(people)
    order = {p: i for i, p in enumerate(people)}
    prefs = {}
    for p in people:
        explicit = [q for q in rankings.get(p, []) if q in pool and q != p]
        seen = set(explicit)
        rest = [q for q in people if q != p and q not in seen]
        rest.sort(key=lambda q: (-language_score(languages.get(p, []), languages.get(q, [])), order[q]))
        prefs[p] = explicit + rest
    return prefs


def stable_roommates(prefs):
    """Irving's algorithm. prefs must be complete lists over an even-sized pool.

    Returns {person: partner} or None if no stable matching exists.
    """
    table = {p: list(lst) for p, lst in prefs.items()}
    rank = {p: {q: i for i, q in enumerate(lst)} for p, lst in prefs.items()}

    def drop(a, b):
        if b in table[a]:
            table[a].remove(b)
        if a in table[b]:
            table[b].remove(a)

    # Phase 1: everyone proposes down their list; each person holds the best offer.
    held_by = {}  # receiver -> proposer currently held
    free = deque(table)
    while free:
        p = free.popleft()
        while True:
            if not table[p]:
                return None
            q = table[p][0]
            current = held_by.get(q)
            if current is None:
                held_by[q] = p
                break
            if rank[q][p] < rank[q][current]:
                held_by[q] = p
                drop(q, current)
                free.append(current)
                break
            drop(p, q)

    # Reduce: q discards everyone it likes less than the proposal it holds.
    for q, p in held_by.items():
        cut = table[q].index(p)
        for worse in table[q][cut + 1:]:
            drop(q, worse)

    # Phase 2: find and eliminate rotations until every list has one entry.
    while True:
        if any(not lst for lst in table.values()):
            return None
        start = next((p for p in table if len(table[p]) > 1), None)
        if start is None:
            break
        xs, seen = [], {}
        x = start
        while x not in seen:
            seen[x] = len(xs)
            xs.append(x)
            x = table[table[x][1]][-1]
        cycle = xs[seen[x]:]
        # Each x_i moves on to their second choice y_{i+1}, who then drops
        # everyone ranked below x_i.
        moves = [(xi, table[xi][1]) for xi in cycle]
        for xi, y in moves:
            if xi not in table[y]:
                # An earlier step in this rotation already emptied a list;
                # the empty-list check above will report no stable matching.
                continue
            cut = table[y].index(xi)
            for worse in table[y][cut + 1:]:
                drop(y, worse)

    match = {p: lst[0] for p, lst in table.items()}
    if any(match[match[p]] != p for p in match):
        return None
    return match


def greedy_match(prefs):
    """Fallback: repeatedly pair the two people with the lowest combined rank."""
    rank = {p: {q: i for i, q in enumerate(lst)} for p, lst in prefs.items()}
    people = list(prefs)
    pairs = sorted(
        ((rank[a][b] + rank[b][a], max(rank[a][b], rank[b][a]), a, b)
         for i, a in enumerate(people) for b in people[i + 1:]),
        key=lambda t: t[:2],
    )
    match = {}
    for _, _, a, b in pairs:
        if a not in match and b not in match:
            match[a], match[b] = b, a
    return match


def compute_matching(people, rankings, languages):
    """Match everyone in the pool.

    Returns (match, method) where match maps id -> partner id (or None for the
    person sitting out when the pool is odd) and method is "stable" or "greedy".
    """
    if len(people) < 2:
        return {p: None for p in people}, "stable"

    prefs = build_preferences(people, rankings, languages)
    if len(people) % 2:
        # Everyone ranks the bye last; the bye prefers the newest signups, who
        # have had the least time to be ranked by others.
        for p in people:
            prefs[p].append(BYE)
        prefs[BYE] = list(reversed(people))

    match = stable_roommates(prefs)
    method = "stable"
    if match is None:
        real = {p: [q for q in lst if q != BYE] for p, lst in prefs.items() if p != BYE}
        match = greedy_match(real)
        method = "greedy"

    result = {p: (None if match.get(p) in (None, BYE) else match[p]) for p in people}
    return result, method
