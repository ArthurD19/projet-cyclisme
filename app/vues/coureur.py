import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import components as ui
from src import profile
from src.config import (INK, INK_2, KEY_DURATIONS, METRIC, MUTED, POWER_ZONES, STATUS, TSB_BANDS, WARMUP_DAYS,
                        ZONE_COLORS)
from src.tracking import HOOPER_ITEMS

ui.setup("Coureur")
R, RIDES, D, MMP, FTP = ui.riders(), ui.rides(), ui.daily(), ui.ride_mmp(), ui.ftp()

# --------------------------------------------------------------------------
# Barre latérale
# --------------------------------------------------------------------------
st.sidebar.markdown("### Coureur")
cid = st.sidebar.selectbox("Coureur", ui.rider_options(), format_func=ui.rider_label, label_visibility="collapsed",
                           key="rider")
r = R.loc[cid]
kg = r["weight_kg"]
d_all = D[D["cyclist"] == cid]
st.sidebar.markdown("### Période")
t0, t1 = ui.period_filter(d_all["date"].min(), d_all["date"].max(), key=f"per_{cid}", label="Période")
st.sidebar.caption(f"Du {ui.fmt_date(t0)} au {ui.fmt_date(t1)}")

rides = RIDES[(RIDES["cyclist"] == cid) & RIDES["date"].between(t0, t1)]
d = d_all[d_all["date"].between(t0, t1)]
mm_all = MMP[MMP["cyclist"] == cid]
mm = mm_all[mm_all["date"].between(t0, t1)]
ftp_c = FTP[FTP["cyclist"] == cid]
ftp_p = ftp_c[ftp_c["month"].between(t0.to_period("M").start_time, t1)]

curve = profile.record_curve(mm)
curve_all = profile.record_curve(mm_all)
cp = profile.fit_cp(curve)
scores = profile.profile_scores(curve, kg)
pheno, pheno_txt = profile.phenotype(scores)
ftp_now = ftp_p["ftp_w"].iloc[-1] if len(ftp_p) else np.nan
last = d.iloc[-1] if len(d) else None

ui.header(f"Fiche individuelle · {kg:.0f} kg · saison {r['seasons']}", r["label"],
          f"Profil dominant sur la période : <b>{pheno}</b>. {pheno_txt}")
rec5 = curve.loc[curve["dur_s"] == 300, "p_wkg"]
ui.kpis([
    dict(label="FTP du mois", value=ui.fmt(ftp_now / kg, 2), unit="W/kg", sub=f"{ui.fmt(ftp_now)} W · 95 % du meilleur 20 min",
         color=METRIC["power"]),
    dict(label="Puissance critique", value=ui.fmt(cp["cp_w"] / kg, 2), unit="W/kg",
         sub=f"{ui.fmt(cp['cp_w'])} W · W′ {ui.fmt(cp['wprime_j'] / 1000, 1)} kJ", color=METRIC["power"]),
    dict(label="Record 5 min", value=ui.fmt(rec5.iloc[0] if len(rec5) else np.nan, 2), unit="W/kg",
         sub="sur la période", color=METRIC["power"]),
    dict(label="Forme (CTL)", value=ui.fmt(last["ctl"] if last is not None else np.nan), unit="TSS/j",
         sub=f"fraîcheur {ui.fmt(last['tsb'], sign=True)} ({ui.fmt(last['tsb_pct'], sign=True)} %)" if last is not None else "", color=METRIC["ctl"]),
    dict(label="Volume", value=ui.fmt(rides["dur_s"].sum() / 3600), unit="h",
         sub=f"{len(rides)} sorties · {ui.fmt(rides['dist_km'].sum())} km", color=METRIC["ctl"]),
    dict(label="Questionnaires", value=ui.fmt(d["hooper_filled"].mean() * 100), unit="%",
         sub=f"Hooper rempli · RPE {ui.fmt(rides['rpe'].notna().mean() * 100)} %", color=METRIC["hooper"]),
])

tab_p, tab_c, tab_w, tab_s = st.tabs(["Profil", "Charge", "Bien-être", "Séance"])
LOG_TICKS = dict(tickvals=[1, 5, 15, 60, 300, 1200, 3600, 7200], tickangle=0,
                 ticktext=["1 s", "5 s", "15 s", "1 min", "5 min", "20 min", "1 h", "2 h"])

