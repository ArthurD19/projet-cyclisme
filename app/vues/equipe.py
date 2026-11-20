import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import components as ui
from src import tracking
from src.config import INK, INK_2, METRIC, MUTED, STATUS, STATUS_ICON

ui.setup("Équipe")
R, D, F = ui.riders(), ui.daily(), ui.ftp()
ids = ui.rider_options()

# --------------------------------------------------------------------------
# Barre latérale : quelle semaine regarde-t-on ?
# --------------------------------------------------------------------------
st.sidebar.markdown("### Semaine observée")
mode = st.sidebar.segmented_control("Référence", ["Semaine de saison", "Date"], default="Semaine de saison",
                                    help="Les coureurs n'ont pas tous été suivis la même année : « semaine de saison » "
                                         "place chacun à la même semaine de sa propre saison.") or "Semaine de saison"
if mode == "Semaine de saison":
    season = st.sidebar.selectbox("Saison", ["Dernière saison de chacun", "2022", "2023"])
    week = st.sidebar.slider("Semaine", 1, 52, 28, help="Semaine de la saison (1 = début janvier)")
    ref = {}
    for cid in ids:
        years = [int(y) for y in R.loc[cid, "seasons"].split(", ")]
        y = max(years) if season.startswith("Dernière") else int(season)
        ref[cid] = (pd.Timestamp(y, 1, 1) + pd.Timedelta(days=7 * week - 1)) if y in years else None
    when = f"semaine {week}" + ("" if season.startswith("Dernière") else f" · {season}")
else:
    day = st.sidebar.date_input("Jour", pd.Timestamp(2023, 6, 4), min_value=D["date"].min(), max_value=D["date"].max(),
                                format="DD/MM/YYYY")
    ref = {cid: pd.Timestamp(day) for cid in ids}
    when = ui.fmt_date(day)

st.sidebar.markdown("### Seuils")
st.sidebar.caption("Fraîcheur = TSB en % de la forme (CTL) du coureur : > −25 % équilibré · −25 à −50 % chargé · < −50 % très chargé.  \n"
                   "Bien-être : Hooper comparé aux 28 jours précédents du coureur (z > 1 : moins bien que d'habitude).")

# --------------------------------------------------------------------------
# Statut de chaque coureur
# --------------------------------------------------------------------------
stat = {}
for cid in ids:
    d = D[D["cyclist"] == cid]
    day = ref[cid]
    if day is None or day < d["date"].min() or day > d["date"].max():
        stat[cid] = dict(available=False)
        continue
    stat[cid] = tracking.status_on(d, day)
    stat[cid]["spark"] = d[(d["date"] > day - pd.Timedelta(days=56)) & (d["date"] <= day)]["ctl"].to_numpy()
    f = F[(F["cyclist"] == cid) & (F["month"] <= day)]
    stat[cid]["ftp_wkg"] = f["ftp_w"].iloc[-1] / R.loc[cid, "weight_kg"] if len(f) else np.nan

avail = [c for c in ids if stat[c]["available"]]
n_alert = sum(stat[c]["overall"] in ("warning", "critical") for c in avail)
n_crit = sum(stat[c]["overall"] == "critical" for c in avail)
n_fresh = sum(stat[c]["tsb_status"] == "good" and stat[c]["hooper_status"] == "good" for c in avail)

ui.header("Vue collective · " + when, "L'effectif cette semaine",
          "Un coup d'œil pour savoir qui est prêt, qui encaisse et qui ne remplit plus ses questionnaires. "
          "Chaque coureur est comparé à <b>lui-même</b>.")
ui.kpis([
    dict(label="Coureurs observés", value=f"{len(avail)}/{len(ids)}", sub="avec des données cette semaine",
         color=METRIC["power"]),
    dict(label="Prêts", value=str(n_fresh), sub=f"{STATUS_ICON['good']} fraîcheur et bien-être au vert", color=STATUS["good"]),
    dict(label="À surveiller", value=str(n_alert - n_crit), sub=f"{STATUS_ICON['warning']} un indicateur à l'orange",
         color=STATUS["warning"]),
    dict(label="Alerte", value=str(n_crit), sub=f"{STATUS_ICON['critical']} un indicateur au rouge", color=STATUS["critical"]),
    dict(label="Charge moyenne 7 j", value=ui.fmt(np.nanmean([stat[c]["load_7d"] for c in avail]) if avail else np.nan),
         unit="TSS", sub="somme des 7 derniers jours", color=METRIC["power"]),
])

