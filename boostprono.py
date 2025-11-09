import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import shutil

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Boost Prono", layout="wide")

TEAMS_FILE = "teams_form.json"
HISTORIQUE_FILE = "historique_pronos.json"
BACKUP_DIR = "sauvegardes"
os.makedirs(BACKUP_DIR, exist_ok=True)

# ---------------- BACKUP ----------------
if os.path.exists(TEAMS_FILE):
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    shutil.copy(TEAMS_FILE, os.path.join(BACKUP_DIR, f"teams_form_backup_{date_str}.json"))

# ---------------- CHARGEMENT DES DONNEES ----------------
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

# ---------------- INTERFACE ----------------
st.title("⚽ Boost Prono – Analyse avancée")

# --------- Gestion des équipes ----------
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

# --------- Ajouter un pronostic ----------
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
        # --------- Algorithme amélioré ---------
        def form_score(seq):
            mapping = {"v":3,"n":1,"d":0}
            vals = [mapping.get(x.strip(),0) for x in seq.split(",") if x.strip() in mapping]
            vals = vals[-5:] if len(vals) > 5 else vals
            weights = np.array([5,4,3,2,1][:len(vals)])
            return np.dot(vals, weights)/sum(weights)

        def improved_prob(home, away, cote_h, cote_a):
            fh = form_score(home["last5"])
            fa = form_score(away["last5"])
            # Ratio attaque/défense
            home_attack = home["goals_scored"] / max(home["goals_scored"] + away["goals_against"], 1)
            away_attack = away["goals_scored"] / max(away["goals_scored"] + home["goals_against"], 1)
            # Score combiné
            score_home = 0.5*fh + 0.25*home_attack + 0.25*(1-away_attack)
            score_away = 0.5*fa + 0.25*away_attack + 0.25*(1-home_attack)
            # Probabilité selon cote
            p_home_odds = 1 / cote_h
            p_away_odds = 1 / cote_a
            # Fusion
            prob_home = 0.6*score_home + 0.4*p_home_odds
            prob_away = 0.6*score_away + 0.4*p_away_odds
            total = prob_home + prob_away
            return prob_home/total, prob_away/total

        ph, pa = improved_prob(teams_data[home_team], teams_data[away_team], cote_home, cote_away)
        winner = home_team if ph>pa else away_team
        prob_victoire = round(max(ph, pa)*100,2)
        mise = 10
        gain = 0

        pronostic = {
            "home_team": home_team,
            "away_team": away_team,
            "cote_home": cote_home,
            "cote_away": cote_away,
            "winner_pred": winner,
            "prob_victoire": prob_victoire,
            "mise": mise,
            "resultat": None,
            "gain": gain
        }

        historique.append(pronostic)
        with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique, f, indent=2, ensure_ascii=False)
        st.success(f"✅ Pronostic ajouté : victoire de {winner} ({prob_victoire}%)")
else:
    st.warning("⚠️ Ajoute d'abord des équipes.")

# --------- Suivi des résultats ----------
st.header("📅 Suivi des résultats & statistiques")
if historique:
    df = pd.DataFrame(historique)
    st.dataframe(df[["home_team","away_team","winner_pred","prob_victoire","resultat","gain"]], use_container_width=True)

    st.subheader("📝 Mettre à jour le résultat d’un match")
    match_index = st.selectbox("Sélectionne un match", range(len(historique)),
                               format_func=lambda i: f"{historique[i]['home_team']} vs {historique[i]['away_team']}")
    resultat = st.selectbox("Résultat réel", ["home","draw","away"])
    if st.button("✅ Enregistrer résultat réel"):
        prono = historique[match_index]
        cote = prono["cote_home"] if prono["winner_pred"] == prono["home_team"] else prono["cote_away"]
        # Calcul gain
        if (resultat=="home" and prono["winner_pred"]==prono["home_team"]) or \
           (resultat=="away" and prono["winner_pred"]==prono["away_team"]):
            gain = round(prono["mise"]*cote - prono["mise"],2)
        else:
            gain = -prono["mise"]
        prono["resultat"] = resultat
        prono["gain"] = gain
        with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique,f, indent=2, ensure_ascii=False)
        st.success(f"Résultat enregistré ✅ (gain : {gain}€)")

    # Statistiques
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
    st.info("Aucun pronostic enregistré.")
