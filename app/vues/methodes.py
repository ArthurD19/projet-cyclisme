import pandas as pd
import streamlit as st

import components as ui
from src.config import (COGGAN_PROFILE, FTP_WINDOW_MONTHS, HR_REST_DEFAULT_BPM, METRIC, POWER_ZONES, STATUS)

ui.setup("Méthodes")
R, RIDES = ui.riders(), ui.rides()
raw = pd.read_parquet(ui.OUTPUTS / "rides.parquet", columns=["cyclist", "artifact"])

ui.header("Transparence", "Méthodes & limites",
          "Comment chaque chiffre est obtenu, les choix faits, et ce qu'il ne faut pas en conclure.")

t1, t2, t3, t4 = st.tabs(["Données", "Profil de performance", "Charge de travail", "Bien-être & alertes"])

with t1:
    st.markdown("#### Ce qui entre dans l'outil")
    q = R[["label", "weight_kg", "seasons", "n_rides", "n_artifacts", "share_power", "share_hr", "share_indoor",
           "compliance_rpe", "compliance_hooper", "hr_rest_measured"]].copy()
    for c in ["share_power", "share_hr", "share_indoor", "compliance_rpe", "compliance_hooper"]:
        q[c] *= 100
    st.dataframe(q, hide_index=True, column_config={
        "label": "Coureur", "weight_kg": st.column_config.NumberColumn("Poids (kg)", format="%.0f"), "seasons": "Saison(s)",
        "n_rides": "Sorties", "n_artifacts": st.column_config.NumberColumn("Écartées", help="Enregistrements aberrants"),
        "share_power": st.column_config.ProgressColumn("Avec puissance", format="%.0f %%", min_value=0, max_value=100),
        "share_hr": st.column_config.ProgressColumn("Avec FC", format="%.0f %%", min_value=0, max_value=100),
        "share_indoor": st.column_config.NumberColumn("Intérieur", format="%.0f %%"),
        "compliance_rpe": st.column_config.ProgressColumn("RPE rempli", format="%.0f %%", min_value=0, max_value=100),
        "compliance_hooper": st.column_config.ProgressColumn("Hooper rempli", format="%.0f %%", min_value=0, max_value=100),
        "hr_rest_measured": st.column_config.CheckboxColumn("FC repos mesurée"),
    })
    st.markdown(f"""
- **Une ligne par seconde** par sortie (puissance, FC, cadence, vitesse, altitude, GPS). Le poids vient du nom du dossier.
- **Nettoyage** : puissance négative ou > 2 500 W → 0 W ; FC hors 30-230 bpm → manquante ; `-255` (température,
  équilibre G/D) et `0` (pente, GPS) → manquants. Les fichiers bruts ne sont jamais modifiés.
- **Intérieur** : GPS dans le Pacifique (îles Zwift) ou distance nulle. La FC et la vitesse indoor ne sont pas
  comparées à l'outdoor.
- **{int(raw['artifact'].sum())} enregistrements écartés** : ni puissance ni FC, et 24 h d'enregistrement ou vitesse
  de véhicule (capteur oublié allumé).
- **Questionnaires** (RPE, lactate, Hooper : données fictives) joints par nom de fichier et par date. Les cases vides
  sont comptées : le taux de remplissage mesure le suivi de chaque coureur.
""")

with t2:
    st.markdown("#### Courbe de puissance record")
    st.markdown("Pour chaque durée *d* (1 s → 2 h), on prend le maximum de la moyenne glissante sur *d* secondes, "
                "en W et en W/kg. Elle se recalcule sur la période choisie dans la barre latérale.")
    st.markdown("#### Puissance normalisée, FTP")
    st.latex(r"NP = \sqrt[4]{\overline{\left(\text{moy. glissante 30 s de } P\right)^4}} \qquad (0\ \text{W gardés})")
    st.latex(r"FTP_{\text{mois } M} = 0{,}95 \times \max\left(P_{20\,\text{min}}\right)_{M-2\,..\,M}")
    st.markdown(f"La FTP est **recalculée chaque mois** sur une fenêtre glissante de {FTP_WINDOW_MONTHS} mois : un mois "
                "de coupure sans effort maximal ne fait pas s'effondrer la FTP (ce qui gonflerait le TSS des sorties "
                "suivantes). Pas de test terrain fourni : c'est une **estimation** à partir des sorties.")
    st.markdown("#### Puissance critique et W′")
    st.latex(r"P(t) = CP + \frac{W'}{t} \;\Longleftrightarrow\; \text{Travail}(t) = CP \cdot t + W'")
    st.markdown("Régression linéaire du travail sur la durée, avec les records de **2 à 15 min**. CP ≈ intensité "
                "soutenable longtemps ; W′ = réserve (en kJ) disponible au-dessus de CP.")
    st.markdown("#### Type de coureur")
    rows = [dict(Durée={5: "5 s", 60: "1 min", 300: "5 min", 1200: "FTP"}[k], **{"0 / 100 (W/kg)": f"{lo} → {hi}"})
            for k, (lo, hi) in COGGAN_PROFILE.items()]
    c1, c2 = st.columns([1, 1.6])
    c1.dataframe(pd.DataFrame(rows), hide_index=True)
    c2.markdown("Chaque qualité est placée entre « non entraîné » (0) et « niveau mondial » (100) du tableau de profil "
                "de puissance de Coggan (valeurs arrondies, hommes). La qualité la plus haute donne le profil "
                "dominant ; si tout est à moins de 8 points d'écart : *complet*. C'est une **lecture relative**, "
                "pas un classement absolu.")
    st.markdown("#### Indice d'efficacité et dérive cardiaque")
    st.markdown("EF = NP / FC moyenne (sorties extérieures > 1 h). Dérive = baisse de EF entre la 1re et la 2e "
                "moitié de la sortie ; < 5 % = bonne endurance aérobie.")

