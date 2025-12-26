from typing import Optional, Tuple


def implied_prob_from_odds(odds: Optional[float]) -> Optional[float]:
    if not odds or odds <= 0:
        return None
    return 1.0 / odds


def value_score(model_prob: Optional[float], odds: Optional[float]) -> Optional[float]:
    if model_prob is None or odds is None:
        return None
    imp = implied_prob_from_odds(odds)
    if imp is None:
        return None
    return round(model_prob * odds - 1, 4)


def pick_best_value(prob_home: float, prob_draw: float, prob_away: float, odds_home, odds_draw, odds_away) -> Tuple[str, Optional[float]]:
    options = {
        "home": value_score(prob_home, odds_home),
        "draw": value_score(prob_draw, odds_draw),
        "away": value_score(prob_away, odds_away),
    }
    best_label = max(options, key=lambda k: options[k] if options[k] is not None else -1)
    return best_label, options[best_label]
