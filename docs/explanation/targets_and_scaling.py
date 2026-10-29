"""Simulations behind the design note on targets, scaling and the cosine IC.

Run from the repository root with the development dependencies installed (scipy is one):

    uv run python docs/explanation/targets_and_scaling.py

Each section prints one table of the note. The time-series cases simulate returns whose
volatility clusters, with the skill set in units of risk:
`r[t+1] = sigma[t] * (drift + k * s[t] + noise)`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, spearmanr

from alphatonic.demo import synthetic_market
from alphatonic.stats import row_correlations, summarize_ic

BARS, RUNS = 2520, 300  # ten years of daily bars per series


def simulate(rng, ic, bias, drift_sharpe, persistence=0.9, vol_of_vol=0.12):
    """Return a score series, its raw one-bar label and the label scaled by ex-ante volatility."""
    log_vol = np.empty(BARS)
    log_vol[0] = 0.0
    shocks = rng.normal(0, vol_of_vol, BARS)
    for t in range(1, BARS):
        log_vol[t] = 0.98 * log_vol[t - 1] + shocks[t]
    sigma = 0.01 * np.exp(log_vol)
    s = np.empty(BARS)
    s[0] = rng.normal()
    eps = rng.normal(size=BARS) * np.sqrt(1 - persistence**2)
    for t in range(1, BARS):
        s[t] = persistence * s[t - 1] + eps[t]
    s = s + bias
    k = ic / np.sqrt(1 - ic**2)
    r = np.full(BARS, np.nan)
    noise = rng.normal(size=BARS - 1)
    r[1:] = sigma[:-1] * (drift_sharpe / np.sqrt(252) + k * (s[:-1] - bias) + noise)
    # Ex-ante volatility known at t: EWMA of squared returns through t, centre of mass 60.
    sig_hat = np.sqrt(pd.Series(r).pow(2).ewm(com=60, min_periods=20).mean()).to_numpy()
    label = np.append(r[1:], np.nan)
    return s, label, label / sig_hat


def _finite(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    return a[ok], b[ok]


def cosine(a, b):
    """Uncentred correlation of the finite pairs."""
    a, b = _finite(a, b)
    return a @ b / np.sqrt((a @ a) * (b @ b))


def pearson(a, b):
    """Pearson correlation of the finite pairs."""
    a, b = _finite(a, b)
    return np.corrcoef(a, b)[0, 1] if np.ptp(a) > 0 else np.nan


def spearman(a, b):
    """Spearman correlation of the finite pairs."""
    a, b = _finite(a, b)
    return spearmanr(a, b).statistic if np.ptp(a) > 0 else np.nan


def sharpe_per_bar(pnl):
    """Mean over standard deviation of a profit series, not annualised."""
    pnl = pnl[np.isfinite(pnl)]
    return pnl.mean() / pnl.std(ddof=1)


def table(rows):
    """Mean, standard deviation across runs and their ratio, per statistic."""
    frame = pd.DataFrame(rows)
    return pd.DataFrame(
        {"mean": frame.mean(), "sd": frame.std(), "t": frame.mean() / frame.std()}
    ).round(4)


def time_series_case(ic, bias, drift_sharpe):
    """Raw against vol-scaled targets, and centred against uncentred statistics."""
    rng = np.random.default_rng(42)
    rows = []
    for _ in range(RUNS):
        s, raw, scaled = simulate(rng, ic=ic, bias=bias, drift_sharpe=drift_sharpe)
        rows.append(
            {
                "pearson raw": pearson(s, raw),
                "pearson vol": pearson(s, scaled),
                "spearman raw": spearman(s, raw),
                "spearman vol": spearman(s, scaled),
                "cosine raw": cosine(s, raw),
                "cosine vol": cosine(s, scaled),
                "sharpe/bar s*r/sigma": sharpe_per_bar(s * scaled),
            }
        )
    frame = pd.DataFrame(rows)
    agreement = frame["cosine vol"].corr(frame["sharpe/bar s*r/sigma"])
    return table(rows), agreement


def price_unit_signal():
    """The same information expressed in price units, so the score grows with volatility."""
    rng = np.random.default_rng(7)
    rows = []
    for _ in range(RUNS):
        s, raw, scaled = simulate(rng, ic=0.03, bias=0.0, drift_sharpe=0.0)
        s_price = s * (raw / scaled)
        rows.append(
            {
                "pearson price signal, raw target": pearson(s_price, raw),
                "pearson risk signal, vol target": pearson(s, scaled),
                "spearman price signal, raw target": spearman(s_price, raw),
                "spearman risk signal, vol target": spearman(s, scaled),
                "cosine price signal, raw target": cosine(s_price, raw),
                "cosine risk signal, vol target": cosine(s, scaled),
            }
        )
    return table(rows)


def fat_tails():
    """Student-t(3) innovations with unit variance and the skill in units of risk."""
    rng = np.random.default_rng(11)
    rows = []
    k = 0.03 / np.sqrt(1 - 0.03**2)
    for _ in range(RUNS):
        s, raw, scaled = simulate(rng, ic=0.03, bias=0.0, drift_sharpe=0.0)
        sig_hat = raw / scaled
        noise = rng.standard_t(3, size=BARS) / np.sqrt(3)
        r_fat = np.append(sig_hat[:-1] * (k * s[:-1] + noise[:-1]), np.nan)
        target = r_fat / sig_hat
        rows.append(
            {
                "pearson": pearson(s, target),
                "spearman": spearman(s, target),
                "cosine": cosine(s, target),
            }
        )
    return table(rows)


def cross_section_volatility(n_assets=100, n_bars=1000, ic=0.03):
    """Cross-sectional IC against raw and risk-adjusted returns, vols from 10% to 80%."""
    rng = np.random.default_rng(3)
    vols = np.linspace(0.10, 0.80, n_assets) / np.sqrt(252)
    k = ic / np.sqrt(1 - ic**2)
    out = {name: [] for name in ("spearman raw", "spearman risk", "pearson raw", "pearson risk")}
    for _ in range(n_bars):
        s = rng.normal(size=n_assets)
        r = vols * (k * s + rng.normal(size=n_assets))
        out["spearman raw"].append(spearmanr(s, r).statistic)
        out["spearman risk"].append(spearmanr(s, r / vols).statistic)
        out["pearson raw"].append(np.corrcoef(s, r)[0, 1])
        out["pearson risk"].append(np.corrcoef(s, r / vols)[0, 1])
    return pd.DataFrame(
        {
            name: {"mean": np.mean(v), "t": np.mean(v) / np.std(v) * np.sqrt(len(v))}
            for name, v in out.items()
        }
    ).T.round(4)


def kendall_rows(x, y):
    """Kendall's tau-b of each row's finite pairs."""
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        ok = np.isfinite(x[i]) & np.isfinite(y[i])
        if ok.sum() >= 3:
            out[i] = kendalltau(x[i, ok], y[i, ok]).statistic
    return out


def _hac_z(series, horizon):
    return summarize_ic(pd.Series(series), max(horizon - 1, 4)).get("hac_z", np.nan)


def kendall_against_spearman():
    """Per-timestamp Kendall and Spearman IC on the synthetic market."""
    rows = []
    for n_assets in (8, 30, 200):
        factor, prices = synthetic_market(n_assets=n_assets, n_bars=2000, ic=0.04, seed=3)
        for h in (1, 5):
            labels = (prices.shift(-h) / prices - 1).to_numpy()
            s = row_correlations(factor.to_numpy(), labels, "spearman")
            k = kendall_rows(factor.to_numpy(), labels)
            ok = np.isfinite(s) & np.isfinite(k)
            rows.append(
                {
                    "assets": n_assets,
                    "horizon": h,
                    "spearman": np.nanmean(s),
                    "kendall": np.nanmean(k),
                    "correlation": np.corrcoef(s[ok], k[ok])[0, 1],
                    "z spearman": _hac_z(s, h),
                    "z kendall": _hac_z(k, h),
                }
            )
    disagree = 0
    for seed in range(200):
        factor, prices = synthetic_market(n_assets=10, n_bars=500, ic=0.0, seed=seed)
        labels = (prices.shift(-1) / prices - 1).to_numpy()
        zs = _hac_z(row_correlations(factor.to_numpy(), labels, "spearman"), 1)
        zk = _hac_z(kendall_rows(factor.to_numpy(), labels), 1)
        disagree += (abs(zs) > 1.96) != (abs(zk) > 1.96)
    return pd.DataFrame(rows).round(4), disagree


def cross_sectional_cosine():
    """Cross-sectional cosine of the same ranks at different score locations."""
    factor, prices = synthetic_market(n_assets=30, n_bars=2000, ic=0.04, seed=3)
    rng = np.random.default_rng(1)
    market = rng.normal(0.0004, 0.01, size=(len(prices), 1))
    labels = np.roll(prices.pct_change().to_numpy() + market, -1, axis=0)
    labels[-1] = np.nan
    x = factor.to_numpy()
    rows = {}
    for name, scores in {
        "factor": x,
        "factor + 2": x + 2,
        "3 * factor + 1": 3 * x + 1,
        "constant 1": np.ones_like(x),
    }.items():
        ok = np.isfinite(scores) & np.isfinite(labels)
        a, b = np.where(ok, scores, 0), np.where(ok, labels, 0)
        norm = np.sqrt((a * a).sum(1) * (b * b).sum(1))
        cos = np.divide((a * b).sum(1), norm, out=np.full(len(a), np.nan), where=norm > 0)
        rows[name] = {
            # A constant score has no rank IC at any timestamp: the mean is NaN.
            "spearman": pd.Series(row_correlations(scores, labels, "spearman")).mean(),
            "cosine": np.nanmean(cos),
            "z cosine": _hac_z(cos, 1),
        }
    return pd.DataFrame(rows).T.round(4)


def main():
    """Print every table of the note."""
    cases = {
        "Timing skill only (IC 0.03 in risk units)": dict(ic=0.03, bias=0.0, drift_sharpe=0.0),
        "No timing skill, long bias 0.5 sd, drift Sharpe 0.5": dict(
            ic=0.0, bias=0.5, drift_sharpe=0.5
        ),
        "Timing skill, long bias and drift": dict(ic=0.03, bias=0.5, drift_sharpe=0.5),
    }
    for title, case in cases.items():
        frame, agreement = time_series_case(**case)
        print(f"\n{title}\n{frame.to_string()}")
        print(f"correlation of cosine (vol target) with per-bar Sharpe: {agreement:.3f}")
    print(f"\nSignal in price units\n{price_unit_signal().to_string()}")
    print(f"\nFat tails, t(3) innovations\n{fat_tails().to_string()}")
    print(f"\nCross-section, volatilities 10%-80%\n{cross_section_volatility().to_string()}")
    kendall, disagree = kendall_against_spearman()
    print(f"\nKendall against Spearman\n{kendall.to_string()}")
    print(f"runs without skill where 5% significance differs: {disagree}/200")
    print(f"\nCross-sectional cosine\n{cross_sectional_cosine().to_string()}")


if __name__ == "__main__":
    main()
