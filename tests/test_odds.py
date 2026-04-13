"""Unit tests for odds.py — 6 cases as specified in the plan."""
from __future__ import annotations

import pytest
from odds import EntryInput, calc_payouts, find_winners, PERIOD_SECONDS, PERIOD_MULT


def make_entries(*args: tuple) -> list[EntryInput]:
    """Helper: args are (entry_id, period_key, weight) tuples, amount=100 fixed."""
    return [EntryInput(entry_id=eid, period_key=pk, amount=100, weight=w) for eid, pk, w in args]


# Case 1: single winner, k=1 (elapsed == winning period exactly)
def test_single_winner_k1():
    elapsed = float(PERIOD_SECONDS["1w"])  # 604800s
    entries = make_entries(
        (1, "1w", 64),
        (2, "1mo", 36),
    )
    total_pool = sum(e.amount for e in entries)  # 200
    alive = ["1w", "1mo", "3mo", "6mo", "1y"]
    winners = find_winners(elapsed, alive)
    assert winners == ["1w"]

    payouts = calc_payouts(entries, winners, elapsed, total_pool)
    # k=1, M=1.7, entry 1 gets all base share (it's the only winner entry)
    # base_share_1 = 200 * (64*100) / (64*100) = 200
    # payout = round(1.0 * 1.7 * 200) = 340
    assert payouts[1] == 340
    assert payouts[2] == 0


# Case 2: single winner, k < 1 (elapsed != winning period)
def test_single_winner_k_partial():
    # elapsed = 700000s: closer to "1w" (604800) than to "2w" (1209600)
    # dist_1w = |604800 - 700000| = 95200
    # dist_2w = |1209600 - 700000| = 509600  → "1w" wins
    w_sec = PERIOD_SECONDS["1w"]  # 604800
    elapsed = 700_000.0
    k = min(w_sec, elapsed) / max(w_sec, elapsed)  # 604800/700000

    entries = make_entries(
        (1, "1w", 64),
        (2, "2w", 49),
    )
    total_pool = 200
    alive = ["1w", "2w", "1mo", "3mo", "6mo", "1y"]
    winners = find_winners(elapsed, alive)
    assert winners == ["1w"]

    payouts = calc_payouts(entries, winners, elapsed, total_pool)
    # base_share_1 = 200 * (64*100)/(64*100) = 200  (only winner group)
    # payout = round(k * 1.7 * 200)
    assert payouts[1] == round(k * PERIOD_MULT["1w"] * 200)
    assert payouts[2] == 0


# Case 3: tie, both groups have bets
def test_tie_both_groups():
    # Equidistant between "1w" (604800) and "2w" (1209600)
    # midpoint = (604800 + 1209600) / 2 = 907200
    elapsed = (PERIOD_SECONDS["1w"] + PERIOD_SECONDS["2w"]) / 2.0

    entries = make_entries(
        (1, "1w", 64),
        (2, "2w", 64),
    )
    total_pool = 200
    alive = ["1w", "2w", "1mo", "3mo", "6mo", "1y"]
    winners = find_winners(elapsed, alive)
    assert set(winners) == {"1w", "2w"}

    payouts = calc_payouts(entries, winners, elapsed, total_pool)
    # Both groups get some payout (non-zero)
    assert payouts[1] > 0
    assert payouts[2] > 0


# Case 4: tie, only one group has bets → all goes to that group
def test_tie_one_side_empty():
    elapsed = (PERIOD_SECONDS["1w"] + PERIOD_SECONDS["2w"]) / 2.0

    # Only "2w" has a bet
    entries = make_entries(
        (1, "2w", 64),
    )
    total_pool = 100
    alive = ["1w", "2w", "1mo", "3mo", "6mo", "1y"]
    winners = find_winners(elapsed, alive)
    assert set(winners) == {"1w", "2w"}

    payouts = calc_payouts(entries, winners, elapsed, total_pool)
    # Entry 1 ("2w") should get all of the pool
    assert payouts[1] > 0


# Case 5: winning period has no bets → return stake to all
def test_no_bets_on_winner_returns_stake():
    elapsed = float(PERIOD_SECONDS["1w"])

    # Nobody bet on "1w"
    entries = make_entries(
        (1, "1mo", 36),
        (2, "3mo", 25),
    )
    total_pool = 200
    alive = ["1w", "1mo", "3mo", "6mo", "1y"]
    winners = find_winners(elapsed, alive)
    assert winners == ["1w"]

    payouts = calc_payouts(entries, winners, elapsed, total_pool)
    # Everyone gets their stake back
    assert payouts[1] == 100
    assert payouts[2] == 100


# Case 6: period multiplier causes house deficit (sum of payouts > pool)
def test_period_multiplier_house_deficit():
    elapsed = float(PERIOD_SECONDS["1y"])  # exactly 1 year, k=1

    entries = make_entries(
        (1, "1y", 64),
        (2, "1y", 64),
    )
    total_pool = 200
    alive = ["1y"]
    winners = find_winners(elapsed, alive)
    assert winners == ["1y"]

    payouts = calc_payouts(entries, winners, elapsed, total_pool)
    total_paid = sum(payouts.values())
    # M=15.0x, k=1 → each gets round(1.0 * 15.0 * 100) = 1500
    # total = 3000, pool = 200 → house deficit confirmed
    assert total_paid > total_pool, f"Expected payout > pool, got {total_paid} <= {total_pool}"
    assert payouts[1] == 1500
    assert payouts[2] == 1500
