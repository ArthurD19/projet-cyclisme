import plotly.graph_objects as go
import streamlit as st

import components as ui
from src.config import METRIC, MUTED, RIDER_COLORS

ui.setup("Accueil")
R, rides = ui.riders(), ui.rides()

# Bandeau : silhouette de la sortie la plus vallonnée de l'effectif
top = rides[~rides["indoor"]].sort_values("elev_gain_m", ascending=False).iloc[0]
tr = ui.trace(top["cyclist"], top["file"])
cap = (f"Profil réel · {R.loc[top['cyclist'], 'label']} · {ui.fmt_date(top['date'])} · "
       f"{ui.fmt(top['dist_km'])} km · {ui.fmt(top['elev_gain_m'])} m D+")
st.markdown(
    f"""<div class="hero"><div class="kicker">Cellule performance · ENSAI Digisport</div>
    <h1>Charge, forme<br>&amp; profil de l'effectif</h1>
    <p>Un outil pour le staff : qui est frais, qui encaisse, et ce que chaque coureur sait faire.
    Toutes les valeurs sont calculées <b>par coureur</b> (FTP, FCmax, zones), et les comparaisons se font en W/kg
    ou par rapport à la propre moyenne de chacun.</p>
    {ui.profile_silhouette(tr['alt'].to_numpy())}<div class="cap">{cap}</div></div>""",
    unsafe_allow_html=True,
)

ui.kpis([
    dict(label="Coureurs", value=str(len(R)), sub="2 saisons · 2022-2023", color=METRIC["power"]),
    dict(label="Sorties analysées", value=ui.fmt(len(rides)), sub=f"{ui.fmt(rides['indoor'].mean() * 100)} % en intérieur",
         color=METRIC["power"]),
    dict(label="Heures de selle", value=ui.fmt(rides["dur_s"].sum() / 3600), unit="h", color=METRIC["ctl"]),
    dict(label="Distance", value=ui.fmt(rides["dist_km"].sum()), unit="km", color=METRIC["ctl"]),
    dict(label="Dénivelé", value=ui.fmt(rides["elev_gain_m"].sum() / 1000), unit="km D+", color=METRIC["ctl"]),
])

# Couverture des données : pourquoi on compare en relatif
fig = go.Figure()
for cid in reversed(ui.rider_options()):
    r = rides[rides["cyclist"] == cid]
    fig.add_trace(go.Scatter(
        x=r["date"], y=[R.loc[cid, "label"]] * len(r), mode="markers", name=R.loc[cid, "label"],
        marker=dict(symbol="line-ns", size=14, line=dict(width=1.6, color=RIDER_COLORS[cid])),
        customdata=r[["dist_km", "dur_s"]].assign(h=r["dur_s"] / 3600).to_numpy(),
        hovertemplate="%{y} · %{x|%d/%m/%Y}<br>%{customdata[0]:.0f} km · %{customdata[2]:.1f} h<extra></extra>",
        showlegend=False))
fig.update_xaxes(showgrid=True)
fig.update_yaxes(tickfont=dict(color="#c3c2b7", size=13))
ui.titled(fig, "Les coureurs n'ont pas été suivis sur la même période",
          "Chaque trait = une sortie · C1 et C7 en 2022, C3, C5 et C6 en 2023, C2 et C4 sur les deux saisons "
          "→ les comparaisons s'alignent sur le mois de saison ou se font en relatif", height=330)
ui.show(fig)

st.markdown("### Par où commencer")
cols = st.columns(4)
cards = [
    ("vues/equipe.py", "Vue collective", "Équipe", "Feux tricolores de la semaine : fraîcheur, bien-être, charge et suivi des questionnaires."),
    ("vues/coureur.py", "Vue individuelle", "Coureur", "Profil de puissance, FTP du mois, charge chronique et aiguë, bien-être et explorateur de séance."),
    ("vues/comparaison.py", "Comparer juste", "Comparaison", "Records en W/kg, intensité relative à la FTP de chacun, saisons alignées."),
    ("vues/methodes.py", "Transparence", "Méthodes", "Formules, hypothèses et limites : ce que les chiffres disent, et ce qu'ils ne disent pas."),
]
for col, (page, tag, title, txt) in zip(cols, cards):
    with col:
        st.markdown(f'<div class="nav-card"><div class="tag">{tag}</div><h4>{title}</h4><p>{txt}</p></div>',
                    unsafe_allow_html=True)
        st.page_link(page, label=f"Ouvrir {title}", icon=":material/arrow_forward:")

st.markdown(f"<p class='note' style='margin-top:1.6rem;color:{MUTED}'>Données : 7 coureurs, fichiers à la seconde "
            "(puissance, FC, cadence, GPS) et questionnaires (RPE, lactate, Hooper, fictifs). "
            "Relations charge-performance descriptives : aucune causalité n'est revendiquée.</p>",
            unsafe_allow_html=True)
