import streamlit as st
import json
import os
import numpy as np
import pandas as pd
from datetime import datetime
import shutil

st.set_page_config(page_title="BoostProno – Pronostics avancés", layout="wide")
st.title("⚽ BoostProno – Application de pronostics complète")

# --- Fichiers ---
TEAMS_FILE = "teams_form.json"
HISTORIQUE_FILE = "historique_pronos.json"
BACKUP_DIR = "sauvegardes"
os.makedirs(BACKUP_DIR, exist_ok=True)

# --- Sauvegarde automatique ---
if os.path.exists(TEAMS_FILE):
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = os.path.join(BACKUP_DIR, f"teams_form_backup_{date_str}.json")
    shutil.copy(TEAMS_FILE, backup_file)

# --- Équipes par championnat ---
championship_teams = {
    "Ligue 1": ["Paris SG","Marseille","Monaco","Lyon","Nice","Lens","Rennes","Strasbourg","Brest","Toulouse","Montpellier","Lille","Reims","Nantes","Angers","Clermont","Auxerre","Ajaccio","Lorient","Troyes"],
    "Premier League": ["Arsenal","Manchester City","Manchester United","Chelsea","Liverpool","Tottenham","Leicester","West Ham","Brighton","Aston Villa","Newcastle","Wolves","Everton","Brentford","Fulham","Crystal Palace","Bournemouth","Nottingham","Sheffield Utd","Burnley"],
    "La Liga": ["Real Madrid","Barcelona","Atletico Madrid","Sevilla","Real Sociedad","Betis","Valencia","Villarreal","Athletic Bilbao","Celta Vigo","Osasuna","Espanyol","Mallorca","Getafe","Girona","Almeria","Rayo Vallecano","Cadiz","Elche","Valladolid"]
}

# --- Charger ou initialiser les équipes ---
if os.path.exists(TEAMS_FILE):
    with open(TEAMS_FILE, "r", encoding="utf-8") as f:
        teams_data = json.load(f)
else:
    # Préremplir avec les équipes des championnats
    teams_data = {}
    for league, teams in championship_teams.items():
        for t in teams:
            teams_data[t] = {"league": league, "last5":"v,v,n,d,d","goals_scored":0,"goals_against":0}
    with open(TEAMS_FILE,"w",encoding="utf-8") as f:
        json.dump(teams_data,f,indent=2,ensure_ascii=False)

# --- Charger l'historique ---
if os.path.exists(HISTORIQUE_FILE):
    with open(HISTORIQUE_FILE, "r", encoding="utf-8") as f:
        historique = json.load(f)
else:
    historique = []

# --- Sélection rapide des équipes ---
st.sidebar.header("📋 Sélection rapide équipes")
home_team_quick = None
away_team_quick = None
if teams_data:
    team_list = sorted(teams_data.keys())
    selected_team = st.sidebar.selectbox("Choisir une équipe", team_list)
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button(f"🏠 Mettre {selected_team} en domicile"):
            st.session_state.home_team = selected_team
    with col2:
        if st.button(f"🛫 Mettre {selected_team} en extérieur"):
            st.session_state.away_team = selected_team

# ================== AJOUT / GESTION ÉQUIPES ==================
st.header("🧾 Gestion des équipes")
with st.form("form_teams"):
    league = st.selectbox("Championnat", ["Ligue 1","Premier League","La Liga"])
    team_name = st.text_input("Nom de l'équipe")
    last5 = st.text_input("5 derniers matchs (ex: v,v,n,d,v)", value="v,v,n,d,d")
    goals_scored = st.number_input("Buts marqués", 0, 200, 0)
    goals_against = st.number_input("Buts encaissés", 0, 200, 0)
    submitted_team = st.form_submit_button("💾 Ajouter / Mettre à jour équipe")