# ==========================================================================
# PROFIL
# ==========================================================================
with tab_p:
    a, b = st.columns([1.5, 1])
    with a:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=curve_all["dur_s"], y=curve_all["p_wkg"], name="Meilleur historique",
                                 line=dict(color="#55544f", width=2, shape="spline"),
                                 hovertemplate="%{y:.2f} W/kg<extra>historique</extra>"))
        fig.add_trace(go.Scatter(x=curve["dur_s"], y=curve["p_wkg"], name="Période choisie",
                                 line=dict(color=METRIC["power"], width=2.5, shape="spline"),
                                 fill="tozeroy", fillcolor=ui.hex_rgba(METRIC["power"], .08),
                                 customdata=np.c_[curve["p_w"], curve["date"].dt.strftime("%d/%m/%Y")],
                                 hovertemplate="%{y:.2f} W/kg · %{customdata[0]:.0f} W<br>le %{customdata[1]}<extra>période</extra>"))
        kd = curve[curve["dur_s"].isin(KEY_DURATIONS)]
        fig.add_trace(go.Scatter(x=kd["dur_s"], y=kd["p_wkg"], mode="markers+text", showlegend=False,
                                 text=[f"{v:.1f}" for v in kd["p_wkg"]], textposition="top right",
                                 textfont=dict(color=INK, size=12), hoverinfo="skip",
                                 marker=dict(size=9, color=METRIC["power"], line=dict(color="#1a1a19", width=2))))
        fig.update_xaxes(type="log", showgrid=True, gridcolor="#242422", **LOG_TICKS, title="Durée de l'effort")
        fig.update_yaxes(title="W/kg", showgrid=True, rangemode="tozero")
        best_d = curve.loc[curve["dur_s"] == 300]
        t = (f"Record 5 min : {ui.fmt(best_d['p_wkg'].iloc[0], 2)} W/kg ({ui.fmt(best_d['p_w'].iloc[0])} W), "
             f"le {ui.fmt_date(best_d['date'].iloc[0])}") if len(best_d) else "Pas de données de puissance"
        ui.show(ui.titled(fig, t, "Meilleure puissance moyenne tenue sur chaque durée · échelle log · W/kg", height=420))

    with b:
        s = scores.dropna()
        names = {5: "Sprint 5 s", 60: "Anaérobie 1 min", 300: "PMA 5 min", 1200: "Seuil (FTP)"}
        top = s.loc[s["score"].idxmax(), "dur_s"] if len(s) else None
        fig = go.Figure(go.Bar(
            y=[names[x] for x in s["dur_s"]], x=s["score"], orientation="h",
            marker=dict(color=[METRIC["power"] if x == top else "#4a4766" for x in s["dur_s"]], cornerradius=4),
            text=[f"{w:.1f} W/kg" for w in s["wkg"]], textposition="outside", textfont=dict(color=INK_2),
            hovertemplate="%{y}<br>niveau %{x:.0f}/100<extra></extra>", width=.55))
        fig.update_xaxes(range=[0, 115], title="Position sur l'échelle de Coggan (0 = non entraîné, 100 = niveau mondial)",
                         showgrid=True, tickvals=[0, 25, 50, 75, 100])
        fig.update_yaxes(autorange="reversed", tickfont=dict(color=INK_2, size=13))
        ui.show(ui.titled(fig, f"Profil dominant : {pheno}", "Chaque qualité située sur le tableau de profil de puissance",
                          height=420))

    a, b = st.columns(2)
    with a:
        fig = go.Figure()
        if len(curve):
            fit = curve[(curve["dur_s"] >= 60) & (curve["dur_s"] <= 1800)]
            tt = np.geomspace(90, 1800, 80)
            fig.add_trace(go.Scatter(x=fit["dur_s"], y=fit["p_w"], mode="markers", name="Records",
                                     marker=dict(size=9, color=METRIC["power"], line=dict(color="#1a1a19", width=2)),
                                     hovertemplate="%{y:.0f} W<extra>record</extra>"))
            fig.add_trace(go.Scatter(x=tt, y=cp["cp_w"] + cp["wprime_j"] / tt, name="Modèle CP + W′/t",
                                     line=dict(color=INK_2, width=2), hovertemplate="%{y:.0f} W<extra>modèle</extra>"))
            fig.add_hline(y=cp["cp_w"], line=dict(color=MUTED, width=1),
                          annotation=dict(text=f"CP {cp['cp_w']:.0f} W", font=dict(color=INK_2), xanchor="right", x=1))
            fig.add_vrect(x0=120, x1=900, fillcolor="rgba(255,255,255,.03)", line_width=0,
                          annotation=dict(text="zone d'ajustement 2-15 min", font=dict(color=MUTED, size=11), y=1.02,
                                          yanchor="bottom"))
        fig.update_xaxes(type="log", **LOG_TICKS, showgrid=True, gridcolor="#242422", title="Durée")
        fig.update_yaxes(title="W", showgrid=True)
        ui.show(ui.titled(fig, f"CP = {ui.fmt(cp['cp_w'])} W, réserve anaérobie W′ = {ui.fmt(cp['wprime_j'] / 1000, 1)} kJ",
                          f"Ajusté sur les records 2-15 min (R² = {ui.fmt(cp['r2'], 3)}) · au-dessus de CP, W′ se vide",
                          height=380))
    with b:
        f = ftp_p.dropna(subset=["ftp_w"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=f["month"], y=f["ftp_w"] / kg, mode="lines+markers", name="FTP",
                                 line=dict(color=METRIC["power"], width=2.5, shape="hv"),
                                 marker=dict(size=8, color=METRIC["power"], line=dict(color="#1a1a19", width=2)),
                                 customdata=np.c_[f["ftp_w"], f["best20_w"]],
                                 hovertemplate="%{x|%m/%Y}<br>FTP %{y:.2f} W/kg · %{customdata[0]:.0f} W"
                                               "<br>meilleur 20 min du mois : %{customdata[1]:.0f} W<extra></extra>"))
        fig.update_yaxes(title="W/kg", showgrid=True)
        if len(f) > 1:
            lo, hi = f["ftp_w"].iloc[0] / kg, f["ftp_w"].iloc[-1] / kg
            t = f"FTP de {ui.fmt(lo, 2)} à {ui.fmt(hi, 2)} W/kg sur la période ({ui.fmt((hi / lo - 1) * 100, sign=True)} %)"
        else:
            t = "FTP du mois"
        ui.show(ui.titled(fig, t, "Recalculée chaque mois : 95 % du meilleur 20 min des 3 derniers mois", height=380))

    # Efficacité aérobie (outdoor seulement)
    e = rides[(~rides["indoor"]) & rides["ef"].notna() & (rides["dur_s"] > 3600)].copy()
    if len(e) > 5:
        e["month"] = e["date"].dt.to_period("M").dt.to_timestamp()
        em = e.groupby("month").agg(ef=("ef", "median"), dec=("decoupling_pct", "median"), n=("file", "size")).reset_index()
        a, b = st.columns(2)
        with a:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=e["date"], y=e["ef"], mode="markers", name="Sortie",
                                     marker=dict(size=6, color=ui.hex_rgba(METRIC["power"], .35)),
                                     hovertemplate="%{x|%d/%m}<br>%{y:.2f} W/bpm<extra></extra>"))
            fig.add_trace(go.Scatter(x=em["month"] + pd.Timedelta(days=14), y=em["ef"], name="Médiane du mois",
                                     line=dict(color=METRIC["power"], width=2.5, shape="spline")))
            fig.update_yaxes(title="NP / FC moyenne (W/bpm)", showgrid=True)
            chg = (em["ef"].iloc[-1] / em["ef"].iloc[0] - 1) * 100
            t = (f"Efficacité aérobie {'en hausse' if chg > 3 else 'en baisse' if chg < -3 else 'stable'} "
                 f"({ui.fmt(chg, sign=True)} % du 1er au dernier mois)")
            ui.show(ui.titled(fig, t, "NP / FC moyenne · sorties extérieures > 1 h · plus haut = mieux", height=360))
        with b:
            fig = go.Figure(go.Bar(x=em["month"], y=em["dec"], marker=dict(color=METRIC["hr"], cornerradius=4),
                                   hovertemplate="%{x|%m/%Y}<br>dérive médiane %{y:.1f} %<extra></extra>"))
            fig.add_hline(y=5, line=dict(color=MUTED, width=1),
                          annotation=dict(text="repère 5 %", font=dict(color=MUTED, size=11), x=1, xanchor="right"))
            fig.update_yaxes(title="Dérive cardiaque (%)", showgrid=True)
            good = (em["dec"] < 5).mean() * 100
            ui.show(ui.titled(fig, f"Dérive cardiaque sous 5 % dans {ui.fmt(good)} % des mois",
                              "Perte de NP/FC entre 1re et 2e moitié (> 1 h) · faible = endurant", height=360))

