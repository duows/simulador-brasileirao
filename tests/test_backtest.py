import numpy as np

from futdados.backtest.walkforward import (
    baseline_freq,
    baseline_home,
    brier,
    calibration_table,
    log_loss,
    outcome_index,
)


def test_metrics_known_values():
    y = np.array([0, 1, 2])
    perfect = np.eye(3)
    assert brier(perfect, y) == 0
    uniform = np.full((3, 3), 1 / 3)
    assert np.isclose(brier(uniform, y), 2 / 3)
    assert np.isclose(log_loss(uniform, y), np.log(3))
    assert np.isclose(brier(baseline_home(3), y), (0 + 2 + 2) / 3)


def test_outcome_index_and_freq_baseline():
    y = outcome_index([2, 1, 0, 3], [1, 1, 2, 0])
    assert list(y) == [0, 1, 2, 0]
    f = baseline_freq(y, 2)
    assert np.allclose(f[0], [0.5, 0.25, 0.25])


def test_calibration_table_counts():
    p = np.array([[0.55, 0.25, 0.2]] * 10)
    y = np.array([0] * 6 + [1] * 2 + [2] * 2)
    t = calibration_table(p, y, 10)
    row = t[(t.resultado == "mandante")].iloc[0]
    assert row.n == 10 and np.isclose(row.observado, 0.6)
