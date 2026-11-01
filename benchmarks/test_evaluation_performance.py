import time
import tracemalloc

import pytest

from alphatonic import evaluate
from alphatonic.demo import synthetic_market as market

pytestmark = pytest.mark.benchmark


@pytest.mark.parametrize("sparse", [False, True])
def test_dense_sparse_evaluation_measurements(sparse, record_property):
    x, p = market(n_bars=1000, n_assets=100)
    if sparse:
        x.iloc[::3, ::2] = float("nan")
    tracemalloc.start()
    start = time.perf_counter()
    result = evaluate(x, p, horizons=[1, 5, 20], time_series={"bootstrap_samples": 0})
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert len(result.periods) == 3000
    record_property("seconds", elapsed)
    record_property("peak_bytes", peak)
