import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import shutil

# --- Fichiers ---
TEAMS_FILE = "teams_form.json"
HIST_FILE = "historique_pronos.json"
BACKUP_DIR = "sauvegardes"

os.makedirs(BACKUP_DIR, exist_ok=True)

# --- Sauvegarde automatique ---
if os.path.exists(TEAMS_FILE):
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = os.path.join(BACKUP_DIR, f"teams_form_backup_{date_str}.json")
    shutil.copy(TEAMS_FILE, backup_file)

# --- Chargement données ---
if os.path.exists(TEAMS_FILE):
    with open(TEAMS_FILE, "r", encoding="utf-8") as f:
        teams_data = json.load(f)
else:
    teams_data = {}

if os.path.exists(HIST_FILE):
    with open(HIST_FILE, "r", encoding="utf-8") as f:
        historique = json.load(f)
else:
    historique = []

st.set_page_config(page_title="BoostProno", layout="wide")
st.title("⚽ BoostProno – Analyseur de matchs et suivi")

# ===================== Gestion des équipes =====================
st.header("🧾 Ajouter / Mettre à jour une équipe")
with st.form("form_teams"):
    team_name = st.text_input("Nom de l'équipe")
    last5 = st.text_input("5 derniers matchs (v,n,d) ex: v,v,n,d,v")
    goals_scored = st.number_input("Buts marqués", 0, 200, 0)
    goals_against = st.number_input("Buts encaissés", 0, 200, 0)
    submitted_team = st.form_submit_button("💾 Enregistrer l'équipe")

