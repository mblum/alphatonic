import time

import pytest

from alphatonic import evaluate
from alphatonic.demo import synthetic_market as market

pytestmark = pytest.mark.benchmark


def test_report_and_json_measurements(record_property):
    result = evaluate(
        *market(n_bars=500, n_assets=30), horizons=[1, 5], time_series={"bootstrap_samples": 0}
    )
    start = time.perf_counter()
    page = result.render_tearsheet()
    document = result.to_dict()
    record_property("seconds", time.perf_counter() - start)
    record_property("html_bytes", len(page.encode()))
    assert document["cross_section"]["summary"] and "chart-data" in page
