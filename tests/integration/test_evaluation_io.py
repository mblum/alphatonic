import json

from alphatonic import Evaluation
from tests.support.assertions import same_frame


def test_saved_result_exports_and_renders_without_market_data(result, tmp_path, monkeypatch):
    result.save(tmp_path / "tables")
    stored = Evaluation.load(tmp_path / "tables")

    def fail(*args, **kwargs):
        raise AssertionError("Inference rerun during rendering")

    monkeypatch.setattr("alphatonic.evaluation.evaluate", fail)
    monkeypatch.setattr("alphatonic.time_series.hac_tests", fail)
    monkeypatch.setattr("alphatonic.time_series.bootstrap_intervals", fail)
    page = stored.tearsheet(tmp_path, title="Stored evaluation")
    assert "Stored evaluation" in page.read_text()
    assert stored.forward_returns == {} and stored.volatility is None
    json.dumps(stored.to_dict(), allow_nan=False)
    same_frame(stored.summary, result.summary)
