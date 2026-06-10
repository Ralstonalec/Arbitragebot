"""
The math: de-vig the sharp book's line to get fair probabilities, then
find soft-book prices that beat them (+EV), plus cross-book arbitrage.

Why this is "piggybacking winners": Pinnacle's line is the closest public
thing to the aggregated opinion of winning bettors — it's shaped by sharp
money and rarely beaten at closing. A soft book lagging that line is the
most durable, well-documented edge in sports betting.
"""


def devig_multiplicative(prices: list[float]) -> list[float] | None:
    """Decimal odds -> fair probabilities (proportional vig removal)."""
    if not prices or any(p <= 1.0 for p in prices):
        return None
    implied = [1.0 / p for p in prices]
    total = sum(implied)
    if total <= 0:
        return None
    return [i / total for i in implied]


def extract_h2h(event: dict) -> dict[str, dict[str, float]]:
    """{book_key: {outcome_name: decimal_price}} for the h2h market."""
    out = {}
    for bm in event.get("bookmakers", []):
        for mkt in bm.get("markets", []):
            if mkt.get("key") != "h2h":
                continue
            prices = {o["name"]: float(o["price"]) for o in mkt.get("outcomes", [])}
            if prices:
                out[bm["key"]] = prices
    return out


def fair_probs(books: dict, sharp_book: str) -> dict[str, float] | None:
    """De-vigged probabilities from the sharp book's prices."""
    sharp = books.get(sharp_book)
    if not sharp or len(sharp) < 2:
        return None
    names = sorted(sharp)
    probs = devig_multiplicative([sharp[n] for n in names])
    if probs is None:
        return None
    return dict(zip(names, probs))


def find_ev_bets(books: dict, fair: dict, min_ev: float,
                 max_odds: float, sharp_book: str) -> list[dict]:
    """[{outcome, book, price, fair_prob, ev}] sorted by EV desc."""
    bets = []
    for book, prices in books.items():
        if book == sharp_book:
            continue
        for outcome, price in prices.items():
            p = fair.get(outcome)
            if p is None or price > max_odds:
                continue
            ev = p * price - 1.0
            if ev >= min_ev:
                bets.append({"outcome": outcome, "book": book,
                             "price": price, "fair_prob": p, "ev": ev})
    return sorted(bets, key=lambda b: -b["ev"])


def find_arb(books: dict) -> dict | None:
    """Best price per outcome across books; arb if implied total < 1."""
    outcomes = set()
    for prices in books.values():
        outcomes.update(prices)
    if len(outcomes) < 2:
        return None
    best = {}
    for o in outcomes:
        candidates = [(prices[o], book) for book, prices in books.items() if o in prices]
        if not candidates:
            return None
        best[o] = max(candidates)
    total_implied = sum(1.0 / price for price, _ in best.values())
    if total_implied >= 1.0:
        return None
    return {
        "legs": [{"outcome": o, "price": price, "book": book}
                 for o, (price, book) in best.items()],
        "edge": 1.0 - total_implied,  # guaranteed return on total stake
        "total_implied": total_implied,
    }


def arb_stakes(legs: list[dict], total_stake: float, total_implied: float) -> list[float]:
    """Split total_stake so every outcome pays the same amount."""
    return [round(total_stake * (1.0 / leg["price"]) / total_implied, 2)
            for leg in legs]
