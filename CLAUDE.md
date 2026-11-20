# Projet cyclisme : outil d'analyse de la charge et du profil de performance

## Contexte
- Cours « Méthodologie & optimisation de la performance sportive » (ENSAI Digisport). Groupe : Arthur, Clémence, Lucas.
- Mission : en tant que data scientist d'une équipe pro, présenter au staff (entraîneurs, DS) un outil d'analyse de l'effectif.
- Périmètre : les 7 coureurs, à trois niveaux :
  - individuel : fiche détaillée par coureur (profil, charge, bien-être), pour des analyses précises ;
  - collectif : vue équipe (charge de chacun cette semaine, alertes, qui est frais ou fatigué) ;
  - comparaisons : seulement quand elles sont utiles et justes (W/kg, valeurs relatives à la propre moyenne du coureur, mêmes périodes).
- Livrables : outil + oral (15 min + 10 min de questions, temps de parole égal) + rapport concis et visuel pour le staff.
- Vocabulaire du rendu : simple, orienté entraîneur (forme, fatigue, fraîcheur), pas un cours de stats.
- Grille :
  - Volet 1, profil de performance : variables choisies, justification, étapes de calcul, interprétation.
  - Volet 2, charge de travail : évolution, méthodes de calcul et de visualisation, choix graphiques (formats, couleurs), interprétation.

## Données (dans `data/`, jamais versionnées)
- Coureurs : `data/Data_Cyclist/cyclistN_XXkg/` (N de 1 à 7, CSV à plat ou rangés par année). Classeurs psy dans `data/Data_interne_psy/`. Le poids est dans le nom du dossier → calculs en W/kg.
  - cyclist1 76 kg (2022) · cyclist2 63 kg (2022-2023) · cyclist3 65 kg (2023) · cyclist4 58 kg (2022-2023) · cyclist5 65 kg (2023) · cyclist6 71 kg (2023) · cyclist7 74 kg (2022).
  - Les périodes diffèrent : pour comparer, aligner sur une période commune ou en relatif (mois de saison, z-scores).
  - Tous les paramètres (FTP, FCmax, zones, CTL/ATL) sont calculés PAR coureur, jamais en commun.
- Sorties : un CSV par sortie, 1 ligne par seconde, nommé `YYYY_MM_DD_HH_MM_SS.csv` (date et heure de départ).
  - Colonnes utiles : secs, km, kph, hr, cad, watts, alt, slope, lat, lon.
  - Toujours à 0, à ignorer : nm, interval, headwind, smo2, thb, o2hb, hhb.
  - Manquants : -255 dans temp et lrbalance ; 0 dans lte, rte, lps, rps, slope. lrbalance valide entre 0 et 100.
  - GPS dans le Pacifique (lat ≈ -10/-11, lon ≈ 165/167) = Zwift, donc sortie indoor.
- Classeur `Charge_interne_psy_cyclisteN.xlsx` (données psy fictives) :
  - feuille `seances` : cycliste, date, heure, fichier, rpe (CR-10), lactate (mmol/L, fin de séance) ;
  - feuille `hooper` : une ligne par jour, sommeil, stress, fatigue, courbatures (1 = très bon/faible, 7 = très mauvais/élevé) ;
  - jointure : `seances.fichier` = nom du CSV ; `hooper` par date.
