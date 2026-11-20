"""Point d'entrée : `streamlit run app/Accueil.py`."""
import streamlit as st

st.set_page_config(page_title="Cellule Perf · Cyclisme", page_icon=":material/directions_bike:",
                   layout="wide", initial_sidebar_state="expanded")

pages = [
    st.Page("vues/accueil.py", title="Accueil", icon=":material/home:", default=True),
    st.Page("vues/equipe.py", title="Équipe", icon=":material/groups:"),
    st.Page("vues/coureur.py", title="Coureur", icon=":material/person:"),
    st.Page("vues/comparaison.py", title="Comparaison", icon=":material/compare_arrows:"),
    st.Page("vues/methodes.py", title="Méthodes", icon=":material/functions:"),
]
st.navigation(pages, position="top").run()
