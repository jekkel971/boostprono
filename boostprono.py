import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import shutil
import matplotlib.pyplot as plt
from datetime import datetime

# ==================== CONFIGURATION ====================
st.set_page_config(page_title="⚽ Analyseur de matchs avancé", layout="wide")

TEAMS_FILE = "teams_form.json"
HISTORIQUE_FILE = "historique_pronos.json"
BACKUP_DIR = "sauvegardes"
BACKUP_HISTORIQUE = "sauvegardes_historique"
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(BACKUP_HISTORIQUE, exist_ok=True)

# --- Sauvegarde automatique au démarrage ---
def backup_file(src, dest_dir):
    if os.path.exists(src):
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        dest = os.path.join(dest_dir, f"{os.path.basename(src).replace('.json','')}_{date_str}.json")
        shutil.copy(src, dest)

backup_file(TEAMS_FILE, BACKUP_DIR)
backup_file(HISTORIQUE_FILE, BACKUP_HISTORIQUE)

# ==================== CHARGEMENT DES DONNÉES ====================
def load_json(file):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

teams_data = load_json(TEAMS_FILE)
historique = load_json(HISTORIQUE_FILE)

# ==================== SIDEBAR SAUVEGARDES ====================
st.sidebar.header("💾 Gestion des sauvegardes")
if st.sidebar.button("🧱 Sauvegarde manuelle des équipes"):
    backup_file(TEAMS_FILE, BACKUP_DIR)
    st.sidebar.success("✅ Sauvegarde des équipes effectuée.")
if st.sidebar.button("🧱 Sauvegarde manuelle des pronostics"):
    backup_file(HISTORIQUE_FILE, BACKUP_HISTORIQUE)
    st.sidebar.success("✅ Sauvegarde de l’historique effectuée.")

# ==================== SECTION AJOUT ÉQUIPES ====================
st.title("⚽ Analyseur de matchs & suivi des pronostics")

st.header("🧾 Gestion des équipes")
with st.form("form_teams"):
    team_name = st.text_input("Nom de l'équipe")
    form_last5 = st.text_input("5 derniers matchs (ex: v,v,n,d,v)")
    goals_scored = st.number_input("Buts marqués", 0, 200, 0)
    goals_against = st.number_input("Buts encaissés", 0, 200, 0)
    submitted = st.form_submit_button("💾 Enregistrer l'équipe")

if submitted and team_name:
    teams_data[team_name] = {
        "last5": form_last5.lower(),
        "goals_scored": goals_scored,
        "goals_against": goals_against
    }
    with open(TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(teams_data, f, indent=2, ensure_ascii=False)
    st.success(f"✅ {team_name} enregistrée avec succès")

# ==================== SECTION PRONOSTICS ====================
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
        def form_score(seq):
            mapping = {"v": 3, "n": 1, "d": 0}
            vals = [mapping.get(x.strip(), 0) for x in seq.split(",") if x.strip() in mapping]
            if not vals: return 0.5
            weights = np.array([5,4,3,2,1])[:len(vals)]
            return np.dot(vals, weights) / (15 if len(vals) == 5 else sum(weights))

        form_home = form_score(teams_data[home_team]["last5"])
        form_away = form_score(teams_data[away_team]["last5"])

        # --- Probabilités via cotes ---
        p_home = 1 / cote_home
        p_away = 1 / cote_away

        # --- Ajustement par la forme et les buts ---
        g_diff_home = teams_data[home_team]["goals_scored"] - teams_data[home_team]["goals_against"]
        g_diff_away = teams_data[away_team]["goals_scored"] - teams_data[away_team]["goals_against"]

        form_factor_home = (form_home + (g_diff_home / 50)) * 0.4
        form_factor_away = (form_away + (g_diff_away / 50)) * 0.4

        # --- Avantage domicile ---
        p_home_adj = p_home * (1 + 0.10) + form_factor_home
        p_away_adj = p_away + form_factor_away

        total = p_home_adj + p_away_adj
        prob_home = p_home_adj / total
        prob_away = p_away_adj / total

        winner = home_team if prob_home > prob_away else away_team
        prob_victoire = round(max(prob_home, prob_away) * 100, 2)

        mise = 10
        pronostic = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "home_team": home_team,
            "away_team": away_team,
            "cote_home": cote_home,
            "cote_away": cote_away,
            "winner_pred": winner,
            "prob_victoire": prob_victoire,
            "mise": mise,
            "resultat": None,
            "gain": 0
        }

        historique.append(pronostic)
        with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique, f, indent=2, ensure_ascii=False)
        st.success(f"✅ Pronostic enregistré : victoire de {winner} ({prob_victoire}%)")

else:
    st.warning("⚠️ Ajoute d'abord des équipes avant de pouvoir analyser un match.")

# ==================== SUIVI DES RÉSULTATS ====================
st.header("📅 Suivi des résultats & statistiques")

if historique:
    df = pd.DataFrame(historique)
    st.dataframe(df[["date", "home_team", "away_team", "winner_pred", "prob_victoire", "resultat", "gain"]],
                 use_container_width=True)

    st.subheader("📝 Mettre à jour le résultat d’un match")
    match_index = st.selectbox("Sélectionne un match", range(len(historique)),
                               format_func=lambda i: f"{historique[i]['home_team']} vs {historique[i]['away_team']}")
    resultat = st.selectbox("Résultat réel", ["home", "draw", "away"])
    if st.button("✅ Enregistrer le résultat réel"):
        prono = historique[match_index]
        cote = prono["cote_home"] if prono["winner_pred"] == prono["home_team"] else prono["cote_away"]

        if (resultat == "home" and prono["winner_pred"] == prono["home_team"]) or \
           (resultat == "away" and prono["winner_pred"] == prono["away_team"]):
            gain = round(prono["mise"] * cote - prono["mise"], 2)
        else:
            gain = -prono["mise"]

        prono["resultat"] = resultat
        prono["gain"] = gain
        with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique, f, indent=2, ensure_ascii=False)
        st.success(f"Résultat enregistré ✅ (gain : {gain}€)")

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

        df_valides["profit_cumule"] = df_valides["gain"].cumsum()
        fig, ax = plt.subplots()
        ax.plot(df_valides["profit_cumule"], marker='o', linestyle='-', linewidth=2)
        ax.set_title("Évolution du profit cumulé (€)")
        ax.set_xlabel("Matchs")
        ax.set_ylabel("Profit (€)")
        st.pyplot(fig)

    st.download_button("📥 Télécharger l’historique (CSV)",
                       df.to_csv(index=False).encode("utf-8"),
                       "historique_pronos.csv",
                       "text/csv")

    if st.button("🗑️ Réinitialiser l’historique"):
        historique.clear()
        with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique, f, indent=2, ensure_ascii=False)
        st.warning("Historique réinitialisé.")
else:
    st.info("Aucun pronostic enregistré pour le moment.")