- Plusieurs sorties le même jour sont possibles : sommer la charge par jour.
- Les cases vides comptent : taux de remplissage RPE/Hooper = compliance du coureur.
- FC de repos : fournie seulement pour le cycliste 4 (`fc_repos_cycliste4.csv`, rangé par erreur dans le dossier du cycliste 3 ; 50 bpm par hypothèse pour les autres). Pas de FTP fournie, pas de test FC-lactate (donc pas d'iTRIMP).

## Objectif produit : une app très soignée
- Livrable phare : une application web Streamlit (multipage) présentée en live au staff, déployable sur Streamlit Community Cloud depuis ce repo.
- Pages : Équipe (vue collective, alertes feux tricolores) · Coureur (sélecteur + onglets Profil, Charge, Bien-être) · Comparaison (2-7 coureurs, W/kg et valeurs relatives) · Méthodes.
- Design :
  - un graphique = un message, avec un titre qui donne la conclusion ;
  - une palette fixe partout : une couleur par métrique, feux tricolores (vert/orange/rouge) pour les alertes, jamais de couleurs par défaut ;
  - cartes KPI en haut de page, filtres de période dans la barre latérale ;
  - plotly en `template="plotly_white"` ou thème sombre cohérent, police lisible, pas de décimales inutiles ;
  - thème Streamlit dans `.streamlit/config.toml`.
- L'app ne fait que lire `outputs/` : tous les calculs sont dans `src/`.

## Organisation du code
- `app/` : `Accueil.py` (routeur `st.navigation`) + `vues/` (une page par fichier), composants réutilisables dans `app/components.py`. Ne pas renommer `vues/` en `pages/` : Streamlit réactiverait sa navigation automatique.
- `src/` : code partagé, en `.py` uniquement.
  - `load.py` : lecture et nettoyage des CSV et du classeur.
  - `metrics.py` : métriques par sortie.
  - `tracking.py` : agrégations jour/semaine/mois, CTL/ATL/TSB.
  - `profile.py` : courbe de puissance record, FTP, CP et W'.
- `notebooks/` : un notebook par personne (`prenom_sujet.ipynb`), qui importe `src/` ; pas de logique dupliquée.
- `outputs/` : tables centrales avec une colonne `cyclist` : `rides.parquet` (une ligne par sortie), `daily.parquet` (une ligne par coureur et par jour, charge + Hooper), `mmp.parquet` (records de puissance par coureur et par mois), plus `ride_mmp` (records par sortie, pour filtrer une période), `ftp` (FTP mensuelle), `riders` (fiche synthèse), `traces` (1 point / 20 s pour l'explorateur de séance).
- Le pipeline tourne sur les 7 coureurs d'un coup (`python -m src.build`), l'app ne fait que lire `outputs/`.
- Ne jamais modifier les fichiers bruts de `data/`.
- Unités dans les noms de colonnes : `dur_s`, `np_w`, `np_wkg`, `work_kj`, `hr_mean_bpm`.
- Python : pandas, numpy, matplotlib ou plotly. Petits commits, messages en français, `git pull` avant de travailler.

## Formules de référence
- NP : moyenne glissante 30 s → puissance 4 → moyenne → racine 4e. Garder les 0 W.
- IF = NP / FTP ; TSS = durée_s × NP × IF / (FTP × 3600) × 100 (1 h à FTP = 100).
- FTP ≈ 0,95 × meilleure puissance 20 min (à recalculer par mois ou par bloc, pas fixe sur la saison).
- Travail (kJ) = somme des watts / 1000 ; VI = NP / Pmoy ; indice d'efficacité = NP / FC moyenne.
- Zones puissance (% FTP, Coggan) : Z1 ≤ 55, Z2 56-75, Z3 76-90, Z4 91-105, Z5 ≥ 106.
- Zones FC (% FCmax) : 50-59, 60-69, 70-79, 80-89, 90-100. FCmax = max de la saison.
- TRIMP Edwards = Σ minutes par zone FC × coefficient 1 à 5.
- TRIMP Banister = durée_min × ΔFC × 0,64 × e^(1,92 × ΔFC), ΔFC = (FCexo − FCrepos) / (FCmax − FCrepos).
- sRPE (UA) = RPE × durée_min ; Hooper = sommeil + stress + fatigue + courbatures (4 à 28).
- CTL(j) = CTL(j−1) + (charge(j) − CTL(j−1)) / 42 ; ATL idem sur 7 ; TSB = CTL − ATL. Jour sans sortie : charge = 0. Ne pas interpréter les ~42 premiers jours.
- Courbe de puissance record : max de la moyenne glissante sur d secondes (5 s, 1 min, 5 min, 20 min, 60 min), en W et W/kg.
- Puissance critique : P = CP + W'/t, ajusté sur les records de 2 à 15 min.
- Changement significatif : SWC = 0,2 × écart-type individuel ; z-score par rapport à la moyenne du coureur (Hooper : 28 jours précédents).
- Charge unifiée (`load`, échelle TSS) : TSS si puissance, sinon TRIMP Banister × k, sinon sRPE × k′ (k = médiane des ratios du coureur).
- FTP du mois = 0,95 × meilleur 20 min sur une fenêtre glissante de 3 mois.
- Alerte fraîcheur sur TSB / CTL (%) : orange < −25 %, rouge < −50 % (les seuils absolus −10 / −30 mettaient 15-25 % des jours au rouge).
- Enregistrements sans puissance ni FC et > 6 h ou > 50 km/h = artefacts, écartés (`artifact`).

## À éviter
- Versionner les données ou des fichiers lourds.
- Conclure à de la causalité : les relations charge-performance observées sont descriptives.
- Présenter le ratio aigu/chronique (ATL/CTL) comme prédicteur de blessure.
- Mélanger indoor et outdoor dans les comparaisons de FC ou de vitesse.
