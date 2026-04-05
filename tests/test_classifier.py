import pytest

from classifier import ClassificationError, classify_attachment


def _answers(**kwargs: int) -> dict[str, int]:
    base = {f"A{i}": 3 for i in range(1, 7)} | {f"B{i}": 3 for i in range(1, 7)}
    base.update(kwargs)
    return base


def test_secure_typical():
    code, ax, av = classify_attachment(_answers())
    assert code == "SECURE"
    assert ax == 3.0
    assert av == 3.0


def test_anxious_typical():
    # 焦虑高、回避低
    a_high = {f"A{i}": 6 for i in range(1, 7)}
    b_low = {f"B{i}": 2 for i in range(1, 7)}
    code, ax, av = classify_attachment(_answers(**a_high, **b_low))
    assert code == "ANXIOUS"
    assert ax == 6.0
    assert av == 2.0


def test_avoidant_typical():
    a_low = {f"A{i}": 2 for i in range(1, 7)}
    b_high = {f"B{i}": 6 for i in range(1, 7)}
    code, ax, av = classify_attachment(_answers(**a_low, **b_high))
    assert code == "AVOIDANT"


def test_fearful_typical():
    a_high = {f"A{i}": 6 for i in range(1, 7)}
    b_high = {f"B{i}": 6 for i in range(1, 7)}
    code, ax, av = classify_attachment(_answers(**a_high, **b_high))
    assert code == "FEARFUL"


def test_boundary_anxiety_exactly_35():
    # 均分恰好 3.5：和为 21
    a = {"A1": 3, "A2": 3, "A3": 3, "A4": 3, "A5": 4, "A6": 5}
    b = {f"B{i}": 2 for i in range(1, 7)}
    code, ax, av = classify_attachment(_answers(**a, **b))
    assert ax == 3.5
    assert av == 2.0
    assert code == "ANXIOUS"


def test_boundary_avoidance_exactly_35():
    a = {f"A{i}": 2 for i in range(1, 7)}
    b = {"B1": 3, "B2": 3, "B3": 3, "B4": 3, "B5": 4, "B6": 5}
    code, ax, av = classify_attachment(_answers(**a, **b))
    assert av == 3.5
    assert code == "AVOIDANT"


def test_boundary_both_35():
    a = {"A1": 3, "A2": 3, "A3": 3, "A4": 3, "A5": 4, "A6": 5}
    b = {"B1": 3, "B2": 3, "B3": 3, "B4": 3, "B5": 4, "B6": 5}
    code, _, _ = classify_attachment(_answers(**a, **b))
    assert code == "FEARFUL"


def test_extreme_all_ones():
    one = {f"A{i}": 1 for i in range(1, 7)} | {f"B{i}": 1 for i in range(1, 7)}
    code, ax, av = classify_attachment(one)
    assert code == "SECURE"
    assert ax == 1.0
    assert av == 1.0


def test_extreme_all_sevens():
    seven = {f"A{i}": 7 for i in range(1, 7)} | {f"B{i}": 7 for i in range(1, 7)}
    code, ax, av = classify_attachment(seven)
    assert code == "FEARFUL"
    assert ax == 7.0
    assert av == 7.0


def test_missing_key_raises():
    d = {f"A{i}": 3 for i in range(1, 6)} | {f"B{i}": 3 for i in range(1, 7)}
    with pytest.raises(ClassificationError) as e:
        classify_attachment(d)
    assert "A6" in str(e.value) or "missing" in str(e.value).lower()


def test_invalid_value_raises():
    d = _answers(A1=8)
    with pytest.raises(ClassificationError):
        classify_attachment(d)
