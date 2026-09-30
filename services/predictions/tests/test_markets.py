import pytest
from predictor.betting.staking import kelly_fraction, stake_fraction
from predictor.betting.value import ev, find_value
from predictor.markets.devig import devig, margin
from predictor.markets.scorelines import market_groups, markets, outcome, poisson_grid


def test_grid_is_a_distribution_and_books_sum_to_one():
    grid = poisson_grid(1.6, 1.1, rho=-0.1)
    assert grid.sum() == pytest.approx(1)
    probs = markets(grid)
    for group in market_groups():
        assert sum(probs[m] for m in group) == pytest.approx(1), group


def test_markets_agree_with_hand_computed_poisson():
    probs = markets(poisson_grid(1.5, 1.0))
    # P(0 goals total) = e^-2.5 for independent Poissons with rates summing to 2.5
    assert probs["under_0.5"] == pytest.approx(0.0821, abs=1e-4)
    assert probs["home"] > probs["away"]
    assert probs["ah_home_-0.5"] == pytest.approx(probs["home"])
    assert probs["ah_away_+0.5"] == pytest.approx(probs["draw_or_away"])


@pytest.mark.parametrize(
    "market, hg, ag, expected",
    [
        ("home", 2, 1, 1),
        ("draw", 2, 1, 0),
        ("over_2.5", 2, 1, 1),
        ("under_2.5", 2, 1, 0),
        ("btts_yes", 1, 0, 0),
        ("dnb_home", 1, 1, None),
        ("dnb_away", 0, 1, 1),
        ("ah_home_-1.5", 2, 1, 0),
        ("ah_home_-1.5", 3, 1, 1),
        ("ah_away_+1.5", 2, 1, 1),
        ("correct_score", 1, 0, None),
    ],
)
def test_outcome_settles_markets(market, hg, ag, expected):
    assert outcome(market, hg, ag) == expected


@pytest.mark.parametrize("method", ["proportional", "power"])
def test_devig_removes_margin(method):
    odds = [1.9, 3.6, 4.2]
    assert margin(odds) > 0
    fair = devig(odds, method)
    assert sum(fair) == pytest.approx(1)
    assert all(f < 1 / o for f, o in zip(fair, odds))  # margin taken off every outcome
    assert fair[0] > fair[1] > fair[2]


def test_power_devig_shades_the_longshot_more():
    odds = [1.3, 5.0, 11.0]
    prop, power = devig(odds, "proportional"), devig(odds, "power")
    assert power[2] < prop[2] and power[0] > prop[0]


def test_find_value_needs_positive_ev_and_ranks_by_probability():
    probs = {"home": 0.55, "draw": 0.25, "away": 0.20, "over_1.5": 0.81, "under_1.5": 0.19}
    odds = {"home": 2.0, "draw": 3.5, "away": 4.5, "over_1.5": 1.30, "under_1.5": 3.4}
    picks = find_value(probs, odds)
    assert [p.market for p in picks] == ["over_1.5", "home"]  # draw/away/under have EV < 0
    assert picks[0].ev == pytest.approx(0.81 * 1.30 - 1)
    # The example from the design: model 81% vs a book implying ~72% once devigged.
    assert picks[0].fair_prob == pytest.approx(0.7234, abs=1e-3)


def test_short_price_favourite_is_not_value_despite_high_probability():
    assert ev(0.93, 1.05) < 0
    assert find_value({"over_0.5": 0.93}, {"over_0.5": 1.05}) == []


def test_fractional_kelly_is_scaled_and_capped():
    assert kelly_fraction(0.5, 2.0) == 0
    assert kelly_fraction(0.6, 2.0) == pytest.approx(0.2)
    assert stake_fraction(0.6, 2.0) == pytest.approx(0.05)  # 0.25 * 0.2
    assert stake_fraction(0.9, 2.0) == 0.05  # capped
