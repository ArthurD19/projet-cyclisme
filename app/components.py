"""Briques communes de l'app : données (lecture seule de outputs/), style, graphiques."""
from __future__ import annotations

import sys
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import (AXIS, GRID, INK, INK_2, METRIC, MUTED, OUTPUTS, PAGE, RIDER_COLORS,  # noqa: E402
                        STATUS, STATUS_ICON, SURFACE)

# ==========================================================================
# Données
# ==========================================================================


def _read(name: str, **kw) -> pd.DataFrame:
    path = OUTPUTS / f"{name}.parquet"
    if not path.exists():
        st.error(f"`outputs/{name}.parquet` introuvable : lancez d'abord `python -m src.build`.")
        st.stop()
    return pd.read_parquet(path, **kw)


@st.cache_data(show_spinner=False)
def riders() -> pd.DataFrame:
    return _read("riders").set_index("cyclist")


@st.cache_data(show_spinner=False)
def rides() -> pd.DataFrame:
    r = _read("rides")
    return r[~r["artifact"]].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def daily() -> pd.DataFrame:
    return _read("daily")


@st.cache_data(show_spinner=False)
def ride_mmp() -> pd.DataFrame:
    return _read("ride_mmp")


@st.cache_data(show_spinner=False)
def ftp() -> pd.DataFrame:
    return _read("ftp")


@st.cache_data(show_spinner=False, max_entries=64)
def trace(cyclist: str, file: str) -> pd.DataFrame:
    return _read("traces", filters=[("cyclist", "==", cyclist), ("file", "==", file)])


def rider_label(cid: str) -> str:
    r = riders().loc[cid]
    return f"{r['label']} · {r['weight_kg']:.0f} kg"


def rider_options() -> list[str]:
    return list(riders().sort_values("num").index)


# ==========================================================================
# Format (français : espace fine pour les milliers, virgule décimale)
# ==========================================================================


def fmt(x, dec: int = 0, unit: str = "", sign: bool = False) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    if round(float(x), dec) == 0:
        x = 0.0
    s = f"{x:+,.{dec}f}" if sign else f"{x:,.{dec}f}"
    s = s.replace(",", " ").replace(".", ",").replace("-", "−")
    return f"{s} {unit}" if unit else s


def fmt_dur(seconds: float) -> str:
    if not np.isfinite(seconds):
        return "—"
    h, m = divmod(int(round(seconds / 60)), 60)
    return f"{h} h {m:02d}" if h else f"{m} min"


MONTHS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def fmt_date(d, year: bool = True) -> str:
    d = pd.Timestamp(d)
    return f"{d.day} {MONTHS_FR[d.month - 1]}" + (f" {d.year}" if year else "")


# ==========================================================================
# Style
# ==========================================================================

