import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import shutil

# =================== CONFIG ===================
st.set_page_config(page_title="BoostProno – Analyse et Suivi", layout="wide")
st.title("⚽ BoostProno – Analyse de matchs et suivi des pronostics")

# =================== FICHIERS ===================
TEAMS_FILE = "teams_form.json"
HIST_FILE = "historique_pronos.json"
BACKUP_DIR = "sauvegardes"

os.makedirs(BACKUP_DIR, exist_ok=True)

# --- Sauvegarde automatique des équipes au démarrage ---
if os.path.exists(TEAMS_FILE):
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    shutil.copy(TEAMS_FILE, os.path.join(BACKUP_DIR, f"teams_form_backup_{date_str}.json"))

# =================== CHARGEMENT ===================
# Équipes
if os.path.exists(TEAMS_FILE):
    with open(TEAMS_FILE, "r", encoding="utf-8") as f:
        teams_data = json.load(f)
else:
    teams_data = {}

# Historique pronos
if os.path.exists(HIST_FILE):
    with open(HIST_FILE, "r", encoding="utf-8") as f:
        historique = json.load(f)
else:
    historique = []

# =================== FONCTIONS ===================
def save_teams():
    with open(TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(teams_data, f, indent=2, ensure_ascii=False)

def save_historique():
    with open(HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(historique, f, indent=2, ensure_ascii=False)

def calculate_form(last5):
    mapping = {"v":3, "n":1, "d":0}
    seq = [mapping.get(x.strip(),0) for x in last5.split(",")]
    seq = seq[-5:] if len(seq)>5 else seq
    weights = np.array([5,4,3,2,1])[:len(seq)]
    return np.dot(seq, weights)/sum(weights)

def calculate_prob(home, away, cote_home, cote_away):
    home_form = calculate_form(home["last5"])
    away_form = calculate_form(away["last5"])
    # Attaque / défense simplifiée
    home_attack = home["goals_scored"] / max(home["goals_scored"] + home["goals_against"],1)
    away_attack = away["goals_scored"] / max(away["goals_scored"] + away["goals_against"],1)
    # Score combiné
    home_score = 0.5*home_form + 0.25*home_attack + 0.25*(1-away_attack)
    away_score = 0.5*away_form + 0.25*away_attack + 0.25*(1-home_attack)
    # Probabilités implicites via cotes
    prob_home_cote = 1 / cote_home
    prob_away_cote = 1 / cote_away
    # Fusion forme + cotes
    prob_home = 0.7*home_score + 0.3*prob_home_cote
    prob_away = 0.7*away_score + 0.3*prob_away_cote
    total = prob_home + prob_away
    prob_home /= total
    prob_away /= total
    return prob_home, prob_away

def update_team_form(team_name, result):
    """Met à jour définitivement la forme de l'équipe"""
    last5 = teams_data.get(team_name, {"last5":"v,v,n,d,d"})["last5"].split(",")[:4]
    if result == "win":
        last5 = ["v"] + last5
    elif result == "lose":
        last5 = ["d"] + last5
    else:
        last5 = ["n"] + last5
    if team_name in teams_data:
        teams_data[team_name]["last5"] = ",".join(last5)
    else:
        teams_data[team_name] = {"last5":",".join(last5), "goals_scored":0, "goals_against":0}
    save_teams()

# =================== GESTION DES ÉQUIPES ===================
st.header("🧾 Gestion des équipes")
with st.form("form_teams"):
    team_name = st.text_input("Nom de l'équipe")
    form_last5 = st.text_input("5 derniers matchs (ex: v,v,n,d,v)", value="v,v,n,d,d")
    goals_scored = st.number_input("Buts marqués", 0, 200, 0)
    goals_against = st.number_input("Buts encaissés", 0, 200, 0)
    submitted_team = st.form_submit_button("💾 Enregistrer l'équipe")
if submitted_team and team_name:
    teams_data[team_name] = {"last5":form_last5.lower(), "goals_scored":goals_scored, "goals_against":goals_against}
    save_teams()
    st.success(f"✅ {team_name} enregistrée / mise à jour")

# =================== AJOUT PRONOSTICS ===================
st.header("📊 Ajouter un pronostic")
if len(teams_data)>=2:
    col1,col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("Équipe Domicile", list(teams_data.keys()))
    with col2:
        away_team = st.selectbox("Équipe Extérieure", [t for t in teams_data.keys() if t!=home_team])
    cote_home = st.number_input("Cote Domicile", 1.01, 20.0, 1.5)
    cote_away = st.number_input("Cote Extérieure", 1.01, 20.0, 2.5)
    if st.button("➕ Ajouter et analyser pronostic"):
        prob_home, prob_away = calculate_prob(teams_data[home_team], teams_data[away_team], cote_home, cote_away)
        winner_pred = home_team if prob_home>prob_away else away_team
        pronostic = {
            "home_team":home_team,
            "away_team":away_team,
            "cote_home":cote_home,
            "cote_away":cote_away,
            "winner_pred":winner_pred,
            "prob_victoire":round(max(prob_home,prob_away)*100,2),
            "mise":10,
            "resultat":None,
            "gain":0
        }
        historique.append(pronostic)
        save_historique()
        st.success(f"✅ Pronostic ajouté : {winner_pred} ({round(max(prob_home,prob_away)*100,2)}%)")

else:
    st.info("⚠️ Ajoute au moins 2 équipes pour créer un pronostic")

# =================== SUIVI DES PRONOSTICS ===================
st.header("📅 Suivi des résultats & statistiques")
if historique:
    df = pd.DataFrame(historique)
    st.dataframe(df[["home_team","away_team","winner_pred","prob_victoire","resultat","gain"]], use_container_width=True)
    
    st.subheader("📝 Mettre à jour un résultat")
    match_index = st.selectbox("Sélectionne un match", range(len(historique)), format_func=lambda i: f"{historique[i]['home_team']} vs {historique[i]['away_team']}")
    resultat = st.selectbox("Résultat réel", ["home","draw","away"])
    if st.button("✅ Enregistrer le résultat"):
        prono = historique[match_index]
        if resultat=="home":
            prono["resultat"]="home"
            prono["gain"]=round(prono["mise"]*(prono["cote_home"]-1),2) if prono["winner_pred"]==prono["home_team"] else -prono["mise"]
            update_team_form(prono["home_team"], "win" if prono["winner_pred"]==prono["home_team"] else "lose")
            update_team_form(prono["away_team"], "lose" if prono["winner_pred"]==prono["home_team"] else "win")
        elif resultat=="away":
            prono["resultat"]="away"
            prono["gain"]=round(prono["mise"]*(prono["cote_away"]-1),2) if prono["winner_pred"]==prono["away_team"] else -prono["mise"]
            update_team_form(prono["home_team"], "lose" if prono["winner_pred"]==prono["away_team"] else "win")
            update_team_form(prono["away_team"], "win" if prono["winner_pred"]==prono["away_team"] else "lose")
        else:
            prono["resultat"]="draw"
            prono["gain"]=-prono["mise"]
            update_team_form(prono["home_team"], "draw")
            update_team_form(prono["away_team"], "draw")
        save_historique()
        st.success("Résultat enregistré et forme mise à jour")

    # --- Statistiques
    df_valid = df[df["resultat"].notna()]
    if not df_valid.empty:
        total_gain = df_valid["gain"].sum()
        nb_pronos = len(df_valid)
        nb_gagnants = (df_valid["gain"]>0).sum()
        precision = nb_gagnants/nb_pronos*100
        roi = (total_gain/(nb_pronos*10))*100
        st.metric("🎯 Précision", f"{precision:.2f}%")
        st.metric("💰 ROI", f"{roi:.2f}%")
        st.metric("📈 Gain total", f"{total_gain:.2f}€")

    # Export CSV
    st.download_button("📥 Télécharger l’historique (CSV)", df.to_csv(index=False).encode("utf-8"), "historique_pronos.csv", "text/csv")
    
    # Supprimer un match
    if st.button("🗑️ Supprimer le dernier match"):
        if historique:
            historique.pop()
            save_historique()
            st.warning("Dernier match supprimé (la forme des équipes reste inchangée)")
else:
    st.info("Aucun pronostic enregistré pour le moment")
