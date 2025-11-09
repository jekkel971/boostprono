import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import shutil

# ================== FICHIERS ==================
TEAMS_FILE = "teams_form.json"
HISTORIQUE_FILE = "historique_pronos.json"
BACKUP_DIR = "sauvegardes"

os.makedirs(BACKUP_DIR, exist_ok=True)

# ================== SAUVEGARDE AUTOMATIQUE ==================
if os.path.exists(TEAMS_FILE):
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    shutil.copy(TEAMS_FILE, os.path.join(BACKUP_DIR, f"teams_form_backup_{date_str}.json"))
if os.path.exists(HISTORIQUE_FILE):
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    shutil.copy(HISTORIQUE_FILE, os.path.join(BACKUP_DIR, f"historique_pronos_backup_{date_str}.json"))

# ================== CHARGEMENT DES DONNÉES ==================
if os.path.exists(TEAMS_FILE):
    with open(TEAMS_FILE, "r", encoding="utf-8") as f:
        teams_data = json.load(f)
else:
    teams_data = {}

if os.path.exists(HISTORIQUE_FILE):
    with open(HISTORIQUE_FILE, "r", encoding="utf-8") as f:
        historique = json.load(f)
else:
    historique = []

# ================== PAGE ==================
st.set_page_config(page_title="BoostProno ⚽", layout="wide")
st.title("⚽ BoostProno – Analyse et suivi des pronostics")

# ================== SECTION AJOUT / MISE À JOUR ÉQUIPES ==================
st.sidebar.header("🧾 Gestion des équipes")
with st.sidebar.form("form_teams"):
    team_name = st.text_input("Nom de l'équipe")
    last5 = st.text_input("5 derniers matchs (ex: v,v,n,d,v)")
    goals_scored = st.number_input("Buts marqués", 0, 200, 0)
    goals_against = st.number_input("Buts encaissés", 0, 200, 0)
    submitted_team = st.form_submit_button("💾 Enregistrer équipe")
if submitted_team and team_name:
    teams_data[team_name] = {
        "last5": last5.lower(),
        "goals_scored": goals_scored,
        "goals_against": goals_against
    }
    with open(TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(teams_data, f, indent=2, ensure_ascii=False)
    st.success(f"✅ {team_name} enregistrée avec succès")

# ================== SECTION PRONOSTICS ==================
st.header("📊 Ajouter un pronostic")
if teams_data:
    col1, col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("Équipe Domicile", list(teams_data.keys()))
    with col2:
        away_team = st.selectbox("Équipe Extérieure", [t for t in teams_data.keys() if t != home_team])

    cote_home = st.number_input("Cote Domicile", 1.01, 20.0, 1.5)
    cote_away = st.number_input("Cote Extérieure", 1.01, 20.0, 2.8)

    if st.button("➕ Analyser & Sauvegarder pronostic"):
        # --- Calcul des probabilités ---
        def form_score(seq):
            mapping = {"v": 3, "n": 1, "d": 0}
            vals = [mapping.get(x.strip(), 0) for x in seq.split(",") if x.strip() in mapping]
            vals = vals[-5:] if len(vals) > 5 else vals
            weights = np.array([5, 4, 3, 2, 1])[:len(vals)]
            return np.dot(vals, weights) / (15 if len(vals) == 5 else sum(weights))

        form_home = form_score(teams_data[home_team]["last5"])
        form_away = form_score(teams_data[away_team]["last5"])

        # Probabilité implicite des cotes
        p_home_odds = 1 / cote_home
        p_away_odds = 1 / cote_away

        # Fusion forme + cotes
        prob_home = 0.7 * form_home + 0.3 * p_home_odds
        prob_away = 0.7 * form_away + 0.3 * p_away_odds
        total = prob_home + prob_away
        prob_home /= total
        prob_away /= total

        winner = home_team if prob_home > prob_away else away_team
        prob_victoire = round(max(prob_home, prob_away) * 100, 2)
        mise = 10

        pronostic = {
            "home_team": home_team,
            "away_team": away_team,
            "cote_home": cote_home,
            "cote_away": cote_away,
            "winner_pred": winner,
            "prob_victoire": prob_victoire,
            "mise": mise,
            "resultat": None,
            "score_home": None,
            "score_away": None,
            "gain": 0
        }
        historique.append(pronostic)
        with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique, f, indent=2, ensure_ascii=False)
        st.success(f"✅ Pronostic enregistré : victoire de {winner} ({prob_victoire}%)")

