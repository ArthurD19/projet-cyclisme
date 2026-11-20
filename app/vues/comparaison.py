import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import components as ui
from src import profile
from src.config import INK, INK_2, KEY_DURATIONS, METRIC, MUTED, POWER_ZONES, RIDER_COLORS, ZONE_COLORS

ui.setup("Comparaison")
R, RIDES, D, MMP = ui.riders(), ui.rides(), ui.daily(), ui.ride_mmp()
ids = ui.rider_options()

st.sidebar.markdown("### Coureurs comparés")
sel = st.sidebar.pills("Coureurs", ids, selection_mode="multi", default=ids, format_func=lambda c: f"C{R.loc[c, 'num']}",
                       label_visibility="collapsed")
sel = [c for c in ids if c in (sel or [])]
st.sidebar.markdown("### Période comparée")
months = st.sidebar.slider("Mois de saison", 1, 12, (1, 12), help="Même fenêtre de mois pour tous, quelle que soit l'année")
season = st.sidebar.selectbox("Saison des coureurs suivis 2 ans", ["La plus récente", "2022", "2023"])
st.sidebar.caption("Les coureurs ne sont pas suivis la même année : on compare les <b>mêmes mois de saison</b>, "
                   "en W/kg ou en % de la FTP de chacun.", unsafe_allow_html=True)

ui.header("Comparer juste", "Comparaison de l'effectif",
          "Uniquement des grandeurs comparables : puissance rapportée au poids, intensité rapportée à la FTP de chacun, "
          "mêmes mois de saison. La FC et la vitesse ne sont pas comparées entre coureurs.")

if len(sel) < 2:
    st.info("Choisissez au moins deux coureurs dans la barre latérale.")
    st.stop()


def season_of(cid: str) -> int:
    years = [int(y) for y in R.loc[cid, "seasons"].split(", ")]
    return max(years) if season == "La plus récente" or int(season) not in years else int(season)


def in_window(df: pd.DataFrame, cid: str) -> pd.DataFrame:
    y = season_of(cid)
    m = df["date"].dt.month
    return df[(df["cyclist"] == cid) & (df["date"].dt.year == y) & m.between(*months)]


def short(cid):
    return f"C{R.loc[cid, 'num']}"


curves = {c: profile.record_curve(in_window(MMP, c)) for c in sel}
cps = {c: profile.fit_cp(curves[c]) for c in sel}

# ---------------------------------------------------------------- KPI
best = {c: curves[c].set_index("dur_s")["p_wkg"] for c in sel}
def leader(dur):
    v = {c: best[c].get(dur, np.nan) for c in sel}
    c = max(v, key=lambda k: -1 if not np.isfinite(v[k]) else v[k])
    return c, v[c]
items = []
for dur, lab in [(5, "Sprint 5 s"), (60, "1 min"), (300, "5 min"), (1200, "20 min")]:
    c, v = leader(dur)
    items.append(dict(label=f"Meilleur {lab}", value=ui.fmt(v, 1), unit="W/kg", sub=f"{R.loc[c, 'label']}",
                      color=RIDER_COLORS[c]))
c = max(sel, key=lambda k: cps[k]["cp_w"] / R.loc[k, "weight_kg"])
items.append(dict(label="Meilleure CP", value=ui.fmt(cps[c]["cp_w"] / R.loc[c, "weight_kg"], 2), unit="W/kg",
                  sub=R.loc[c, "label"], color=RIDER_COLORS[c]))
ui.kpis(items)