# --------------------------------------------------------------------------
# Cartes coureurs
# --------------------------------------------------------------------------
cards = []
for cid in ids:
    s, r = stat[cid], R.loc[cid]
    if not s["available"]:
        cards.append(f'<div class="rcard"><div class="light" style="--lc:{STATUS["na"]}"></div><div class="top">'
                     f'<div class="num"><span>COUREUR</span>{r["num"]}</div><div class="meta"><b>{r["weight_kg"]:.0f} kg</b>'
                     f'<br>saison {r["seasons"]}</div></div><div class="na">○ Pas suivi à cette date</div></div>')
        continue
    jump = s["load_change"]
    jump_txt = f"{ui.fmt(jump * 100, sign=True)} % vs 4 sem." if np.isfinite(jump) else "—"
    h_txt = s["hooper_label"] + (f" ({s['hooper']:.0f}/28)" if np.isfinite(s["hooper"]) else "")
    warm = " · forme non interprétable (début de suivi)" if s["warmup"] else ""
    rows = [
        ("Fraîcheur", ui.pill(s["tsb_status"], f"{s['tsb_label']} · {ui.fmt(s['tsb_pct'], sign=True)} %")),
        ("Bien-être", ui.pill(s["hooper_status"], h_txt)),
        ("Charge 7 j", ui.pill(s["load_status"], jump_txt)),
        ("Questionnaires", ui.pill(s["compliance_status"], f"{ui.fmt(s['compliance'] * 100)} % (28 j)")),
    ]
    rows_html = "".join(f'<div class="row"><span>{k}</span>{v}</div>' for k, v in rows)
    cards.append(
        f'<div class="rcard"><div class="light" style="--lc:{STATUS[s["overall"]]}"></div><div class="top">'
        f'<div class="num"><span>COUREUR</span>{r["num"]}</div><div class="meta"><b>{r["weight_kg"]:.0f} kg</b> · {r["phenotype"]}'
        f'<br>FTP <b>{ui.fmt(s["ftp_wkg"], 1)} W/kg</b><br>Forme (CTL) <b>{ui.fmt(s["ctl"])}</b>{warm}</div></div>'
        f'<div class="rows">{rows_html}</div>{ui.sparkline(s["spark"], METRIC["ctl"])}</div>')
st.markdown(f'<div class="rcards">{"".join(cards)}</div>', unsafe_allow_html=True)
ui.note("Barre de couleur en haut de carte = l'indicateur le plus défavorable entre fraîcheur et bien-être. "
        "Courbe bleue = forme (CTL) sur les 8 dernières semaines.")