# ==========================================================================
# CHARGE
# ==========================================================================
with tab_c:
    first_day = d_all["date"].min()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.62, .38], vertical_spacing=.06)
    fig.add_trace(go.Bar(x=d["date"], y=d["load"], name="Charge du jour (TSS)",
                         marker=dict(color=ui.hex_rgba(METRIC["power"], .45), line_width=0),
                         hovertemplate="%{x|%d/%m/%Y}<br>%{y:.0f} TSS<extra>charge du jour</extra>"), 1, 1)
    fig.add_trace(go.Scatter(x=d["date"], y=d["ctl"], name="Forme · CTL 42 j", line=dict(color=METRIC["ctl"], width=2.5),
                             hovertemplate="%{y:.0f}<extra>forme (CTL)</extra>"), 1, 1)
    fig.add_trace(go.Scatter(x=d["date"], y=d["atl"], name="Fatigue · ATL 7 j", line=dict(color=METRIC["atl"], width=2),
                             hovertemplate="%{y:.0f}<extra>fatigue (ATL)</extra>"), 1, 1)
    tsb_lim = 100
    for (lo, label, stt), hi in zip(TSB_BANDS, [tsb_lim] + [b[0] for b in TSB_BANDS[:-1]]):
        if stt != "good":
            fig.add_hrect(y0=max(lo, -tsb_lim), y1=hi, fillcolor=ui.hex_rgba(STATUS[stt], .09), line_width=0, row=2, col=1)
            fig.add_annotation(x=1, xref="x domain", y=(max(lo, -tsb_lim) + hi) / 2, yref="y2", text=label, showarrow=False,
                               xanchor="right", font=dict(color=MUTED, size=11))
    fig.add_trace(go.Scatter(x=d["date"], y=d["tsb_pct"].clip(-tsb_lim, tsb_lim), name="Fraîcheur · TSB / CTL",
                             line=dict(color=METRIC["tsb"], width=1.8), fill="tozeroy", fillcolor="rgba(195,194,183,.10)",
                             customdata=d["tsb"], hovertemplate="%{y:+.0f} % (TSB %{customdata:+.0f})<extra>fraîcheur</extra>"), 2, 1)
    warm_end = first_day + pd.Timedelta(days=WARMUP_DAYS)
    if warm_end > t0:
        for row in (1, 2):
            fig.add_vrect(x0=max(t0, first_day), x1=min(warm_end, t1), fillcolor="rgba(255,255,255,.04)", line_width=0,
                          row=row, col=1)
        fig.add_annotation(x=max(t0, first_day), y=1, yref="y domain", text="42 premiers jours : non interprétable",
                           showarrow=False, xanchor="left", font=dict(color=MUTED, size=11))
    fig.update_yaxes(title="TSS / jour", showgrid=True, row=1, col=1)
    fig.update_yaxes(title="TSB / CTL", ticksuffix=" %", showgrid=True, range=[-tsb_lim, tsb_lim], row=2, col=1)
    fig.update_layout(bargap=0, hovermode="x unified")
    if last is not None:
        peak = d.loc[d["ctl"].idxmax()]
        t = (f"Forme au plus haut le {ui.fmt_date(peak['date'])} (CTL {ui.fmt(peak['ctl'])}) · "
             f"en fin de période {ui.fmt(last['ctl'])}, fraîcheur {ui.fmt(last['tsb_pct'], sign=True)} %")
    else:
        t = "Pas de données"
    ui.show(ui.titled(fig, t, "Forme (CTL 42 j) et fatigue (ATL 7 j) en TSS · fraîcheur = (forme − fatigue) en % de la forme",
                      height=560))
    src_counts = rides["load_source"].value_counts()
    est = int(src_counts.drop("puissance", errors="ignore").sum())
    ui.note(f"{est} sorties sur {len(rides)} sans capteur de puissance : leur charge est estimée depuis la FC "
            f"(TRIMP × {ui.fmt(r['k_tss_per_trimp'], 2)}) ou le ressenti (sRPE × {ui.fmt(r['k_tss_per_srpe'], 2)}), "
            "coefficients propres au coureur.")

    a, b = st.columns([1.35, 1])
    with a:
        w = rides.copy()
        w["week"] = w["date"].dt.to_period("W-SUN").dt.start_time
        wz = w.groupby("week")[[f"pz{i}_s" for i in range(1, 6)]].sum() / 3600
        fig = go.Figure()
        for i, (name, *_) in enumerate(POWER_ZONES):
            fig.add_trace(go.Bar(x=wz.index, y=wz[f"pz{i + 1}_s"], name=name, marker=dict(color=ZONE_COLORS[i], line_width=0),
                                 hovertemplate="%{x|sem. du %d/%m}<br>%{y:.1f} h<extra>" + name + "</extra>"))
        fig.update_layout(barmode="stack", bargap=.18, legend=dict(traceorder="normal"))
        fig.update_yaxes(title="Heures", showgrid=True)
        tot = wz.sum()
        low = (tot.iloc[:2].sum() / tot.sum() * 100) if tot.sum() else np.nan
        ui.show(ui.titled(fig, f"{ui.fmt(low)} % du temps sous 75 % de la FTP (Z1-Z2)",
                          "Heures par semaine et par zone de puissance (% FTP du mois)",
                          height=400))
    with b:
        cal = d[["date", "load"]].copy()
        cal["wk"] = cal["date"].dt.to_period("W-SUN").dt.start_time
        cal["dow"] = cal["date"].dt.dayofweek
        piv = cal.pivot_table(index="dow", columns="wk", values="load", aggfunc="sum")
        dates = cal.pivot_table(index="dow", columns="wk", values="date", aggfunc="first")
        fig = go.Figure(go.Heatmap(
            z=piv.to_numpy(), x=piv.columns, y=["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"], xgap=2, ygap=2,
            customdata=dates.apply(lambda c: c.dt.strftime("%d/%m/%Y")).to_numpy(),
            colorscale=[[0, "#1f1e2b"], [.05, "#2c2950"], [.4, "#5c53b0"], [.75, "#9085e9"], [1, "#e4e0ff"]],
            zmin=0, zmax=float(np.nanpercentile(d["load"], 98)) if len(d) else 1,
            colorbar=dict(thickness=10, title=dict(text="TSS", font=dict(size=11, color=MUTED)), tickfont=dict(color=MUTED)),
            hovertemplate="%{customdata}<br>%{z:.0f} TSS<extra></extra>"))
        fig.update_yaxes(autorange="reversed", tickfont=dict(size=11))
        rest = (d["load"] == 0).mean() * 100
        dow = cal.groupby("dow")["load"].mean()
        jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        ui.show(ui.titled(fig, f"Grosse journée : le {jours[int(dow.idxmax())]} · {ui.fmt(rest)} % de repos",
                          "Calendrier de la charge quotidienne (TSS)", height=400))

    with st.expander("Détail des sorties de la période", icon=":material/table_rows:"):
        tbl = rides.sort_values("start", ascending=False)[
            ["start", "dur_s", "dist_km", "elev_gain_m", "np_w", "if_", "load", "load_source", "hr_mean_bpm", "rpe",
             "lactate_mmol", "indoor"]].copy()
        tbl["dur_s"] = tbl["dur_s"] / 3600
        st.dataframe(tbl, hide_index=True, height=360, column_config={
            "start": st.column_config.DatetimeColumn("Départ", format="DD/MM/YYYY HH:mm"),
            "dur_s": st.column_config.NumberColumn("Durée (h)", format="%.1f"),
            "dist_km": st.column_config.NumberColumn("km", format="%.0f"),
            "elev_gain_m": st.column_config.NumberColumn("D+ (m)", format="%.0f"),
            "np_w": st.column_config.NumberColumn("NP (W)", format="%.0f"),
            "if_": st.column_config.NumberColumn("IF", format="%.2f"),
            "load": st.column_config.ProgressColumn("Charge (TSS)", format="%.0f", min_value=0,
                                                    max_value=float(max(rides["load"].max(), 1)) if len(rides) else 1),
            "load_source": "Source charge", "hr_mean_bpm": st.column_config.NumberColumn("FC moy", format="%.0f"),
            "rpe": st.column_config.NumberColumn("RPE", format="%.0f"),
            "lactate_mmol": st.column_config.NumberColumn("Lactate", format="%.1f"),
            "indoor": st.column_config.CheckboxColumn("Intérieur"),
        })

