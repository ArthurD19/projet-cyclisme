# Projet cyclisme : charge et profil de performance

Outil d'analyse de l'effectif (7 coureurs) pour le staff : vue équipe à feux tricolores, fiche coureur
(profil, charge, bien-être, séance), comparaisons justes (W/kg, % FTP, saisons alignées), méthodes.

## Installation
```bash
uv venv --python 3.12 .venv && uv pip install -p .venv -r requirements.txt
# (ou : python -m venv .venv && .venv/bin/pip install -r requirements.txt)
```
Les données brutes vont dans `data/` (jamais versionnées) :
`data/Data_Cyclist/cyclistN_XXkg/…/*.csv` et `data/Data_interne_psy/Charge_interne_psy_cyclisteN.xlsx`.

## Lancer
```bash
.venv/bin/python -m src.build              # ~20 s : calcule tout → outputs/*.parquet
.venv/bin/streamlit run app/Accueil.py     # l'app ne fait que lire outputs/
```

## Organisation
- `src/` : tout le calcul (`load`, `metrics`, `profile`, `tracking`, `build`, `config` = seuils + palette).
- `app/Accueil.py` : routeur ; pages dans `app/vues/` ; briques communes dans `app/components.py`.
  (Le dossier s'appelle `vues/` et non `pages/` : un dossier `pages/` réactive l'ancienne navigation de Streamlit et court-circuite le routeur.)
- `notebooks/` : un notebook par personne (`prenom_sujet.ipynb`), qui importe `src/`.
- `outputs/` : `rides`, `daily`, `mmp`, `ride_mmp`, `ftp`, `riders`, `traces` (parquet).
