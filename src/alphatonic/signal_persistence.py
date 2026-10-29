"""Descriptive signal changes, independent of forward returns and trading assumptions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from alphatonic.config import EvaluationConfig
from alphatonic.stats import row_correlations

TABLES = ("periods", "quantiles", "assets", "summary")


@dataclass
class PersistenceEvaluation:
    """Stored signal diagnostics. Fractions are decimals; lags count original grid rows."""

    periods: pd.DataFrame
    """Rank persistence and eligible-universe overlap by timestamp and lag."""

    quantiles: pd.DataFrame
    """Bucket entry/exit counts and entry fractions by timestamp, lag and quantile."""

    assets: pd.DataFrame
    """Normalised signal change, sign and zero transitions by asset and lag."""

    summary: pd.DataFrame
    """Equal-timestamp CS means and equal-asset TS means with contributing counts."""

    def tables(self) -> dict[str, pd.DataFrame]:
        """Return all stored tables by name."""
        return {name: getattr(self, name) for name in TABLES}


def _ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    return np.divide(
        numerator, denominator, out=np.full(numerator.shape, np.nan), where=denominator > 0
    )


def evaluate_persistence(
    factor: pd.DataFrame, prices: pd.DataFrame, config: EvaluationConfig
) -> PersistenceEvaluation:
    """Compare endpoints using finite scores and prices known at those endpoints only.

    Each endpoint is ranked within its own eligible universe. Rank persistence is Pearson
    correlation of those ranks on common assets (the Alphalens convention). Quantiles use
    average ranks and ceil(Q * rank / count), preserving ties. Missing interior observations
    do not compress the grid; a lag-k comparison uses exactly k rows, not a trading path.
    """
    scores = factor.where(prices.notna())
    x = scores.to_numpy(float)
    valid = np.isfinite(x)
    n_current = valid.sum(axis=1)
    ranks = scores.rank(axis=1, method="average")
    counts = scores.count(axis=1).astype(float).replace(0, np.nan)
    buckets = pd.DataFrame(
        np.ceil(ranks.div(counts, axis=0).to_numpy() * config.quantiles),
        index=scores.index,
        columns=scores.columns,
    )
    varying = scores.nunique(axis=1).gt(1).to_numpy()
    eligible = (n_current >= config.min_assets) & varying
    periods, quantiles, assets = [], [], []
    for lag in config.persistence.lags:
        previous = scores.shift(lag).to_numpy(float)
        previous_valid = np.isfinite(previous)
        common = valid & previous_valid
        pairs = common.sum(axis=1)
        n_previous = previous_valid.sum(axis=1)
        boundary = np.arange(len(scores)) < lag
        old_ranks = ranks.shift(lag).to_numpy(float)
        rank_ic = row_correlations(ranks.to_numpy(float), old_ranks, "pearson")
        status = np.where(pairs < config.min_assets, "insufficient_assets", "valid")
        status = status.astype(object)
        status[(pairs >= config.min_assets) & ~np.isfinite(rank_ic)] = "constant_signal"
        status[boundary] = "boundary_excluded"
        rank_ic[status != "valid"] = np.nan
        periods.append(
            pd.DataFrame(
                {
                    "timestamp": scores.index,
                    "lag": lag,
                    "rank_autocorrelation": rank_ic,
                    "n_current": n_current,
                    "n_previous": n_previous,
                    "n_common": pairs,
                    "pair_coverage": _ratio(pairs, np.maximum(n_current, n_previous)),
                    "n_entries": (valid & ~previous_valid).sum(axis=1),
                    "n_exits": (~valid & previous_valid).sum(axis=1),
                    "status": status,
                }
            )
        )
        old_buckets = buckets.shift(lag).to_numpy(float)
        old_eligible = pd.Series(eligible).shift(lag, fill_value=False).to_numpy(bool)
        for q in range(1, config.quantiles + 1):
            current_q = buckets.to_numpy(float) == q
            previous_q = old_buckets == q
            size = current_q.sum(axis=1)
            old_size = previous_q.sum(axis=1)
            entries = (current_q & ~previous_q).sum(axis=1)
            exits = (previous_q & ~current_q).sum(axis=1)
            qstatus = np.full(len(scores), "valid", dtype=object)
            qstatus[size == 0] = "empty_quantile"
            qstatus[~eligible | ~old_eligible] = "ineligible_endpoint"
            qstatus[boundary] = "boundary_excluded"
            fraction = _ratio(entries, size)
            fraction[qstatus != "valid"] = np.nan
            quantiles.append(
                pd.DataFrame(
                    {
                        "timestamp": scores.index,
                        "lag": lag,
                        "quantile": q,
                        "n_current": size,
                        "n_previous": old_size,
                        "n_entries": entries,
                        "n_exits": exits,
                        "n_universe_entries": (current_q & ~previous_valid).sum(axis=1),
                        "n_universe_exits": (previous_q & ~valid).sum(axis=1),
                        "entry_fraction": fraction,
                        "status": qstatus,
                    }
                )
            )
        # Scale before arithmetic to avoid overflow and preserve scale invariance.
        scale = np.maximum(
            np.max(np.where(common, np.abs(x), 0), axis=0, initial=0),
            np.max(np.where(common, np.abs(previous), 0), axis=0, initial=0),
        )
        a = np.divide(np.where(common, x, 0), scale, out=np.zeros_like(x), where=scale > 0)
        b = np.divide(np.where(common, previous, 0), scale, out=np.zeros_like(x), where=scale > 0)
        change = _ratio(np.abs(a - b).sum(axis=0), ((np.abs(a) + np.abs(b)) / 2).sum(axis=0))
        count = common.sum(axis=0)
        flips = (common & (np.sign(x) * np.sign(previous) == -1)).sum(axis=0)
        zero = (common & ((x == 0) != (previous == 0))).sum(axis=0)
        sufficient = count >= config.persistence.min_pairs
        asset_status = np.where(sufficient, "valid", "insufficient_pairs")
        change_status = asset_status.astype(object)
        change_status[sufficient & (scale == 0)] = "zero_signal"
        change[~sufficient] = np.nan
        flip_fraction, zero_fraction = _ratio(flips, count), _ratio(zero, count)
        flip_fraction[~sufficient] = np.nan
        zero_fraction[~sufficient] = np.nan
        expected = max(len(scores) - lag, 0)
        assets.append(
            pd.DataFrame(
                {
                    "asset": scores.columns,
                    "lag": lag,
                    "n_expected": expected,
                    "n_pairs": count,
                    "pair_coverage": count / expected if expected else np.full(len(count), np.nan),
                    "normalized_change": change,
                    "change_status": change_status,
                    "n_sign_changes": flips,
                    "sign_change_fraction": flip_fraction,
                    "n_zero_transitions": zero,
                    "zero_transition_fraction": zero_fraction,
                    "status": asset_status,
                }
            )
        )
    period_table = pd.concat(periods, ignore_index=True)
    quantile_table = pd.concat(quantiles, ignore_index=True)
    asset_table = pd.concat(assets, ignore_index=True)
    summaries = []
    analyses: tuple[tuple[str, pd.DataFrame, tuple[str, ...]], ...] = (
        ("cs", period_table, ("rank_autocorrelation",)),
        ("quantile", quantile_table, ("entry_fraction",)),
        (
            "ts",
            asset_table,
            ("normalized_change", "sign_change_fraction", "zero_transition_fraction"),
        ),
    )
    for scope, frame, metrics in analyses:
        grouped = frame if scope == "quantile" else frame.assign(quantile=0)
        for (lag, q), group in grouped.groupby(["lag", "quantile"], sort=True):
            for metric in metrics:
                values = group[metric].dropna()
                summaries.append(
                    {
                        "scope": scope,
                        "lag": lag,
                        "quantile": q,
                        "metric": metric,
                        "mean": values.mean() if len(values) else np.nan,
                        "n_valid": len(values),
                        "n_total": len(group),
                        "status": "valid" if len(values) else "unavailable",
                    }
                )
    return PersistenceEvaluation(period_table, quantile_table, asset_table, pd.DataFrame(summaries))
