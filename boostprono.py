import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import shutil

# ---------------- CONFIG -----------------
st.set_page_config(page_title="⚽ BoostProno Top5", layout="wide")

TEAMS_FILE = "teams_form.json"
HISTORIQUE_FILE = "historique_pronos.json"
BACKUP_DIR = "sauvegardes"
os.makedirs(BACKUP_DIR, exist_ok=True)

# ---------------- SAUVEGARDES -----------------
def save_backup(file_path):
    if os.path.exists(file_path):
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_file = os.path.join(BACKUP_DIR, f"{os.path.basename(file_path).replace('.json','')}_backup_{date_str}.json")
        shutil.copy(file_path, backup_file)

save_backup(TEAMS_FILE)
save_backup(HISTORIQUE_FILE)

# ---------------- CHARGEMENT DONNEES -----------------
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

# ---------------- GESTION EQUIPES -----------------
st.sidebar.header("💾 Gestion équipes & sauvegardes")
with st.sidebar.expander("Ajouter / Modifier une équipe"):
    team_name = st.text_input("Nom de l'équipe")
    last5 = st.text_input("5 derniers matchs (ex: v,v,n,d,v)")
    goals_scored = st.number_input("Buts marqués", 0, 200, 0)
    goals_against = st.number_input("Buts encaissés", 0, 200, 0)
    if st.button("💾 Enregistrer équipe"):
        if team_name:
            teams_data[team_name] = {
                "last5": last5.lower(),
                "goals_scored": goals_scored,
                "goals_against": goals_against,
                "points": 0
            }
            with open(TEAMS_FILE, "w", encoding="utf-8") as f:
                json.dump(teams_data, f, indent=2, ensure_ascii=False)
            save_backup(TEAMS_FILE)
            st.success(f"✅ {team_name} enregistrée")

# ---------------- PRONOSTICS -----------------
st.header("📊 Ajouter un pronostic")
if teams_data:
    col1, col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("Équipe Domicile", list(teams_data.keys()))
    with col2:
        away_team = st.selectbox("Équipe Extérieure", [t for t in teams_data.keys() if t != home_team])
    cote_home = st.number_input("Cote Domicile", 1.01, 20.0, 1.5)
    cote_away = st.number_input("Cote Extérieure", 1.01, 20.0, 2.8)

    if st.button("➕ Ajouter le pronostic"):
        def form_score(seq):
            mapping = {"v":3,"n":1,"d":0}
            vals = [mapping.get(x.strip(),0) for x in seq.split(",") if x.strip() in mapping]
            vals = vals[-5:] if len(vals)>5 else vals
            weights = np.array([5,4,3,2,1])[:len(vals)]
            return np.dot(vals, weights)/ (15 if len(vals)==5 else sum(weights))
        form_home = form_score(teams_data[home_team]["last5"])
        form_away = form_score(teams_data[away_team]["last5"])
        
        p_home_odds = 1 / cote_home
        p_away_odds = 1 / cote_away
        prob_home = 0.7*p_home_odds + 0.3*form_home
        prob_away = 0.7*p_away_odds + 0.3*form_away
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
            "score_home": None,
            "score_away": None,
            "gain": 0
        }
        historique.append(pronostic)
        with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique, f, indent=2, ensure_ascii=False)
        save_backup(HISTORIQUE_FILE)
        st.success(f"✅ Pronostic ajouté : victoire de {winner} ({prob_victoire}%)")
else:
    st.warning("⚠️ Ajoute d'abord des équipes.")

# ---------------- SUIVI RESULTATS -----------------
st.header("📅 Suivi des résultats & statistiques")
if historique:
    df = pd.DataFrame(historique)
    st.dataframe(df[["home_team","away_team","winner_pred","prob_victoire","resultat","score_home","score_away","gain"]], use_container_width=True)

    st.subheader("📝 Mettre à jour le résultat d’un match")
    match_index = st.selectbox("Sélectionne un match", range(len(historique)),
                               format_func=lambda i: f"{historique[i]['home_team']} vs {historique[i]['away_team']}")
    resultat = st.selectbox("Résultat réel", ["home","draw","away"])
    score_home = st.number_input("Buts Domicile", 0, 20, 0)
    score_away = st.number_input("Buts Extérieur", 0, 20, 0)
    if st.button("✅ Enregistrer le résultat réel"):
        prono = historique[match_index]
        prono["resultat"] = resultat
        prono["score_home"] = score_home
        prono["score_away"] = score_away
        cote = prono["cote_home"] if prono["winner_pred"]==prono["home_team"] else prono["cote_away"]
        prono["gain"] = round(prono["mise"]*(cote-1),2) if (
            (resultat=="home" and prono["winner_pred"]==prono["home_team"]) or
            (resultat=="away" and prono["winner_pred"]==prono["away_team"])
        ) else -prono["mise"]
        # Mise à jour forme et buts
        for team,score,against,last5 in [
            (prono["home_team"], score_home, score_away, teams_data[prono["home_team"]]["last5"]),
            (prono["away_team"], score_away, score_home, teams_data[prono["away_team"]]["last5"])
        ]:
            seq = last5.split(",")[:4]
            if prono["winner_pred"]==team and ((team==prono["home_team"] and resultat=="home") or (team==prono["away_team"] and resultat=="away")):
                seq = ["v"]+seq
                teams_data[team]["points"] += 3
            elif resultat=="draw":
                seq = ["n"]+seq
                teams_data[team]["points"] += 1
            else:
                seq = ["d"]+seq
            teams_data[team]["last5"] = ",".join(seq)
            teams_data[team]["goals_scored"] += score
            teams_data[team]["goals_against"] += against
        with open(TEAMS_FILE, "w", encoding="utf-8") as f:
            json.dump(teams_data, f, indent=2, ensure_ascii=False)
        with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique, f, indent=2, ensure_ascii=False)
        st.success(f"Résultat enregistré ✅ Gain : {prono['gain']}€")

    # ----------------- TOP 5 PRONOS -----------------
    st.subheader("🔥 Top 5 Pronostics à jouer")
    top_pronos = []
    for h in historique:
        if h["resultat"] is None:
            prob = h["prob_victoire"]/100
            cote = h["cote_home"] if h["winner_pred"]==h["home_team"] else h["cote_away"]
            ev = prob*(cote-1) - (1-prob)
            b = cote-1
            f_star = max((b*prob - (1-prob))/b,0)
            mise_opt = round(f_star*100,2)
            top_pronos.append({
                "Match": f"{h['home_team']} vs {h['away_team']}",
                "Pronostic": h["winner_pred"],
                "Probabilité (%)": round(prob*100,2),
                "Cote": cote,
                "EV": round(ev,2),
                "Mise Kelly (€)": mise_opt
            })
    if top_pronos:
        df_top = pd.DataFrame(top_pronos).sort_values(by="EV", ascending=False).head(5)
        st.dataframe(df_top, use_container_width=True)

