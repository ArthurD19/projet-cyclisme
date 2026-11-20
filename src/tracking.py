"""Suivi de la charge : agrégations jour / semaine, CTL-ATL-TSB, bien-être, statut."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (ATL_DAYS, BASELINE_DAYS, COMPLIANCE_CRIT, COMPLIANCE_WARN, CTL_DAYS,
                     HOOPER_Z_CRIT, HOOPER_Z_WARN, LOAD_JUMP_WARN, SWC_FACTOR, TSB_BANDS, WARMUP_DAYS)

HOOPER_ITEMS = ["sommeil", "stress", "fatigue", "courbatures"]
SUM_COLS = ["dur_s", "dist_km", "work_kj", "elev_gain_m", "tss", "load", "srpe", "trimp_edwards",
            "trimp_banister"] + [f"pz{i}_s" for i in range(1, 6)] + [f"hz{i}_s" for i in range(1, 6)]


def ewm_load(load: pd.Series, days: int) -> pd.Series:
    """X(j) = X(j-1) + (charge(j) - X(j-1)) / days, départ à 0."""
    out, x = np.empty(len(load)), 0.0
    for i, v in enumerate(load.fillna(0).to_numpy()):
        x += (v - x) / days
        out[i] = x
    return pd.Series(out, index=load.index)


def build_daily(rides: pd.DataFrame, hooper: pd.DataFrame, cyclist_id: str) -> pd.DataFrame:
    """Une ligne par jour calendaire (jours sans sortie : charge = 0)."""
    r = rides[rides["cyclist"] == cyclist_id]
    h = hooper.set_index("date")
    start = min(r["date"].min(), h.index.min())
    end = max(r["date"].max(), h.index.max())
    days = pd.date_range(start, end, freq="D", name="date")

    agg = r.groupby("date").agg(
        n_rides=("file", "size"), rpe_filled=("rpe", lambda s: s.notna().sum()),
        **{c: (c, lambda s: s.sum(min_count=1)) for c in SUM_COLS},
    )
    d = agg.reindex(days)
    d["n_rides"] = d["n_rides"].fillna(0).astype(int)
    d["rpe_filled"] = d["rpe_filled"].fillna(0).astype(int)
    for c in ["dur_s", "dist_km", "work_kj", "tss", "load", "srpe", "trimp_edwards", "trimp_banister"]:
        d[c] = d[c].fillna(0.0)

    d["ctl"] = ewm_load(d["load"], CTL_DAYS)
    d["atl"] = ewm_load(d["load"], ATL_DAYS)
    d["tsb"] = d["ctl"] - d["atl"]
    d["tsb_pct"] = d["tsb"] / d["ctl"].where(d["ctl"] >= 5) * 100   # fraîcheur relative à la forme
    d["ctl_srpe"] = ewm_load(d["srpe"], CTL_DAYS)
    d["atl_srpe"] = ewm_load(d["srpe"], ATL_DAYS)
    d["warmup"] = np.arange(len(d)) < WARMUP_DAYS

    # Charge 7 j / 28 j (descriptif : hausse ou baisse marquée de la charge)
    d["load_7d"] = d["load"].rolling(7, min_periods=1).sum()
    d["load_28d_wk"] = d["load"].rolling(28, min_periods=7).sum() / 4
    d["load_change"] = d["load_7d"] / d["load_28d_wk"] - 1
    # Monotonie et contrainte de Foster sur 7 jours (sRPE)
    m = d["srpe"].rolling(7, min_periods=7)
    d["monotony"] = m.mean() / m.std().replace(0, np.nan)
    d["strain"] = d["srpe"].rolling(7, min_periods=7).sum() * d["monotony"]

    # Bien-être (Hooper : 4 = très bien … 28 = très mal)
    d = d.join(h[HOOPER_ITEMS])
    d["hooper"] = d[HOOPER_ITEMS].sum(axis=1, min_count=4)
    d["hooper_filled"] = d["hooper"].notna()
    base = d["hooper"].shift(1).rolling(BASELINE_DAYS, min_periods=10)
    d["hooper_base"] = base.mean()
    d["hooper_sd"] = base.std()
    d["hooper_z"] = (d["hooper"] - d["hooper_base"]) / d["hooper_sd"]
    d["hooper_swc"] = SWC_FACTOR * d["hooper_sd"]
    for it in HOOPER_ITEMS:
        b = d[it].shift(1).rolling(BASELINE_DAYS, min_periods=10)
        d[f"{it}_z"] = (d[it] - b.mean()) / b.std()
    d["compliance_hooper_28d"] = d["hooper_filled"].rolling(28, min_periods=1).mean()
    rides_28 = d["n_rides"].rolling(28, min_periods=1).sum()
    d["compliance_rpe_28d"] = d["rpe_filled"].rolling(28, min_periods=1).sum() / rides_28.replace(0, np.nan)

    d.insert(0, "cyclist", cyclist_id)
    return d.reset_index()


def weekly(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.copy()
    d["week"] = d["date"].dt.to_period("W-SUN").dt.start_time
    cols = ["load", "tss", "srpe", "dur_s", "dist_km", "work_kj"] + [f"pz{i}_s" for i in range(1, 6)]
    w = d.groupby(["cyclist", "week"]).agg(
        **{c: (c, "sum") for c in cols}, n_rides=("n_rides", "sum"), hooper=("hooper", "mean"),
        ctl=("ctl", "last"), tsb=("tsb", "last"), days=("date", "size"))
    return w.reset_index()


# --------------------------------------------------------------------------
# Statut (feux tricolores) à une date donnée
# --------------------------------------------------------------------------

def tsb_band(tsb_pct: float) -> tuple[str, str]:
    """Statut de fraîcheur à partir du TSB exprimé en % de la CTL."""
    tsb = tsb_pct
    if not np.isfinite(tsb):
        return "—", "na"
    for lo, label, status in TSB_BANDS:
        if tsb >= lo:
            return label, status
    return TSB_BANDS[-1][1], TSB_BANDS[-1][2]


def hooper_status(z: float) -> tuple[str, str]:
    if not np.isfinite(z):
        return "Pas de réponse", "na"
    if z >= HOOPER_Z_CRIT:
        return "Nettement dégradé", "critical"
    if z >= HOOPER_Z_WARN:
        return "Dégradé", "warning"
    if z <= -HOOPER_Z_WARN:
        return "Mieux que d'hab.", "good"
    return "Habituel", "good"


def compliance_status(rate: float) -> str:
    if not np.isfinite(rate):
        return "na"
    return "good" if rate >= COMPLIANCE_WARN else "warning" if rate >= COMPLIANCE_CRIT else "critical"


SEVERITY = {"na": 0, "good": 1, "warning": 2, "serious": 3, "critical": 4}


def status_on(daily: pd.DataFrame, day: pd.Timestamp, lookback_days: int = 3) -> dict:
    """Résumé d'un coureur au matin du jour `day` (Hooper : dernière réponse ≤ 3 jours)."""
    d = daily[daily["date"] <= day]
    if d.empty:
        return dict(available=False)
    row = d.iloc[-1]
    recent = d[d["date"] > day - pd.Timedelta(days=lookback_days)].dropna(subset=["hooper"])
    hz = float(recent["hooper_z"].iloc[-1]) if len(recent) else np.nan
    hv = float(recent["hooper"].iloc[-1]) if len(recent) else np.nan
    tsb_label, tsb_st = tsb_band(row["tsb_pct"])
    h_label, h_st = hooper_status(hz)
    jump = row["load_change"]
    load_st = "warning" if np.isfinite(jump) and jump > LOAD_JUMP_WARN else "good"
    worst = max([tsb_st, h_st], key=SEVERITY.get)
    return dict(
        available=True, date=row["date"], ctl=row["ctl"], atl=row["atl"], tsb=row["tsb"], tsb_pct=row["tsb_pct"],
        tsb_label=tsb_label, tsb_status=tsb_st, hooper=hv, hooper_z=hz, hooper_label=h_label,
        hooper_status=h_st, load_7d=row["load_7d"], load_change=jump, load_status=load_st,
        compliance=row["compliance_hooper_28d"], compliance_status=compliance_status(row["compliance_hooper_28d"]),
        warmup=bool(row["warmup"]), overall=worst,
    )