with t3:
    st.markdown("#### Charge de chaque sortie (TSS)")
    st.latex(r"IF = \frac{NP}{FTP} \qquad TSS = \frac{\text{durée}_s \times NP \times IF}{FTP \times 3600} \times 100")
    st.markdown("Une heure à FTP = 100. Sans capteur de puissance, la charge est **estimée** sur la même échelle :")
    st.latex(r"TRIMP_{Banister} = \text{durée}_{min} \cdot \Delta FC \cdot 0{,}64\, e^{1{,}92\,\Delta FC} \qquad "
             r"\Delta FC = \frac{FC_{exo} - FC_{repos}}{FC_{max} - FC_{repos}}")
    st.markdown(f"TSS estimé = TRIMP × *k*, où *k* = médiane de TSS / TRIMP sur les sorties du coureur qui ont les deux "
                f"(à défaut : sRPE × *k′*). FCmax = max de la saison (pic isolé écarté). FC de repos : mesurée pour le "
                f"coureur 4, **{HR_REST_DEFAULT_BPM} bpm par hypothèse** pour les autres. Le TRIMP d'Edwards "
                "(minutes par zone FC × 1 à 5) est aussi calculé.")
    st.markdown("#### Forme, fatigue, fraîcheur")
    st.latex(r"CTL_j = CTL_{j-1} + \frac{charge_j - CTL_{j-1}}{42} \qquad ATL_j = ATL_{j-1} + \frac{charge_j - ATL_{j-1}}{7}"
             r"\qquad TSB = CTL - ATL")
    st.markdown("Charge sommée par jour (plusieurs sorties possibles), 0 les jours sans vélo. Les **42 premiers jours** "
                "ne sont pas interprétés (la CTL part de 0).")
    st.latex(r"\text{Fraîcheur relative} = \frac{TSB}{CTL} \times 100")
    st.markdown("Les alertes utilisent la fraîcheur **relative à la forme du coureur** : un TSB de −30 est banal pour une "
                "CTL de 150, préoccupant pour une CTL de 60. Avec les seuils absolus classiques (−10 / −30), 15 à 25 % "
                "des jours passaient au rouge ; avec −25 % / −50 % de la CTL, le rouge reste rare (3 à 12 % des jours).")
    st.markdown("#### Zones")
    z = pd.DataFrame([dict(Zone=n, **{"% FTP": f"{lo}-{hi if hi < 1000 else '…'}"}) for n, lo, hi in POWER_ZONES])
    st.dataframe(z, hide_index=True)
    st.markdown("#### Charge ressentie")
    st.latex(r"sRPE = RPE_{CR10} \times \text{durée}_{min} \qquad \text{Monotonie} = \frac{\bar{x}_{7j}}{\sigma_{7j}}")

with t4:
    st.markdown("#### Hooper")
    st.markdown("Sommeil + stress + fatigue + courbatures (1 à 7 chacun) → score de 4 (très bien) à 28 (très mal). "
                "Chaque jour est comparé à l'**habitude du coureur** : moyenne et écart-type des 28 jours précédents.")
    st.latex(r"z_j = \frac{Hooper_j - \overline{Hooper}_{j-28..j-1}}{\sigma_{j-28..j-1}} \qquad SWC = 0{,}2 \times \sigma")
    st.markdown("#### Feux tricolores")
    st.markdown(f"""
| Indicateur | {ui.pill('good', 'Vert')} | {ui.pill('warning', 'Orange')} | {ui.pill('critical', 'Rouge')} |
|---|---|---|---|
| Fraîcheur (TSB en % de la CTL) | > −25 % | −25 à −50 % | < −50 % |
| Bien-être (z Hooper) | < 1 | 1 à 2 | ≥ 2 |
| Questionnaires remplis (28 j) | ≥ 80 % | 60-80 % | < 60 % |
| Charge 7 j vs moyenne 28 j | — | > +30 % (information) | — |
""", unsafe_allow_html=True)
    st.markdown("Le statut d'une carte = le plus défavorable entre fraîcheur et bien-être. Les couleurs vert / orange / "
                "rouge sont **réservées aux alertes** ; chaque métrique a sa propre couleur partout dans l'outil.")
    ui.legend([("Puissance · TSS", METRIC["power"]), ("Fréquence cardiaque", METRIC["hr"]), ("Forme (CTL)", METRIC["ctl"]),
               ("Fatigue (ATL)", METRIC["atl"]), ("Fraîcheur (TSB)", METRIC["tsb"]), ("Ressenti (sRPE)", METRIC["srpe"]),
               ("Bien-être (Hooper)", METRIC["hooper"])])
    st.markdown("#### Ce que l'outil ne dit pas")
    ui.callout("Les liens entre charge, bien-être et performance sont <b>descriptifs</b> : ils aident à ouvrir la "
               "discussion avec le coureur, pas à conclure à une cause. Le rapport charge aiguë / chronique n'est "
               "<b>pas</b> utilisé comme prédicteur de blessure. Les données psychométriques sont fictives.")