# ==========================================================================
# BIEN-ÊTRE
# ==========================================================================
with tab_w:
    h = d.dropna(subset=["hooper"])
    a, b = st.columns([1.5, 1])
    with a:
        fig = go.Figure()
        band = d.dropna(subset=["hooper_base"])
        fig.add_trace(go.Scatter(x=band["date"], y=band["hooper_base"] + band["hooper_sd"], line=dict(width=0),
                                 hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=band["date"], y=band["hooper_base"] - band["hooper_sd"], line=dict(width=0),
                                 fill="tonexty", fillcolor=ui.hex_rgba(METRIC["hooper"], .12), name="Habitude ± 1 écart-type",
                                 hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=band["date"], y=band["hooper_base"], name="Référence 28 j",
                                 line=dict(color=METRIC["hooper"], width=1.5), hoverinfo="skip"))
        cols = [STATUS["critical"] if z >= 2 else STATUS["warning"] if z >= 1 else METRIC["hooper"] for z in h["hooper_z"].fillna(0)]
        fig.add_trace(go.Scatter(x=h["date"], y=h["hooper"], mode="markers", name="Score du jour",
                                 marker=dict(size=6, color=cols, line=dict(color="#1a1a19", width=1)),
                                 customdata=np.c_[h[HOOPER_ITEMS].to_numpy(), h["hooper_z"]],
                                 hovertemplate="%{x|%d/%m/%Y}<br><b>Hooper %{y:.0f}/28</b> (z %{customdata[4]:+.1f})"
                                               "<br>sommeil %{customdata[0]:.0f} · stress %{customdata[1]:.0f}"
                                               "<br>fatigue %{customdata[2]:.0f} · courbatures %{customdata[3]:.0f}<extra></extra>"))
        fig.update_yaxes(title="Hooper (4 = très bien · 28 = très mal)", showgrid=True, autorange="reversed")
        n_bad = int((h["hooper_z"] >= 1).sum())
        ui.show(ui.titled(fig, f"{n_bad} jours nettement moins bien que d'habitude sur la période",
                          "Hooper du jour (vers le haut = mieux) · bande = habitude des 28 j précédents · orange z ≥ 1, rouge z ≥ 2", height=420))
    with b:
        hi = h.copy()
        sd = hi[HOOPER_ITEMS].std()
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=.07,
                            subplot_titles=[x.capitalize() for x in HOOPER_ITEMS])
        for i, it in enumerate(HOOPER_ITEMS, 1):
            sm = hi.set_index("date")[it].rolling("7D").mean()
            fig.add_trace(go.Scatter(x=sm.index, y=sm, line=dict(color=METRIC["hooper"], width=2), showlegend=False,
                                     hovertemplate="%{x|%d/%m}<br>%{y:.1f}/7<extra>" + it + "</extra>"), i, 1)
            fig.update_yaxes(range=[7.3, .7], tickvals=[2, 6], showgrid=True, row=i, col=1)
        fig.update_annotations(font=dict(size=12, color=INK_2), x=0, xanchor="left")
        ui.show(ui.titled(fig, f"{sd.idxmax().capitalize()} : la composante qui varie le plus",
                          "Moyenne 7 jours de chaque item (1 = très bien, 7 = très mal)", height=420))

    a, b = st.columns(2)
    with a:
        x = rides.dropna(subset=["rpe", "if_"])
        fig = go.Figure()
        if len(x) > 5:
            rr = np.corrcoef(x["if_"], x["rpe"])[0, 1]
            k = np.polyfit(x["if_"], x["rpe"], 1)
            xx = np.linspace(x["if_"].min(), x["if_"].max(), 20)
            fig.add_trace(go.Scatter(x=x["if_"], y=x["rpe"] + np.random.default_rng(0).uniform(-.18, .18, len(x)),
                                     mode="markers", name="Sortie",
                                     marker=dict(size=7, color=ui.hex_rgba(METRIC["srpe"], .55), line=dict(width=0)),
                                     customdata=np.c_[x["date"].dt.strftime("%d/%m/%Y"), x["rpe"], x["dur_s"] / 3600],
                                     hovertemplate="%{customdata[0]} · %{customdata[2]:.1f} h<br>IF %{x:.2f} · RPE %{customdata[1]:.0f}<extra></extra>"))
            fig.add_trace(go.Scatter(x=xx, y=np.polyval(k, xx), name="Tendance", line=dict(color=INK_2, width=2)))
            fig.update_xaxes(title="Intensité mesurée (IF = NP / FTP)", showgrid=True)
            fig.update_yaxes(title="Effort ressenti (RPE, CR-10)", showgrid=True, range=[0, 10.6])
            verdict = "concordent" if rr > .5 else "concordent moyennement" if rr > .25 else "divergent"
            ui.show(ui.titled(fig, f"Ressenti et intensité mesurée {verdict} (r = {ui.fmt(rr, 2)})",
                              "Une sortie par point · au-dessus de la droite = vécue plus dure que mesurée", height=380))
        else:
            st.info("Pas assez de séances avec RPE et puissance sur la période.")
    with b:
        ww = d.copy()
        ww["week"] = ww["date"].dt.to_period("W-SUN").dt.start_time
        g = ww.groupby("week").agg(srpe=("srpe", "sum"), mono=("monotony", "last")).reset_index()
        fig = go.Figure(go.Bar(x=g["week"], y=g["srpe"], marker=dict(color=METRIC["srpe"], cornerradius=3),
                               customdata=g["mono"], name="sRPE",
                               hovertemplate="sem. du %{x|%d/%m}<br>%{y:.0f} UA · monotonie %{customdata:.1f}<extra></extra>"))
        fig.update_yaxes(title="sRPE (UA) par semaine", showgrid=True)
        hm = (g["mono"] > 2).sum()
        ui.show(ui.titled(fig, f"Charge ressentie : {hm} semaine{'s' if hm > 1 else ''} trop monotone{'s' if hm > 1 else ''} (> 2)",
                          "sRPE = RPE × minutes, cumulé par semaine · monotonie (Foster) = moyenne / écart-type "
                          "des 7 jours, au survol", height=380))

    c = st.columns(3)
    for col, (lab, val, txt) in zip(c, [
        ("Hooper rempli", d["hooper_filled"].mean(), "jours avec un questionnaire complet"),
        ("RPE renseigné", rides["rpe"].notna().mean(), "sorties avec un RPE"),
        ("Lactate mesuré", rides["lactate_mmol"].notna().mean(), "sorties avec une lactatémie")]):
        with col:
            stt = "good" if val >= .8 else "warning" if val >= .6 else "critical"
            st.markdown(f"{ui.pill(stt, f'{lab} : {ui.fmt(val * 100)} %')} <span class='note'>{txt}</span>",
                        unsafe_allow_html=True)