if submitted_team and team_name:
    teams_data[team_name] = {
        "league": league,
        "last5": last5.lower(),
        "goals_scored": goals_scored,
        "goals_against": goals_against
    }
    with open(TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(teams_data, f, indent=2, ensure_ascii=False)
    st.success(f"✅ {team_name} enregistrée !")

# ================== AJOUT PRONOSTICS ==================
st.header("📊 Ajouter un pronostic")
home_team_default = st.session_state.get("home_team","")
away_team_default = st.session_state.get("away_team","")
if teams_data:
    col1, col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("Équipe Domicile", list(teams_data.keys()), index=list(teams_data.keys()).index(home_team_default) if home_team_default in teams_data else 0)
    with col2:
        away_team = st.selectbox("Équipe Extérieure", [t for t in teams_data.keys() if t != home_team], index=0 if away_team_default not in teams_data else list(teams_data.keys()).index(away_team_default))

    cote_home = st.number_input("Cote Domicile", 1.01, 20.0, 1.5)
    cote_away = st.number_input("Cote Extérieure", 1.01, 20.0, 2.8)

    if st.button("➕ Analyser & Sauvegarder pronostic"):
        def form_score(seq):
            mapping = {"v":3,"n":1,"d":0}
            vals = [mapping.get(x.strip(),0) for x in seq.split(",")]
            vals = vals[-5:] if len(vals)>5 else vals
            weights=np.array([5,4,3,2,1])[:len(vals)]
            return np.dot(vals,weights)/sum(weights)

        form_home = form_score(teams_data[home_team]["last5"])
        form_away = form_score(teams_data[away_team]["last5"])

        # Probabilités combinant forme et cote
        p_home_odds = 1 / cote_home
        p_away_odds = 1 / cote_away
        prob_home = 0.7 * p_home_odds + 0.3 * form_home
        prob_away = 0.7 * p_away_odds + 0.3 * form_away
        total = prob_home + prob_away
        prob_home /= total
        prob_away /= total

        winner = home_team if prob_home > prob_away else away_team
        prob_victoire = round(max(prob_home, prob_away)*100,2)

        pronostic = {
            "home_team": home_team,
            "away_team": away_team,
            "cote_home": cote_home,
            "cote_away": cote_away,
            "winner_pred": winner,
            "prob_victoire": prob_victoire,
            "mise": 10,
            "resultat": None,
            "gain": 0
        }
        historique.append(pronostic)
        with open(HISTORIQUE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique,f,indent=2,ensure_ascii=False)
        st.success(f"✅ Pronostic ajouté : {winner} ({prob_victoire}%)")

# ================== SUIVI PRONOS ==================
st.header("📅 Suivi des pronostics")
if historique:
    df = pd.DataFrame(historique)
    st.dataframe(df[["home_team","away_team","winner_pred","prob_victoire","resultat","gain"]])

    st.subheader("📝 Mettre à jour le résultat d’un match")
    match_index = st.selectbox(
        "Sélectionne un match",
        range(len(historique)),
        format_func=lambda i: f"{historique[i]['home_team']} vs {historique[i]['away_team']}"
    )
    resultat = st.selectbox("Résultat réel", ["home","draw","away"])
    if st.button("✅ Enregistrer résultat réel"):
        prono = historique[match_index]
        cote = prono["cote_home"] if prono["winner_pred"] == prono["home_team"] else prono["cote_away"]
        if (resultat=="home" and prono["winner_pred"]==prono["home_team"]) or \
           (resultat=="away" and prono["winner_pred"]==prono["away_team"]):
            gain = round(prono["mise"]*cote - prono["mise"],2)
        else:
            gain = -prono["mise"]
        prono["resultat"]=resultat
        prono["gain"]=gain
        with open(HISTORIQUE_FILE,"w",encoding="utf-8") as f:
            json.dump(historique,f,indent=2,ensure_ascii=False)
        st.success(f"Résultat enregistré ✅ (gain : {gain}€)")

    # Statistiques
    df_valides = df[df["resultat"].notna()]
    if not df_valides.empty:
        total_gain = df_valides["gain"].sum()
        nb_pronos = len(df_valides)
        nb_gagnants = (df_valides["gain"]>0).sum()
        precision = nb_gagnants/nb_pronos*100
        roi = total_gain/(nb_pronos*10)*100
        st.metric("🎯 Précision",f"{precision:.2f}%")
        st.metric("💰 ROI",f"{roi:.2f}%")
        st.metric("📈 Gain total",f"{total_gain:.2f}€")

    st.download_button(
        "📥 Télécharger l’historique (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        "historique_pronos.csv",
        "text/csv"
    )

    if st.button("🗑️ Réinitialiser historique"):
        historique.clear()
        with open(HISTORIQUE_FILE,"w",encoding="utf-8") as f:
            json.dump(historique,f,indent=2,ensure_ascii=False)
        st.warning("Historique réinitialisé.")
else:
    st.info("Aucun pronostic enregistré pour le moment.")