CSS = f"""
<style>
:root {{
  --surface: {SURFACE}; --page: {PAGE}; --ink: {INK}; --ink2: {INK_2}; --muted: {MUTED};
  --grid: {GRID}; --axis: {AXIS}; --accent: {METRIC['power']};
}}
.block-container {{ padding-top: 4.6rem; max-width: 1380px; }}
h1, h2, h3 {{ letter-spacing: .01em; }}
h1 {{ text-transform: uppercase; }}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ text-transform: uppercase; font-size: 1.05rem; color: var(--ink2); }}

/* En-tête de page */
.kicker {{ font: 600 .78rem/1 Inter, sans-serif; letter-spacing: .18em; text-transform: uppercase; color: var(--accent); margin-bottom: .35rem; }}
.page-title {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 2.9rem; line-height: 1;
  text-transform: uppercase; color: var(--ink); margin: 0 0 .4rem; }}
.page-sub {{ color: var(--ink2); font-size: 1.02rem; max-width: 70ch; margin-bottom: 1.2rem; }}

/* Tuiles KPI */
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin: .3rem 0 1.4rem; }}
.kpi {{ background: var(--surface); border: 1px solid rgba(255,255,255,.07); border-radius: 14px; padding: 14px 16px 12px;
  position: relative; overflow: hidden; }}
.kpi::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--kc, var(--axis)); }}
.kpi .l {{ font-size: .74rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }}
.kpi .v {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 2.05rem; color: var(--ink); line-height: 1.1; margin-top: 4px; }}
.kpi .v small {{ font-family: Inter, sans-serif; font-size: .85rem; font-weight: 500; color: var(--ink2); margin-left: 3px; }}
.kpi .s {{ font-size: .8rem; color: var(--ink2); margin-top: 2px; }}

/* Pastilles de statut : toujours icône + texte */
.pill {{ display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px 3px 8px; border-radius: 999px;
  font-size: .78rem; font-weight: 500; color: var(--ink); background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.08); white-space: nowrap; }}
.pill i {{ font-style: normal; font-size: .72rem; }}

/* Carte coureur (vue équipe) */
.rcards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(255px, 1fr)); gap: 14px; margin-bottom: 1.2rem; }}
.rcard {{ background: linear-gradient(160deg, #20201e 0%, var(--surface) 55%); border: 1px solid rgba(255,255,255,.07);
  border-radius: 16px; padding: 14px 16px 12px; position: relative; overflow: hidden; }}
.rcard .top {{ display: flex; justify-content: space-between; align-items: flex-start; }}
.rcard .num {{ font-family: 'Barlow Condensed', sans-serif; font-size: 3.1rem; font-weight: 700; line-height: .9; color: var(--ink); }}
.rcard .num span {{ font-size: 1rem; color: var(--muted); font-weight: 500; letter-spacing: .1em; display: block; }}
.rcard .meta {{ text-align: right; font-size: .78rem; color: var(--ink2); line-height: 1.5; }}
.rcard .meta b {{ color: var(--ink); font-weight: 600; }}
.rcard .light {{ position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--lc); }}
.rcard .rows {{ margin-top: 10px; display: grid; gap: 6px; }}
.rcard .row {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: .8rem; color: var(--ink2); }}
.rcard .row > span:first-child {{ white-space: nowrap; }}
.rcard .pill {{ min-width: 0; overflow: hidden; text-overflow: ellipsis; }}
.rcard .na {{ color: var(--muted); font-size: .85rem; padding: 18px 0 8px; }}
.rcard svg {{ display: block; margin-top: 8px; }}

/* Bandeau d'accueil */
.hero {{ position: relative; border-radius: 22px; overflow: hidden; padding: 34px 34px 120px;
  background: radial-gradient(1200px 400px at 85% -10%, rgba(144,133,233,.22), transparent 60%),
              radial-gradient(800px 300px at 0% 120%, rgba(57,135,229,.18), transparent 60%), var(--surface);
  border: 1px solid rgba(255,255,255,.07); margin-bottom: 1.4rem; }}
.hero h1 {{ font-family: 'Barlow Condensed', sans-serif; font-size: 4.2rem; line-height: .92; margin: 0; text-transform: uppercase; color: var(--ink); }}
.hero p {{ color: var(--ink2); max-width: 62ch; font-size: 1.05rem; margin-top: .8rem; }}
.hero svg {{ position: absolute; left: 0; right: 0; bottom: 0; width: 100%; height: 130px; }}
.hero .cap {{ position: absolute; right: 22px; bottom: 12px; font-size: .72rem; color: var(--muted); letter-spacing: .06em; }}

.nav-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; }}
.nav-card {{ background: var(--surface); border: 1px solid rgba(255,255,255,.07); border-radius: 16px; padding: 18px; min-height: 178px; }}
.nav-card h4 {{ font-family: 'Barlow Condensed', sans-serif; text-transform: uppercase; font-size: 1.35rem; margin: 0 0 .3rem; color: var(--ink); }}
.nav-card p {{ color: var(--ink2); font-size: .88rem; margin: 0; }}
.nav-card .tag {{ font-size: .7rem; color: var(--accent); letter-spacing: .14em; text-transform: uppercase; }}

.note {{ color: var(--muted); font-size: .8rem; margin-top: -.4rem; }}
.callout {{ border-left: 3px solid var(--accent); background: rgba(144,133,233,.07); padding: 10px 14px; border-radius: 0 10px 10px 0;
  color: var(--ink2); font-size: .9rem; margin: .4rem 0 1rem; }}
.legend-inline {{ display: flex; flex-wrap: wrap; gap: 14px; font-size: .8rem; color: var(--ink2); margin: -.2rem 0 .6rem; }}
.legend-inline span::before {{ content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; background: var(--c); vertical-align: -1px; }}
div[data-testid="stTabs"] button p {{ font-family: 'Barlow Condensed', sans-serif; font-size: 1.12rem; text-transform: uppercase; letter-spacing: .04em; }}
</style>
"""


