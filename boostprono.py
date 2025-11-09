import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import shutil

st.set_page_config(page_title="BoostProno – Analyseur de matchs", layout="wide")

# === Fichiers ===
TEAMS_FILE = "teams_form.json"
HISTORIQUE_FILE = "historique_pronos.json"
BACKUP_DIR = "sauvegardes"

os.makedirs(BACKUP_DIR, exist_ok=True)

# --- Pré-remplissage des équipes si le fichier n'existe pas ---
if not os.path.exists(TEAMS_FILE):
    teams_data = {
        # Ligue 1
        "Paris SG": {"last5":"v,v,n,d,v","goals_scored":60,"goals_against":20},
        "Marseille": {"last5":"v,d,v,n,d","goals_scored":50,"goals_against":30},
        "Lyon": {"last5":"n,v,d,v,d","goals_scored":48,"goals_against":32},
        "Monaco": {"last5":"d,v,n,d,v","goals_scored":45,"goals_against":35},
        "Rennes": {"last5":"v,n,d,v,n","goals_scored":42,"goals_against":36},
        # Premier League
        "Manchester City": {"last5":"v,v,v,v,v","goals_scored":70,"goals_against":20},
        "Liverpool": {"last5":"v,v,n,d,v","goals_scored":65,"goals_against":25},
        "Chelsea": {"last5":"n,v,d,v,d","goals_scored":50,"goals_against":30},
        "Arsenal": {"last5":"v,d,v,v,n","goals_scored":55,"goals_against":28},
        # Liga
        "Real Madrid": {"last5":"v,v,d,v,v","goals_scored":60,"goals_against":22},
        "Barcelona": {"last5":"v,d,v,n,v","goals_scored":58,"goals_against":25},
        "Atletico Madrid": {"last5":"n,v,d,v,d","goals_scored":50,"goals_against":30},
        "Sevilla": {"last5":"v,v,n,d,v","goals_scored":48,"goals_against":35}
    }
    with open(TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(teams_data, f, indent=2, ensure_ascii=False)
else:
    with open(TEAMS_FILE, "r", encoding="utf-8") as f:
        teams_data = json.load(f)

# --- Historique pronos ---
if os.path.exists(HISTORIQUE_FILE):
    with open(HISTORIQUE_FILE, "r", encoding="utf-8") as f:
        historique = json.load(f)
else:
    historique = []

# === Sauvegarde automatique ===
if os.path.exists(TEAMS_FILE):
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = os.path.join(BACKUP_DIR, f"teams_form_backup_{date_str}.json")
    shutil.copy(TEAMS_FILE, backup_file)

# === Interface ===
st.title("⚽ BoostProno – Analyseur de matchs avancé")

# --- Gestion équipes ---
st.header("🧾 Ajouter ou modifier une équipe")
with st.form("form_teams"):
    team_name = st.text_input("Nom de l'équipe")
    form_last5 = st.text_input("5 derniers matchs (ex: v,v,n,d,v)")
    goals_scored = st.number_input("Buts marqués", 0, 200, 0)
    goals_against = st.number_input("Buts encaissés", 0, 200, 0)
    submitted_team = st.form_submit_button("💾 Enregistrer l'équipe")

if submitted_team and team_name:
    teams_data[team_name] = {
        "last5": form_last5.lower(),
        "goals_scored": goals_scored,
        "goals_against": goals_against
    }
    with open(TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(teams_data, f, indent=2, ensure_ascii=False)
    st.success(f"✅ {team_name} enregistrée")

# --- Ajouter un pronostic ---
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
        # --- Calcul probabilité ---
        def form_score(seq):
            mapping = {"v":3,"n":1,"d":0}
            vals = [mapping.get(x.strip(),0) for x in seq.split(",") if x.strip() in mapping]
            vals = vals[-5:] if len(vals) > 5 else vals
            weights = np.array([5,4,3,2,1])[:len(vals)]
            return np.dot(vals, weights)/(15 if len(vals)==5 else sum(weights))

        form_home = form_score(teams_data[home_team]["last5"])
        form_away = form_score(teams_data[away_team]["last5"])

        # Probabilités implicites des cotes
        p_home_odds = 1 / cote_home
        p_away_odds = 1 / cote_away

        # Fusion cotes et forme
        prob_home = p_home_odds * 0.7 + form_home * 0.3
        prob_away = p_away_odds * 0.7 + form_away * 0.3
        total = prob_home + prob_away
        prob_home /= total
        prob_away /= total

        winner = home_team if prob_home > prob_away else away_team
        prob_victoire = round(max(prob_home, prob_away)*100,2)
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
            "gain": 0
        }
        historique.append(pronostic)
        with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique, f, indent=2, ensure_ascii=False)
        st.success(f"✅ Pronostic enregistré : {winner} ({prob_victoire}%)")

