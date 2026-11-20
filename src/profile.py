"""Profil de performance : courbe de puissance record, FTP, CP / W', type de coureur."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import COGGAN_PROFILE, CP_FIT_RANGE_S, FTP_FACTOR, FTP_WINDOW_MONTHS


def record_curve(ride_mmp: pd.DataFrame) -> pd.DataFrame:
    """Courbe record (une ligne par durée) sur les sorties fournies.

    `ride_mmp` : format long (cyclist, file, date, dur_s, p_w, p_wkg).
    """
    if ride_mmp.empty:
        return pd.DataFrame(columns=["dur_s", "p_w", "p_wkg", "date", "file"])
    idx = ride_mmp.dropna(subset=["p_w"]).groupby("dur_s")["p_w"].idxmax()
    return ride_mmp.loc[idx, ["dur_s", "p_w", "p_wkg", "date", "file"]].sort_values("dur_s").reset_index(drop=True)


def monthly_ftp(ride_mmp: pd.DataFrame) -> pd.DataFrame:
    """FTP par mois = 0,95 × meilleur 20 min sur le mois et les 2 précédents.

    Une fenêtre glissante évite qu'un mois léger (repos, coupure) fasse chuter
    la FTP, ce qui gonflerait artificiellement le TSS des sorties suivantes.
    """
    d = ride_mmp[ride_mmp["dur_s"] == 1200].dropna(subset=["p_w"]).copy()
    d["month"] = d["date"].dt.to_period("M")
    best = d.groupby("month")["p_w"].max()
    if best.empty:
        return pd.DataFrame(columns=["month", "best20_w", "ftp_w"])
    months = pd.period_range(best.index.min(), best.index.max(), freq="M")
    best = best.reindex(months)
    win = best.rolling(FTP_WINDOW_MONTHS, min_periods=1).max()
    # premiers mois : pas encore d'historique → on prend le meilleur des 3 premiers mois
    first = best.iloc[:FTP_WINDOW_MONTHS].max()
    win.iloc[:FTP_WINDOW_MONTHS] = win.iloc[:FTP_WINDOW_MONTHS].fillna(first).clip(lower=first)
    win = win.ffill()
    return pd.DataFrame({"month": months, "best20_w": best.values, "ftp_w": (win * FTP_FACTOR).values})


def fit_cp(curve: pd.DataFrame, lo: int = CP_FIT_RANGE_S[0], hi: int = CP_FIT_RANGE_S[1]) -> dict:
    """Puissance critique : travail = CP·t + W' (équivaut à P = CP + W'/t), records 2-15 min."""
    d = curve[(curve["dur_s"] >= lo) & (curve["dur_s"] <= hi)].dropna(subset=["p_w"])
    if len(d) < 3:
        return dict(cp_w=np.nan, wprime_j=np.nan, r2=np.nan)
    t = d["dur_s"].to_numpy(float)
    work = d["p_w"].to_numpy(float) * t
    slope, intercept = np.polyfit(t, work, 1)
    pred = slope * t + intercept
    r2 = 1 - np.sum((work - pred) ** 2) / np.sum((work - work.mean()) ** 2)
    return dict(cp_w=float(slope), wprime_j=float(intercept), r2=float(r2))


def profile_scores(curve: pd.DataFrame, weight_kg: float) -> pd.DataFrame:
    """Situe 5 s, 1 min, 5 min et FTP sur une échelle 0-100 (tableau de Coggan)."""
    rows = []
    for dur, (low, high) in COGGAN_PROFILE.items():
        p = curve.loc[curve["dur_s"] == dur, "p_w"]
        p = float(p.iloc[0]) if len(p) else np.nan
        if dur == 1200:
            p *= FTP_FACTOR
        wkg = p / weight_kg
        rows.append(dict(dur_s=dur, wkg=wkg, score=float(np.clip((wkg - low) / (high - low) * 100, 0, 100))))
    return pd.DataFrame(rows)


PHENOTYPES = {
    5: ("Sprinteur", "Explosivité sur quelques secondes au-dessus de son niveau d'ensemble."),
    60: ("Puncheur", "Capacité anaérobie (efforts d'environ 1 min) supérieure au reste du profil."),
    300: ("Grimpeur · PMA", "Puissance maximale aérobie (efforts de 3 à 8 min) au-dessus du reste."),
    1200: ("Rouleur", "Endurance au seuil (FTP) plus forte que les qualités explosives."),
}


def phenotype(scores: pd.DataFrame) -> tuple[str, str]:
    s = scores.dropna(subset=["score"])
    if s.empty:
        return "Profil incomplet", "Pas assez de données de puissance."
    if s["score"].max() - s["score"].min() < 8:
        return "Complet", "Profil équilibré : aucune durée ne se détache nettement."
    return PHENOTYPES[int(s.loc[s["score"].idxmax(), "dur_s"])]