def setup(title: str, icon: str = ":material/directions_bike:") -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def header(kicker: str, title: str, sub: str = "") -> None:
    st.markdown(
        f'<div class="kicker">{escape(kicker)}</div><div class="page-title">{escape(title)}</div>'
        + (f'<div class="page-sub">{sub}</div>' if sub else ""),
        unsafe_allow_html=True,
    )


def kpis(items: list[dict]) -> None:
    """items : dicts (label, value, unit?, sub?, color?)."""
    html = []
    for it in items:
        unit = f"<small>{escape(it['unit'])}</small>" if it.get("unit") else ""
        sub = f'<div class="s">{it["sub"]}</div>' if it.get("sub") else ""
        html.append(f'<div class="kpi" style="--kc:{it.get("color", AXIS)}"><div class="l">{escape(it["label"])}</div>'
                    f'<div class="v">{it["value"]}{unit}</div>{sub}</div>')
    st.markdown(f'<div class="kpis">{"".join(html)}</div>', unsafe_allow_html=True)


def pill(status: str, text: str) -> str:
    return (f'<span class="pill"><i style="color:{STATUS[status]}">{STATUS_ICON[status]}</i>{escape(text)}</span>')


def note(text: str) -> None:
    st.markdown(f'<div class="note">{text}</div>', unsafe_allow_html=True)


def callout(text: str) -> None:
    st.markdown(f'<div class="callout">{text}</div>', unsafe_allow_html=True)


def legend(items: list[tuple[str, str]]) -> None:
    st.markdown('<div class="legend-inline">' + "".join(
        f'<span style="--c:{c}">{escape(t)}</span>' for t, c in items) + "</div>", unsafe_allow_html=True)


def sparkline(values, color: str, w: int = 220, h: int = 38) -> str:
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    if len(v) < 2:
        return ""
    lo, hi = v.min(), v.max()
    span = hi - lo or 1
    xs = np.linspace(2, w - 6, len(v))
    ys = h - 4 - (v - lo) / span * (h - 10)
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    area = f"2,{h} " + pts + f" {xs[-1]:.1f},{h}"
    return (f'<svg width="100%" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
            f'<polygon points="{area}" fill="{color}" opacity=".12"/>'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>'
            f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="3.2" fill="{color}" stroke="{SURFACE}" stroke-width="2"/></svg>')


def profile_silhouette(alt: np.ndarray, w: int = 1200, h: int = 130) -> str:
    """Silhouette d'un profil d'altitude réel (bandeau d'accueil)."""
    a = pd.Series(alt).interpolate().bfill().ffill().rolling(5, center=True, min_periods=1).mean().to_numpy()
    lo, hi = np.nanmin(a), np.nanmax(a)
    xs = np.linspace(0, w, len(a))
    ys = h - 6 - (a - lo) / ((hi - lo) or 1) * (h - 22)
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none"><defs><linearGradient id="g" x1="0" x2="0" y1="0" y2="1">'
            f'<stop offset="0" stop-color="{METRIC["power"]}" stop-opacity=".45"/><stop offset="1" stop-color="{METRIC["power"]}" stop-opacity="0"/>'
            f'</linearGradient></defs><polygon points="0,{h} {pts} {w},{h}" fill="url(#g)"/>'
            f'<polyline points="{pts}" fill="none" stroke="{METRIC["power"]}" stroke-width="2"/></svg>')


# ==========================================================================
# Graphiques plotly (template unique)
# ==========================================================================

FONT = "Inter, system-ui, -apple-system, Segoe UI, sans-serif"