else:
    st.warning("⚠️ Ajoute d'abord des équipes avant de pouvoir analyser un match.")

# ================== SUIVI DES RÉSULTATS ==================
st.header("📅 Suivi des résultats & statistiques")
if historique:
    df = pd.DataFrame(historique)
    st.dataframe(df[["home_team", "away_team", "winner_pred", "prob_victoire", "resultat", "score_home", "score_away", "gain"]], use_container_width=True)

    st.subheader("📝 Mettre à jour le résultat d’un match")
    match_index = st.selectbox("Sélectionne un match", range(len(historique)),
                               format_func=lambda i: f"{historique[i]['home_team']} vs {historique[i]['away_team']}")
    resultat = st.selectbox("Résultat réel", ["home", "draw", "away"])
    score_home = st.number_input("Buts Domicile", 0, 20, 0, key="score_home")
    score_away = st.number_input("Buts Extérieur", 0, 20, 0, key="score_away")
    if st.button("✅ Enregistrer résultat"):
        prono = historique[match_index]
        prono["resultat"] = resultat
        prono["score_home"] = score_home
        prono["score_away"] = score_away

        # Calcul du gain
        cote = prono["cote_home"] if prono["winner_pred"] == prono["home_team"] else prono["cote_away"]
        if (resultat == "home" and prono["winner_pred"] == prono["home_team"]) or \
           (resultat == "away" and prono["winner_pred"] == prono["away_team"]):
            gain = round(prono["mise"] * cote - prono["mise"], 2)
        else:
            gain = -prono["mise"]
        prono["gain"] = gain

        # --- Mise à jour des équipes ---
        home = prono["home_team"]
        away = prono["away_team"]
        # Forme
        def update_last5(team, resultat_match):
            seq = teams_data[team]["last5"].split(",")[:4]
            seq = [resultat_match] + seq
            teams_data[team]["last5"] = ",".join(seq)
        if resultat == "home":
            update_last5(home, "v")
            update_last5(away, "d")
        elif resultat == "away":
            update_last5(home, "d")
            update_last5(away, "v")
        else:
            update_last5(home, "n")
            update_last5(away, "n")
        # Scores
        teams_data[home]["goals_scored"] += score_home
        teams_data[home]["goals_against"] += score_away
        teams_data[away]["goals_scored"] += score_away
        teams_data[away]["goals_against"] += score_home

        # Sauvegarde
        with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique, f, indent=2, ensure_ascii=False)
        with open(TEAMS_FILE, "w", encoding="utf-8") as f:
            json.dump(teams_data, f, indent=2, ensure_ascii=False)

        st.success(f"Résultat enregistré ✅ (gain : {gain}€)")

    # ================== STATISTIQUES ==================
    df_valides = df[df["resultat"].notna()]
    if not df_valides.empty:
        total_gain = df_valides["gain"].sum()
        nb_pronos = len(df_valides)
        nb_gagnants = (df_valides["gain"] > 0).sum()
        precision = nb_gagnants / nb_pronos * 100
        roi = (total_gain / (nb_pronos * 10)) * 100

        st.metric("🎯 Précision", f"{precision:.2f}%")
        st.metric("💰 ROI", f"{roi:.2f}%")
        st.metric("📈 Gain total", f"{total_gain:.2f}€")

    # Supprimer un match
    st.subheader("🗑️ Supprimer un match")
    match_to_del = st.selectbox("Sélectionner le match à supprimer", range(len(historique)),
                                format_func=lambda i: f"{historique[i]['home_team']} vs {historique[i]['away_team']}")
    if st.button("❌ Supprimer le match"):
        historique.pop(match_to_del)
        with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique, f, indent=2, ensure_ascii=False)
        st.warning("Match supprimé. Les statistiques des équipes restent intactes.")

    # Réinitialiser l'application
    if st.button("♻️ Réinitialiser tout"):
        historique.clear()
        teams_data.clear()
        for f in [HISTORIQUE_FILE, TEAMS_FILE]:
            if os.path.exists(f):
                os.remove(f)
        st.warning("Application réinitialisée. Toutes les données supprimées.")
