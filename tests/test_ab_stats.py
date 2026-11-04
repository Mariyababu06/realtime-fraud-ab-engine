from pipeline.ab_stats import srm_check, two_proportion_test, verdict


def test_known_proportion_test():
    r = two_proportion_test(50, 100, 70, 100)
    assert abs(r["z"] - 2.89) < 0.05 and r["p_value"] < 0.01 and r["ci_low"] > 0


def test_no_difference_is_not_significant():
    assert two_proportion_test(50, 100, 50, 100)["p_value"] > 0.99


def test_srm_detects_broken_split():
    assert srm_check(5000, 5050)["ok"]
    assert not srm_check(4000, 6000)["ok"]


def test_verdict_picks_b_when_better():
    a = {"tp": 40, "fn": 60, "fp": 500, "tn": 99_400}
    b = {"tp": 90, "fn": 10, "fp": 100, "tn": 99_800}
    assert "Variant B detects significantly more" in verdict({"A": a, "B": b})["text"]