pio.templates["cellule"] = go.layout.Template(layout=dict(
    font=dict(family=FONT, size=13, color=INK_2),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    colorway=list(RIDER_COLORS.values()),
    title=dict(font=dict(family=FONT, size=17, color=INK), x=0, xref="container", xanchor="left", y=1, yref="container", yanchor="top", pad=dict(t=14, l=4, b=10)),
    margin=dict(l=64, r=28, t=104, b=60, autoexpand=True),
    xaxis=dict(automargin=True, gridcolor=GRID, linecolor=AXIS, zeroline=False, tickcolor=AXIS, ticks="", showgrid=False,
               title=dict(font=dict(size=12, color=MUTED)), tickfont=dict(color=MUTED)),
    yaxis=dict(automargin=True, gridcolor=GRID, linecolor=AXIS, zeroline=False, showline=False, ticks="",
               title=dict(font=dict(size=12, color=MUTED)), tickfont=dict(color=MUTED)),
    legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0, xanchor="left", bgcolor="rgba(0,0,0,0)",
                font=dict(color=INK_2, size=12), title=dict(text="")),
    hoverlabel=dict(bgcolor="#262624", bordercolor="#3a3a37", font=dict(family=FONT, color=INK, size=12)),
    hovermode="closest",
    separators=", ",
))
pio.templates.default = "cellule"


def titled(fig: go.Figure, title: str, sub: str = "", height: int = 380) -> go.Figure:
    """Titre = la conclusion ; sous-titre = ce qu'on regarde."""
    text = f"<b>{title}</b>" + (f"<br><span style='font-size:12.5px;color:{MUTED}'>{sub}</span>" if sub else "")
    fig.update_layout(title=dict(text=text), height=height)
    return fig


def _date_span(fig: go.Figure):
    lo = hi = None
    for tr in fig.data:
        x = getattr(tr, "x", None)
        if x is None or len(x) == 0:
            continue
        try:
            xs = pd.to_datetime(pd.Series(np.asarray(x)), errors="raise")
        except (ValueError, TypeError):
            return None
        if not pd.api.types.is_datetime64_any_dtype(xs) or xs.isna().all():
            return None
        lo = xs.min() if lo is None else min(lo, xs.min())
        hi = xs.max() if hi is None else max(hi, xs.max())
    return (lo, hi) if lo is not None else None


def french_dates(fig: go.Figure) -> None:
    """Graduations mensuelles en français sur les axes de dates (plotly n'a pas la locale fr chargée)."""
    if fig.layout.xaxis.tickvals is not None or fig.layout.xaxis.type in ("log", "category"):
        return
    span = _date_span(fig)
    if span is None:
        return
    lo, hi = span
    months = (hi.year - lo.year) * 12 + hi.month - lo.month
    step = 1 if months <= 8 else 2 if months <= 15 else 3
    ticks = pd.date_range(lo.to_period("M").start_time, hi + pd.offsets.MonthBegin(1), freq=f"{step}MS")
    text = [f"{MONTHS_FR[t.month - 1]}" + (f" {t.year}" if t.month == 1 or i == 0 else "") for i, t in enumerate(ticks)]
    fig.update_xaxes(tickvals=ticks, ticktext=text, tickangle=0)


def show(fig: go.Figure, key: str | None = None) -> None:
    french_dates(fig)
    st.plotly_chart(fig, theme=None, key=key, config={"displayModeBar": False, "locale": "fr"})


def hex_rgba(hex_color: str, a: float) -> str:
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def period_filter(dmin, dmax, key: str, label: str = "Période") -> tuple[pd.Timestamp, pd.Timestamp]:
    """Filtre de période (barre latérale) : préréglages + plage personnalisée."""
    dmin, dmax = pd.Timestamp(dmin), pd.Timestamp(dmax)
    presets = {"Tout": None, "12 mois": 365, "90 jours": 90, "6 semaines": 42}
    choice = st.sidebar.segmented_control(label, list(presets) + ["Perso"], default="Tout", key=f"{key}_p")
    choice = choice or "Tout"
    if choice == "Perso":
        v = st.sidebar.date_input("Du … au …", (dmin.date(), dmax.date()), min_value=dmin.date(),
                                  max_value=dmax.date(), key=f"{key}_d", format="DD/MM/YYYY")
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return pd.Timestamp(v[0]), pd.Timestamp(v[1])
        return dmin, dmax
    days = presets[choice]
    return (max(dmin, dmax - pd.Timedelta(days=days - 1)) if days else dmin), dmax
