"""Evaluate predictive signals with information coefficients you can trust.

Pass a factor (scores) and prices to [`evaluate`][alphatonic.evaluate] to measure how well the
scores rank assets at each timestamp (cross-sectional IC) and predict each asset's own returns
over time (time-series IC), with Newey-West and block-bootstrap uncertainty, explicit reasons
for every undefined statistic, and an offline HTML tearsheet.
"""

from importlib.metadata import PackageNotFoundError, version

from alphatonic.config import EvaluationConfig, PersistenceOptions, ReportOptions, TimeSeriesOptions
from alphatonic.evaluation import Evaluation, evaluate
from alphatonic.returns import bar_volatility, forward_returns
from alphatonic.signal_persistence import PersistenceEvaluation
from alphatonic.stats import summarize_ic
from alphatonic.study import HoldoutError, Study, Trial, UnknownTrialError
from alphatonic.time_series import TimeSeriesEvaluation

try:
    __version__ = version("alphatonic")
except PackageNotFoundError:  # pragma: no cover - running from an unbuilt source tree
    __version__ = "0+unknown"

__all__ = [
    "Evaluation",
    "EvaluationConfig",
    "HoldoutError",
    "PersistenceEvaluation",
    "PersistenceOptions",
    "ReportOptions",
    "Study",
    "TimeSeriesEvaluation",
    "TimeSeriesOptions",
    "Trial",
    "UnknownTrialError",
    "__version__",
    "bar_volatility",
    "evaluate",
    "forward_returns",
    "summarize_ic",
]
