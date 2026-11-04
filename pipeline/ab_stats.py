"""Experiment statistics. Transaction-level tests are exploratory; prefer user-cluster bootstrap for inference."""
import math
import random


def _norm_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2))


def two_proportion_test(x_a: int, n_a: int, x_b: int, n_b: int) -> dict:
    """Classic transaction-level two-proportion test; invalid for repeated correlated events per user."""
    if min(n_a, n_b) <= 0 or min(x_a, x_b) < 0 or x_a > n_a or x_b > n_b:
        return {"rate_a": float("nan"), "rate_b": float("nan"), "diff": float("nan"), "ci_low": float("nan"),
                "ci_high": float("nan"), "z": float("nan"), "p_value": float("nan")}
    p_a, p_b = x_a / n_a, x_b / n_b
    pooled = (x_a + x_b) / (n_a + n_b)
    se_pool = math.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z = (p_b - p_a) / se_pool if se_pool > 0 else 0.0
    se = math.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    diff = p_b - p_a
    return {"rate_a": p_a, "rate_b": p_b, "diff": diff, "ci_low": diff - 1.96 * se, "ci_high": diff + 1.96 * se,
            "z": z, "p_value": 2 * _norm_sf(abs(z))}


def cluster_bootstrap_rate_difference(rows, *, user_col="orig_id_masked", variant_col="variant",
                                      outcome_col="isFraud", flagged_col="flagged", iterations=2000,
                                      seed=2026):
    """Bootstrap users (not transactions) and estimate difference in user-level fraud recall.

    Input is an iterable of mappings/dataframe records. Recall per user is fraction of that user's fraud
    events detected; each user receives equal weight. Returns percentile CI and a two-sided bootstrap p-value
    for the difference. Use pre-registered metrics and a production-grade stats package for final inference.
    """
    records = list(rows.to_dict("records") if hasattr(rows, "to_dict") else rows)
    by_variant = {"A": {}, "B": {}}
    for row in records:
        variant = row[variant_col]
        if variant not in by_variant:
            continue
        user = str(row[user_col])
        entry = by_variant[variant].setdefault(user, [0, 0])
        if int(row[outcome_col]) == 1:
            entry[1] += 1
            entry[0] += int(row[flagged_col]) == 1
    rates = {}
    for variant, users in by_variant.items():
        rates[variant] = [detected / fraud for detected, fraud in users.values() if fraud]
    if not rates["A"] or not rates["B"]:
        return {"diff": float("nan"), "ci_low": float("nan"), "ci_high": float("nan"),
                "p_value": float("nan"), "users_a": len(rates["A"]), "users_b": len(rates["B"])}
    observed = sum(rates["B"]) / len(rates["B"]) - sum(rates["A"]) / len(rates["A"])
    rng = random.Random(seed)
    diffs = []
    for _ in range(max(100, iterations)):
        a = [rng.choice(rates["A"]) for _ in rates["A"]]
        b = [rng.choice(rates["B"]) for _ in rates["B"]]
        diffs.append(sum(b) / len(b) - sum(a) / len(a))
    diffs.sort()
    lo = diffs[int(0.025 * (len(diffs) - 1))]
    hi = diffs[int(0.975 * (len(diffs) - 1))]
    p = min(1.0, 2 * min(sum(d <= 0 for d in diffs) / len(diffs), sum(d >= 0 for d in diffs) / len(diffs)))
    return {"diff": observed, "ci_low": lo, "ci_high": hi, "p_value": p,
            "users_a": len(rates["A"]), "users_b": len(rates["B"])}


def srm_check(n_a: int, n_b: int, expected_a: float = 0.5) -> dict:
    total = n_a + n_b
    if total == 0 or not 0 < expected_a < 1:
        return {"chi2": float("nan"), "p_value": float("nan"), "ok": False}
    e_a, e_b = total * expected_a, total * (1 - expected_a)
    chi2 = (n_a - e_a) ** 2 / e_a + (n_b - e_b) ** 2 / e_b
    p = math.erfc(math.sqrt(chi2 / 2))
    return {"chi2": chi2, "p_value": p, "ok": p >= 0.01}


def verdict(metrics: dict[str, dict], alpha: float = 0.05) -> dict:
    a, b = metrics["A"], metrics["B"]
    det = two_proportion_test(int(a["tp"]), int(a["tp"] + a["fn"]), int(b["tp"]), int(b["tp"] + b["fn"]))
    fpr = two_proportion_test(int(a["fp"]), int(a["fp"] + a["tn"]), int(b["fp"]), int(b["fp"] + b["tn"]))
    better_det = det["p_value"] < alpha and det["diff"] > 0
    not_worse_fpr = not (fpr["p_value"] < alpha and fpr["diff"] > 0)
    if better_det and not_worse_fpr:
        text = "Variant B detects significantly more fraud without a significantly higher false-positive rate."
    elif better_det:
        text = "Variant B detects more fraud but also raises the false-positive rate: weigh fraud loss against blocked customers."
    elif det["p_value"] < alpha and det["diff"] < 0:
        text = "Variant A detects significantly more fraud."
    else:
        text = "No significant difference in detection rate yet: keep collecting data."
    return {"detection": det, "false_positive": fpr, "text": text}