if submitted_team and team_name:
    if team_name not in teams_data:
        teams_data[team_name] = {}
    teams_data[team_name].update({
        "last5": last5.lower(),
        "goals_scored": goals_scored,
        "goals_against": goals_against,
        "points": teams_data.get(team_name, {}).get("points", 0)
    })
    with open(TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(teams_data, f, indent=2, ensure_ascii=False)
    st.success(f"✅ {team_name} enregistrée")

# ===================== Ajout pronostic =====================
st.header("📊 Ajouter un pronostic")
if len(teams_data) >= 2:
    col1, col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("Équipe domicile", list(teams_data.keys()))
    with col2:
        away_team = st.selectbox("Équipe extérieur", [t for t in teams_data.keys() if t != home_team])

    cote_home = st.number_input("Cote domicile", 1.01, 20.0, 1.5)
    cote_away = st.number_input("Cote extérieur", 1.01, 20.0, 2.8)

    score_home = st.number_input(f"Buts {home_team} prévus", 0, 20, 0)
    score_away = st.number_input(f"Buts {away_team} prévus", 0, 20, 0)

    if st.button("➕ Ajouter le pronostic"):
        def form_score(seq):
            mapping = {"v":3, "n":1, "d":0}
            vals = [mapping.get(x.strip(),0) for x in seq.split(",") if x.strip() in mapping]
            vals = vals[-5:] if len(vals) > 5 else vals
            weights = np.array([5,4,3,2,1])[:len(vals)]
            return np.dot(vals, weights)/(15 if len(vals)==5 else sum(weights))

        home_form = form_score(teams_data[home_team]["last5"])
        away_form = form_score(teams_data[away_team]["last5"])
        p_home_odds = 1 / cote_home
        p_away_odds = 1 / cote_away
        prob_home = 0.7*home_form + 0.3*p_home_odds
        prob_away = 0.7*away_form + 0.3*p_away_odds
        total = prob_home + prob_away
        prob_home /= total
        prob_away /= total
        winner = home_team if prob_home > prob_away else away_team

        pronostic = {
            "home_team": home_team,
            "away_team": away_team,
            "cote_home": cote_home,
            "cote_away": cote_away,
            "winner_pred": winner,
            "prob_victoire": round(max(prob_home, prob_away)*100,2),
            "mise": 10,
            "resultat": None,
            "score_home": score_home,
            "score_away": score_away,
            "gain": 0
        }
        historique.append(pronostic)
        with open(HIST_FILE, "w", encoding="utf-8") as f:
            json.dump(historique, f, indent=2, ensure_ascii=False)
        st.success(f"✅ Pronostic ajouté : victoire de {winner} ({pronostic['prob_victoire']}%)")

else:
    st.warning("⚠️ Ajoute d'abord au moins 2 équipes")

# ===================== Suivi des résultats =====================
st.header("📅 Suivi des résultats et statistiques")
if historique:
    df = pd.DataFrame(historique)
    st.dataframe(df[["home_team","away_team","winner_pred","prob_victoire","resultat","gain"]], use_container_width=True)

    # Mise à jour résultat réel
    st.subheader("📝 Mettre à jour un résultat réel")
    match_idx = st.selectbox("Choisir un match", range(len(historique)),
                             format_func=lambda i: f"{historique[i]['home_team']} vs {historique[i]['away_team']}")
    resultat = st.selectbox("Résultat réel", ["home","draw","away"])
    if st.button("✅ Enregistrer résultat"):
        prono = historique[match_idx]
        # Mise à jour gains
        cote = prono["cote_home"] if prono["winner_pred"]==prono["home_team"] else prono["cote_away"]
        if (resultat=="home" and prono["winner_pred"]==prono["home_team"]) or \
           (resultat=="away" and prono["winner_pred"]==prono["away_team"]):
            gain = round(prono["mise"]*cote - prono["mise"],2)
        else:
            gain = -prono["mise"]
        prono["resultat"] = resultat
        prono["gain"] = gain

        # Mise à jour forme et points
        for team in [prono["home_team"], prono["away_team"]]:
            if "points" not in teams_data[team]:
                teams_data[team]["points"] = 0
            if "last5" not in teams_data[team]:
                teams_data[team]["last5"] = "v,v,n,d,d"
            if "goals_scored" not in teams_data[team]:
                teams_data[team]["goals_scored"] = 0
            if "goals_against" not in teams_data[team]:
                teams_data[team]["goals_against"] = 0

        h_seq = teams_data[prono["home_team"]]["last5"].split(",")[:4]
        a_seq = teams_data[prono["away_team"]]["last5"].split(",")[:4]

        if resultat=="home":
            h_seq = ["v"] + h_seq
            a_seq = ["d"] + a_seq
            teams_data[prono["home_team"]]["points"] +=3
        elif resultat=="away":
            h_seq = ["d"] + h_seq
            a_seq = ["v"] + a_seq
            teams_data[prono["away_team"]]["points"] +=3
        else:
            h_seq = ["n"] + h_seq
            a_seq = ["n"] + a_seq
            teams_data[prono["home_team"]]["points"] +=1
            teams_data[prono["away_team"]]["points"] +=1

        teams_data[prono["home_team"]]["last5"] = ",".join(h_seq)
        teams_data[prono["away_team"]]["last5"] = ",".join(a_seq)

        # Mise à jour buts
        teams_data[prono["home_team"]]["goals_scored"] += prono["score_home"]
        teams_data[prono["home_team"]]["goals_against"] += prono["score_away"]
        teams_data[prono["away_team"]]["goals_scored"] += prono["score_away"]
        teams_data[prono["away_team"]]["goals_against"] += prono["score_home"]

        # Sauvegarde
        with open(TEAMS_FILE,"w",encoding="utf-8") as f:
            json.dump(teams_data,f,indent=2,ensure_ascii=False)
        with open(HIST_FILE,"w",encoding="utf-8") as f:
            json.dump(historique,f,indent=2,ensure_ascii=False)
        st.success(f"Résultat enregistré. Gain : {gain}€")

    # Supprimer un match
    st.subheader("🗑️ Supprimer un match")
    del_idx = st.selectbox("Choisir le match à supprimer", range(len(historique)),
                           format_func=lambda i: f"{historique[i]['home_team']} vs {historique[i]['away_team']}")
    if st.button("❌ Supprimer le match"):
        historique.pop(del_idx)
        with open(HIST_FILE,"w",encoding="utf-8") as f:
            json.dump(historique,f,indent=2,ensure_ascii=False)
        st.success("Match supprimé")

    # Réinitialiser l’application
    if st.button("♻️ Réinitialiser l'application"):
        historique.clear()
        teams_data.clear()
        if os.path.exists(TEAMS_FILE): os.remove(TEAMS_FILE)
        if os.path.exists(HIST_FILE): os.remove(HIST_FILE)
        st.warning("Application réinitialisée. Redémarre la page.")

    # Statistiques
    valid_df = df[df["resultat"].notna()]
    if not valid_df.empty:
        total_gain = valid_df["gain"].sum()
        nb_pronos = len(valid_df)
        nb_gagnants = (valid_df["gain"]>0).sum()
        precision = nb_gagnants/nb_pronos*100
        roi = (total_gain/(nb_pronos*10))*100
        st.metric("🎯 Précision", f"{precision:.2f}%")
        st.metric("💰 ROI", f"{roi:.2f}%")
        st.metric("📈 Gain total", f"{total_gain:.2f}€")

else:
    st.info("Aucun pronostic enregistré")