# --------------------------------------------------------------------------
# Quadrant fraîcheur × bien-être
# --------------------------------------------------------------------------
c1, c2 = st.columns([1.05, 1])
with c1:
    q = pd.DataFrame([dict(cid=c, tsb=stat[c]["tsb_pct"], tsb_abs=stat[c]["tsb"], well=-stat[c]["hooper_z"], st=stat[c]["overall"],
                           lab=f"C{R.loc[c, 'num']}", load=stat[c]["load_7d"]) for c in avail])
    fig = go.Figure()
    if not q.empty:
        xr = max(70, float(np.nanmax(np.abs(q["tsb"]))) + 12)
        yr = max(2.6, float(np.nanmax(np.abs(q["well"].fillna(0)))) + .6)
        for (x0, x1, y0, y1, txt, xa, ya) in [(-25, xr, 0, yr, "Prêt", "right", "top"),
                                               (-xr, -25, 0, yr, "Encaisse bien la charge", "left", "top"),
                                               (-25, xr, -yr, 0, "Frais mais moral en baisse", "right", "bottom"),
                                               (-xr, -25, -yr, 0, "À surveiller", "left", "bottom")]:
            fig.add_annotation(x=x1 if xa == "right" else x0, y=y1 if ya == "top" else y0, text=txt, showarrow=False,
                               xanchor=xa, yanchor=ya, font=dict(color=MUTED, size=12))
        fig.add_shape(type="rect", x0=-xr, x1=-25, y0=-yr, y1=0, fillcolor="rgba(208,59,59,.07)", line_width=0, layer="below")
        fig.add_vline(x=-25, line=dict(color="#3a3a37", width=1))
        fig.add_hline(y=0, line=dict(color="#3a3a37", width=1))
        qq = q.dropna(subset=["well"])
        fig.add_trace(go.Scatter(
            x=qq["tsb"], y=qq["well"], mode="markers+text", text=qq["lab"], textposition="middle right",
            textfont=dict(color=INK, size=13, family="Barlow Condensed"),
            marker=dict(size=16, color=[STATUS[s] for s in qq["st"]], line=dict(color="#1a1a19", width=2)),
            customdata=np.c_[qq["load"], qq["tsb_abs"]],
            hovertemplate="<b>%{text}</b><br>Fraîcheur %{x:+.0f} % de la forme (TSB %{customdata[1]:+.0f})<br>Bien-être %{y:+.1f} écart-type vs habitude"
                          "<br>Charge 7 j %{customdata[0]:.0f} TSS<extra></extra>"))
        fig.update_xaxes(range=[-xr, xr], showticklabels=True, title="← plus chargé      Fraîcheur (TSB en % de la CTL)      plus frais →", ticksuffix=" %", showgrid=True)
        fig.update_yaxes(range=[-yr, yr], title="Bien-être vs habitude (z, inversé)", showgrid=True)
    worst = q.dropna(subset=["well"]).query("tsb < -25 and well < 0")["lab"].tolist() if not q.empty else []
    title = ("Personne dans la zone à surveiller" if not worst else
             f"{', '.join(worst)} cumule{'nt' if len(worst) > 1 else ''} charge et bien-être en baisse")
    fig.update_layout(showlegend=False)
    ui.show(ui.titled(fig, title, "Fraîcheur (TSB / CTL) × bien-être vs habitude · en haut à droite = prêt", height=460))

# --------------------------------------------------------------------------
# Carte de chaleur : charge hebdomadaire relative
# --------------------------------------------------------------------------
with c2:
    W = tracking.weekly(D)
    rows, labels = [], []
    for cid in ids:
        day = ref[cid] if ref[cid] is not None else pd.Timestamp(max(int(y) for y in R.loc[cid, "seasons"].split(", ")), 12, 31)
        w = W[(W["cyclist"] == cid) & (W["days"] == 7)].copy()
        med = w["load"].median()
        cur = day.to_period("W-SUN").start_time
        w = w[(w["week"] <= cur) & (w["week"] > cur - pd.Timedelta(weeks=12))]
        k = 11 - ((cur - w["week"]).dt.days // 7)
        rows.append(pd.Series((w["load"] / med * 100).to_numpy(), index=k.to_numpy()))
        labels.append(f"C{R.loc[cid, 'num']}")
    Z = pd.DataFrame(rows, index=labels).reindex(columns=range(12))
    xl = [f"−{11 - i}" if i < 11 else "0" for i in range(12)]
    fig = go.Figure(go.Heatmap(
        z=Z.to_numpy(), x=xl, y=labels, zmin=0, zmax=180, xgap=3, ygap=3,
        colorscale=[[0, "#1f1e2b"], [.35, "#4b4390"], [.6, "#9085e9"], [1, "#e4e0ff"]],
        colorbar=dict(title=dict(text="% d'une<br>semaine type", font=dict(size=11, color=MUTED)), thickness=10,
                      tickfont=dict(color=MUTED), ticksuffix=" %", len=.85),
        hovertemplate="%{y} · %{x}<br>%{z:.0f} % de sa semaine type<extra></extra>"))
    fig.update_yaxes(autorange="reversed", tickfont=dict(color=INK_2, size=13))
    fig.update_xaxes(tickfont=dict(size=11), tickangle=0, title="Semaines avant la semaine observée (0)")
    last = Z.iloc[:, -1]
    hi = last[last > 130].index.tolist()
    t = (f"{', '.join(hi)} au-dessus de 130 % de leur semaine type" if hi
         else "Aucune semaine nettement au-dessus de l'habitude")
    ui.show(ui.titled(fig, t, "TSS hebdo en % de la semaine médiane du coureur · 12 semaines",
                      height=460))

ui.callout("Lecture : une fraîcheur très négative n'est pas un problème en soi pendant un bloc d'entraînement ; "
           "c'est l'association <b>charge élevée + bien-être qui se dégrade</b> qui justifie d'en parler avec le coureur. "
           "Ces indicateurs décrivent, ils ne prédisent pas la blessure.")
