"""Métriques par sortie.

Deux temps :
1. `summarize_ride` lit une sortie et calcule tout ce qui ne dépend d'aucun
   paramètre du coureur (NP, travail, records de puissance, histogrammes) ;
2. `apply_thresholds` ajoute ce qui dépend de la FTP et de la FCmax du coureur
   (IF, TSS, zones, TRIMP), une fois ces seuils estimés sur la saison.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import HR_ZONES, MMP_DURATIONS_S, POWER_ZONES
from .load import is_zwift, read_ride, ride_start

POWER_BIN_W = 5
POWER_BINS = np.arange(0, 2505, POWER_BIN_W)
HR_BINS = np.arange(0, 232)
TRACE_STEP_S = 20


# --------------------------------------------------------------------------
# Formules élémentaires
# --------------------------------------------------------------------------

def rolling_mean(x: np.ndarray, window: int) -> np.ndarray:
    """Moyenne glissante sur `window` échantillons (fenêtres complètes seulement)."""
    if len(x) < window:
        return np.array([])
    c = np.concatenate([[0.0], np.cumsum(x, dtype="float64")])
    return (c[window:] - c[:-window]) / window


def normalized_power(watts: np.ndarray) -> float:
    """NP : moyenne glissante 30 s → puissance 4 → moyenne → racine 4e (0 W gardés)."""
    r = rolling_mean(watts, 30)
    return float(np.mean(r ** 4) ** 0.25) if len(r) else np.nan


def mmp(watts: np.ndarray, durations=MMP_DURATIONS_S) -> dict[int, float]:
    """Meilleure puissance moyenne sur chaque durée (W)."""
    out = {}
    for d in durations:
        r = rolling_mean(watts, d)
        out[d] = float(r.max()) if len(r) else np.nan
    return out


def elevation_gain(alt: np.ndarray) -> float:
    a = pd.Series(alt).rolling(15, center=True, min_periods=1).mean().to_numpy()
    d = np.diff(a)
    return float(np.nansum(d[d > 0]))


def tss(dur_s: float, np_w: float, ftp_w: float) -> float:
    """TSS = durée_s × NP × IF / (FTP × 3600) × 100."""
    if not (ftp_w and np_w and ftp_w > 0):
        return np.nan
    return dur_s * np_w * (np_w / ftp_w) / (ftp_w * 3600) * 100


def trimp_banister(dur_min: float, hr_mean: float, hr_rest: float, hr_max: float) -> float:
    if not np.isfinite(hr_mean) or hr_max <= hr_rest:
        return np.nan
    dhr = np.clip((hr_mean - hr_rest) / (hr_max - hr_rest), 0, 1)
    return float(dur_min * dhr * 0.64 * np.exp(1.92 * dhr))


# --------------------------------------------------------------------------
# Passe 1 : une sortie
# --------------------------------------------------------------------------

def summarize_ride(path: Path | str, cyclist_id: str, weight_kg: float) -> dict:
    path = Path(path)
    df = read_ride(path)
    start = ride_start(path)
    w = df["watts"].fillna(0).to_numpy()
    hr = df["hr"].to_numpy()
    n = len(df)
    has_power = bool((w > 0).mean() > 0.05 and w.sum() > 0)
    hr_ok = np.isfinite(hr)
    has_hr = bool(hr_ok.mean() > 0.5)
    km = df["km"].to_numpy()
    dist = float(np.nanmax(km)) if n else 0.0
    zwift = is_zwift(df)
    indoor = zwift or (dist < 1.0 and n > 600)

    rec = dict(
        cyclist=cyclist_id, file=path.name, start=pd.Timestamp(start), date=pd.Timestamp(start.date()),
        dur_s=n, elapsed_s=int(df["secs"].max() - df["secs"].min() + 1) if n else 0,
        dist_km=dist, elev_gain_m=elevation_gain(df["alt"].to_numpy()) if not indoor else np.nan,
        speed_kph=float(df.loc[df["kph"] > 3, "kph"].mean()) if not indoor else np.nan,
        indoor=indoor, zwift=zwift, has_power=has_power, has_hr=has_hr,
        cad_mean_rpm=float(df.loc[df["cad"] > 0, "cad"].mean()),
        temp_mean_c=float(df["temp"].mean()), lrbalance_mean=float(df["lrbalance"].mean()),
    )
    # Artefact : ni puissance ni FC, et enregistrement interminable ou à vitesse de véhicule
    rec["artifact"] = bool(not has_power and not has_hr
                           and (n > 6 * 3600 or (rec["speed_kph"] or 0) > 50))

    if has_power:
        np_w = normalized_power(w)
        rec.update(p_mean_w=float(w.mean()), np_w=np_w, work_kj=float(w.sum() / 1000),
                   vi=np_w / w.mean() if w.mean() > 0 else np.nan)
        best = mmp(w)
    else:
        rec.update(p_mean_w=np.nan, np_w=np.nan, work_kj=np.nan, vi=np.nan)
        best = {d: np.nan for d in MMP_DURATIONS_S}
    rec["np_wkg"] = rec["np_w"] / weight_kg

    if has_hr:
        hr_f = pd.Series(hr).interpolate(limit=10).to_numpy()
        rec["hr_mean_bpm"] = float(np.nanmean(hr))
        r5 = rolling_mean(np.nan_to_num(hr_f, nan=0.0), 5)
        rec["hr_max_bpm"] = float(r5.max()) if len(r5) else float(np.nanmax(hr))
        rec["ef"] = rec["np_w"] / rec["hr_mean_bpm"] if has_power else np.nan
        # Découplage cardiaque (Pa:HR) : dérive de NP/FC entre 1re et 2e moitié
        if has_power and n >= 3600:
            h = n // 2
            ef1 = normalized_power(w[:h]) / np.nanmean(hr[:h])
            ef2 = normalized_power(w[h:]) / np.nanmean(hr[h:])
            rec["decoupling_pct"] = float((ef1 - ef2) / ef1 * 100)
        else:
            rec["decoupling_pct"] = np.nan
    else:
        rec.update(hr_mean_bpm=np.nan, hr_max_bpm=np.nan, ef=np.nan, decoupling_pct=np.nan)

    p_hist = np.histogram(w, bins=POWER_BINS)[0].astype("int32") if has_power else None
    h_hist = np.histogram(hr[hr_ok], bins=HR_BINS)[0].astype("int32") if has_hr else None

    # Trace allégée (1 point / 20 s) pour l'explorateur de séance
    g = np.arange(n) // TRACE_STEP_S
    tr = df[["watts", "hr", "alt", "kph", "cad", "lat", "lon"]].groupby(g).mean()
    tr.insert(0, "t_min", (tr.index * TRACE_STEP_S / 60).astype("float32"))
    tr = tr.astype("float32")
    tr.insert(0, "file", path.name)
    tr.insert(0, "cyclist", cyclist_id)

    return dict(rec=rec, mmp=best, p_hist=p_hist, h_hist=h_hist, trace=tr)


# --------------------------------------------------------------------------
# Passe 2 : seuils du coureur
# --------------------------------------------------------------------------

def power_zone_seconds(p_hist: np.ndarray | None, ftp_w: float) -> list[float]:
    if p_hist is None or not np.isfinite(ftp_w):
        return [np.nan] * len(POWER_ZONES)
    centers = POWER_BINS[:-1] + POWER_BIN_W / 2
    pct = centers / ftp_w * 100
    return [float(p_hist[(pct >= lo) & (pct < hi)].sum()) for _, lo, hi in POWER_ZONES]


def hr_zone_seconds(h_hist: np.ndarray | None, hr_max: float) -> list[float]:
    if h_hist is None or not np.isfinite(hr_max):
        return [np.nan] * len(HR_ZONES)
    pct = HR_BINS[:-1] / hr_max * 100
    return [float(h_hist[(pct >= lo) & (pct < hi)].sum()) for _, lo, hi, _ in HR_ZONES]


def apply_thresholds(rec: dict, p_hist, h_hist, ftp_w: float, hr_max: float, hr_rest: float) -> dict:
    out = dict(ftp_w=ftp_w, hr_max_season_bpm=hr_max, hr_rest_bpm=hr_rest)
    out["if_"] = rec["np_w"] / ftp_w if rec["has_power"] else np.nan
    out["tss"] = tss(rec["dur_s"], rec["np_w"], ftp_w) if rec["has_power"] else np.nan
    pz = power_zone_seconds(p_hist, ftp_w)
    for i, s in enumerate(pz, 1):
        out[f"pz{i}_s"] = s
    hz = hr_zone_seconds(h_hist, hr_max)
    for i, s in enumerate(hz, 1):
        out[f"hz{i}_s"] = s
    if rec["has_hr"]:
        out["trimp_edwards"] = float(sum(s / 60 * k for s, (*_, k) in zip(hz, HR_ZONES)))
        out["trimp_banister"] = trimp_banister(rec["dur_s"] / 60, rec["hr_mean_bpm"], hr_rest, hr_max)
    else:
        out["trimp_edwards"] = out["trimp_banister"] = np.nan
    return out