# ==========================================================================
# SÉANCE
# ==========================================================================
with tab_s:
    rs = rides.sort_values("start", ascending=False)
    if rs.empty:
        st.info("Aucune sortie sur la période.")
    else:
        def lab(i):
            x = rs.loc[i]
            return (f"{ui.fmt_date(x['start'])} · {x['start']:%H:%M} · {ui.fmt_dur(x['dur_s'])} · "
                    f"{ui.fmt(x['dist_km'])} km · {ui.fmt(x['load'])} TSS" + (" · intérieur" if x["indoor"] else ""))
        pick = st.selectbox("Sortie", rs.index, format_func=lab, index=int(np.argmax(rs["tss"].fillna(0).to_numpy())))
        x = rs.loc[pick]
        tr = ui.trace(cid, x["file"])
        ui.kpis([
            dict(label="Durée", value=ui.fmt_dur(x["dur_s"]), sub=f"{ui.fmt(x['dist_km'], 1)} km · {ui.fmt(x['elev_gain_m'])} m D+",
                 color=METRIC["ctl"]),
            dict(label="Puissance normalisée", value=ui.fmt(x["np_w"]), unit="W",
                 sub=f"{ui.fmt(x['np_wkg'], 2)} W/kg · VI {ui.fmt(x['vi'], 2)}", color=METRIC["power"]),
            dict(label="Intensité", value=ui.fmt(x["if_"], 2), unit="IF", sub=f"FTP du mois {ui.fmt(x['ftp_w'])} W",
                 color=METRIC["power"]),
            dict(label="Charge", value=ui.fmt(x["load"]), unit="TSS", sub=f"source : {x['load_source']}", color=METRIC["power"]),
            dict(label="FC moyenne", value=ui.fmt(x["hr_mean_bpm"]), unit="bpm", sub=f"TRIMP {ui.fmt(x['trimp_edwards'])} (Edwards)",
                 color=METRIC["hr"]),
            dict(label="Ressenti", value=ui.fmt(x["rpe"]), unit="/10", sub=f"lactate {ui.fmt(x['lactate_mmol'], 1, 'mmol/L')}",
                 color=METRIC["srpe"]),
        ])
        a, b = st.columns([1, 1.25])
        with a:
            g = tr.dropna(subset=["lat", "lon"])
            if x["indoor"] or g.empty:
                st.markdown('<div class="callout">Sortie en intérieur (home-trainer / Zwift) : pas de parcours à afficher, '
                            'et FC / vitesse non comparables aux sorties extérieures.</div>', unsafe_allow_html=True)
            else:
                use_w = bool(x["has_power"])
                col, unit = (g["watts"], "W") if use_w else (g["hr"], "bpm")
                base = METRIC["power"] if use_w else METRIC["hr"]
                span = max(g["lat"].max() - g["lat"].min(), (g["lon"].max() - g["lon"].min()) * .7, 1e-3)
                zoom = float(np.clip(np.log2(360 / span) - 1.4, 3, 15))
                fig = go.Figure(go.Scattermap(
                    lat=g["lat"], lon=g["lon"], mode="markers",
                    marker=dict(size=5, color=col, colorscale=[[0, "#26252b"], [.5, base], [1, "#f6f4ff"]],
                                cmin=float(np.nanpercentile(col, 3)) if col.notna().any() else 0,
                                cmax=float(np.nanpercentile(col, 97)) if col.notna().any() else 1,
                                colorbar=dict(title=dict(text=unit, font=dict(color=MUTED)), thickness=8, tickfont=dict(color=MUTED))),
                    customdata=np.c_[g["t_min"], g["watts"], g["hr"]],
                    hovertemplate="%{customdata[0]:.0f} min<br>%{customdata[1]:.0f} W · %{customdata[2]:.0f} bpm<extra></extra>"))
                fig.update_layout(map=dict(style="carto-darkmatter", center=dict(lat=g["lat"].mean(), lon=g["lon"].mean()),
                                           zoom=zoom), margin=dict(l=0, r=0, t=74, b=0))
                what = "la puissance" if use_w else "la fréquence cardiaque (pas de capteur de puissance)"
                ui.show(ui.titled(fig, f"Le parcours, coloré par {what}", "Moyenne par tranche de 20 s · plus clair = plus intense",
                                  height=470))
        with b:
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[.42, .33, .25], vertical_spacing=.05)
            fig.add_trace(go.Scatter(x=tr["t_min"], y=tr["watts"], line=dict(color=METRIC["power"], width=1.4), name="Puissance",
                                     fill="tozeroy", fillcolor=ui.hex_rgba(METRIC["power"], .12),
                                     hovertemplate="%{y:.0f} W<extra></extra>"), 1, 1)
            if np.isfinite(x["ftp_w"]):
                fig.add_hline(y=x["ftp_w"], line=dict(color=MUTED, width=1), row=1, col=1,
                              annotation=dict(text="FTP", font=dict(color=MUTED, size=11), x=1, xanchor="right"))
            fig.add_trace(go.Scatter(x=tr["t_min"], y=tr["hr"], line=dict(color=METRIC["hr"], width=1.6), name="FC",
                                     hovertemplate="%{y:.0f} bpm<extra></extra>"), 2, 1)
            fig.add_trace(go.Scatter(x=tr["t_min"], y=tr["alt"], line=dict(color="#8a8984", width=1.2), name="Altitude",
                                     fill="tozeroy", fillcolor="rgba(138,137,132,.15)",
                                     hovertemplate="%{y:.0f} m<extra></extra>"), 3, 1)
            fig.update_yaxes(title="W", showgrid=True, row=1, col=1)
            fig.update_yaxes(title="bpm", showgrid=True, row=2, col=1)
            alt = tr["alt"].dropna()
            if len(alt):
                fig.update_yaxes(title="m", showgrid=True, range=[alt.min() - 10, alt.max() + 10], row=3, col=1)
            fig.update_xaxes(title="Minutes", row=3, col=1)
            fig.update_layout(showlegend=False, hovermode="x unified")
            iff = x["if_"]
            kind = ("pas de capteur de puissance" if not np.isfinite(iff) else "sortie de récupération" if iff < .65
                    else "endurance" if iff < .8 else "sortie soutenue (tempo)" if iff < .9
                    else "très soutenue, proche du seuil" if iff < 1 else "effort de course ou intervalles")
            title = f"IF {ui.fmt(iff, 2)} : {kind}" if np.isfinite(iff) else f"Séance : {kind}"
            ui.show(ui.titled(fig, title, "Puissance, fréquence cardiaque et altitude (moyennes 20 s)", height=470))