# ---------------------------------------------------------------- Courbes de puissance
LOG_TICKS = dict(tickvals=[1, 5, 15, 60, 300, 1200, 3600], ticktext=["1 s", "5 s", "15 s", "1 min", "5 min", "20 min", "1 h"], tickangle=0)
a, b = st.columns([1.3, 1])
with a:
    fig = go.Figure()
    for c in sel:
        cu = curves[c][curves[c]["dur_s"] <= 3600]
        fig.add_trace(go.Scatter(x=cu["dur_s"], y=cu["p_wkg"], name=short(c), line=dict(color=RIDER_COLORS[c], width=2, shape="spline"),
                                 customdata=cu["p_w"], hovertemplate=short(c) + " · %{y:.2f} W/kg (%{customdata:.0f} W)<extra></extra>"))
    fig.update_xaxes(type="log", **LOG_TICKS, showgrid=True, gridcolor="#242422", title="Durée de l'effort")
    fig.update_yaxes(type="log", title="W/kg (échelle log)", showgrid=True,
                     tickvals=[3, 4, 5, 6, 8, 10, 12, 15, 20, 25])
    fig.update_layout(hovermode="x unified")
    c5, v5 = leader(5)
    c60, _ = leader(1200)
    t = (f"{short(c5)} le plus explosif, {short(c60)} le plus fort sur 20 min" if c5 != c60
         else f"{short(c5)} domine du sprint au seuil")
    ui.show(ui.titled(fig, t, "Courbes de puissance record en W/kg sur les mêmes mois de saison", height=470))
with b:
    rows = []
    for c in sel:
        sc = profile.profile_scores(curves[c], R.loc[c, "weight_kg"])
        for s in sc.itertuples():
            rows.append(dict(c=c, dur=s.dur_s, wkg=s.wkg, score=s.score))
    P = pd.DataFrame(rows)
    names = {5: "Sprint 5 s", 60: "1 min", 300: "5 min", 1200: "FTP"}
    fig = go.Figure()
    for i, (dur, nm) in enumerate(names.items()):
        p = P[P["dur"] == dur]
        fig.add_shape(type="line", x0=p["wkg"].min(), x1=p["wkg"].max(), y0=nm, y1=nm, line=dict(color="#3a3a37", width=6),
                      layer="below")
    for c in sel:
        p = P[P["c"] == c]
        fig.add_trace(go.Scatter(x=p["wkg"], y=[names[x] for x in p["dur"]], mode="markers", name=short(c),
                                 marker=dict(size=14, color=RIDER_COLORS[c], line=dict(color="#1a1a19", width=2)),
                                 customdata=p["score"],
                                 hovertemplate=short(c) + " · %{x:.2f} W/kg<br>niveau %{customdata:.0f}/100<extra></extra>"))
    fig.update_xaxes(type="log", title="W/kg (échelle log)", showgrid=True, tickvals=[3, 4, 5, 6, 8, 10, 12, 15, 20, 25])
    fig.update_yaxes(autorange="reversed", tickfont=dict(color=INK_2, size=13))
    spread = P.groupby("dur")["wkg"].agg(lambda s: s.max() / s.min() - 1)
    t = f"Plus gros écart : {names[int(spread.idxmax())].lower()} (+{ui.fmt(spread.max() * 100)} %)"
    ui.show(ui.titled(fig, t, "Quatre qualités clés en W/kg · chaque point = un coureur", height=470))

