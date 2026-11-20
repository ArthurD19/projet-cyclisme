"""Lecture et nettoyage des données brutes (jamais modifiées sur disque)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .config import HR_REST_FILE, RAW_PSY, Cyclist

USE_COLS = ["secs", "km", "kph", "hr", "cad", "watts", "alt", "slope", "lat", "lon", "temp", "lrbalance"]
MAX_VALID_WATTS = 2500   # au-delà : pic capteur
HR_VALID = (30, 230)


def list_ride_files(c: Cyclist) -> list[Path]:
    """Tous les CSV d'un coureur (à plat ou rangés par année)."""
    files = [p for p in c.folder.rglob("*.csv") if p.stem[:4].isdigit() and len(p.stem) == 19]
    return sorted(files, key=lambda p: p.name)


def ride_start(path: Path | str) -> datetime:
    return datetime.strptime(Path(path).stem, "%Y_%m_%d_%H_%M_%S")


def read_ride(path: Path | str) -> pd.DataFrame:
    """Une sortie, 1 ligne par seconde enregistrée, valeurs manquantes en NaN."""
    df = pd.read_csv(path, engine="pyarrow")
    df = df[[c for c in USE_COLS if c in df.columns]].copy()
    for col in USE_COLS:
        if col not in df:
            df[col] = np.nan
    df = df.astype("float64")

    w = df["watts"].clip(lower=0)
    df["watts"] = w.mask(w > MAX_VALID_WATTS, 0.0)          # NP : on garde les 0 W
    df["hr"] = df["hr"].where(df["hr"].between(*HR_VALID))   # 0 = capteur absent
    df["temp"] = df["temp"].mask(df["temp"] <= -100)          # -255 = manquant
    df["lrbalance"] = df["lrbalance"].where(df["lrbalance"].between(0.01, 99.99))
    df["slope"] = df["slope"].mask(df["slope"] == 0)
    for col in ("lat", "lon"):
        df[col] = df[col].mask(df[col] == 0)
    return df


def is_zwift(df: pd.DataFrame) -> bool:
    """GPS dans le Pacifique (îles Zwift) = sortie indoor."""
    lat, lon = df["lat"].median(), df["lon"].median()
    return bool(-12 < lat < -9 and 164 < lon < 168) if pd.notna(lat) else False


def read_psy(c: Cyclist) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Feuilles `seances` (RPE, lactate) et `hooper` du classeur du coureur."""
    path = RAW_PSY / f"Charge_interne_psy_cycliste{c.num}.xlsx"
    seances = pd.read_excel(path, sheet_name="seances")
    hooper = pd.read_excel(path, sheet_name="hooper")
    seances["date"] = pd.to_datetime(seances["date"]).dt.normalize()
    hooper["date"] = pd.to_datetime(hooper["date"]).dt.normalize()
    seances["fichier"] = seances["fichier"].astype(str)
    seances = seances.rename(columns={"lactate": "lactate_mmol"})
    return seances[["fichier", "rpe", "lactate_mmol"]], hooper[["date", "sommeil", "stress", "fatigue", "courbatures"]]


def read_hr_rest() -> pd.Series:
    """FC de repos du coureur 4, par jour. Valeurs aberrantes (> médiane + 15) retirées."""
    df = pd.read_csv(HR_REST_FILE, sep=";", encoding="utf-8-sig")
    df.columns = ["date", "hr_rest_bpm"]
    # horodatage 22-23 h UTC = mesure du lendemain matin (heure de Paris)
    df["date"] = (pd.to_datetime(df["date"]) + pd.Timedelta(hours=2)).dt.normalize()
    s = df.groupby("date")["hr_rest_bpm"].median()
    return s[s <= s.median() + 15]
