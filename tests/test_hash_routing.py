import collections

from pipeline.hashing import assign_variant


def test_split_is_close_to_50_50():
    counts = collections.Counter(assign_variant(f"C{i}") for i in range(100_000))
    assert abs(counts["A"] / 100_000 - 0.5) < 0.01


def test_assignment_is_sticky_and_deterministic():
    assert all(assign_variant("C123456789") == assign_variant("C123456789") for _ in range(100))


def test_custom_split_respected():
    counts = collections.Counter(assign_variant(f"C{i}", split_a=20) for i in range(50_000))
    assert abs(counts["A"] / 50_000 - 0.20) < 0.01


def test_different_experiment_salt_reshuffles_users():
    ids = [f"C{i}" for i in range(2000)]
    same = sum(assign_variant(i, 50, "exp1") == assign_variant(i, 50, "exp2") for i in ids)
    assert 0.4 < same / len(ids) < 0.6  # independent assignments agree about half the time


def test_invalid_split_rejected():
    import pytest
    with pytest.raises(ValueError):
        assign_variant("C1", split_a=101)