# --- Suivi résultats ---
st.header("📅 Suivi des pronostics")

if historique:
    df = pd.DataFrame(historique)
    st.dataframe(df[["home_team","away_team","winner_pred","prob_victoire","resultat","gain"]])

    st.subheader("📝 Mettre à jour le résultat réel")
    match_index = st.selectbox("Sélectionner un match", range(len(historique)),
                               format_func=lambda i: f"{historique[i]['home_team']} vs {historique[i]['away_team']}")
    resultat = st.selectbox("Résultat réel", ["home","draw","away"])
    if st.button("✅ Enregistrer le résultat réel"):
        prono = historique[match_index]
        cote = prono["cote_home"] if prono["winner_pred"]==prono["home_team"] else prono["cote_away"]

        # Calcul du gain
        if (resultat=="home" and prono["winner_pred"]==prono["home_team"]) or \
           (resultat=="away" and prono["winner_pred"]==prono["away_team"]):
            gain = round(prono["mise"]*cote - prono["mise"],2)
        else:
            gain = -prono["mise"]

        prono["resultat"] = resultat
        prono["gain"] = gain
        with open(HISTORIQUE_FILE,"w",encoding="utf-8") as f:
            json.dump(historique,f,indent=2,ensure_ascii=False)
        st.success(f"Résultat enregistré ✅ (gain : {gain}€)")

        # --- Mise à jour automatique des 5 derniers matchs ---
        home_seq = teams_data[prono["home_team"]]["last5"].split(",")[:4]
        away_seq = teams_data[prono["away_team"]]["last5"].split(",")[:4]
        if resultat=="home":
            home_seq = ["v"] + home_seq
            away_seq = ["d"] + away_seq
        elif resultat=="away":
            home_seq = ["d"] + home_seq
            away_seq = ["v"] + away_seq
        else:
            home_seq = ["n"] + home_seq
            away_seq = ["n"] + away_seq
        teams_data[prono["home_team"]]["last5"] = ",".join(home_seq)
        teams_data[prono["away_team"]]["last5"] = ",".join(away_seq)

        # Sauvegarde équipes
        with open(TEAMS_FILE,"w",encoding="utf-8") as f:
            json.dump(teams_data,f,indent=2,ensure_ascii=False)
        st.success("✅ Forme des équipes mise à jour automatiquement")

    # --- Statistiques ---
    df_valides = df[df["resultat"].notna()]
    if not df_valides.empty:
        total_gain = df_valides["gain"].sum()
        nb_pronos = len(df_valides)
        nb_gagnants = (df_valides["gain"]>0).sum()
        precision = nb_gagnants/nb_pronos*100
        roi = (total_gain/(nb_pronos*10))*100

        st.metric("🎯 Précision", f"{precision:.2f}%")
        st.metric("💰 ROI", f"{roi:.2f}%")
        st.metric("📈 Gain total", f"{total_gain:.2f}€")

    # Export CSV
    st.download_button("📥 Télécharger l’historique (CSV)",
                       df.to_csv(index=False).encode("utf-8"),
                       "historique_pronos.csv",
                       "text/csv")
else:
    st.info("Aucun pronostic enregistré pour le moment.")
