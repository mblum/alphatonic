import json

import numpy as np
import pytest

from alphatonic import evaluate
from tests.support.assertions import same_frame


def test_options_equivalent_ic_order_metrics_and_export(panel, config):
    a = evaluate(*panel, config)
    b = evaluate(*panel, **config.model_dump())
    same_frame(a.periods, b.periods)
    assert list(a.ic()) == list(config.horizons)
    with pytest.raises(ValueError, match="method"):
        a.ic("cosine")
    with pytest.raises(TypeError, match="either"):
        evaluate(*panel, config, horizons=[1])
    assert "Evaluation(horizons=" in repr(a)
    metrics = a.metrics()
    assert metrics and all(isinstance(v, float) and np.isfinite(v) for v in metrics.values())
    assert {"cs", "ts", "persistence"} == {key.split(".")[0] for key in metrics}
    doc = a.to_dict()
    json.dumps(doc, allow_nan=False)
    assert doc["format"] == "alphatonic.evaluation" and doc["format_version"] == 1
    assert doc["bar_seconds"] == 86400
    for name, table in [("periods", a.periods), ("summary", a.summary), ("quantiles", a.quantiles)]:
        stored = doc["cross_section"][name]
        assert list(stored) == list(table)
        assert all(len(v) == len(table) for v in stored.values())


@pytest.mark.parametrize("cs", ["return", "vol_scaled"])
@pytest.mark.parametrize("ts", ["return", "vol_scaled"])
def test_targets_keep_raw_labels_and_volatility_presence(panel, config, cs, ts):
    from alphatonic.evaluation import _targets
    from alphatonic.inputs import prepare
    from alphatonic.returns import forward_returns, scale_by_volatility

    config = config.model_copy(
        update={"target": cs, "time_series": config.time_series.model_copy(update={"target": ts})}
    )
    panel_data = prepare(*panel, config)
    labels = {h: forward_returns(panel_data.prices, h) for h in config.horizons}
    vol, targets = _targets(labels, panel_data, config)
    a = evaluate(*panel, config)
    assert (a.volatility is None) == (cs == ts == "return")
    for h in config.horizons:
        same_frame(a.forward_returns[h], labels[h])
        for analysis, kind in [("cross_sectional", cs), ("time_series", ts)]:
            expected = labels[h] if kind == "return" else scale_by_volatility(labels[h], vol, h)
            same_frame(targets[analysis][h], expected)


def test_progress_hook_does_not_change_results(panel, config, progress_log):
    progress, events = progress_log
    a = evaluate(*panel, config, progress=progress)
    b = evaluate(*panel, config)
    same_frame(a.summary, b.summary)
    assert events and events[-1][0] == "close"
