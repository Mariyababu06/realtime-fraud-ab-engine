from pipeline.ab_stats import cluster_bootstrap_rate_difference


def test_cluster_bootstrap_is_reproducible_and_reports_users():
    rows = []
    for variant, users, hit in [("A", ["a1", "a2", "a3"], 0), ("B", ["b1", "b2", "b3"], 1)]:
        for user in users:
            rows.append({"orig_id_masked": user, "variant": variant, "isFraud": 1, "flagged": hit})
    result = cluster_bootstrap_rate_difference(rows, iterations=200, seed=4)
    assert result["users_a"] == 3 and result["users_b"] == 3
    assert result["diff"] == 1
    assert result == cluster_bootstrap_rate_difference(rows, iterations=200, seed=4)


def test_cluster_bootstrap_handles_no_fraud():
    result = cluster_bootstrap_rate_difference([])
    assert result["users_a"] == 0
