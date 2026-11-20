"""Paramètres communs : chemins, coureurs, seuils d'alerte et palette fixe.

Tout ce qui est « réglage » du projet vit ici, pour que le pipeline, les
notebooks et l'app utilisent exactement les mêmes valeurs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_RIDES = DATA / "Data_Cyclist"
RAW_PSY = DATA / "Data_interne_psy"
OUTPUTS = ROOT / "outputs"

# --------------------------------------------------------------------------
# Coureurs (le poids est lu dans le nom du dossier : cyclistN_XXkg)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Cyclist:
    id: str          # "cyclist4"
    num: int         # 4
    weight_kg: float
    folder: Path

    @property
    def label(self) -> str:
        return f"Coureur {self.num}"

    @property
    def short(self) -> str:
        return f"C{self.num}"


def list_cyclists() -> list[Cyclist]:
    out = []
    for d in sorted(RAW_RIDES.glob("cyclist*_*kg")):
        m = re.fullmatch(r"cyclist(\d+)_(\d+)kg", d.name)
        if m:
            out.append(Cyclist(f"cyclist{m[1]}", int(m[1]), float(m[2]), d))
    return sorted(out, key=lambda c: c.num)


# --------------------------------------------------------------------------
# Hypothèses physiologiques
# --------------------------------------------------------------------------
# FC de repos : fournie seulement pour le coureur 4. Pour les autres, valeur
# conventionnelle d'un cycliste entraîné (hypothèse documentée dans Méthodes).
HR_REST_DEFAULT_BPM = 50
HR_REST_FILE = RAW_RIDES / "cyclist3_65kg" / "fc_repos_cycliste4.csv"  # rangé dans le dossier 3 par erreur
HR_REST_FILE_OWNER = "cyclist4"

FTP_FACTOR = 0.95          # FTP ≈ 0,95 × meilleure puissance 20 min
FTP_WINDOW_MONTHS = 3      # FTP du mois M = 0,95 × meilleur 20 min sur M-2..M
CTL_DAYS, ATL_DAYS = 42, 7
WARMUP_DAYS = 42           # CTL non interprétable avant ~42 jours
BASELINE_DAYS = 28         # référence glissante pour les z-scores bien-être
SWC_FACTOR = 0.2

MMP_DURATIONS_S = [1, 2, 3, 5, 8, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 300,
                   420, 600, 900, 1200, 1800, 2400, 3600, 5400, 7200]
KEY_DURATIONS = {5: "5 s", 60: "1 min", 300: "5 min", 1200: "20 min", 3600: "60 min"}
CP_FIT_RANGE_S = (120, 900)

POWER_ZONES = [  # (nom, borne basse %FTP, borne haute %FTP) — Coggan, 5 zones
    ("Z1 Récup", 0, 55), ("Z2 Endurance", 55, 75), ("Z3 Tempo", 75, 90),
    ("Z4 Seuil", 90, 105), ("Z5 PMA+", 105, 10_000),
]
HR_ZONES = [  # (nom, % FCmax bas, haut, coefficient Edwards)
    ("Z1", 50, 60, 1), ("Z2", 60, 70, 2), ("Z3", 70, 80, 3), ("Z4", 80, 90, 4), ("Z5", 90, 101, 5),
]

# Profil de puissance (W/kg, hommes), bornes « non entraîné » → « niveau mondial »
# du tableau de Coggan (valeurs arrondies) : sert à situer chaque durée sur 0-100.
COGGAN_PROFILE = {
    5: (10.2, 24.0),
    60: (5.6, 11.5),
    300: (2.3, 7.6),
    1200: (1.9, 6.4),  # on utilise la FTP (≈ 0,95 × 20 min)
}

# --------------------------------------------------------------------------
# Seuils d'alerte (feux tricolores)
# --------------------------------------------------------------------------
# Fraîcheur relative = TSB / CTL (%) : le même TSB de −30 ne pèse pas pareil pour une CTL
# de 60 ou de 150. Seuils choisis pour que le rouge reste rare (3-12 % des jours selon le coureur).
TSB_BANDS = [  # (borne basse en % de la CTL, libellé, statut)
    (10, "Frais", "good"),
    (-25, "Équilibré", "good"),
    (-50, "Chargé", "warning"),
    (-1_000, "Très chargé", "critical"),
]
HOOPER_Z_WARN, HOOPER_Z_CRIT = 1.0, 2.0     # z > 1 : moins bien que d'habitude
COMPLIANCE_WARN, COMPLIANCE_CRIT = 0.80, 0.60
LOAD_JUMP_WARN = 0.30   # charge 7 j > +30 % de la moyenne 28 j : hausse marquée (descriptif)

# --------------------------------------------------------------------------
# Palette fixe (thème sombre). Une couleur = une métrique, partout.
# Pas de vert/orange/rouge pour les métriques : ils sont réservés aux alertes.
# --------------------------------------------------------------------------
SURFACE = "#1a1a19"
PAGE = "#0d0d0d"
INK = "#f0efec"
INK_2 = "#c3c2b7"
MUTED = "#898781"
GRID = "#2c2c2a"
AXIS = "#383835"

METRIC = {
    "power": "#9085e9",     # puissance, W/kg, charge externe (TSS)
    "hr": "#d95926",        # fréquence cardiaque, TRIMP
    "ctl": "#3987e5",       # forme (charge chronique)
    "atl": "#d55181",       # fatigue (charge aiguë)
    "tsb": INK_2,           # fraîcheur
    "srpe": "#c98500",      # charge interne ressentie
    "hooper": "#199e70",    # bien-être
    "lactate": "#e66767",
    "speed": "#3987e5",
    "alt": "#6b6a64",
}
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b", "na": "#55544f"}
STATUS_ICON = {"good": "●", "warning": "▲", "serious": "▲", "critical": "■", "na": "○"}

# Identité des coureurs dans les comparaisons : ordre catégoriel fixe (jamais recyclé).
RIDER_COLORS = {
    "cyclist1": "#3987e5", "cyclist2": "#d95926", "cyclist3": "#199e70", "cyclist4": "#c98500",
    "cyclist5": "#d55181", "cyclist6": "#0ca30c", "cyclist7": "#9085e9",
}
# Zones de puissance : rampe ordinale d'une seule teinte (plus clair = plus intense).
ZONE_COLORS = ["#1c5cab", "#2a78d6", "#5598e7", "#86b6ef", "#cde2fb"]
