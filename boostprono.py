import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

# =================== FICHIERS ===================
TEAMS_FILE = "teams_form.json"
HISTORIQUE_FILE = "historique_pronos.json"

# --- Création des fichiers si inexistants ---
if not os.path.exists(TEAMS_FILE):
    with open(TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f)
if not os.path.exists(HISTORIQUE_FILE):
    with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

# =================== CHARGEMENT DES DONNÉES ===================
with open(TEAMS_FILE, "r", encoding="utf-8") as f:
    teams_data = json.load(f)

with open(HISTORIQUE_FILE, "r", encoding="utf-8") as f:
    historique = json.load(f)

# =================== FONCTIONS ===================
def save_teams():
    with open(TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(teams_data, f, indent=2, ensure_ascii=False)

def save_historique():
    with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
        json.dump(historique, f, indent=2, ensure_ascii=False)

def form_score(seq):
    mapping = {"v":3,"n":1,"d":0}
    vals = [mapping.get(x.strip(),0) for x in seq.split(",") if x.strip() in mapping]
    vals = vals[-5:] if len(vals)>5 else vals
    weights = np.array([5,4,3,2,1])[:len(vals)]
    return np.dot(vals,weights)/ (15 if len(vals)==5 else sum(weights))

def calculate_prob(home_team, away_team, cote_home, cote_away):
    form_home = form_score(teams_data[home_team]["last5"])
    form_away = form_score(teams_data[away_team]["last5"])
    
    # Probabilités implicites à partir des cotes
    p_home_odds = 1 / cote_home
    p_away_odds = 1 / cote_away
    
    # Pondération forme + cotes
    prob_home = 0.7*p_home_odds + 0.3*form_home
    prob_away = 0.7*p_away_odds + 0.3*form_away
    
    total = prob_home + prob_away
    prob_home /= total
    prob_away /= total
    return prob_home, prob_away

def update_form_after_result(match):
    """Met à jour la forme des équipes après résultat d'un match"""
    winner = match["winner_pred"]
    home = match["home_team"]
    away = match["away_team"]
    
    home_seq = teams_data.get(home, {"last5":"v,v,n,d,d"})["last5"].split(",")[:4]
    away_seq = teams_data.get(away, {"last5":"v,v,n,d,d"})["last5"].split(",")[:4]
    
    if match["resultat"]=="home":
        home_seq = ["v"]+home_seq
        away_seq = ["d"]+away_seq
    elif match["resultat"]=="away":
        home_seq = ["d"]+home_seq
        away_seq = ["v"]+away_seq
    else:
        home_seq = ["n"]+home_seq
        away_seq = ["n"]+away_seq
    
    teams_data[home]["last5"] = ",".join(home_seq)
    teams_data[away]["last5"] = ",".join(away_seq)
    save_teams()

# =================== INTERFACE ===================
st.set_page_config(page_title="Analyseur de matchs complet", layout="wide")
st.title("⚽ Analyseur de matchs & suivi des pronostics")

# =================== GESTION DES ÉQUIPES ===================
st.header("🧾 Gestion des équipes")
with st.form("form_teams"):
    team_name = st.text_input("Nom de l'équipe")
    form_last5 = st.text_input("5 derniers matchs (v,n,d)", "v,v,n,d,d")
    goals_scored = st.number_input("Buts marqués", 0, 200, 0)
    goals_against = st.number_input("Buts encaissés", 0, 200, 0)
    submitted_team = st.form_submit_button("💾 Enregistrer l'équipe")
    
if submitted_team and team_name:
    teams_data[team_name] = {
        "last5": form_last5.lower(),
        "goals_scored": goals_scored,
        "goals_against": goals_against
    }
    save_teams()
    st.success(f"✅ Équipe {team_name} enregistrée")

# =================== AJOUT DE PRONOSTICS ===================
st.header("📊 Ajouter un pronostic")
if teams_data:
    col1,col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("Équipe Domicile", list(teams_data.keys()))
    with col2:
        away_team = st.selectbox("Équipe Extérieure", [t for t in teams_data.keys() if t != home_team])
    
    cote_home = st.number_input("Cote Domicile", 1.01, 20.0, 1.5)
    cote_away = st.number_input("Cote Extérieure", 1.01, 20.0, 2.5)
    
    if st.button("➕ Ajouter & Analyser le pronostic"):
        prob_home, prob_away = calculate_prob(home_team, away_team, cote_home, cote_away)
        winner = home_team if prob_home>prob_away else away_team
        prob_victoire = round(max(prob_home,prob_away)*100,2)
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
        save_historique()
        st.success(f"✅ Pronostic ajouté : victoire probable de {winner} ({prob_victoire}%)")
else:
    st.warning("⚠️ Ajoute d'abord des équipes")

# =================== SUIVI DES RESULTATS ===================
st.header("📅 Suivi des résultats & statistiques")
if historique:
    df = pd.DataFrame(historique)
    st.dataframe(df[["home_team","away_team","winner_pred","prob_victoire","resultat","gain"]], use_container_width=True)
    
    st.subheader("📝 Mettre à jour le résultat réel d'un match")
    match_index = st.selectbox(
        "Sélectionne un match",
        range(len(historique)),
        format_func=lambda i: f"{historique[i]['home_team']} vs {historique[i]['away_team']}"
    )
    resultat = st.selectbox("Résultat réel", ["home","draw","away"])
    
    if st.button("✅ Enregistrer le résultat réel"):
        prono = historique[match_index]
        cote = prono["cote_home"] if prono["winner_pred"]==prono["home_team"] else prono["cote_away"]
        if (resultat=="home" and prono["winner_pred"]==prono["home_team"]) or \
           (resultat=="away" and prono["winner_pred"]==prono["away_team"]):
            gain = round(prono["mise"]*cote - prono["mise"],2)
        elif resultat=="draw":
            gain = 0
        else:
            gain = -prono["mise"]
        
        prono["resultat"] = resultat
        prono["gain"] = gain
        save_historique()
        update_form_after_result(prono)
        st.success(f"Résultat enregistré ✅ (gain : {gain}€)")
    
    # =================== SUPPRESSION & RESET ===================
    st.subheader("🗑️ Gérer l'historique")
    match_to_delete = st.selectbox(
        "Sélectionne le match à supprimer",
        range(len(historique)),
        format_func=lambda i: f"{historique[i]['home_team']} vs {historique[i]['away_team']}"
    )
    if st.button("❌ Supprimer le match sélectionné"):
        historique.pop(match_to_delete)
        save_historique()
        st.warning("✅ Match supprimé (la forme des équipes reste inchangée)")

    if st.button("🔄 Réinitialiser toute l'application"):
        historique.clear()
        teams_data.clear()
        save_historique()
        save_teams()
        st.warning("⚠️ Application réinitialisée : équipes et pronostics supprimés")

    # =================== STATISTIQUES ===================
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
else:
    st.info("Aucun pronostic enregistré pour le moment")
