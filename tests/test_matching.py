import random

from matching import (
    build_preferences,
    compute_matching,
    language_score,
    stable_roommates,
)


def perfect_matchings(people):
    if not people:
        yield {}
        return
    a, rest = people[0], people[1:]
    for i, b in enumerate(rest):
        for m in perfect_matchings(rest[:i] + rest[i + 1:]):
            yield {**m, a: b, b: a}


def is_stable(match, prefs):
    rank = {p: {q: i for i, q in enumerate(lst)} for p, lst in prefs.items()}
    for a in prefs:
        for b in prefs:
            if a != b and match[a] != b:
                if rank[a][b] < rank[a][match[a]] and rank[b][a] < rank[b][match[b]]:
                    return False
    return True


def random_prefs(n, rng):
    people = list(range(n))
    return {p: rng.sample([q for q in people if q != p], n - 1) for p in people}


def test_irving_matches_brute_force():
    rng = random.Random(2610)
    for n in (2, 4, 6, 8):
        for _ in range(200):
            prefs = random_prefs(n, rng)
            result = stable_roommates(prefs)
            any_stable = any(is_stable(m, prefs) for m in perfect_matchings(list(prefs)))
            if result is None:
                assert not any_stable, prefs
            else:
                assert is_stable(result, prefs), prefs


def test_mutual_first_choices_pair_up():
    prefs = {
        "a": ["b", "c", "d"],
        "b": ["a", "d", "c"],
        "c": ["d", "a", "b"],
        "d": ["c", "b", "a"],
    }
    assert stable_roommates(prefs) == {"a": "b", "b": "a", "c": "d", "d": "c"}


def test_no_stable_matching_falls_back_to_greedy():
    # Classic cyclic instance: a, b, c each chase the next; everyone dislikes d.
    rankings = {
        "a": ["b", "c", "d"],
        "b": ["c", "a", "d"],
        "c": ["a", "b", "d"],
        "d": ["a", "b", "c"],
    }
    people = list(rankings)
    match, method = compute_matching(people, rankings, {})
    assert method == "greedy"
    assert all(match[match[p]] == p for p in people)


def test_odd_pool_leaves_exactly_one_out():
    rng = random.Random(7)
    people = list(range(5))
    rankings = random_prefs(5, rng)
    match, _ = compute_matching(people, rankings, {})
    assert sum(1 for p in people if match[p] is None) == 1
    for p in people:
        if match[p] is not None:
            assert match[match[p]] == p


def test_tiny_pools():
    assert compute_matching([], {}, {}) == ({}, "stable")
    assert compute_matching([1], {}, {}) == ({1: None}, "stable")
    assert compute_matching([1, 2], {}, {})[0] == {1: 2, 2: 1}


def test_language_score_weights_rank():
    assert language_score(["Rust", "Go", "C"], ["Rust", "Go", "C"]) == 9 + 4 + 1
    assert language_score(["Rust"], ["Python"]) == 0
    assert language_score(["Rust", "Go", "C"], ["C", "Go", "Rust"]) == 3 + 4 + 3


def test_build_preferences_fills_gaps_by_language():
    people = [1, 2, 3, 4]
    langs = {1: ["Rust", "Go", "C"], 2: ["Java", "C#", "Kotlin"], 3: ["Rust", "C", "Zig"], 4: ["Go"]}
    # 1 has ranked only 4 (plus a user who no longer exists); 2 and 3 are filled in.
    prefs = build_preferences(people, {1: [4, 99]}, langs)
    assert prefs[1] == [4, 3, 2]
    # 2 hasn't ranked anyone: no overlaps, so signup order.
    assert prefs[2] == [1, 3, 4]