# ---------------------------------------------------------------- Distribution d'intensité + forme alignée
a, b = st.columns([1, 1.2])
with a:
    Z = []
    for c in sel:
        w = in_window(RIDES, c)
        z = w[[f"pz{i}_s" for i in range(1, 6)]].sum()
        Z.append((z / z.sum() * 100).rename(short(c)))
    Z = pd.DataFrame(Z)
    fig = go.Figure()
    for i, (nm, *_) in enumerate(POWER_ZONES):
        col = Z.iloc[:, i]
        fig.add_trace(go.Bar(y=Z.index, x=col, name=nm, orientation="h",
                             marker=dict(color=ZONE_COLORS[i], line=dict(color="#0d0d0d", width=2)),
                             text=[f"{v:.0f} %" if v >= 7 else "" for v in col], textposition="inside", insidetextanchor="middle",
                             textfont=dict(color="#0b0b0b" if i >= 3 else INK, size=11),
                             hovertemplate="%{y} · " + nm + " : %{x:.1f} %<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=.3, legend=dict(traceorder="normal"))
    fig.update_xaxes(range=[0, 100], ticksuffix=" %", showgrid=True)
    fig.update_yaxes(autorange="reversed", tickfont=dict(color=INK_2, size=13))
    hi_int = (Z.iloc[:, 3:].sum(axis=1)).idxmax()
    ui.show(ui.titled(fig, f"{hi_int} passe le plus de temps au seuil et au-dessus",
                      "Temps par zone, en % de la FTP de chacun", height=430))
with b:
    fig = go.Figure()
    for c in sel:
        d = D[(D["cyclist"] == c) & (D["date"].dt.year == season_of(c))].copy()
        d["doy"] = d["date"].dt.dayofyear
        d = d[d["date"].dt.month.between(*months)]
        d.loc[d["warmup"], "ctl"] = np.nan
        fig.add_trace(go.Scatter(x=d["doy"], y=d["ctl"], name=short(c),
                                 line=dict(color=RIDER_COLORS[c], width=2),
                                 hovertemplate=short(c) + " · jour %{x}<br>CTL %{y:.0f}<extra></extra>"))
    ticks = pd.date_range("2023-01-01", "2023-12-01", freq="MS")
    fig.update_xaxes(tickvals=ticks.dayofyear, ticktext=[ui.MONTHS_FR[t.month - 1] for t in ticks], showgrid=True,
                     title="Mois de saison")
    fig.update_yaxes(title="Forme (CTL, TSS/jour)", showgrid=True)
    fig.update_layout(hovermode="x unified")
    peaks = {short(c): D[(D["cyclist"] == c) & (D["date"].dt.year == season_of(c)) & ~D["warmup"]]
             .set_index("date")["ctl"].idxmax() for c in sel}
    pk = pd.Series({k: v.month for k, v in peaks.items()})
    t = f"Pics de forme entre {ui.MONTHS_FR[pk.min() - 1]} et {ui.MONTHS_FR[pk.max() - 1]} selon les coureurs"
    ui.show(ui.titled(fig, t, "Charge chronique (CTL) alignée sur le jour de la saison · 42 premiers jours masqués", height=430))
    ui.note("La CTL est en TSS, donc relative à la FTP de chacun : elle compare des charges d'entraînement, pas des niveaux.")

# ---------------------------------------------------------------- Tableau récapitulatif
rows = []
for c in sel:
    w = in_window(RIDES, c)
    dd = in_window(D, c)
    rr = R.loc[c]
    kg = rr["weight_kg"]
    rows.append({
        "Coureur": rr["label"], "Poids (kg)": kg, "Profil": rr["phenotype"],
        "FTP (W/kg)": best[c].get(1200, np.nan) * 0.95, "CP (W/kg)": cps[c]["cp_w"] / kg, "W′ (kJ)": cps[c]["wprime_j"] / 1000,
        "Heures / sem.": w["dur_s"].sum() / 3600 / max(dd["date"].nunique() / 7, 1),
        "TSS / sem.": dd["load"].sum() / max(dd["date"].nunique() / 7, 1),
        "Hooper moyen": dd["hooper"].mean(), "Questionnaires": dd["hooper_filled"].mean() * 100,
    })
T = pd.DataFrame(rows)
st.markdown("### En chiffres, sur la même fenêtre")
st.dataframe(T, hide_index=True, column_config={
    "Poids (kg)": st.column_config.NumberColumn(format="%.0f"),
    "FTP (W/kg)": st.column_config.NumberColumn(format="%.2f"),
    "CP (W/kg)": st.column_config.NumberColumn(format="%.2f"),
    "W′ (kJ)": st.column_config.NumberColumn(format="%.1f"),
    "Heures / sem.": st.column_config.ProgressColumn(format="%.1f", min_value=0, max_value=float(T["Heures / sem."].max())),
    "TSS / sem.": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=float(T["TSS / sem."].max())),
    "Hooper moyen": st.column_config.NumberColumn(format="%.1f", help="4 = très bien · 28 = très mal"),
    "Questionnaires": st.column_config.ProgressColumn("Hooper rempli", format="%.0f %%", min_value=0, max_value=100),
})
ui.note("Le Hooper moyen est indicatif : chaque coureur utilise l'échelle à sa façon, d'où les alertes calculées "
        "par rapport à la propre habitude de chacun.")
