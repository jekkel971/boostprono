import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import shutil

# --- Fichiers ---
TEAMS_FILE = "teams_form.json"
HISTORIQUE_FILE = "historique_pronos.json"
BACKUP_DIR = "sauvegardes"

os.makedirs(BACKUP_DIR, exist_ok=True)

# --- Sauvegarde automatique au démarrage ---
if os.path.exists(TEAMS_FILE):
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = os.path.join(BACKUP_DIR, f"teams_form_backup_{date_str}.json")
    shutil.copy(TEAMS_FILE, backup_file)

# --- Config page ---
st.set_page_config(page_title="BoostProno", layout="wide")
st.title("⚽ BoostProno – Analyse de matchs et suivi des pronostics")

# --- Charger équipes ---
if os.path.exists(TEAMS_FILE):
    with open(TEAMS_FILE, "r", encoding="utf-8") as f:
        teams_data = json.load(f)
else:
    teams_data = {}

# --- Charger historique ---
if os.path.exists(HISTORIQUE_FILE):
    with open(HISTORIQUE_FILE, "r", encoding="utf-8") as f:
        historique = json.load(f)
else:
    historique = []

# ================== GESTION DES ÉQUIPES ==================
st.header("🧾 Gestion des équipes")
with st.form("form_teams"):
    team_name = st.text_input("Nom de l'équipe")
    last5 = st.text_input("5 derniers matchs (ex: v,v,n,d,v)")
    goals_scored = st.number_input("Buts marqués", 0, 200, 0)
    goals_against = st.number_input("Buts encaissés", 0, 200, 0)
    submitted_team = st.form_submit_button("💾 Enregistrer l'équipe")

if submitted_team and team_name:
    teams_data[team_name] = {
        "last5": last5.lower(),
        "goals_scored": goals_scored,
        "goals_against": goals_against
    }
    with open(TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(teams_data, f, indent=2, ensure_ascii=False)
    st.success(f"✅ {team_name} enregistrée.")

# ================== AJOUT PRONOSTICS ==================
st.header("📊 Ajouter un pronostic")
if teams_data:
    col1, col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("Équipe Domicile", list(teams_data.keys()))
    with col2:
        away_team = st.selectbox("Équipe Extérieure", [t for t in teams_data.keys() if t != home_team])

    cote_home = st.number_input("Cote Domicile", 1.01, 20.0, 1.5)
    cote_away = st.number_input("Cote Extérieure", 1.01, 20.0, 2.8)

    if st.button("➕ Analyser & Sauvegarder le pronostic"):
        # --- Calcul probabilités amélioré ---
        def form_score(seq):
            mapping = {"v": 3, "n": 1, "d": 0}
            vals = [mapping.get(x.strip(), 0) for x in seq.split(",") if x.strip() in mapping]
            vals = vals[-5:] if len(vals) > 5 else vals
            weights = np.array([5, 4, 3, 2, 1])[:len(vals)]
            return np.dot(vals, weights) / (15 if len(vals) == 5 else sum(weights))

        form_home = form_score(teams_data[home_team]["last5"])
        form_away = form_score(teams_data[away_team]["last5"])

        p_home_odds = 1 / cote_home
        p_away_odds = 1 / cote_away

        prob_home = 0.6*form_home + 0.4*p_home_odds
        prob_away = 0.6*form_away + 0.4*p_away_odds

        total = prob_home + prob_away
        prob_home /= total
        prob_away /= total

        winner = home_team if prob_home > prob_away else away_team
        prob_victoire = round(max(prob_home, prob_away) * 100, 2)
        mise = 10

        pronostic = {
            "home": home_team,
            "away": away_team,
            "cote_home": cote_home,
            "cote_away": cote_away,
            "winner_pred": winner,
            "winner_name": winner,
            "prob_victoire": prob_victoire,
            "mise": mise,
            "result": None,
            "gain": 0,
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        historique.append(pronostic)
        with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique, f, indent=2, ensure_ascii=False)
        st.success(f"✅ Pronostic enregistré : victoire de {winner} ({prob_victoire}%)")
else:
    st.warning("⚠️ Ajoute d'abord des équipes avant d’analyser un match.")

# ================== SUIVI DES RÉSULTATS ==================
st.header("📅 Suivi des résultats & statistiques")
if historique:
    df = pd.DataFrame(historique)
    st.dataframe(df[["home","away","winner_name","prob_victoire","result","gain"]], use_container_width=True)

    st.subheader("📝 Mettre à jour le résultat réel")
    match_index = st.selectbox(
        "Sélectionne un match",
        range(len(historique)),
        format_func=lambda i: f"{historique[i].get('home','N/A')} vs {historique[i].get('away','N/A')}"
    )
    resultat = st.selectbox("Résultat réel", ["home", "draw", "away"])
    if st.button("✅ Enregistrer le résultat réel"):
        prono = historique[match_index]
        cote = prono["cote_home"] if prono["winner_pred"] == prono["home"] else prono["cote_away"]
        if (resultat == "home" and prono["winner_pred"] == prono["home"]) or \
           (resultat == "away" and prono["winner_pred"] == prono["away"]):
            gain = round(prono["mise"] * cote - prono["mise"], 2)
        elif resultat == "draw":
            gain = -prono["mise"]
        else:
            gain = -prono["mise"]

        prono["result"] = resultat
        prono["gain"] = gain
        with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique, f, indent=2, ensure_ascii=False)
        st.success(f"Résultat enregistré ✅ (gain : {gain}€)")

    # --- Statistiques ---
    df_valides = df[df["result"].notna()]
    if not df_valides.empty:
        total_gain = df_valides["gain"].sum()
        nb_pronos = len(df_valides)
        nb_gagnants = (df_valides["gain"] > 0).sum()
        precision = nb_gagnants / nb_pronos * 100
        st.metric("🎯 Précision", f"{precision:.2f}%")
        st.metric("💰 Gain total", f"{total_gain:.2f}€")
        st.metric("📊 Nombre de pronos gagnants", nb_gagnants)

    # --- Export CSV ---
    st.download_button(
        "📥 Télécharger l’historique (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        "historique_pronos.csv",
        "text/csv"
    )

    # --- Réinitialiser ---
    if st.button("🗑️ Réinitialiser l’historique"):
        historique.clear()
        with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique, f, indent=2, ensure_ascii=False)
        st.warning("Historique réinitialisé.")
else:
    st.info("Aucun pronostic enregistré pour le moment.")
